import tempfile
import unittest
from dataclasses import replace

from habitroute.flows import (
    FlowDefinition,
    FlowEventKind,
    FlowNode,
    FlowNodeKind,
    FlowStatus,
    JsonlFlowJournal,
    PersistentFlow,
)
from habitroute.machine import (
    CostMetric,
    EfficiencyGate,
    HarnessOperationResult,
    HarnessProfile,
    MachineHabit,
    MachineHabitStatus,
    OperationEffect,
    OperationOutcome,
    OperationStep,
    PerformanceProfile,
    StateCondition,
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


def harness_profile():
    return HarnessProfile(
        "local-harness",
        "v3",
        "test-machine",
        "project-x",
        frozenset({"repo.scan", "repo.test"}),
        max_step_attempts=3,
    )


def two_operation_habit(profile):
    baseline = PerformanceProfile("matched", 100, 99, 99, 900.0, 5.0, 30.0)
    candidate = PerformanceProfile("matched", 100, 99, 99, 850.0, 4.0, 28.0)
    return MachineHabit(
        "refresh-index",
        2,
        profile.harness_id,
        profile.version,
        profile.environment_id,
        profile.context_id,
        (StateCondition("task.kind", "refresh"),),
        (StateCondition("repo.present", "true"),),
        (
            OperationStep("repo.scan", OperationEffect.READ_ONLY),
            OperationStep(
                "repo.test",
                OperationEffect.IDEMPOTENT,
                input_bindings=(("scan_result", "$state.scan.result"),),
            ),
        ),
        (StateCondition("index.ready", "true"),),
        baseline,
        candidate,
        EfficiencyGate(
            CostMetric.OPERATION_CALLS,
            min_samples=50,
            min_relative_gain=0.05,
        ),
        MachineHabitStatus.ACTIVE,
    )


def flow_definition():
    return FlowDefinition(
        "checkpoint-flow",
        1,
        "refresh",
        (
            FlowNode(
                "refresh",
                FlowNodeKind.HABIT,
                "refresh-index",
                "done",
                target_version=2,
                postconditions=(("index.ready", "true"),),
            ),
            FlowNode("done", FlowNodeKind.END),
        ),
    )


def initial_flow(journal, run_id):
    return PersistentFlow.start(
        flow_definition(),
        run_id,
        journal,
        {"task.kind": "refresh", "repo.present": "true"},
    )


class CrashAfterOperationEffectJournal(JsonlFlowJournal):
    """Simulates process loss after a provider effect, before result acknowledgement."""

    def __init__(self, root):
        super().__init__(root)
        self.injected = False

    def append(self, event):
        if (
            event.kind is FlowEventKind.HABIT_OPERATION_SUCCEEDED
            and not self.injected
        ):
            self.injected = True
            raise OSError("simulated process crash before operation acknowledgement")
        super().append(event)





class CrashBeforeSecondOperationIntentJournal(JsonlFlowJournal):
    """Stops the process before dispatching the second operation."""

    def append(self, event):
        payload = dict(event.payload)
        if (
            event.kind is FlowEventKind.HABIT_OPERATION_STARTED
            and payload.get("$meta.operation_index") == "1"
        ):
            raise OSError("simulated crash before second operation intent")
        super().append(event)


class HabitOperationCheckpointTests(unittest.TestCase):
    def test_each_operation_is_checkmarked_before_next_operation_runs(self):
        profile = harness_profile()
        harness = StubHarness(
            profile,
            {
                "repo.scan": [
                    HarnessOperationResult(
                        OperationOutcome.SUCCEEDED,
                        (("scan.result", "clean"),),
                        10.0,
                        1.0,
                    )
                ],
                "repo.test": [
                    HarnessOperationResult(
                        OperationOutcome.SUCCEEDED,
                        (("index.ready", "true"),),
                        12.0,
                        1.5,
                    )
                ],
            },
        )
        habit = two_operation_habit(profile)

        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = initial_flow(journal, "checkpoint-001")
            result = FlowWorker(harness, HabitRegistry((habit,))).dispatch(flow)

            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(flow.snapshot.status, FlowStatus.SUCCEEDED)
            self.assertEqual([call[0] for call in harness.calls], ["repo.scan", "repo.test"])

            events = journal.load("checkpoint-001")
            kinds = [event.kind for event in events]
            self.assertEqual(
                kinds,
                [
                    FlowEventKind.STARTED,
                    FlowEventKind.HABIT_OPERATION_STARTED,
                    FlowEventKind.HABIT_OPERATION_SUCCEEDED,
                    FlowEventKind.HABIT_OPERATION_STARTED,
                    FlowEventKind.HABIT_OPERATION_SUCCEEDED,
                    FlowEventKind.STEP_SUCCEEDED,
                ],
            )
            first_result = dict(events[2].payload)
            self.assertEqual(first_result["output.scan.result"], "clean")
            self.assertEqual(first_result["$meta.operation_index"], "0")
            second_start = dict(events[3].payload)
            self.assertEqual(second_start["$meta.operation_index"], "1")
            self.assertEqual(harness.calls[1][1]["scan_result"], "clean")

    def test_unacknowledged_operation_intent_is_not_replayed_after_restore(self):
        profile = harness_profile()
        harness = StubHarness(
            profile,
            {
                "repo.scan": [
                    HarnessOperationResult(
                        OperationOutcome.SUCCEEDED,
                        (("scan.result", "clean"),),
                    )
                ]
            },
        )
        habit = two_operation_habit(profile)

        with tempfile.TemporaryDirectory() as tmp:
            faulted_journal = CrashAfterOperationEffectJournal(tmp)
            flow = initial_flow(faulted_journal, "checkpoint-002")
            with self.assertRaisesRegex(OSError, "simulated process crash"):
                FlowWorker(harness, HabitRegistry((habit,))).dispatch(flow)

            self.assertEqual(len(harness.calls), 1)
            persisted = JsonlFlowJournal(tmp).load("checkpoint-002")
            self.assertEqual(persisted[-1].kind, FlowEventKind.HABIT_OPERATION_STARTED)

            restored = PersistentFlow.restore(
                flow_definition(),
                "checkpoint-002",
                JsonlFlowJournal(tmp),
            )
            result = FlowWorker(harness, HabitRegistry((habit,))).dispatch(restored)

            self.assertEqual(result.status, DispatchStatus.NEEDS_ATTENTION)
            self.assertEqual(restored.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertEqual(len(harness.calls), 1)
            self.assertEqual(
                restored.snapshot.pending_habit_operation.operation_ref,
                "repo.scan",
            )


    def test_known_failure_retries_with_same_idempotency_key_and_durable_attempt_count(self):
        profile = harness_profile()
        harness = StubHarness(
            profile,
            {
                "repo.scan": [
                    HarnessOperationResult(OperationOutcome.FAILED, error_code="temporary"),
                    HarnessOperationResult(
                        OperationOutcome.SUCCEEDED,
                        (("scan.result", "clean"),),
                    ),
                ],
                "repo.test": [
                    HarnessOperationResult(
                        OperationOutcome.SUCCEEDED,
                        (("index.ready", "true"),),
                    )
                ],
            },
        )
        base = two_operation_habit(profile)
        habit = replace(
            base,
            operations=(
                OperationStep("repo.scan", OperationEffect.IDEMPOTENT, max_attempts=2),
                base.operations[1],
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = initial_flow(journal, "checkpoint-003")
            result = FlowWorker(harness, HabitRegistry((habit,))).dispatch(flow)

            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            scan_calls = [call for call in harness.calls if call[0] == "repo.scan"]
            self.assertEqual(len(scan_calls), 2)
            self.assertEqual(scan_calls[0][2], scan_calls[1][2])

            events = journal.load("checkpoint-003")
            operation_events = [
                event for event in events
                if event.kind in (
                    FlowEventKind.HABIT_OPERATION_STARTED,
                    FlowEventKind.HABIT_OPERATION_FAILED,
                    FlowEventKind.HABIT_OPERATION_SUCCEEDED,
                )
            ]
            self.assertEqual(
                [event.kind for event in operation_events[:4]],
                [
                    FlowEventKind.HABIT_OPERATION_STARTED,
                    FlowEventKind.HABIT_OPERATION_FAILED,
                    FlowEventKind.HABIT_OPERATION_STARTED,
                    FlowEventKind.HABIT_OPERATION_SUCCEEDED,
                ],
            )
            self.assertEqual(
                dict(operation_events[0].payload)["$meta.attempt"], "1"
            )
            self.assertEqual(
                dict(operation_events[2].payload)["$meta.attempt"], "2"
            )

    def test_restore_after_committed_operation_resumes_at_next_index(self):
        profile = harness_profile()
        harness = StubHarness(
            profile,
            {
                "repo.scan": [
                    HarnessOperationResult(
                        OperationOutcome.SUCCEEDED,
                        (("scan.result", "clean"),),
                    )
                ],
                "repo.test": [
                    HarnessOperationResult(
                        OperationOutcome.SUCCEEDED,
                        (("index.ready", "true"),),
                    )
                ],
            },
        )
        habit = two_operation_habit(profile)

        with tempfile.TemporaryDirectory() as tmp:
            faulted_journal = CrashBeforeSecondOperationIntentJournal(tmp)
            flow = initial_flow(faulted_journal, "checkpoint-004")
            with self.assertRaisesRegex(OSError, "before second operation intent"):
                FlowWorker(harness, HabitRegistry((habit,))).dispatch(flow)

            restored = PersistentFlow.restore(
                flow_definition(),
                "checkpoint-004",
                JsonlFlowJournal(tmp),
            )
            self.assertEqual(restored.snapshot.habit_operation_index, 1)
            self.assertIsNone(restored.snapshot.pending_habit_operation)
            self.assertEqual(dict(restored.snapshot.context)["scan.result"], "clean")

            result = FlowWorker(harness, HabitRegistry((habit,))).dispatch(restored)
            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(
                [call[0] for call in harness.calls],
                ["repo.scan", "repo.test"],
            )


if __name__ == "__main__":
    unittest.main()
