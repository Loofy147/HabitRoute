from __future__ import annotations

import tempfile
import unittest

from habitroute.flows import (
    FlowDefinition, FlowEventKind, FlowNode, FlowNodeKind, FlowStatus,
    JsonlFlowJournal, PersistentFlow,
)
from habitroute.machine import (
    CostMetric, EfficiencyGate, HarnessOperationResult, HarnessProfile,
    MachineHabit, MachineHabitStatus, OperationEffect, OperationOutcome,
    OperationStep, PerformanceProfile, StateCondition,
)
from habitroute.worker import DispatchStatus, FlowWorker, HabitRegistry


class SimulatedProcessCrash(BaseException):
    """Bypass application exception handling to model abrupt worker termination."""


class CrashHarness:
    def __init__(self, profile: HarnessProfile, crash_operation: str) -> None:
        self.profile = profile
        self.crash_operation = crash_operation
        self.crashed = False
        self.calls: list[tuple[str, str]] = []
        self.external_effects: dict[str, int] = {}
        self.deduplicated_results: dict[str, HarnessOperationResult] = {}

    def invoke(self, operation, inputs, *, idempotency_key):
        self.calls.append((operation.operation_ref, idempotency_key))
        if operation.effect is OperationEffect.DEDUPLICATED:
            if idempotency_key in self.deduplicated_results:
                return self.deduplicated_results[idempotency_key]

        if operation.effect is not OperationEffect.READ_ONLY:
            self.external_effects[operation.operation_ref] = (
                self.external_effects.get(operation.operation_ref, 0) + 1
            )

        outputs = ()
        if operation.operation_ref == "deploy.publish":
            outputs = (("release.published", "true"),)
        result = HarnessOperationResult(OperationOutcome.SUCCEEDED, outputs)

        if operation.effect is OperationEffect.DEDUPLICATED:
            # The provider has durably recorded the result against the key before
            # the client receives its acknowledgement.
            self.deduplicated_results[idempotency_key] = result

        if operation.operation_ref == self.crash_operation and not self.crashed:
            self.crashed = True
            raise SimulatedProcessCrash(
                "process terminated after provider effect, before journal acknowledgement"
            )
        return result


class FailIntentJournal(JsonlFlowJournal):
    def append(self, event):
        if event.kind is FlowEventKind.OPERATION_INTENT:
            raise OSError("simulated disk/fsync failure before operation invocation")
        super().append(event)


class FailOperationResultJournal(JsonlFlowJournal):
    def append(self, event):
        if event.kind is FlowEventKind.OPERATION_SUCCEEDED:
            raise OSError("simulated result checkpoint failure after provider acknowledgement")
        super().append(event)


def make_profile() -> HarnessProfile:
    return HarnessProfile(
        "fault-injection-harness", "1", "ci-linux", "repository-x",
        frozenset({"deploy.publish", "repo.prepare", "orders.submit"}),
    )


def make_habit(profile: HarnessProfile) -> MachineHabit:
    baseline = PerformanceProfile("fault-cohort", 100, 100, 100, 100.0, 3.0, 10.0)
    candidate = PerformanceProfile("fault-cohort", 100, 100, 100, 90.0, 2.0, 9.0)
    return MachineHabit(
        habit_id="publish-after-prepare", version=1,
        harness_id=profile.harness_id, harness_version=profile.version,
        environment_id=profile.environment_id, context_id=profile.context_id,
        trigger=(StateCondition("task.kind", "release"),),
        preconditions=(StateCondition("branch.clean", "true"),),
        operations=(
            OperationStep("repo.prepare", OperationEffect.READ_ONLY),
            OperationStep("deploy.publish", OperationEffect.NON_REPEATABLE),
        ),
        postconditions=(StateCondition("release.published", "true"),),
        baseline=baseline, candidate=candidate,
        efficiency_gate=EfficiencyGate(
            CostMetric.OPERATION_CALLS, min_samples=20, min_relative_gain=0.1
        ),
        lifecycle=MachineHabitStatus.ACTIVE,
    )


class DurableOperationCheckpointTests(unittest.TestCase):
    def test_nonrepeatable_operation_is_not_reissued_after_crash_and_can_be_reconciled(self):
        profile = make_profile()
        harness = CrashHarness(profile, "deploy.publish")
        node = FlowNode(
            "publish", FlowNodeKind.OPERATION, "deploy.publish", "done",
            max_attempts=1, effect=OperationEffect.NON_REPEATABLE,
            postconditions=(("release.published", "true"),),
        )
        definition = FlowDefinition(
            "single-operation-crash", 1, "publish",
            (node, FlowNode("done", FlowNodeKind.END)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(definition, "crash-op-001", journal)
            with self.assertRaises(SimulatedProcessCrash):
                FlowWorker(harness).dispatch(flow)

            events = journal.load("crash-op-001")
            self.assertEqual(
                [event.kind for event in events],
                [FlowEventKind.STARTED, FlowEventKind.OPERATION_INTENT],
            )
            self.assertEqual(events[-1].payload and dict(events[-1].payload)["$op.idempotency_key"],
                             flow.snapshot.pending_operation.idempotency_key)

            restored = PersistentFlow.restore(
                definition, "crash-op-001", JsonlFlowJournal(tmp)
            )
            blocked = FlowWorker(harness).dispatch(restored)
            self.assertEqual(blocked.status, DispatchStatus.NEEDS_ATTENTION)
            self.assertEqual(restored.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertIsNotNone(restored.snapshot.pending_operation)
            self.assertEqual(harness.external_effects["deploy.publish"], 1)
            self.assertEqual(len(harness.calls), 1)

            # Reconciliation records evidence that the provider effect did occur.
            restored.reconcile_pending_operation(
                applied=True,
                evidence_ref="provider:release-123",
                reconciled_by="operator:verified",
                outputs={"release.published": "true"},
            )
            completed = FlowWorker(harness).dispatch(restored)
            self.assertEqual(completed.status, DispatchStatus.TERMINAL)
            self.assertEqual(restored.snapshot.status, FlowStatus.SUCCEEDED)
            self.assertEqual(harness.external_effects["deploy.publish"], 1)
            self.assertEqual(len(harness.calls), 1)
            final_events = JsonlFlowJournal(tmp).load("crash-op-001")
            self.assertEqual(final_events[-2].kind, FlowEventKind.OPERATION_RECONCILED)

    def test_multi_operation_habit_resumes_from_completed_prefix_after_reconciliation(self):
        profile = make_profile()
        harness = CrashHarness(profile, "deploy.publish")
        habit = make_habit(profile)
        definition = FlowDefinition(
            "multi-operation-crash", 1, "habit",
            (
                FlowNode(
                    "habit", FlowNodeKind.HABIT, "publish-after-prepare", "done",
                    target_version=1,
                ),
                FlowNode("done", FlowNodeKind.END),
            ),
        )
        initial_context = {"task.kind": "release", "branch.clean": "true"}
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(
                definition, "crash-habit-001", journal, initial_context
            )
            registry = HabitRegistry((habit,))
            worker = FlowWorker(harness, registry)
            with self.assertRaises(SimulatedProcessCrash):
                worker.dispatch(flow)

            events = journal.load("crash-habit-001")
            self.assertEqual(
                [event.kind for event in events],
                [
                    FlowEventKind.STARTED,
                    FlowEventKind.OPERATION_INTENT,
                    FlowEventKind.OPERATION_SUCCEEDED,
                    FlowEventKind.OPERATION_INTENT,
                ],
            )
            restored = PersistentFlow.restore(
                definition, "crash-habit-001", JsonlFlowJournal(tmp)
            )
            blocked = FlowWorker(harness, registry).dispatch(restored)
            self.assertEqual(blocked.status, DispatchStatus.NEEDS_ATTENTION)
            self.assertEqual(len(restored.snapshot.completed_operations), 1)
            self.assertEqual(restored.snapshot.completed_operations[0].operation_ref,
                             "repo.prepare")
            self.assertEqual(harness.external_effects["deploy.publish"], 1)
            self.assertEqual(
                [operation_ref for operation_ref, _ in harness.calls],
                ["repo.prepare", "deploy.publish"],
            )

            restored.reconcile_pending_operation(
                applied=True,
                evidence_ref="provider:release-456",
                reconciled_by="operator:verified",
                outputs={"release.published": "true"},
            )
            self.assertEqual(restored.snapshot.status, FlowStatus.RUNNING)
            self.assertIsNone(restored.snapshot.pending_operation)
            self.assertEqual(dict(restored.snapshot.context).get("release.published"), "true")
            finished = FlowWorker(harness, registry).dispatch(restored)
            self.assertEqual(
                finished.status, DispatchStatus.TERMINAL,
                f"reason={finished.reason}; state={dict(restored.snapshot.context)}; "
                f"completed={restored.snapshot.completed_operations}",
            )
            self.assertEqual(restored.snapshot.status, FlowStatus.SUCCEEDED)
            # Both operations are already checkpointed; neither is replayed.
            self.assertEqual(
                [operation_ref for operation_ref, _ in harness.calls],
                ["repo.prepare", "deploy.publish"],
            )
            self.assertEqual(harness.external_effects["deploy.publish"], 1)

    def test_provider_deduplicated_operation_retries_pending_intent_with_same_key(self):
        profile = make_profile()
        harness = CrashHarness(profile, "orders.submit")
        node = FlowNode(
            "submit", FlowNodeKind.OPERATION, "orders.submit", "done",
            max_attempts=2, effect=OperationEffect.DEDUPLICATED,
            idempotency_key_supported=True,
        )
        definition = FlowDefinition(
            "deduplicated-operation-crash", 1, "submit",
            (node, FlowNode("done", FlowNodeKind.END)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(definition, "dedupe-001", journal)
            with self.assertRaises(SimulatedProcessCrash):
                FlowWorker(harness).dispatch(flow)
            first_key = harness.calls[0][1]

            restored = PersistentFlow.restore(
                definition, "dedupe-001", JsonlFlowJournal(tmp)
            )
            result = FlowWorker(harness).dispatch(restored)
            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(restored.snapshot.status, FlowStatus.SUCCEEDED)
            self.assertEqual(len(harness.calls), 2)
            self.assertEqual(harness.calls[0][1], first_key)
            self.assertEqual(harness.calls[1][1], first_key)
            # The simulated provider applied the side effect only once.
            self.assertEqual(harness.external_effects["orders.submit"], 1)

    def test_intent_journal_failure_prevents_provider_invocation(self):
        profile = make_profile()
        harness = CrashHarness(profile, "deploy.publish")
        node = FlowNode(
            "publish", FlowNodeKind.OPERATION, "deploy.publish", "done",
            effect=OperationEffect.NON_REPEATABLE,
        )
        definition = FlowDefinition(
            "intent-write-failure", 1, "publish",
            (node, FlowNode("done", FlowNodeKind.END)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal = FailIntentJournal(tmp)
            flow = PersistentFlow.start(definition, "intent-fail-001", journal)
            with self.assertRaisesRegex(OSError, "fsync failure"):
                FlowWorker(harness).dispatch(flow)
            self.assertEqual(harness.calls, [])
            self.assertEqual(harness.external_effects, {})
            self.assertEqual(
                [event.kind for event in JsonlFlowJournal(tmp).load("intent-fail-001")],
                [FlowEventKind.STARTED],
            )

    def test_result_checkpoint_failure_keeps_nonrepeatable_intent_for_reconciliation(self):
        profile = make_profile()
        harness = CrashHarness(profile, "no-crash")
        node = FlowNode(
            "publish", FlowNodeKind.OPERATION, "deploy.publish", "done",
            effect=OperationEffect.NON_REPEATABLE,
        )
        definition = FlowDefinition(
            "result-write-failure", 1, "publish",
            (node, FlowNode("done", FlowNodeKind.END)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal = FailOperationResultJournal(tmp)
            flow = PersistentFlow.start(definition, "result-fail-001", journal)
            with self.assertRaisesRegex(OSError, "result checkpoint failure"):
                FlowWorker(harness).dispatch(flow)
            self.assertEqual(harness.external_effects["deploy.publish"], 1)
            self.assertIsNotNone(flow.snapshot.pending_operation)
            restored = PersistentFlow.restore(
                definition, "result-fail-001", JsonlFlowJournal(tmp)
            )
            blocked = FlowWorker(harness).dispatch(restored)
            self.assertEqual(blocked.status, DispatchStatus.NEEDS_ATTENTION)
            self.assertEqual(harness.external_effects["deploy.publish"], 1)
            restored.reconcile_pending_operation(
                applied=True,
                evidence_ref="provider:release-789",
                reconciled_by="operator:verified",
                outputs={"release.published": "true"},
            )
            finished = FlowWorker(harness).dispatch(restored)
            self.assertEqual(finished.status, DispatchStatus.TERMINAL)
            self.assertEqual(harness.external_effects["deploy.publish"], 1)

    def test_reconciliation_that_confirms_not_applied_does_not_auto_retry(self):
        profile = make_profile()
        harness = CrashHarness(profile, "deploy.publish")
        node = FlowNode(
            "publish", FlowNodeKind.OPERATION, "deploy.publish", "done",
            effect=OperationEffect.NON_REPEATABLE,
        )
        definition = FlowDefinition(
            "not-applied-reconciliation", 1, "publish",
            (node, FlowNode("done", FlowNodeKind.END)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            journal = JsonlFlowJournal(tmp)
            flow = PersistentFlow.start(definition, "not-applied-001", journal)
            with self.assertRaises(SimulatedProcessCrash):
                FlowWorker(harness).dispatch(flow)
            restored = PersistentFlow.restore(
                definition, "not-applied-001", JsonlFlowJournal(tmp)
            )
            FlowWorker(harness).dispatch(restored)
            restored.reconcile_pending_operation(
                applied=False,
                evidence_ref="provider:lookup-no-record",
                reconciled_by="operator:verified",
            )
            self.assertEqual(restored.snapshot.status, FlowStatus.NEEDS_ATTENTION)
            self.assertIsNone(restored.snapshot.pending_operation)
            result = FlowWorker(harness).dispatch(restored)
            self.assertEqual(result.status, DispatchStatus.TERMINAL)
            self.assertEqual(len(harness.calls), 1)
            self.assertEqual(harness.external_effects["deploy.publish"], 1)


if __name__ == "__main__":
    unittest.main()
