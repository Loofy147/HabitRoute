from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from habitroute.flows import (
    FlowEvent,
    FlowEventKind,
    FlowStatus,
    JsonlFlowJournal,
    PersistentFlow,
)
from habitroute.git_repository import GitReadOnlyRepositoryAdapter
from habitroute.repertoire import (
    CapabilityStatus,
    CostEstimate,
    HostCapabilitySnapshot,
    SituationFrame,
)
from habitroute.repo_verification import (
    build_git_inspection_capability,
    build_repository_verification_habit,
)
from habitroute.repository_review_flow import (
    RepositoryReviewEvidenceStore,
    RepositoryReviewPlanError,
    create_repository_review_flow,
)
from habitroute.worker import DispatchStatus, FlowWorker


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.stdout.strip()


class FailBeforeStepResultJournal(JsonlFlowJournal):
    def __init__(self, root: str | Path) -> None:
        super().__init__(root)
        self.failed_once = False

    def append(self, event: FlowEvent) -> None:
        if event.kind is FlowEventKind.STEP_SUCCEEDED and not self.failed_once:
            self.failed_once = True
            raise OSError("injected crash after evidence creation, before flow result")
        super().append(event)


class RepositoryReviewFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        git(self.repository, "init", "-q")
        git(self.repository, "config", "user.name", "Repository Review Test")
        git(self.repository, "config", "user.email", "review@example.invalid")
        (self.repository / "module.py").write_text("value = 1\n", encoding="utf-8")
        git(self.repository, "add", "--", "module.py")
        git(self.repository, "commit", "-q", "-m", "base")
        self.base = git(self.repository, "rev-parse", "HEAD")
        (self.repository / "module.py").write_text("value = 2\n", encoding="utf-8")
        (self.repository / "README.md").write_text("bounded review fixture\n", encoding="utf-8")
        git(self.repository, "add", "-A")
        git(self.repository, "commit", "-q", "-m", "target")
        self.target = git(self.repository, "rev-parse", "HEAD")
        self.now = datetime.now(timezone.utc)
        self.adapter = GitReadOnlyRepositoryAdapter(self.repository)
        self.capability = build_git_inspection_capability(
            self.adapter,
            harness_ref="habitroute-review@0.1.0",
            environment_ref="local-git@0.1.0",
            evidence_digest="sha256:independently-reviewed-adapter-fixture",
            cost_estimate=CostEstimate(calls=1),
            status=CapabilityStatus.ACTIVE,
        )
        self.habit = build_repository_verification_habit(
            self.capability,
            max_situation_age_seconds=300,
        )
        self.situation = SituationFrame(
            situation_id="m3-review-situation-001",
            observed_at=self.now,
            harness_id="habitroute-review",
            harness_version="0.1.0",
            environment_id="local-git",
            environment_version="0.1.0",
            available_inputs=frozenset({
                "repository", "base_commit", "target_commit",
            }),
            context_digest="sha256:situation-fixture-001",
            facts=(
                ("repository_root", str(self.repository.resolve())),
                ("base_commit", self.base),
                ("target_commit", self.target),
            ),
        )
        self.host = HostCapabilitySnapshot(
            harness_id="habitroute-review",
            harness_version="0.1.0",
            environment_id="local-git",
            environment_version="0.1.0",
            available_capabilities=frozenset({self.capability.version_ref}),
            granted_permissions=frozenset({"repository.read"}),
            allowed_effects=frozenset({self.capability.effect}),
            snapshot_digest="sha256:host-snapshot-fixture-001",
        )
        self.journal_root = self.root / "journal"
        self.evidence_root = self.root / "evidence"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_session(
        self,
        *,
        journal: JsonlFlowJournal | None = None,
        adapter: GitReadOnlyRepositoryAdapter | None = None,
        situation: SituationFrame | None = None,
        host: HostCapabilitySnapshot | None = None,
    ):
        selected_adapter = adapter or self.adapter
        capability = build_git_inspection_capability(
            selected_adapter,
            harness_ref="habitroute-review@0.1.0",
            environment_ref="local-git@0.1.0",
            evidence_digest="sha256:independently-reviewed-adapter-fixture",
            cost_estimate=CostEstimate(calls=1),
            status=CapabilityStatus.ACTIVE,
        )
        habit = build_repository_verification_habit(
            capability,
            max_situation_age_seconds=300,
        )
        return create_repository_review_flow(
            run_id="m3-review-run-001",
            task_ref="uws://task/TASK-001",
            goal_ref="uws://goal/GOAL-001",
            habit=habit,
            situation=situation or self.situation,
            host=host or self.host,
            adapter=selected_adapter,
            journal=journal or JsonlFlowJournal(self.journal_root),
            evidence_store=RepositoryReviewEvidenceStore(self.evidence_root),
            now=self.now,
        )

    def test_read_only_review_creates_independently_verified_evidence(self):
        before_head = git(self.repository, "rev-parse", "HEAD")
        before_status = git(self.repository, "status", "--porcelain=v1", "--untracked-files=all")
        session = self.create_session()

        dispatched = session.dispatch()

        self.assertEqual(dispatched.status, DispatchStatus.TERMINAL)
        self.assertEqual(session.flow.snapshot.status, FlowStatus.SUCCEEDED)
        context = session.flow.snapshot.context_dict()
        digest = context["review.evidence_digest"]
        package = session.evidence_store.read(digest)

        self.assertEqual(package["review_status"], "complete")
        self.assertEqual(package["uws_task_ref"], "uws://task/TASK-001")
        self.assertEqual(package["uws_goal_ref"], "uws://goal/GOAL-001")
        self.assertEqual(package["verification"]["status"], "PASS")
        self.assertIn("inventory_digest_matches", package["verification"]["checks"])
        self.assertIn("blob_content_digests_match", package["verification"]["checks"])
        self.assertIn("working_tree_unchanged", package["verification"]["checks"])
        self.assertEqual(
            {item["path"] for item in package["inventory"]["changes"]},
            {"module.py", "README.md"},
        )
        self.assertEqual(package["repository"]["base_commit"], self.base)
        self.assertEqual(package["repository"]["target_commit"], self.target)
        self.assertEqual(before_head, git(self.repository, "rev-parse", "HEAD"))
        self.assertEqual(
            before_status,
            git(self.repository, "status", "--porcelain=v1", "--untracked-files=all"),
        )
        raw = json.dumps(package, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_stale_situation_fails_before_any_repository_inspection(self):
        stale = SituationFrame(
            situation_id="m3-stale-situation",
            observed_at=self.now.replace(year=self.now.year - 1),
            harness_id=self.situation.harness_id,
            harness_version=self.situation.harness_version,
            environment_id=self.situation.environment_id,
            environment_version=self.situation.environment_version,
            available_inputs=self.situation.available_inputs,
            context_digest="sha256:stale",
            facts=self.situation.facts,
        )
        command_count = self.adapter._command_count
        with self.assertRaises(RepositoryReviewPlanError):
            self.create_session(situation=stale)
        self.assertEqual(self.adapter._command_count, command_count)

    def test_missing_host_permission_fails_before_flow_creation(self):
        denied = HostCapabilitySnapshot(
            harness_id=self.host.harness_id,
            harness_version=self.host.harness_version,
            environment_id=self.host.environment_id,
            environment_version=self.host.environment_version,
            available_capabilities=self.host.available_capabilities,
            granted_permissions=frozenset(),
            allowed_effects=self.host.allowed_effects,
            snapshot_digest="sha256:denied",
        )
        command_count = self.adapter._command_count
        with self.assertRaises(RepositoryReviewPlanError):
            self.create_session(host=denied)
        self.assertEqual(self.adapter._command_count, command_count)

    def test_incomplete_blob_content_is_recorded_not_promoted(self):
        bounded = GitReadOnlyRepositoryAdapter(self.repository, max_blob_bytes=4)
        session = self.create_session(adapter=bounded)
        session.dispatch()
        package = session.evidence_store.read(
            session.flow.snapshot.context_dict()["review.evidence_digest"]
        )
        self.assertEqual(package["review_status"], "incomplete")
        self.assertEqual(package["verification"]["status"], "PASS")
        self.assertTrue(
            any(
                blob["status"] == "too_large"
                for item in package["inventory"]["changes"]
                for blob in (item["base_blob"], item["target_blob"])
                if blob is not None
            )
        )

    def test_crash_after_artifact_write_replays_read_only_operation_idempotently(self):
        failing_journal = FailBeforeStepResultJournal(self.journal_root)
        session = self.create_session(journal=failing_journal)
        with self.assertRaisesRegex(OSError, "injected crash"):
            session.dispatch()

        persisted_events = JsonlFlowJournal(self.journal_root).load("m3-review-run-001")
        self.assertEqual(persisted_events[-1].kind, FlowEventKind.STARTED)
        first_package = list(self.evidence_root.glob("*.json"))
        self.assertEqual(len(first_package), 1)
        first_digest = first_package[0].stem

        restored = PersistentFlow.restore(
            session.definition,
            "m3-review-run-001",
            JsonlFlowJournal(self.journal_root),
        )
        result = FlowWorker(session.harness).dispatch(restored)

        self.assertEqual(result.status, DispatchStatus.TERMINAL)
        self.assertEqual(restored.snapshot.status, FlowStatus.SUCCEEDED)
        self.assertEqual(
            restored.snapshot.context_dict()["review.evidence_digest"],
            first_digest,
        )
        self.assertEqual(len(list(self.evidence_root.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
