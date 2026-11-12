from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from habitroute.git_repository import (
    BlobReadStatus,
    GitInputError,
    GitReadOnlyRepositoryAdapter,
    GitResourceLimitError,
)


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class GitReadOnlyRepositoryAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "HabitRoute Test")
        git(self.root, "config", "user.email", "habitroute-test@example.invalid")
        (self.root / "README.md").write_text("before\n", encoding="utf-8")
        (self.root / "old.txt").write_text("remove me\n", encoding="utf-8")
        git(self.root, "add", "--", "README.md", "old.txt")
        git(self.root, "commit", "-q", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD")

        (self.root / "README.md").write_text("after\n", encoding="utf-8")
        (self.root / "new file.txt").write_text("new content\n", encoding="utf-8")
        (self.root / "old.txt").unlink()
        (self.root / "image.bin").write_bytes(b"\x00\x01\x02")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "target")
        self.target = git(self.root, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_reads_exact_commit_range_and_changed_blob_contents(self) -> None:
        adapter = GitReadOnlyRepositoryAdapter(self.root)
        snapshot = adapter.inspect_commit_range(self.base, self.target)

        self.assertEqual(snapshot.base_commit, self.base)
        self.assertEqual(snapshot.target_commit, self.target)
        self.assertEqual(snapshot.repository_root, str(self.root.resolve()))
        self.assertEqual(
            {item.path for item in snapshot.changes},
            {"README.md", "old.txt", "new file.txt", "image.bin"},
        )
        by_path = {item.path: item for item in snapshot.changes}

        self.assertEqual(by_path["README.md"].change_type, "M")
        self.assertEqual(by_path["README.md"].target_content, b"after\n")
        self.assertEqual(
            by_path["README.md"].target_sha256,
            hashlib.sha256(b"after\n").hexdigest(),
        )
        self.assertEqual(by_path["new file.txt"].change_type, "A")
        self.assertEqual(by_path["new file.txt"].target_content, b"new content\n")
        self.assertEqual(by_path["old.txt"].change_type, "D")
        self.assertIsNone(by_path["old.txt"].target_blob_id)
        self.assertIsNone(by_path["old.txt"].target_content)
        self.assertEqual(by_path["image.bin"].target_content_status, BlobReadStatus.BINARY)
        self.assertTrue(snapshot.inventory_complete)
        self.assertTrue(snapshot.content_complete)

    def test_inventory_is_stable_for_same_immutable_commits(self) -> None:
        adapter = GitReadOnlyRepositoryAdapter(self.root)
        first = adapter.inspect_commit_range(self.base, self.target)
        second = adapter.inspect_commit_range(self.base, self.target)

        self.assertEqual(first.inventory_digest, second.inventory_digest)
        self.assertEqual(first.changes, second.changes)

    def test_working_tree_changes_do_not_mutate_the_commit_snapshot(self) -> None:
        adapter = GitReadOnlyRepositoryAdapter(self.root)
        before = adapter.inspect_commit_range(self.base, self.target).inventory_digest
        (self.root / "README.md").write_text("uncommitted local change\n", encoding="utf-8")
        after = adapter.inspect_commit_range(self.base, self.target).inventory_digest

        self.assertEqual(before, after)

    def test_rejects_branch_names_and_abbreviated_hashes(self) -> None:
        adapter = GitReadOnlyRepositoryAdapter(self.root)
        for invalid in ("main", self.base[:8], "--help", "../HEAD"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(GitInputError):
                    adapter.inspect_commit_range(invalid, self.target)

    def test_rejects_non_commit_object_ids(self) -> None:
        blob = git(self.root, "rev-parse", f"{self.target}:README.md")
        adapter = GitReadOnlyRepositoryAdapter(self.root)
        with self.assertRaises(GitInputError):
            adapter.inspect_commit_range(blob, self.target)

    def test_rejects_path_count_over_limit_without_partial_inventory(self) -> None:
        adapter = GitReadOnlyRepositoryAdapter(self.root, max_changed_paths=2)
        with self.assertRaises(GitResourceLimitError):
            adapter.inspect_commit_range(self.base, self.target)

    def test_large_blob_is_reported_as_incomplete_not_silently_read(self) -> None:
        adapter = GitReadOnlyRepositoryAdapter(self.root, max_blob_bytes=2)
        snapshot = adapter.inspect_commit_range(self.base, self.target)
        readme = next(item for item in snapshot.changes if item.path == "README.md")

        self.assertEqual(readme.target_content_status, BlobReadStatus.TOO_LARGE)
        self.assertIsNone(readme.target_content)
        self.assertFalse(snapshot.content_complete)
        self.assertTrue(snapshot.inventory_complete)

    def test_repository_root_must_be_a_git_worktree(self) -> None:
        other = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(GitInputError):
                GitReadOnlyRepositoryAdapter(other)
        finally:
            other.rmdir()


    def test_inherited_git_environment_cannot_redirect_repository_identity(self) -> None:
        other = Path(tempfile.mkdtemp())
        try:
            git(other, "init", "-q")
            git(other, "config", "user.name", "Other Repository")
            git(other, "config", "user.email", "other@example.invalid")
            (other / "other.txt").write_text("other\n", encoding="utf-8")
            git(other, "add", "--", "other.txt")
            git(other, "commit", "-q", "-m", "other")
            with patch.dict(os.environ, {
                "GIT_DIR": str(other / ".git"),
                "GIT_WORK_TREE": str(other),
                "GIT_INDEX_FILE": str(other / ".git" / "index"),
            }):
                adapter = GitReadOnlyRepositoryAdapter(self.root)
                self.assertEqual(adapter.repository_root, self.root.resolve())
                snapshot = adapter.inspect_commit_range(self.base, self.target)
                self.assertEqual(snapshot.repository_root, str(self.root.resolve()))
                self.assertEqual(
                    {item.path for item in snapshot.changes},
                    {"README.md", "old.txt", "new file.txt", "image.bin"},
                )
        finally:
            import shutil
            shutil.rmtree(other)


if __name__ == "__main__":
    unittest.main()
