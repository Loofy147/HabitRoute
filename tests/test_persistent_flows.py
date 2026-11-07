import tempfile
import unittest

from habitroute.flows import (
    FlowDefinition, FlowEvent, FlowEventKind, FlowNode, FlowNodeKind,
    FlowStatus, JsonlFlowJournal, PersistentFlow, apply_flow_event,
)
from habitroute.machine import OperationEffect


def definition():
    return FlowDefinition(
        "nightly-maintenance", 3, "scan",
        (
            FlowNode("scan", FlowNodeKind.OPERATION, "repo.scan", "branch",
                     next_on_failure="manual", max_attempts=2,
                     effect=OperationEffect.IDEMPOTENT),
            FlowNode("branch", FlowNodeKind.BRANCH, branch_key="scan.result",
                     branch_equals="clean", next_on_true="wait", next_on_false="manual"),
            FlowNode("wait", FlowNodeKind.WAIT, next_on_success="refresh"),
            FlowNode("refresh", FlowNodeKind.HABIT, "refresh-index", "done",
                     max_attempts=1, effect=OperationEffect.IDEMPOTENT,
                     target_version=2),
            FlowNode("manual", FlowNodeKind.END, end_status=FlowStatus.NEEDS_ATTENTION),
            FlowNode("done", FlowNodeKind.END, end_status=FlowStatus.SUCCEEDED),
        ),
    )


class PersistentFlowTests(unittest.TestCase):
    def test_flow_starts_and_exposes_stable_idempotency_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(definition(), "run-001",
                                        JsonlFlowJournal(tmp), {"repo": "A"})
            self.assertEqual(flow.snapshot.status, FlowStatus.RUNNING)
            self.assertEqual(flow.current_node.node_id, "scan")
            self.assertEqual(flow.idempotency_key, "run-001:nightly-maintenance:3:scan")

    def test_operation_scope_key_is_stable_for_retries_and_changes_on_node_revisit(self):
        loop = FlowDefinition(
            "self-loop", 1, "scan",
            (FlowNode(
                "scan", FlowNodeKind.OPERATION, "repo.scan", "scan",
                max_attempts=2, effect=OperationEffect.READ_ONLY,
            ),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(loop, "run-loop-001", JsonlFlowJournal(tmp))
            first_key = flow.operation_scope_key
            flow.fail_step("retryable")
            self.assertEqual(flow.operation_scope_key, first_key)
            flow.succeed_step()
            self.assertEqual(flow.current_node.node_id, "scan")
            self.assertEqual(flow.snapshot.node_visit_count("scan"), 2)
            self.assertNotEqual(flow.operation_scope_key, first_key)
            self.assertEqual(flow.snapshot.operation_attempt_count(0), 0)


    def test_operation_intents_must_follow_sequential_checkpoint_indices(self):
        habit_flow = FlowDefinition(
            "sequential-checkpoints", 1, "habit",
            (
                FlowNode(
                    "habit", FlowNodeKind.HABIT, "multi-step-habit", "done",
                    target_version=1,
                ),
                FlowNode("done", FlowNodeKind.END),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(
                habit_flow, "run-sequential-001", JsonlFlowJournal(tmp)
            )
            with self.assertRaisesRegex(ValueError, "next sequential operation index"):
                flow.begin_operation(
                    operation_index=1,
                    operation_ref="repo.test.second",
                    effect=OperationEffect.READ_ONLY,
                    idempotency_key=f"{flow.operation_scope_key}:habit:1",
                    attempt=1,
                    input_sha256="a" * 64,
                )
            self.assertEqual(flow.snapshot.operation_index if hasattr(flow.snapshot, "operation_index") else 0, 0)
            self.assertIsNone(flow.snapshot.pending_operation)
            self.assertEqual(len(flow.journal.load("run-sequential-001")), 1)

    def test_retry_preserves_idempotency_key_and_failure_branch(self):
        flow_def = definition()
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(flow_def, "run-002", JsonlFlowJournal(tmp))
            first_key = flow.idempotency_key
            flow.fail_step("temporary")
            self.assertEqual(flow.current_node.node_id, "scan")
            self.assertEqual(flow.snapshot.attempt_count("scan"), 1)
            self.assertEqual(flow.idempotency_key, first_key)
            flow.fail_step("still-failed")
            self.assertEqual(flow.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertEqual(flow.current_node.node_id, "manual")

    def test_success_branch_wait_habit_and_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(definition(), "run-003", JsonlFlowJournal(tmp))
            flow.succeed_step({"scan.result": "clean"})
            self.assertEqual(flow.current_node.node_id, "branch")
            flow.resolve_branch()
            self.assertEqual(flow.snapshot.status, FlowStatus.WAITING)
            self.assertEqual(flow.current_node.node_id, "wait")
            flow.release_wait()
            self.assertEqual(flow.current_node.node_id, "refresh")
            flow.succeed_step({"index.refreshed": "true"})
            self.assertEqual(flow.snapshot.status, FlowStatus.SUCCEEDED)

    def test_failed_branch_routes_to_manual_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(definition(), "run-004", JsonlFlowJournal(tmp),
                                        {"scan.result": "dirty"})
            flow.succeed_step({"scan.result": "dirty"})
            flow.resolve_branch()
            self.assertEqual(flow.snapshot.current_node, "manual")
            self.assertEqual(flow.snapshot.status, FlowStatus.NEEDS_ATTENTION)

    def test_pause_resume_preserves_waiting_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(definition(), "run-005", JsonlFlowJournal(tmp))
            flow.succeed_step({"scan.result": "clean"})
            flow.resolve_branch()
            self.assertEqual(flow.snapshot.status, FlowStatus.WAITING)
            flow.pause()
            self.assertEqual(flow.snapshot.status, FlowStatus.PAUSED)
            flow.resume()
            self.assertEqual(flow.snapshot.status, FlowStatus.WAITING)

    def test_unknown_side_effect_outcome_requires_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(definition(), "run-006", JsonlFlowJournal(tmp))
            flow.mark_outcome_unknown("connection lost after submit")
            self.assertEqual(flow.snapshot.status, FlowStatus.NEEDS_ATTENTION)

    def test_cancel_is_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(definition(), "run-007", JsonlFlowJournal(tmp))
            flow.cancel("operator-request")
            self.assertEqual(flow.snapshot.status, FlowStatus.CANCELLED)
            with self.assertRaises(ValueError):
                flow.succeed_step()

    def test_journal_survives_reopen_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(definition(), "run-008", journal, {"repo": "A"})
            flow.succeed_step({"scan.result": "clean"})
            flow.resolve_branch()
            before = flow.snapshot
            reopened = PersistentFlow.restore(definition(), "run-008", JsonlFlowJournal(tmp))
            self.assertEqual(reopened.snapshot, before)
            self.assertEqual(reopened.snapshot.status, FlowStatus.WAITING)

    def test_duplicate_event_is_idempotent_in_reducer(self):
        flow_def = definition()
        initial = __import__("habitroute.flows", fromlist=["FlowSnapshot"]).FlowSnapshot.initial(
            flow_def, "run-009"
        )
        event = FlowEvent("run-009", 1, "event-start", FlowEventKind.STARTED,
                          "scan", ())
        once = apply_flow_event(flow_def, initial, event)
        twice = apply_flow_event(flow_def, once, event)
        self.assertEqual(once, twice)


    def test_habit_flow_node_must_pin_exact_habit_version(self):
        with self.assertRaises(ValueError):
            FlowNode("refresh", FlowNodeKind.HABIT, "refresh-index", "done")


    def test_definition_rejects_unknown_edges(self):
        with self.assertRaises(ValueError):
            FlowDefinition(
                "bad", 1, "start",
                (FlowNode("start", FlowNodeKind.OPERATION, "do-it", "missing"),),
            )

    def test_non_repeatable_node_cannot_have_automatic_retries(self):
        with self.assertRaises(ValueError):
            FlowNode("charge", FlowNodeKind.OPERATION, "payment.charge", "done",
                     max_attempts=2, effect=OperationEffect.NON_REPEATABLE)

    def test_deduplicated_node_requires_idempotency_support(self):
        with self.assertRaises(ValueError):
            FlowNode("send", FlowNodeKind.OPERATION, "email.send", "done",
                     max_attempts=2, effect=OperationEffect.DEDUPLICATED)

    def test_journal_truncates_only_an_unterminated_final_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(definition(), "run-torn-001", journal)
            path = journal._path("run-torn-001")
            with path.open("ab") as handle:
                handle.write(b'{"run_id":"run-torn-001","sequence":2')
                handle.flush()

            restored = PersistentFlow.restore(
                definition(), "run-torn-001", JsonlFlowJournal(tmp)
            )
            self.assertEqual(restored.snapshot.last_event_sequence, 1)
            self.assertEqual(len(JsonlFlowJournal(tmp).load("run-torn-001")), 1)
            self.assertTrue(path.read_bytes().endswith(b"\\n"))
            restored.fail_step("retry-after-torn-uncommitted-append")
            self.assertEqual(
                [event.sequence for event in JsonlFlowJournal(tmp).load("run-torn-001")],
                [1, 2],
            )

    def test_journal_does_not_silently_repair_newline_terminated_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            PersistentFlow.start(definition(), "run-corrupt-001", journal)
            path = journal._path("run-corrupt-001")
            with path.open("ab") as handle:
                handle.write(b"{corrupt}\\n")
                handle.flush()
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "corrupt flow journal"):
                journal.load("run-corrupt-001")
            self.assertEqual(path.read_bytes(), before)

    def test_journal_rejects_sequence_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(definition(), "run-010", journal)
            bad = FlowEvent("run-010", flow.snapshot.last_event_sequence + 2,
                            "gap", FlowEventKind.STEP_SUCCEEDED, "scan", ())
            with self.assertRaises(ValueError):
                journal.append(bad)

    def test_idempotent_journal_append_does_not_duplicate_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(definition(), "run-011", journal)
            event = journal.load("run-011")[0]
            journal.append(event)
            self.assertEqual(len(journal.load("run-011")), 1)


if __name__ == "__main__":
    unittest.main()
