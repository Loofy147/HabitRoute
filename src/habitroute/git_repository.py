"""Bounded, read-only inspection of immutable Git commit ranges.

Only fixed Git read commands are executed. This adapter never invokes project
scripts, hooks, tests, formatters, external diff drivers or text converters.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Iterable


_COMMIT_OID = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_ZERO_OID = re.compile(r"^0+$")


class GitAdapterError(RuntimeError):
    """Base exception for repository inspection failures."""


class GitInputError(GitAdapterError):
    """The repository or immutable commit input is invalid."""


class GitCommandError(GitAdapterError):
    """A fixed read-only Git command failed."""


class GitResourceLimitError(GitAdapterError):
    """An inspection exceeded an explicit resource bound."""


class BlobReadStatus(str, Enum):
    CONTENT = "content"
    BINARY = "binary"
    TOO_LARGE = "too_large"
    NON_BLOB = "non_blob"


@dataclass(frozen=True, slots=True)
class BlobObservation:
    object_id: str
    object_type: str
    size_bytes: int | None
    status: BlobReadStatus
    content: bytes | None = None
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ChangedPath:
    path: str
    change_type: str
    base_mode: str | None
    target_mode: str | None
    base_blob: BlobObservation | None
    target_blob: BlobObservation | None

    @property
    def base_content(self) -> bytes | None:
        return self.base_blob.content if self.base_blob is not None else None

    @property
    def target_content(self) -> bytes | None:
        return self.target_blob.content if self.target_blob is not None else None

    @property
    def base_content_status(self) -> BlobReadStatus | None:
        return self.base_blob.status if self.base_blob is not None else None

    @property
    def target_content_status(self) -> BlobReadStatus | None:
        return self.target_blob.status if self.target_blob is not None else None

    @property
    def base_sha256(self) -> str | None:
        return self.base_blob.sha256 if self.base_blob is not None else None

    @property
    def target_sha256(self) -> str | None:
        return self.target_blob.sha256 if self.target_blob is not None else None


@dataclass(frozen=True, slots=True)
class RepositoryChangeSnapshot:
    repository_root: str
    base_commit: str
    target_commit: str
    changes: tuple[ChangedPath, ...]
    inventory_digest: str
    git_commands: int
    elapsed_ms: float
    blob_bytes_read: int
    inventory_complete: bool = True

    @property
    def content_complete(self) -> bool:
        observations = (
            blob
            for path in self.changes
            for blob in (path.base_blob, path.target_blob)
            if blob is not None
        )
        return all(
            item.status in (BlobReadStatus.CONTENT, BlobReadStatus.BINARY)
            for item in observations
        )


class GitReadOnlyRepositoryAdapter:
    """Inspect two immutable commits without reading the mutable working tree.

    Rename detection is disabled deliberately: a rename is represented as a
    deletion plus an addition so neither path disappears from the inventory.
    Blob reads are bounded; large blobs remain present in the inventory with
    a TOO_LARGE content status instead of being silently omitted.
    """

    CAPABILITY_ID = "git.read-commit-range"
    CAPABILITY_VERSION = "0.1.0"

    def __init__(
        self,
        repository_path: str | os.PathLike[str],
        *,
        timeout_seconds: float = 10.0,
        max_changed_paths: int = 500,
        max_blob_bytes: int = 512 * 1024,
        max_total_blob_bytes: int = 4 * 1024 * 1024,
        max_command_output_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        for name, value in (
            ("timeout_seconds", timeout_seconds),
            ("max_changed_paths", max_changed_paths),
            ("max_blob_bytes", max_blob_bytes),
            ("max_total_blob_bytes", max_total_blob_bytes),
            ("max_command_output_bytes", max_command_output_bytes),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.max_changed_paths = int(max_changed_paths)
        self.max_blob_bytes = int(max_blob_bytes)
        self.max_total_blob_bytes = int(max_total_blob_bytes)
        self.max_command_output_bytes = int(max_command_output_bytes)
        self._command_count = 0

        candidate = Path(repository_path).expanduser()
        try:
            candidate = candidate.resolve(strict=True)
        except OSError as exc:
            raise GitInputError("repository path does not resolve") from exc
        if not candidate.is_dir():
            raise GitInputError("repository path must be a directory")
        self._cwd = candidate

        try:
            root_bytes = self._run_git(["rev-parse", "--show-toplevel"])
        except GitCommandError as exc:
            raise GitInputError("path is not inside a Git working tree") from exc
        try:
            root = Path(os.fsdecode(root_bytes).rstrip("\r\n")).resolve(strict=True)
        except OSError as exc:
            raise GitInputError("Git repository root does not resolve") from exc
        if not root.is_dir():
            raise GitInputError("Git repository root is not a directory")
        self.repository_root = root
        self._cwd = root

    def _environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update({
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_NO_REPLACE_OBJECTS": "1",
        })
        return env

    def _run_git(self, args: list[str], *, input_bytes: bytes | None = None) -> bytes:
        self._command_count += 1
        try:
            result = subprocess.run(
                ["git", "--no-pager", *args],
                cwd=self._cwd,
                env=self._environment(),
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitCommandError("read-only Git command exceeded its timeout") from exc
        except OSError as exc:
            raise GitCommandError("unable to start Git executable") from exc

        if len(result.stdout) > self.max_command_output_bytes:
            raise GitResourceLimitError("Git command output exceeded its configured limit")
        if len(result.stderr) > self.max_command_output_bytes:
            raise GitResourceLimitError("Git diagnostic output exceeded its configured limit")
        if result.returncode != 0:
            # Avoid returning potentially sensitive stderr to callers.
            raise GitCommandError(
                f"read-only Git command failed with exit code {result.returncode}"
            )
        return result.stdout

    def _resolve_commit(self, value: str, label: str) -> str:
        if not isinstance(value, str) or not _COMMIT_OID.fullmatch(value):
            raise GitInputError(f"{label} must be a full 40- or 64-character commit object ID")
        resolved = os.fsdecode(
            self._run_git(["rev-parse", "--verify", f"{value.lower()}^{{commit}}"])
        ).strip().lower()
        if resolved != value.lower():
            raise GitInputError(f"{label} did not resolve to the supplied commit object")
        return resolved

    def _parse_raw_diff(self, raw: bytes) -> list[tuple[str, str, str | None, str | None, str | None, str | None]]:
        tokens = raw.split(b"\0")
        records: list[tuple[str, str, str | None, str | None, str | None, str | None]] = []
        index = 0
        while index < len(tokens) and tokens[index]:
            header = tokens[index]
            index += 1
            if index >= len(tokens):
                raise GitAdapterError("Git raw-diff output ended before its path field")
            path_bytes = tokens[index]
            index += 1
            if not header.startswith(b":"):
                raise GitAdapterError("Git raw-diff output contained an invalid record")
            fields = header[1:].split()
            if len(fields) != 5:
                raise GitAdapterError("Git raw-diff record has an unsupported shape")
            old_mode, new_mode, old_oid, new_oid, status_token = fields
            status = status_token[:1].decode("ascii", errors="strict")
            if status not in {"A", "D", "M", "T", "U", "X", "B"}:
                raise GitAdapterError(f"unsupported Git change status: {status}")
            path = os.fsdecode(path_bytes)
            old_id = old_oid.decode("ascii").lower()
            new_id = new_oid.decode("ascii").lower()
            if _ZERO_OID.fullmatch(old_id):
                old_id = ""
            if _ZERO_OID.fullmatch(new_id):
                new_id = ""
            records.append((
                path,
                status,
                old_mode.decode("ascii"),
                new_mode.decode("ascii"),
                old_id or None,
                new_id or None,
            ))
            if len(records) > self.max_changed_paths:
                raise GitResourceLimitError("changed path count exceeded its configured limit")
        return records

    def _read_blob_observations(self, object_ids: Iterable[str]) -> tuple[dict[str, BlobObservation], int]:
        unique_ids = tuple(sorted(set(object_ids)))
        if not unique_ids:
            return {}, 0

        request = b"".join(item.encode("ascii") + b"\n" for item in unique_ids)
        check_output = self._run_git(["cat-file", "--batch-check"], input_bytes=request)
        check_lines = check_output.splitlines()
        if len(check_lines) != len(unique_ids):
            raise GitAdapterError("Git returned an incomplete batch object-size response")

        metadata: dict[str, tuple[str, int | None]] = {}
        for expected, line in zip(unique_ids, check_lines):
            fields = line.split()
            if len(fields) == 2 and fields[1] == b"missing":
                metadata[expected] = ("missing", None)
                continue
            if len(fields) != 3:
                raise GitAdapterError("Git returned an invalid batch object-size response")
            oid = fields[0].decode("ascii").lower()
            object_type = fields[1].decode("ascii")
            try:
                size = int(fields[2])
            except ValueError as exc:
                raise GitAdapterError("Git returned an invalid blob size") from exc
            if oid != expected or size < 0:
                raise GitAdapterError("Git batch object-size identity mismatch")
            metadata[expected] = (object_type, size)

        content_ids: list[str] = []
        for oid in unique_ids:
            object_type, size = metadata[oid]
            if object_type != "blob" or size is None:
                continue
            if size <= self.max_blob_bytes:
                content_ids.append(oid)

        total_size = sum(metadata[oid][1] or 0 for oid in content_ids)
        if total_size > self.max_total_blob_bytes:
            raise GitResourceLimitError("total changed blob bytes exceeded the configured limit")

        content_by_oid: dict[str, bytes] = {}
        if content_ids:
            read_request = b"".join(item.encode("ascii") + b"\n" for item in content_ids)
            batch_output = self._run_git(["cat-file", "--batch"], input_bytes=read_request)
            offset = 0
            for expected in content_ids:
                header_end = batch_output.find(b"\n", offset)
                if header_end < 0:
                    raise GitAdapterError("Git batch blob response is missing a header")
                header = batch_output[offset:header_end].split()
                if len(header) != 3:
                    raise GitAdapterError("Git batch blob header has an invalid shape")
                oid = header[0].decode("ascii").lower()
                object_type = header[1].decode("ascii")
                size = int(header[2])
                if oid != expected or object_type != "blob":
                    raise GitAdapterError("Git batch blob identity/type mismatch")
                data_start = header_end + 1
                data_end = data_start + size
                if data_end >= len(batch_output) or batch_output[data_end:data_end + 1] != b"\n":
                    raise GitAdapterError("Git batch blob response is truncated")
                content_by_oid[expected] = batch_output[data_start:data_end]
                offset = data_end + 1
            if offset != len(batch_output):
                raise GitAdapterError("Git batch blob response has unexpected trailing data")

        observations: dict[str, BlobObservation] = {}
        for oid in unique_ids:
            object_type, size = metadata[oid]
            if object_type == "missing":
                observations[oid] = BlobObservation(
                    object_id=oid,
                    object_type="missing",
                    size_bytes=None,
                    status=BlobReadStatus.NON_BLOB,
                )
            elif object_type != "blob":
                observations[oid] = BlobObservation(
                    object_id=oid,
                    object_type=object_type,
                    size_bytes=size,
                    status=BlobReadStatus.NON_BLOB,
                )
            elif size is not None and size > self.max_blob_bytes:
                observations[oid] = BlobObservation(
                    object_id=oid,
                    object_type=object_type,
                    size_bytes=size,
                    status=BlobReadStatus.TOO_LARGE,
                )
            else:
                content = content_by_oid[oid]
                binary = b"\0" in content
                observations[oid] = BlobObservation(
                    object_id=oid,
                    object_type=object_type,
                    size_bytes=len(content),
                    status=BlobReadStatus.BINARY if binary else BlobReadStatus.CONTENT,
                    content=content,
                    sha256=hashlib.sha256(content).hexdigest(),
                )
        return observations, sum(len(item) for item in content_by_oid.values())

    def inspect_commit_range(self, base_commit: str, target_commit: str) -> RepositoryChangeSnapshot:
        """Inventory/read changed objects from two exact immutable commit IDs.

        The mutable worktree and untracked files are deliberately excluded. The
        caller must bind the correct task, base and target revisions beforehand.
        """
        started = time.monotonic()
        self._command_count = 0
        base = self._resolve_commit(base_commit, "base_commit")
        target = self._resolve_commit(target_commit, "target_commit")

        raw_diff = self._run_git([
            "diff",
            "--raw",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            "-z",
            base,
            target,
            "--",
        ])
        records = self._parse_raw_diff(raw_diff)
        object_ids = [
            oid
            for _, _, _, _, old_oid, new_oid in records
            for oid in (old_oid, new_oid)
            if oid is not None
        ]
        blobs, bytes_read = self._read_blob_observations(object_ids)

        changes = tuple(
            ChangedPath(
                path=path,
                change_type=status,
                base_mode=old_mode,
                target_mode=new_mode,
                base_blob=blobs.get(old_oid) if old_oid else None,
                target_blob=blobs.get(new_oid) if new_oid else None,
            )
            for path, status, old_mode, new_mode, old_oid, new_oid in records
        )
        elapsed_ms = (time.monotonic() - started) * 1000.0
        return RepositoryChangeSnapshot(
            repository_root=str(self.repository_root),
            base_commit=base,
            target_commit=target,
            changes=changes,
            inventory_digest=hashlib.sha256(raw_diff).hexdigest(),
            git_commands=self._command_count,
            elapsed_ms=elapsed_ms,
            blob_bytes_read=bytes_read,
        )
