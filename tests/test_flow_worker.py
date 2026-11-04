import tempfile
import unittest

from habitroute.flows import (
    FlowDefinition, FlowNode, FlowNodeKind, FlowStatus, JsonlFlowJournal, PersistentFlow,
)
from habitroute.machine import (
    CostMetric, EfficiencyGate, HarnessOperationResult, HarnessProfile,
    MachineHabit, MachineHabitStatus, OperationEffect, OperationOutcome,
    OperationStep, PerformanceProfile, StateCondition,
)
from habitroute.worker import DispatchStatus, FlowWorker, HabitRegistry


class StubHarness:
    def __init__(self, profile, outcomes=None):
        self.profile = profile
        self.outcomes = {key: list(value) for key, value in (outcomes or {}).items()}
        self.calls = []

    def invoke(self, operation, inputs, *, idempotency_key):
        self.calls.append((operation.operation_ref, dict(inputs), idempotency_key))
        queue = self.outcomes.get(operation.operation_ref, [])
        if queue:
            result = queue.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return HarnessOperationResult(OperationOutcome.SUCCEEDED)


def profile(approval_required=frozenset()):
    return HarnessProfile(
        "local-harness", "v3", "test-machine", "project-x",
        frozenset({"repo.scan", "repo.test", "deploy.preview"}),
        approval_required, max_step_attempts=3,
    )


def simple_flow(node, run_id):
    return FlowDefinition("worker-flow", 1, node.node_id, (node, FlowNode("done", FlowNodeKind.END)))


def machine_habit(harness_profile, version=2, operations=None):
    baseline = PerformanceProfile("cohort-a", 100, 99, 99, 900.0, 5.0, 30.0)
    candidate = PerformanceProfile("cohort-a", 100, 99, 99, 850.0, 4.0, 28.0)
    return MachineHabit(
        "refresh-index", version,
        harness_profile.harness_id, harness_profile.version,
        harness_profile.environment_id, harness_profile.context_id,
        (StateCondition("task.kind", "refresh"),),
        (StateCondition("repo.present", "true"),),
        tuple(operations or (OperationStep("repo.test", OperationEffect.IDEMPOTENT),)),
        (StateCondition("index.ready", "true"),),
        baseline, candidate,
        EfficiencyGate(CostMetric.OPERATION_CALLS, min_samples=50, min_relative_gain=0.05),
        MachineHabitStatus.ACTIVE,
    )


class FlowWorkerTests(unittest.TestCase):
    def test_operation_node_invokes_harness_and_commits_outputs_and_cost(self):
        harness = StubHarness(profile(), {
            "repo.scan": [HarnessOperationResult(
                OperationOutcome.SUCCEEDED, (("scan.done", "yes"),), 12.5, 2.0, 0.01
            )]
        })
        node = FlowNode(
            "scan", FlowNodeKind.OPERATION, "repo.scan", "done",
            postconditions=(("scan.done", "yes"),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(simple_flow(node, "unused"), "worker-001", journal,
                                        {"repo": "A"})
            result = FlowWorker(harness).dispatch(flow)
            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(flow.snapshot.status, FlowStatus.SUCCEEDED)
            self.assertEqual(dict(flow.snapshot.context)["scan.done"], "yes")
            self.assertEqual(len(harness.calls), 1)
            event = journal.load("worker-001")[-1]
            meta = dict(event.payload)
            self.assertEqual(meta["$meta.operation_ref"], "repo.scan")
            self.assertEqual(meta["$meta.duration_ms"], "12.5")
            self.assertNotIn("$meta.duration_ms", flow.snapshot.context_dict())

    def test_idempotent_operation_retry_reuses_same_key(self):
        harness = StubHarness(profile(), {
            "repo.test": [
                HarnessOperationResult(OperationOutcome.FAILED, error_code="temporary"),
                HarnessOperationResult(OperationOutcome.SUCCEEDED, (("test.pass", "true"),)),
            ]
        })
        node = FlowNode(
            "test", FlowNodeKind.OPERATION, "repo.test", "done",
            max_attempts=2, effect=OperationEffect.IDEMPOTENT,
        )
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(simple_flow(node, "unused"), "worker-002",
                                        JsonlFlowJournal(tmp))
            worker = FlowWorker(harness)
            first = worker.dispatch(flow)
            self.assertEqual(first.status, DispatchStatus.ADVANCED)
            self.assertEqual(flow.snapshot.attempt_count("test"), 1)
            second = worker.dispatch(flow)
            self.assertEqual(second.status, DispatchStatus.TERMINAL)
            self.assertEqual(harness.calls[0][2], harness.calls[1][2])

    def test_unknown_outcome_routes_to_needs_attention(self):
        harness = StubHarness(profile(), {
            "repo.scan": [HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="lost-ack")]
        })
        node = FlowNode("scan", FlowNodeKind.OPERATION, "repo.scan", "done")
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(simple_flow(node, "unused"), "worker-003",
                                        JsonlFlowJournal(tmp))
            result = FlowWorker(harness).dispatch(flow)
            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(flow.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertEqual(len(harness.calls), 1)

    def test_adapter_exception_is_treated_as_uncertain_not_retried(self):
        harness = StubHarness(profile(), {"repo.scan": [TimeoutError("connection dropped")]})
        node = FlowNode("scan", FlowNodeKind.OPERATION, "repo.scan", "done",
                        max_attempts=3, effect=OperationEffect.IDEMPOTENT)
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(simple_flow(node, "unused"), "worker-004",
                                        JsonlFlowJournal(tmp))
            result = FlowWorker(harness).dispatch(flow)
            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(flow.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertEqual(len(harness.calls), 1)

    def test_approval_pauses_before_invocation_then_resumes(self):
        harness = StubHarness(profile(frozenset({"deploy.preview"})), {
            "deploy.preview": [HarnessOperationResult(OperationOutcome.SUCCEEDED)]
        })
        node = FlowNode("deploy", FlowNodeKind.OPERATION, "deploy.preview", "done",
                        effect=OperationEffect.NON_REPEATABLE)
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(simple_flow(node, "unused"), "worker-005",
                                        JsonlFlowJournal(tmp))
            paused = FlowWorker(harness).dispatch(flow)
            self.assertEqual(paused.status, DispatchStatus.PAUSED)
            self.assertEqual(harness.calls, [])
            flow.resume()
            completed = FlowWorker(harness, approved_operations=frozenset({"deploy.preview"})).dispatch(flow)
            self.assertEqual(completed.status, DispatchStatus.TERMINAL)
            self.assertEqual(flow.snapshot.status, FlowStatus.SUCCEEDED)

    def test_operation_postcondition_failure_persists_observed_output(self):
        harness = StubHarness(profile(), {
            "repo.scan": [HarnessOperationResult(
                OperationOutcome.SUCCEEDED, (("scan.done", "no"),)
            )]
        })
        node = FlowNode(
            "scan", FlowNodeKind.OPERATION, "repo.scan", "done",
            postconditions=(("scan.done", "yes"),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(simple_flow(node, "unused"), "worker-006",
                                        JsonlFlowJournal(tmp))
            FlowWorker(harness).dispatch(flow)
            self.assertEqual(flow.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertEqual(dict(flow.snapshot.context)["scan.done"], "no")
            metadata = dict(flow.journal.load("worker-006")[-1].payload)
            self.assertEqual(metadata["$meta.reason"], "postconditions_not_satisfied")

    def test_habit_node_uses_exact_registered_version_and_records_cost(self):
        harness_profile = profile()
        harness = StubHarness(harness_profile, {
            "repo.test": [HarnessOperationResult(
                OperationOutcome.SUCCEEDED, (("index.ready", "true"),), 31.0, 7.0, 0.02
            )]
        })
        habit = machine_habit(harness_profile, version=2)
        node = FlowNode(
            "refresh", FlowNodeKind.HABIT, "refresh-index", "done",
            target_version=2, postconditions=(("index.ready", "true"),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(
                simple_flow(node, "unused"), "worker-007", journal,
                {"task.kind": "refresh", "repo.present": "true"},
            )
            result = FlowWorker(harness, HabitRegistry((habit,))).dispatch(flow)
            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(flow.snapshot.status, FlowStatus.SUCCEEDED)
            self.assertEqual(dict(flow.snapshot.context)["index.ready"], "true")
            meta = dict(journal.load("worker-007")[-1].payload)
            self.assertEqual(meta["$meta.habit_version"], "2")
            self.assertEqual(meta["$meta.duration_ms"], "31.0")

    def test_missing_exact_habit_version_does_not_fall_back_to_latest(self):
        harness = StubHarness(profile())
        habit_v1 = machine_habit(harness.profile, version=1)
        node = FlowNode("refresh", FlowNodeKind.HABIT, "refresh-index", "done",
                        target_version=2)
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(
                simple_flow(node, "unused"), "worker-008", JsonlFlowJournal(tmp),
                {"task.kind": "refresh", "repo.present": "true"},
            )
            result = FlowWorker(harness, HabitRegistry((habit_v1,))).dispatch(flow)
            self.assertEqual(result.status, DispatchStatus.NEEDS_ATTENTION)
            self.assertEqual(flow.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertEqual(harness.calls, [])

    def test_inactive_habit_is_not_executed(self):
        harness = StubHarness(profile())
        inactive = machine_habit(harness.profile, version=2)
        inactive = MachineHabit(
            inactive.habit_id, inactive.version, inactive.harness_id, inactive.harness_version,
            inactive.environment_id, inactive.context_id, inactive.trigger, inactive.preconditions,
            inactive.operations, inactive.postconditions, inactive.baseline, inactive.candidate,
            inactive.efficiency_gate, MachineHabitStatus.QUARANTINED,
        )
        node = FlowNode("refresh", FlowNodeKind.HABIT, "refresh-index", "done", target_version=2)
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(
                simple_flow(node, "unused"), "worker-009", JsonlFlowJournal(tmp),
                {"task.kind": "refresh", "repo.present": "true"},
            )
            result = FlowWorker(harness, HabitRegistry((inactive,))).dispatch(flow)
            self.assertEqual(result.status, DispatchStatus.NEEDS_ATTENTION)
            self.assertEqual(harness.calls, [])

    def test_habit_node_pauses_before_any_operation_when_approval_is_missing(self):
        harness_profile = profile(frozenset({"deploy.preview"}))
        harness = StubHarness(harness_profile, {
            "repo.test": [HarnessOperationResult(OperationOutcome.SUCCEEDED)]
        })
        habit = machine_habit(
            harness_profile, version=2,
            operations=(
                OperationStep("repo.test", OperationEffect.IDEMPOTENT),
                OperationStep("deploy.preview", OperationEffect.NON_REPEATABLE),
            ),
        )
        node = FlowNode("refresh", FlowNodeKind.HABIT, "refresh-index", "done", target_version=2)
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(
                simple_flow(node, "unused"), "worker-010", JsonlFlowJournal(tmp),
                {"task.kind": "refresh", "repo.present": "true"},
            )
            result = FlowWorker(harness, HabitRegistry((habit,))).dispatch(flow)
            self.assertEqual(result.status, DispatchStatus.PAUSED)
            self.assertEqual(harness.calls, [])

    def test_branch_dispatch_is_deterministic_and_wait_node_stops_dispatch(self):
        definition = FlowDefinition(
            "branch-flow", 1, "branch",
            (
                FlowNode("branch", FlowNodeKind.BRANCH, branch_key="result",
                         branch_equals="ok", next_on_true="wait", next_on_false="done"),
                FlowNode("wait", FlowNodeKind.WAIT, next_on_success="done"),
                FlowNode("done", FlowNodeKind.END),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            flow = PersistentFlow.start(definition, "worker-011", JsonlFlowJournal(tmp),
                                        {"result": "ok"})
            worker = FlowWorker(StubHarness(profile()))
            resolved = worker.dispatch(flow)
            self.assertEqual(resolved.status, DispatchStatus.WAITING)
            waiting = worker.dispatch(flow)
            self.assertEqual(waiting.status, DispatchStatus.WAITING)
            flow.release_wait()
            terminal = worker.dispatch(flow)
            self.assertEqual(terminal.status, DispatchStatus.TERMINAL)


if __name__ == "__main__":
    unittest.main()
