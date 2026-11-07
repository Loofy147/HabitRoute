from __future__ import annotations

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
from habitroute.worker import FlowWorker, HabitRegistry


class SimulatedProcessCrash(BaseException):
    """Bypass application exception handling to model abrupt worker termination."""


class CrashHarness:
    def __init__(self, profile: HarnessProfile, crash_operation: str) -> None:
        self.profile = profile
        self.crash_operation = crash_operation
        self.crashed = False
        self.calls: list[tuple[str, str]] = []
        self.external_effects: dict[str, int] = {}

    def invoke(self, operation, inputs, *, idempotency_key):
        self.calls.append((operation.operation_ref, idempotency_key))
        if operation.effect is not OperationEffect.READ_ONLY:
            self.external_effects[operation.operation_ref] = (
                self.external_effects.get(operation.operation_ref, 0) + 1
            )
        if operation.operation_ref == self.crash_operation and not self.crashed:
            self.crashed = True
            # The external effect already happened; the worker never received its result.
            raise SimulatedProcessCrash("process terminated after provider effect, before journal acknowledgement")
        outputs = ()
        if operation.operation_ref == "deploy.publish":
            outputs = (("release.published", "true"),)
        return HarnessOperationResult(OperationOutcome.SUCCEEDED, outputs)


def make_profile() -> HarnessProfile:
    return HarnessProfile(
        "fault-injection-harness", "1", "ci-linux", "repository-x",
        frozenset({"deploy.publish", "repo.prepare"}),
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


class CrashWindowCharacterizationTests(unittest.TestCase):
    """These tests intentionally reproduce known defects; they do not close them."""

    def test_nonrepeatable_flow_operation_can_repeat_after_crash_before_ack(self):
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

            # No operation intent/result was committed before the external effect.
            self.assertEqual([event.kind.value for event in journal.load("crash-op-001")], ["started"])
            restored = PersistentFlow.restore(definition, "crash-op-001", JsonlFlowJournal(tmp))
            self.assertEqual(restored.snapshot.status, FlowStatus.RUNNING)
            self.assertEqual(restored.current_node.node_id, "publish")

            # The recovered worker cannot distinguish "never invoked" from "effect happened".
            FlowWorker(harness).dispatch(restored)
            self.assertEqual(harness.external_effects["deploy.publish"], 2)
            self.assertEqual(harness.calls[0][1], harness.calls[1][1])

    def test_multi_operation_habit_replays_completed_prefix_after_later_crash(self):
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

            # The flow journal contains no per-operation progress from the habit.
            self.assertEqual(
                [event.kind.value for event in journal.load("crash-habit-001")],
                ["started"],
            )
            restored = PersistentFlow.restore(
                definition, "crash-habit-001", JsonlFlowJournal(tmp)
            )
            FlowWorker(harness, registry).dispatch(restored)

            refs = [operation_ref for operation_ref, _ in harness.calls]
            self.assertEqual(
                refs,
                ["repo.prepare", "deploy.publish", "repo.prepare", "deploy.publish"],
            )
            self.assertEqual(harness.external_effects["deploy.publish"], 2)
            self.assertEqual(harness.calls[1][1], harness.calls[3][1])
            self.assertEqual(restored.snapshot.status, FlowStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
