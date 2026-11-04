import unittest
from dataclasses import replace

from habitroute.machine import (
    CostMetric, EfficiencyGate, HarnessProfile, MachineHabit, MachineHabitStatus,
    OperationEffect, OperationStep, PerformanceProfile, StateCondition,
    authorize_machine_habit,
)


class MachineHabitTests(unittest.TestCase):
    def setUp(self):
        self.harness = HarnessProfile(
            "shell-harness", "3", "linux-ci", "repo-a",
            frozenset({"git.status", "git.diff", "git.test", "deploy.preview"}),
            frozenset({"deploy.preview"}), max_step_attempts=3, supports_compensation=True,
        )
        self.baseline = PerformanceProfile(
            "cohort-2026-01", 100, 99, 99, 1000.0, 6.0, 50.0, 2.0,
        )
        self.candidate = PerformanceProfile(
            "cohort-2026-01", 100, 99, 99, 800.0, 4.0, 44.0, 1.5,
        )
        self.habit = MachineHabit(
            habit_id="compact-check-flow", version=2,
            harness_id="shell-harness", harness_version="3",
            environment_id="linux-ci", context_id="repo-a",
            trigger=(StateCondition("task.kind", "review"),),
            preconditions=(StateCondition("branch.clean", "true"),),
            operations=(
                OperationStep("git.status", OperationEffect.READ_ONLY),
                OperationStep("git.diff", OperationEffect.READ_ONLY),
                OperationStep("git.test", OperationEffect.IDEMPOTENT, max_attempts=2),
            ),
            postconditions=(StateCondition("checks.pass", "true"),),
            baseline=self.baseline, candidate=self.candidate,
            efficiency_gate=EfficiencyGate(CostMetric.OPERATION_CALLS, 50, 0.05),
            lifecycle=MachineHabitStatus.ACTIVE,
        )
        self.state = {"task.kind": "review", "branch.clean": "true"}

    def test_authorizes_verified_more_efficient_habit(self):
        decision = authorize_machine_habit(self.habit, self.harness, self.state)
        self.assertTrue(decision.eligible)
        self.assertGreater(decision.relative_gain, 0.30)

    def test_rejects_harness_version_mismatch(self):
        other = HarnessProfile(
            "shell-harness", "4", "linux-ci", "repo-a",
            self.harness.allowed_operations,
        )
        d = authorize_machine_habit(self.habit, other, self.state)
        self.assertEqual(d.reason, "harness_version_mismatch")

    def test_rejects_environment_scope_mismatch(self):
        other = HarnessProfile(
            "shell-harness", "3", "windows", "repo-a",
            self.harness.allowed_operations,
        )
        d = authorize_machine_habit(self.habit, other, self.state)
        self.assertEqual(d.reason, "environment_scope_mismatch")

    def test_rejects_trigger_mismatch(self):
        d = authorize_machine_habit(self.habit, self.harness, {"task.kind": "deploy"})
        self.assertEqual(d.reason, "trigger_not_matched")

    def test_rejects_failed_precondition(self):
        d = authorize_machine_habit(
            self.habit, self.harness,
            {"task.kind": "review", "branch.clean": "false"},
        )
        self.assertEqual(d.reason, "precondition_not_satisfied")

    def test_rejects_operation_outside_harness_allowlist(self):
        bad = replace(self.habit, operations=(OperationStep("shell.rm-root"),))
        d = authorize_machine_habit(bad, self.harness, self.state)
        self.assertFalse(d.eligible)
        self.assertEqual(d.reason, "operation_not_allowed")

    def test_requires_approval_for_protected_operation(self):
        habit = MachineHabit(
            self.habit.habit_id, self.habit.version, self.habit.harness_id,
            self.habit.harness_version, self.habit.environment_id, self.habit.context_id,
            self.habit.trigger, self.habit.preconditions,
            (OperationStep("deploy.preview", OperationEffect.NON_REPEATABLE),),
            self.habit.postconditions, self.baseline, self.candidate,
            self.habit.efficiency_gate, MachineHabitStatus.ACTIVE,
        )
        no = authorize_machine_habit(habit, self.harness, self.state)
        yes = authorize_machine_habit(habit, self.harness, self.state, frozenset({"deploy.preview"}))
        self.assertFalse(no.eligible)
        self.assertTrue(no.requires_approval)
        self.assertTrue(yes.eligible)

    def test_rejects_non_repeatable_operation_with_automatic_retry(self):
        with self.assertRaises(ValueError):
            OperationStep("payment.charge", OperationEffect.NON_REPEATABLE, max_attempts=2)

    def test_deduplicated_operation_requires_idempotency_key_support(self):
        with self.assertRaises(ValueError):
            OperationStep("order.create", OperationEffect.DEDUPLICATED, max_attempts=2)

    def test_compensatable_operation_requires_compensation_reference(self):
        with self.assertRaises(ValueError):
            OperationStep("inventory.reserve", OperationEffect.COMPENSATABLE, max_attempts=2)

    def test_rejects_when_success_reliability_regresses(self):
        worse = PerformanceProfile("cohort-2026-01", 100, 92, 99, 700.0, 3.0, 40.0)
        habit = MachineHabit(
            self.habit.habit_id, self.habit.version, self.habit.harness_id,
            self.habit.harness_version, self.habit.environment_id, self.habit.context_id,
            self.habit.trigger, self.habit.preconditions, self.habit.operations,
            self.habit.postconditions, self.baseline, worse,
            EfficiencyGate(CostMetric.OPERATION_CALLS, 50, 0.05),
            MachineHabitStatus.ACTIVE,
        )
        self.assertEqual(habit.efficiency.reason, "success_reliability_regressed")
        self.assertFalse(authorize_machine_habit(habit, self.harness, self.state).eligible)

    def test_rejects_when_postcondition_reliability_regresses(self):
        worse = PerformanceProfile("cohort-2026-01", 100, 99, 90, 700.0, 3.0, 40.0)
        habit = MachineHabit(
            self.habit.habit_id, self.habit.version, self.habit.harness_id,
            self.habit.harness_version, self.habit.environment_id, self.habit.context_id,
            self.habit.trigger, self.habit.preconditions, self.habit.operations,
            self.habit.postconditions, self.baseline, worse,
            EfficiencyGate(CostMetric.OPERATION_CALLS, 50, 0.05),
            MachineHabitStatus.ACTIVE,
        )
        self.assertEqual(habit.efficiency.reason, "postcondition_reliability_regressed")

    def test_rejects_incomparable_cohorts(self):
        other = PerformanceProfile("cohort-other", 100, 99, 99, 700.0, 3.0, 40.0)
        gate = EfficiencyGate(CostMetric.OPERATION_CALLS, 50, 0.05)
        self.assertEqual(gate.evaluate(self.baseline, other).reason, "cohort_mismatch")

    def test_rejects_insufficient_samples(self):
        small = PerformanceProfile("cohort-2026-01", 5, 5, 5, 1000.0, 6.0, 50.0)
        gate = EfficiencyGate(CostMetric.OPERATION_CALLS, 20, 0.05)
        self.assertEqual(gate.evaluate(small, small).reason, "insufficient_samples")

    def test_rejects_without_declared_efficiency_gain(self):
        same = PerformanceProfile("cohort-2026-01", 100, 99, 99, 1000.0, 6.0, 50.0)
        gate = EfficiencyGate(CostMetric.OPERATION_CALLS, 50, 0.05)
        self.assertEqual(gate.evaluate(self.baseline, same).reason, "efficiency_gain_below_threshold")

    def test_rejects_quarantined_habit(self):
        habit = MachineHabit(
            self.habit.habit_id, self.habit.version, self.habit.harness_id,
            self.habit.harness_version, self.habit.environment_id, self.habit.context_id,
            self.habit.trigger, self.habit.preconditions, self.habit.operations,
            self.habit.postconditions, self.baseline, self.candidate,
            self.habit.efficiency_gate, MachineHabitStatus.QUARANTINED,
        )
        self.assertEqual(authorize_machine_habit(habit, self.harness, self.state).reason,
                         "habit_not_active")


if __name__ == "__main__":
    unittest.main()
