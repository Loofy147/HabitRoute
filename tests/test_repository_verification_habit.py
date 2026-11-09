from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest

from habitroute.git_repository import GitReadOnlyRepositoryAdapter
from habitroute.machine import OperationEffect
from habitroute.repertoire import (
    CostDimension,
    CostEstimate,
    HostCapabilitySnapshot,
    PlanStatus,
    SituationFrame,
)
from habitroute.repo_verification import (
    RepositoryInspectionStatus,
    build_git_inspection_capability,
    build_repository_verification_habit,
    run_repository_verification_habit,
)


NOW = datetime(2026, 11, 9, 14, 0, tzinfo=timezone.utc)


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class RepositoryVerificationHabitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "HabitRoute Test")
        git(self.root, "config", "user.email", "habitroute-test@example.invalid")
        (self.root / "module.py").write_text("value = 1\n", encoding="utf-8")
        git(self.root, "add", "--", "module.py")
        git(self.root, "commit", "-q", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD")
        (self.root / "module.py").write_text("value = 2\n", encoding="utf-8")
        (self.root / "README.md").write_text("change summary\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "target")
        self.target = git(self.root, "rev-parse", "HEAD")
        self.adapter = GitReadOnlyRepositoryAdapter(self.root)
        self.capability = build_git_inspection_capability(
            self.adapter,
            harness_ref="local-readonly@1",
            environment_ref="git-worktree@1",
            evidence_digest="sha256:verified-adapter-contract",
            cost_estimate=CostEstimate(calls=1),
        )
        self.habit = build_repository_verification_habit(self.capability)
        self.situation = SituationFrame(
            situation_id="repo-review-001",
            observed_at=NOW,
            harness_id="local-readonly",
            harness_version="1",
            environment_id="git-worktree",
            environment_version="1",
            available_inputs=frozenset({"repository", "base_commit", "target_commit"}),
            context_digest="sha256:repo-review-context",
            facts=(
                ("repository_root", str(self.root.resolve())),
                ("base_commit", self.base),
                ("target_commit", self.target),
            ),
        )
        self.host = HostCapabilitySnapshot(
            harness_id="local-readonly",
            harness_version="1",
            environment_id="git-worktree",
            environment_version="1",
            available_capabilities=frozenset({self.capability.version_ref}),
            granted_permissions=frozenset({"repository.read"}),
            allowed_effects=frozenset({OperationEffect.READ_ONLY}),
            snapshot_digest="sha256:local-host-snapshot",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_habit_composes_and_executes_the_exact_read_only_git_capability(self) -> None:
        before = git(self.root, "status", "--porcelain=v1")
        result = run_repository_verification_habit(
            self.habit,
            self.situation,
            self.host,
            self.adapter,
            now=NOW,
        )

        self.assertEqual(result.status, RepositoryInspectionStatus.COMPLETE)
        self.assertEqual(result.plan.status, PlanStatus.READY)
        self.assertEqual(result.plan.selected_ids, (self.capability.capability_id,))
        self.assertEqual(
            {item.path for item in result.snapshot.changes},
            {"module.py", "README.md"},
        )
        self.assertTrue(result.snapshot.inventory_complete)
        self.assertTrue(result.snapshot.content_complete)
        self.assertEqual(before, git(self.root, "status", "--porcelain=v1"))

    def test_habit_does_not_execute_when_host_permission_is_missing(self) -> None:
        denied = HostCapabilitySnapshot(
            harness_id="local-readonly",
            harness_version="1",
            environment_id="git-worktree",
            environment_version="1",
            available_capabilities=frozenset({self.capability.version_ref}),
            granted_permissions=frozenset(),
            allowed_effects=frozenset({OperationEffect.READ_ONLY}),
            snapshot_digest="sha256:denied-host-snapshot",
        )

        result = run_repository_verification_habit(
            self.habit, self.situation, denied, self.adapter, now=NOW
        )

        self.assertEqual(result.status, RepositoryInspectionStatus.PLAN_REJECTED)
        self.assertIsNone(result.snapshot)
        self.assertEqual(result.plan.status, PlanStatus.NEEDS_CAPABILITY)

    def test_habit_does_not_execute_when_context_repository_does_not_match_adapter(self) -> None:
        wrong_context = SituationFrame(
            situation_id="repo-review-wrong-root",
            observed_at=NOW,
            harness_id="local-readonly",
            harness_version="1",
            environment_id="git-worktree",
            environment_version="1",
            available_inputs=frozenset({"repository", "base_commit", "target_commit"}),
            context_digest="sha256:wrong-root",
            facts=(
                ("repository_root", str(self.root.parent)),
                ("base_commit", self.base),
                ("target_commit", self.target),
            ),
        )

        result = run_repository_verification_habit(
            self.habit, wrong_context, self.host, self.adapter, now=NOW
        )

        self.assertEqual(result.status, RepositoryInspectionStatus.PLAN_REJECTED)
        self.assertIsNone(result.snapshot)
        self.assertEqual(result.plan.status, PlanStatus.NEEDS_CAPABILITY)

    def test_habit_reports_incomplete_when_blob_limits_prevent_full_content_read(self) -> None:
        bounded_adapter = GitReadOnlyRepositoryAdapter(self.root, max_blob_bytes=2)
        bounded_capability = build_git_inspection_capability(
            bounded_adapter,
            harness_ref="local-readonly@1",
            environment_ref="git-worktree@1",
            evidence_digest="sha256:verified-adapter-contract",
            cost_estimate=CostEstimate(calls=1),
        )
        bounded_habit = build_repository_verification_habit(bounded_capability)
        bounded_host = HostCapabilitySnapshot(
            harness_id="local-readonly",
            harness_version="1",
            environment_id="git-worktree",
            environment_version="1",
            available_capabilities=frozenset({bounded_capability.version_ref}),
            granted_permissions=frozenset({"repository.read"}),
            allowed_effects=frozenset({OperationEffect.READ_ONLY}),
            snapshot_digest="sha256:bounded-host",
        )

        result = run_repository_verification_habit(
            bounded_habit,
            self.situation,
            bounded_host,
            bounded_adapter,
            now=NOW,
        )

        self.assertEqual(result.status, RepositoryInspectionStatus.INCOMPLETE)
        self.assertIsNotNone(result.snapshot)
        self.assertTrue(result.snapshot.inventory_complete)
        self.assertFalse(result.snapshot.content_complete)

    def test_habit_rejects_stale_situation_without_repository_access(self) -> None:
        stale = SituationFrame(
            situation_id="repo-review-stale",
            observed_at=NOW.replace(year=2026, month=11, day=9, hour=13, minute=0),
            harness_id="local-readonly",
            harness_version="1",
            environment_id="git-worktree",
            environment_version="1",
            available_inputs=self.situation.available_inputs,
            context_digest=self.situation.context_digest,
            facts=self.situation.facts,
        )

        result = run_repository_verification_habit(
            self.habit, stale, self.host, self.adapter, now=NOW
        )

        self.assertEqual(result.status, RepositoryInspectionStatus.PLAN_REJECTED)
        self.assertEqual(result.plan.status, PlanStatus.STALE_SITUATION)
        self.assertIsNone(result.snapshot)


if __name__ == "__main__":
    unittest.main()
