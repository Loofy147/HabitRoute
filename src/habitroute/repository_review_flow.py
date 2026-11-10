"""Persistent, read-only repository-review flow with inspectable evidence.

This is a deliberately narrow M3 vertical slice. It inspects immutable Git
commit objects only. UWS references are preserved as provenance pointers; this
module does not claim to read/write a live UWS API or database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import Any, Mapping

from .flows import (
    FlowDefinition,
    FlowEvent,
    FlowEventKind,
    FlowNode,
    FlowNodeKind,
    JsonlFlowJournal,
    PersistentFlow,
)
from .git_repository import (
    BlobObservation,
    BlobReadStatus,
    GitReadOnlyRepositoryAdapter,
    RepositoryChangeSnapshot,
)
from .machine import (
    HarnessOperationResult,
    HarnessProfile,
    OperationEffect,
    OperationOutcome,
    OperationStep,
)
from .repertoire import (
    CapabilityEntry,
    CapabilityStatus,
    CompositionPlan,
    HostCapabilitySnapshot,
    PlanStatus,
    SituationFrame,
    compose_habit,
)
from .repo_verification import (
    RepositoryInspectionStatus,
    build_repository_verification_habit,
    run_repository_verification_habit,
)
from .worker import DispatchStatus, FlowDispatchResult, FlowWorker


class RepositoryReviewPlanError(ValueError):
    """The review plan or its host boundary did not pass the pre-execution gate."""


class RepositoryReviewEvidenceError(RuntimeError):
    """The independent verifier could not validate the collected evidence."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


class RepositoryReviewEvidenceStore:
    """Atomic, content-addressed local evidence store.

    The digest is SHA-256 of canonical JSON bytes. Publication uses a temporary
    file, fsync and atomic replacement. The store is local and is not a remote
    provenance authority or backup service.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, package: Mapping[str, Any]) -> str:
        raw = _canonical_json(dict(package))
        digest = hashlib.sha256(raw).hexdigest()
        target = self.root / f"{digest}.json"

        if target.exists():
            try:
                existing = target.read_bytes()
                if hashlib.sha256(existing).hexdigest() == digest and existing == raw:
                    return digest
            except OSError:
                pass

        fd, temporary = tempfile.mkstemp(
            prefix=f".{digest}.",
            suffix=".tmp",
            dir=self.root,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            try:
                directory_fd = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                # Some platforms/filesystems do not permit directory fsync.
                # File fsync + atomic replacement remain the documented scope.
                pass
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return digest

    def read(self, digest: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("evidence digest must be a lowercase SHA-256 hex string")
        raw = (self.root / f"{digest}.json").read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != digest:
            raise RepositoryReviewEvidenceError("evidence artifact digest mismatch")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise RepositoryReviewEvidenceError("evidence artifact root must be an object")
        return value


def _git_environment() -> dict[str, str]:
    env = os.environ.copy()
    # Do not allow inherited Git repository/index/object overrides to redirect
    # the independent verification commands to a different repository.
    for key in tuple(env):
        if (
            key in {
                "GIT_DIR",
                "GIT_WORK_TREE",
                "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                "GIT_COMMON_DIR",
                "GIT_NAMESPACE",
                "GIT_CONFIG_COUNT",
                "GIT_CONFIG_PARAMETERS",
                "GIT_EXTERNAL_DIFF",
            }
            or key.startswith("GIT_CONFIG_KEY_")
            or key.startswith("GIT_CONFIG_VALUE_")
        ):
            env.pop(key, None)
    env.update({
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
    })
    return env


def _git_bytes(
    repository_root: Path,
    args: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout_seconds: float = 10.0,
    max_output_bytes: int = 16 * 1024 * 1024,
) -> bytes:
    try:
        result = subprocess.run(
            ["git", "--no-pager", *args],
            cwd=repository_root,
            env=_git_environment(),
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryReviewEvidenceError(
            "independent Git verification command could not complete"
        ) from exc
    if len(result.stdout) > max_output_bytes or len(result.stderr) > max_output_bytes:
        raise RepositoryReviewEvidenceError(
            "independent Git verification exceeded its output limit"
        )
    if result.returncode != 0:
        raise RepositoryReviewEvidenceError(
            f"independent Git verification failed with exit code {result.returncode}"
        )
    return result.stdout


def _resolve_exact_commit(repository_root: Path, oid: str) -> str:
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid):
        raise RepositoryReviewEvidenceError("commit identity is not a full object ID")
    value = _git_bytes(
        repository_root,
        ["rev-parse", "--verify", f"{oid}^{{commit}}"],
    ).decode("ascii").strip().lower()
    if value != oid:
        raise RepositoryReviewEvidenceError("commit identity did not resolve exactly")
    return value


def _parse_raw_diff(raw: bytes) -> tuple[dict[str, str | None], ...]:
    tokens = raw.split(b"\0")
    index = 0
    records: list[dict[str, str | None]] = []
    while index < len(tokens) and tokens[index]:
        header = tokens[index]
        index += 1
        if index >= len(tokens):
            raise RepositoryReviewEvidenceError("truncated raw-diff path record")
        path = os.fsdecode(tokens[index])
        index += 1
        if not header.startswith(b":"):
            raise RepositoryReviewEvidenceError("invalid raw-diff record")
        fields = header[1:].split()
        if len(fields) != 5:
            raise RepositoryReviewEvidenceError("unsupported raw-diff record shape")
        old_mode, new_mode, old_oid, new_oid, status_token = fields
        status = status_token[:1].decode("ascii", errors="strict")
        if status not in {"A", "D", "M", "T", "U", "X", "B"}:
            raise RepositoryReviewEvidenceError("unsupported raw-diff status")
        old_value = old_oid.decode("ascii").lower()
        new_value = new_oid.decode("ascii").lower()
        if set(old_value) == {"0"}:
            old_value = ""
        if set(new_value) == {"0"}:
            new_value = ""
        records.append({
            "path": path,
            "change_type": status,
            "base_mode": old_mode.decode("ascii"),
            "target_mode": new_mode.decode("ascii"),
            "base_blob_id": old_value or None,
            "target_blob_id": new_value or None,
        })
    return tuple(records)


def _blob_reference(blob: BlobObservation | None) -> dict[str, Any] | None:
    if blob is None:
        return None
    return {
        "object_id": blob.object_id,
        "object_type": blob.object_type,
        "size_bytes": blob.size_bytes,
        "status": blob.status.value,
        "sha256": blob.sha256,
    }


def _snapshot_inventory(snapshot: RepositoryChangeSnapshot) -> dict[str, Any]:
    return {
        "digest": snapshot.inventory_digest,
        "inventory_complete": snapshot.inventory_complete,
        "content_complete": snapshot.content_complete,
        "changes": [
            {
                "path": item.path,
                "change_type": item.change_type,
                "base_mode": item.base_mode,
                "target_mode": item.target_mode,
                "base_blob": _blob_reference(item.base_blob),
                "target_blob": _blob_reference(item.target_blob),
            }
            for item in snapshot.changes
        ],
    }


def _verify_blob_observations(
    repository_root: Path,
    snapshot: RepositoryChangeSnapshot,
    *,
    max_blob_bytes: int,
    max_total_blob_bytes: int,
) -> None:
    expected: dict[str, BlobObservation] = {}
    for change in snapshot.changes:
        for blob in (change.base_blob, change.target_blob):
            if blob is None:
                continue
            prior = expected.get(blob.object_id)
            if prior is not None and prior != blob:
                raise RepositoryReviewEvidenceError(
                    "one Git object has conflicting blob observations"
                )
            expected[blob.object_id] = blob

    object_ids = tuple(sorted(expected))
    if not object_ids:
        return

    request = b"".join(item.encode("ascii") + b"\n" for item in object_ids)
    checked = _git_bytes(
        repository_root,
        ["cat-file", "--batch-check"],
        input_bytes=request,
    ).splitlines()
    if len(checked) != len(object_ids):
        raise RepositoryReviewEvidenceError("Git object metadata response is incomplete")

    metadata: dict[str, tuple[str, int | None]] = {}
    for expected_oid, line in zip(object_ids, checked):
        fields = line.split()
        if len(fields) == 2 and fields[1] == b"missing":
            metadata[expected_oid] = ("missing", None)
            continue
        if len(fields) != 3:
            raise RepositoryReviewEvidenceError("Git object metadata response is malformed")
        oid = fields[0].decode("ascii").lower()
        object_type = fields[1].decode("ascii")
        try:
            size = int(fields[2])
        except ValueError as exc:
            raise RepositoryReviewEvidenceError("Git object size is malformed") from exc
        if oid != expected_oid or size < 0:
            raise RepositoryReviewEvidenceError("Git object metadata identity mismatch")
        metadata[expected_oid] = (object_type, size)

    content_ids: list[str] = []
    aggregate_size = 0
    for oid in object_ids:
        observed = expected[oid]
        object_type, size = metadata[oid]
        if object_type == "missing":
            wanted_type, wanted_size, wanted_status = "missing", None, BlobReadStatus.NON_BLOB
        elif object_type != "blob":
            wanted_type, wanted_size, wanted_status = object_type, size, BlobReadStatus.NON_BLOB
        elif size is not None and size > max_blob_bytes:
            wanted_type, wanted_size, wanted_status = "blob", size, BlobReadStatus.TOO_LARGE
        else:
            wanted_type, wanted_size = "blob", size
            wanted_status = None
            content_ids.append(oid)
            aggregate_size += size or 0

        if observed.object_type != wanted_type or observed.size_bytes != wanted_size:
            raise RepositoryReviewEvidenceError("blob object type/size does not match Git")
        if wanted_status is not None:
            if observed.status is not wanted_status or observed.sha256 is not None:
                raise RepositoryReviewEvidenceError("non-content blob status is incorrect")
    if aggregate_size > max_total_blob_bytes:
        raise RepositoryReviewEvidenceError("independent blob verification exceeded total byte limit")

    if not content_ids:
        return
    batch_request = b"".join(item.encode("ascii") + b"\n" for item in content_ids)
    batch_output = _git_bytes(
        repository_root,
        ["cat-file", "--batch"],
        input_bytes=batch_request,
        max_output_bytes=max(16 * 1024 * 1024, max_total_blob_bytes + 4096),
    )
    offset = 0
    for expected_oid in content_ids:
        header_end = batch_output.find(b"\n", offset)
        if header_end < 0:
            raise RepositoryReviewEvidenceError("Git batch response is missing a header")
        fields = batch_output[offset:header_end].split()
        if len(fields) != 3:
            raise RepositoryReviewEvidenceError("Git batch header is malformed")
        oid = fields[0].decode("ascii").lower()
        object_type = fields[1].decode("ascii")
        try:
            size = int(fields[2])
        except ValueError as exc:
            raise RepositoryReviewEvidenceError("Git batch content size is malformed") from exc
        data_start = header_end + 1
        data_end = data_start + size
        if (
            oid != expected_oid
            or object_type != "blob"
            or size < 0
            or data_end >= len(batch_output)
            or batch_output[data_end:data_end + 1] != b"\n"
        ):
            raise RepositoryReviewEvidenceError("Git batch content identity or framing mismatch")
        content = batch_output[data_start:data_end]
        observed = expected[expected_oid]
        sha256 = hashlib.sha256(content).hexdigest()
        expected_status = (
            BlobReadStatus.BINARY if b"\0" in content else BlobReadStatus.CONTENT
        )
        if (
            observed.object_type != "blob"
            or observed.size_bytes != size
            or observed.status is not expected_status
            or observed.sha256 != sha256
        ):
            raise RepositoryReviewEvidenceError("blob content digest/status mismatch")
        offset = data_end + 1
    if offset != len(batch_output):
        raise RepositoryReviewEvidenceError("Git batch response contains trailing bytes")


def _working_tree_marker(repository_root: Path) -> dict[str, str]:
    head = _git_bytes(repository_root, ["rev-parse", "HEAD"]).decode("ascii").strip()
    status = _git_bytes(
        repository_root,
        ["status", "--porcelain=v1", "--untracked-files=all", "-z"],
    )
    tracked_diff = _git_bytes(
        repository_root,
        ["diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"],
    )
    untracked = _git_bytes(
        repository_root,
        ["ls-files", "--others", "--exclude-standard", "-z"],
    )
    records: list[dict[str, Any]] = []
    total_untracked_bytes = 0
    for raw_path in filter(None, untracked.split(b"\0")):
        path = Path(os.fsdecode(raw_path))
        candidate = repository_root / path
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            records.append({"path": os.fsdecode(raw_path), "status": "vanished"})
            continue
        record: dict[str, Any] = {
            "path": os.fsdecode(raw_path),
            "mode": stat.S_IFMT(metadata.st_mode),
            "size": metadata.st_size,
        }
        if stat.S_ISREG(metadata.st_mode):
            total_untracked_bytes += metadata.st_size
            if total_untracked_bytes > 16 * 1024 * 1024:
                raise RepositoryReviewEvidenceError(
                    "untracked working-tree marker exceeded its byte limit"
                )
            record["sha256"] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        elif stat.S_ISLNK(metadata.st_mode):
            record["link_target"] = os.readlink(candidate)
        records.append(record)
    value = {
        "head": head,
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "untracked": records,
    }
    return {"sha256": hashlib.sha256(_canonical_json(value)).hexdigest()}


def _independent_verify(
    repository_root: Path,
    snapshot: RepositoryChangeSnapshot,
    before_marker: Mapping[str, str],
    after_marker: Mapping[str, str],
    adapter: GitReadOnlyRepositoryAdapter,
) -> list[str]:
    base = _resolve_exact_commit(repository_root, snapshot.base_commit)
    target = _resolve_exact_commit(repository_root, snapshot.target_commit)
    raw_diff = _git_bytes(
        repository_root,
        [
            "diff", "--raw", "--no-abbrev", "--no-renames",
            "--no-ext-diff", "--no-textconv", "-z", base, target, "--",
        ],
    )
    if hashlib.sha256(raw_diff).hexdigest() != snapshot.inventory_digest:
        raise RepositoryReviewEvidenceError("independent inventory digest mismatch")

    expected_records = tuple({
        "path": item.path,
        "change_type": item.change_type,
        "base_mode": item.base_mode,
        "target_mode": item.target_mode,
        "base_blob_id": item.base_blob_id,
        "target_blob_id": item.target_blob_id,
    } for item in snapshot.changes)
    if _parse_raw_diff(raw_diff) != expected_records:
        raise RepositoryReviewEvidenceError("independent changed-path inventory mismatch")

    _verify_blob_observations(
        repository_root,
        snapshot,
        max_blob_bytes=adapter.max_blob_bytes,
        max_total_blob_bytes=adapter.max_total_blob_bytes,
    )
    if before_marker != after_marker:
        raise RepositoryReviewEvidenceError("repository working-tree marker changed during review")
    return [
        "inventory_digest_matches",
        "inventory_records_match",
        "blob_content_digests_match",
        "working_tree_unchanged",
    ]


class _RepositoryReviewHarness:
    def __init__(
        self,
        *,
        habit: Any,
        plan: CompositionPlan,
        situation: SituationFrame,
        host: HostCapabilitySnapshot,
        adapter: GitReadOnlyRepositoryAdapter,
        evidence_store: RepositoryReviewEvidenceStore,
        task_ref: str,
        goal_ref: str,
        run_id: str,
        plan_digest: str,
    ) -> None:
        self.habit = habit
        self.plan = plan
        self.situation = situation
        self.host = host
        self.adapter = adapter
        self.evidence_store = evidence_store
        self.task_ref = task_ref
        self.goal_ref = goal_ref
        self.run_id = run_id
        self.plan_digest = plan_digest
        selected = plan.selected[0]
        self.profile = HarnessProfile(
            harness_id=situation.harness_id,
            version=situation.harness_version,
            environment_id=situation.environment_id,
            context_id=situation.context_digest,
            allowed_operations=frozenset({selected.version_ref}),
            max_step_attempts=1,
        )

    def invoke(
        self,
        operation: OperationStep,
        inputs: Mapping[str, str],
        *,
        idempotency_key: str,
    ) -> HarnessOperationResult:
        selected = self.plan.selected[0]
        if (
            operation.operation_ref != selected.version_ref
            or operation.effect is not OperationEffect.READ_ONLY
            or operation.max_attempts != 1
            or not idempotency_key
        ):
            return HarnessOperationResult(
                OperationOutcome.FAILED,
                error_code="repository_review_operation_contract_mismatch",
            )
        expected_inputs = {
            "repository_root",
            "base_commit",
            "target_commit",
        }
        if set(inputs) != expected_inputs:
            return HarnessOperationResult(
                OperationOutcome.FAILED,
                error_code="repository_review_input_contract_mismatch",
            )
        facts = dict(self.situation.facts)
        if (
            inputs["repository_root"] != str(self.adapter.repository_root)
            or inputs["repository_root"] != facts.get("repository_root")
            or inputs["base_commit"] != facts.get("base_commit")
            or inputs["target_commit"] != facts.get("target_commit")
        ):
            return HarnessOperationResult(
                OperationOutcome.FAILED,
                error_code="repository_review_commit_or_root_mismatch",
            )

        before_marker = _working_tree_marker(self.adapter.repository_root)
        inspection = run_repository_verification_habit(
            self.habit,
            self.situation,
            self.host,
            self.adapter,
            now=datetime.now(timezone.utc),
        )
        after_marker = _working_tree_marker(self.adapter.repository_root)
        if inspection.status is RepositoryInspectionStatus.PLAN_REJECTED:
            return HarnessOperationResult(
                OperationOutcome.FAILED,
                error_code=f"repository_review_plan_rejected:{inspection.reason}",
            )
        if inspection.snapshot is None:
            return HarnessOperationResult(
                OperationOutcome.FAILED,
                error_code="repository_review_snapshot_missing",
            )

        checks = _independent_verify(
            self.adapter.repository_root,
            inspection.snapshot,
            before_marker,
            after_marker,
            self.adapter,
        )
        review_status = (
            "complete"
            if inspection.status is RepositoryInspectionStatus.COMPLETE
            else "incomplete"
        )
        package = {
            "schema": "habitroute.repository-review-evidence.v0.1",
            "run_id": self.run_id,
            "uws_task_ref": self.task_ref,
            "uws_goal_ref": self.goal_ref,
            "review_status": review_status,
            "plan": {
                "habit_id": self.habit.habit_id,
                "habit_version": self.habit.version,
                "plan_digest": self.plan_digest,
                "reason": self.plan.reason,
                "selected_capabilities": [
                    {
                        "id": item.capability_id,
                        "version": item.version,
                        "evidence_digest": item.evidence_digest,
                        "effect": item.effect.value,
                    }
                    for item in self.plan.selected
                ],
            },
            "situation": {
                "id": self.situation.situation_id,
                "observed_at": self.situation.observed_at.isoformat(),
                "context_digest": self.situation.context_digest,
            },
            "host": {
                "snapshot_digest": self.host.snapshot_digest,
                "harness_ref": self.host.harness_ref,
                "environment_ref": self.host.environment_ref,
                "granted_permissions": sorted(self.host.granted_permissions),
                "allowed_effects": sorted(item.value for item in self.host.allowed_effects),
            },
            "repository": {
                "root": str(self.adapter.repository_root),
                "base_commit": inspection.snapshot.base_commit,
                "target_commit": inspection.snapshot.target_commit,
            },
            "inventory": _snapshot_inventory(inspection.snapshot),
            "verification": {
                "verifier": "habitroute.independent-git-review-verifier.v0.1",
                "status": "PASS",
                "checks": checks,
                "scope": "immutable Git object inventory; local worktree marker",
            },
            "limits": [
                "read_only_immutable_commit_range",
                "no_project_code_or_tests_executed",
                "no_live_uws_api_or_database_lookup",
                "not_a_semantic_code_correctness_review",
                "not_a_source_authenticity_attestation",
            ],
        }
        digest = self.evidence_store.write(package)
        return HarnessOperationResult(
            OperationOutcome.SUCCEEDED,
            outputs=(
                ("review.evidence_digest", digest),
                ("review.evidence_ref", f"local-sha256:{digest}"),
                ("review.status", review_status),
            ),
        )


@dataclass(slots=True)
class RepositoryReviewFlowSession:
    definition: FlowDefinition
    flow: PersistentFlow
    harness: _RepositoryReviewHarness
    evidence_store: RepositoryReviewEvidenceStore

    def dispatch(self) -> FlowDispatchResult:
        return FlowWorker(self.harness).dispatch(self.flow)


def create_repository_review_flow(
    *,
    run_id: str,
    task_ref: str,
    goal_ref: str,
    habit: Any,
    situation: SituationFrame,
    host: HostCapabilitySnapshot,
    adapter: GitReadOnlyRepositoryAdapter,
    journal: JsonlFlowJournal,
    evidence_store: RepositoryReviewEvidenceStore,
    now: datetime,
) -> RepositoryReviewFlowSession:
    """Preflight and start a single-node, read-only repository review flow.

    task_ref and goal_ref are opaque UWS provenance references supplied by the
    caller. They are not fetched from, or written to, a live UWS service here.
    """
    for name, value in (
        ("run_id", run_id),
        ("task_ref", task_ref),
        ("goal_ref", goal_ref),
    ):
        if not isinstance(value, str) or not value.strip():
            raise RepositoryReviewPlanError(f"{name} must be non-empty")
    if now.tzinfo is None or now.utcoffset() is None:
        raise RepositoryReviewPlanError("now must be timezone-aware")

    plan = compose_habit(habit, situation, host, now=now)
    if plan.status is not PlanStatus.READY:
        raise RepositoryReviewPlanError(f"repository review plan is not READY: {plan.reason}")
    if len(plan.selected) != 1:
        raise RepositoryReviewPlanError("repository review must select exactly one capability")
    selected: CapabilityEntry = plan.selected[0]
    if (
        selected.capability_id != adapter.CAPABILITY_ID
        or selected.version != adapter.CAPABILITY_VERSION
        or selected.effect is not OperationEffect.READ_ONLY
        or selected.status is not CapabilityStatus.ACTIVE
    ):
        raise RepositoryReviewPlanError(
            "selected capability is not the pinned active read-only Git adapter"
        )

    facts = dict(situation.facts)
    for key in ("repository_root", "base_commit", "target_commit"):
        if not facts.get(key):
            raise RepositoryReviewPlanError(f"situation is missing required fact: {key}")
    if facts["repository_root"] != str(adapter.repository_root):
        raise RepositoryReviewPlanError("situation repository root does not match the adapter")

    plan_payload = {
        "habit_id": habit.habit_id,
        "habit_version": habit.version,
        "plan_reason": plan.reason,
        "selected": [
            {
                "id": item.capability_id,
                "version": item.version,
                "evidence_digest": item.evidence_digest,
            }
            for item in plan.selected
        ],
        "situation_id": situation.situation_id,
        "situation_observed_at": situation.observed_at.isoformat(),
        "situation_digest": situation.context_digest,
        "host_snapshot_digest": host.snapshot_digest,
    }
    plan_digest = hashlib.sha256(_canonical_json(plan_payload)).hexdigest()
    harness = _RepositoryReviewHarness(
        habit=habit,
        plan=plan,
        situation=situation,
        host=host,
        adapter=adapter,
        evidence_store=evidence_store,
        task_ref=task_ref,
        goal_ref=goal_ref,
        run_id=run_id,
        plan_digest=plan_digest,
    )
    initial_context = {
        "review.task_ref": task_ref,
        "review.goal_ref": goal_ref,
        "review.plan_digest": plan_digest,
        "review.situation_digest": situation.context_digest,
        "review.host_snapshot_digest": host.snapshot_digest,
        "review.capability_id": selected.capability_id,
        "review.capability_version": selected.version,
        "review.capability_evidence_digest": selected.evidence_digest or "",
        "review.repository_root": facts["repository_root"],
        "review.base_commit": facts["base_commit"],
        "review.target_commit": facts["target_commit"],
    }
    definition = FlowDefinition(
        flow_id="repository-review",
        version=1,
        start_node="inspect",
        nodes=(
            FlowNode(
                node_id="inspect",
                kind=FlowNodeKind.OPERATION,
                target_ref=selected.version_ref,
                next_on_success="done",
                max_attempts=1,
                effect=OperationEffect.READ_ONLY,
                input_bindings=(
                    ("repository_root", "$state.review.repository_root"),
                    ("base_commit", "$state.review.base_commit"),
                    ("target_commit", "$state.review.target_commit"),
                ),
            ),
            FlowNode(
                node_id="done",
                kind=FlowNodeKind.END,
            ),
        ),
    )
    flow = PersistentFlow.start(definition, run_id, journal, initial_context)
    return RepositoryReviewFlowSession(
        definition=definition,
        flow=flow,
        harness=harness,
        evidence_store=evidence_store,
    )
