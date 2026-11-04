"""Canonical machine-habit contracts.

Machine habits are reusable operation-pattern optimizations. They are not
reinforcement-learning skills or human-behavior models.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Mapping, Protocol


class OperationEffect(str, Enum):
    READ_ONLY = "read_only"
    IDEMPOTENT = "idempotent"
    DEDUPLICATED = "deduplicated"
    COMPENSATABLE = "compensatable"
    NON_REPEATABLE = "non_repeatable"


class MachineHabitStatus(str, Enum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    ACTIVE = "active"
    AT_RISK = "at_risk"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class CostMetric(str, Enum):
    LATENCY_MS = "latency_ms"
    OPERATION_CALLS = "operation_calls"
    RESOURCE_UNITS = "resource_units"
    RECOVERY_COST = "recovery_cost"


@dataclass(frozen=True, slots=True)
class StateCondition:
    key: str
    expected: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("condition key must be non-empty")

    def matches(self, values: Mapping[str, str]) -> bool:
        return values.get(self.key) == self.expected


@dataclass(frozen=True, slots=True)
class OperationStep:
    operation_ref: str
    effect: OperationEffect = OperationEffect.READ_ONLY
    max_attempts: int = 1
    input_bindings: tuple[tuple[str, str], ...] = ()
    idempotency_key_supported: bool = False
    compensation_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_bindings", tuple(sorted(self.input_bindings)))
        if not self.operation_ref.strip():
            raise ValueError("operation_ref must be non-empty")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        keys = [key for key, _ in self.input_bindings]
        if any(not key.strip() for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("operation input bindings must have unique non-empty keys")
        if self.effect is OperationEffect.NON_REPEATABLE and self.max_attempts > 1:
            raise ValueError("non-repeatable operations cannot have automatic retries")
        if self.effect is OperationEffect.DEDUPLICATED and not self.idempotency_key_supported:
            raise ValueError("deduplicated operations require idempotency-key support")
        if self.effect is OperationEffect.COMPENSATABLE and not (
            self.compensation_ref and self.compensation_ref.strip()
        ):
            raise ValueError("compensatable operations require a compensation_ref")


@dataclass(frozen=True, slots=True)
class HarnessProfile:
    harness_id: str
    version: str
    environment_id: str
    context_id: str
    allowed_operations: frozenset[str]
    approval_required: frozenset[str] = frozenset()
    max_step_attempts: int = 3
    supports_compensation: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_operations", frozenset(self.allowed_operations))
        object.__setattr__(self, "approval_required", frozenset(self.approval_required))
        for name in ("harness_id", "version", "environment_id", "context_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if not self.allowed_operations:
            raise ValueError("harness must allow at least one operation")
        if not self.approval_required.issubset(self.allowed_operations):
            raise ValueError("approval-required operations must be in the allowlist")
        if self.max_step_attempts < 1:
            raise ValueError("max_step_attempts must be at least one")


class OperationOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HarnessOperationResult:
    outcome: OperationOutcome
    outputs: tuple[tuple[str, str], ...] = ()
    duration_ms: float = 0.0
    resource_units: float = 0.0
    external_cost: float = 0.0
    error_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", tuple(sorted(self.outputs)))
        for name in ("duration_ms", "resource_units", "external_cost"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        keys = [key for key, _ in self.outputs]
        if any(not key.strip() for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("harness outputs must have unique non-empty keys")


class HarnessAdapter(Protocol):
    """Provider-neutral boundary for one actual machine operation."""

    @property
    def profile(self) -> HarnessProfile: ...

    def invoke(
        self,
        operation: OperationStep,
        inputs: Mapping[str, str],
        *,
        idempotency_key: str,
    ) -> HarnessOperationResult: ...


@dataclass(frozen=True, slots=True)
class PerformanceProfile:
    cohort_id: str
    samples: int
    successes: int
    contract_passes: int
    mean_latency_ms: float
    mean_operation_calls: float
    mean_resource_units: float
    mean_recovery_cost: float = 0.0

    def __post_init__(self) -> None:
        if not self.cohort_id.strip():
            raise ValueError("cohort_id must be non-empty")
        if self.samples < 1 or not 0 <= self.successes <= self.samples:
            raise ValueError("invalid sample/success counts")
        if not 0 <= self.contract_passes <= self.samples:
            raise ValueError("invalid contract_passes count")
        for name in ("mean_latency_ms", "mean_operation_calls",
                     "mean_resource_units", "mean_recovery_cost"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

    def metric(self, metric: CostMetric) -> float:
        return {
            CostMetric.LATENCY_MS: self.mean_latency_ms,
            CostMetric.OPERATION_CALLS: self.mean_operation_calls,
            CostMetric.RESOURCE_UNITS: self.mean_resource_units,
            CostMetric.RECOVERY_COST: self.mean_recovery_cost,
        }[metric]


def wilson_lower_bound(successes: int, samples: int, z: float = 1.96) -> float:
    if samples <= 0:
        return 0.0
    if not 0 <= successes <= samples or not math.isfinite(z) or z <= 0:
        raise ValueError("invalid Wilson interval inputs")
    n = float(samples)
    p = successes / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    radius = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return max(0.0, (centre - radius) / denominator)


@dataclass(frozen=True, slots=True)
class EfficiencyGate:
    metric: CostMetric
    min_samples: int = 20
    min_relative_gain: float = 0.05
    max_success_lcb_drop: float = 0.01
    max_contract_lcb_drop: float = 0.0
    z_value: float = 1.96

    def __post_init__(self) -> None:
        if self.min_samples < 1:
            raise ValueError("min_samples must be positive")
        for name in ("min_relative_gain", "max_success_lcb_drop", "max_contract_lcb_drop"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if not math.isfinite(self.z_value) or self.z_value <= 0:
            raise ValueError("z_value must be positive")

    def evaluate(
        self, baseline: PerformanceProfile, candidate: PerformanceProfile
    ) -> "EfficiencyDecision":
        if baseline.cohort_id != candidate.cohort_id:
            return EfficiencyDecision(False, "cohort_mismatch")
        if baseline.samples != candidate.samples:
            return EfficiencyDecision(False, "sample_count_mismatch")
        if baseline.samples < self.min_samples:
            return EfficiencyDecision(False, "insufficient_samples")
        baseline_success = wilson_lower_bound(baseline.successes, baseline.samples, self.z_value)
        candidate_success = wilson_lower_bound(candidate.successes, candidate.samples, self.z_value)
        baseline_contract = wilson_lower_bound(baseline.contract_passes, baseline.samples, self.z_value)
        candidate_contract = wilson_lower_bound(candidate.contract_passes, candidate.samples, self.z_value)
        if candidate_success < baseline_success - self.max_success_lcb_drop:
            return EfficiencyDecision(
                False, "success_reliability_regressed", 0.0,
                baseline_success, candidate_success, baseline_contract, candidate_contract,
            )
        if candidate_contract < baseline_contract - self.max_contract_lcb_drop:
            return EfficiencyDecision(
                False, "postcondition_reliability_regressed", 0.0,
                baseline_success, candidate_success, baseline_contract, candidate_contract,
            )
        old_cost = baseline.metric(self.metric)
        new_cost = candidate.metric(self.metric)
        if old_cost <= 0.0:
            return EfficiencyDecision(
                False, "baseline_cost_not_positive", 0.0,
                baseline_success, candidate_success, baseline_contract, candidate_contract,
            )
        gain = (old_cost - new_cost) / old_cost
        if gain < self.min_relative_gain:
            return EfficiencyDecision(
                False, "efficiency_gain_below_threshold", gain,
                baseline_success, candidate_success, baseline_contract, candidate_contract,
            )
        return EfficiencyDecision(
            True, "correctness_and_efficiency_gates_passed", gain,
            baseline_success, candidate_success, baseline_contract, candidate_contract,
        )


@dataclass(frozen=True, slots=True)
class EfficiencyDecision:
    accepted: bool
    reason: str
    relative_gain: float = 0.0
    baseline_success_lcb: float | None = None
    candidate_success_lcb: float | None = None
    baseline_contract_lcb: float | None = None
    candidate_contract_lcb: float | None = None


@dataclass(frozen=True, slots=True)
class MachineHabit:
    habit_id: str
    version: int
    harness_id: str
    harness_version: str
    environment_id: str
    context_id: str
    trigger: tuple[StateCondition, ...]
    preconditions: tuple[StateCondition, ...]
    operations: tuple[OperationStep, ...]
    postconditions: tuple[StateCondition, ...]
    baseline: PerformanceProfile
    candidate: PerformanceProfile
    efficiency_gate: EfficiencyGate
    lifecycle: MachineHabitStatus = MachineHabitStatus.CANDIDATE

    def __post_init__(self) -> None:
        if not self.habit_id.strip() or self.version < 1:
            raise ValueError("habit identity and positive version are required")
        for name in ("harness_id", "harness_version", "environment_id", "context_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        object.__setattr__(self, "trigger", tuple(self.trigger))
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(self, "operations", tuple(self.operations))
        object.__setattr__(self, "postconditions", tuple(self.postconditions))
        if not self.trigger:
            raise ValueError("machine habit requires a trigger contract")
        if not self.operations:
            raise ValueError("machine habit requires at least one operation")
        if len({p.key for p in self.trigger}) != len(self.trigger):
            raise ValueError("trigger condition keys must be unique")
        if len({p.key for p in self.preconditions}) != len(self.preconditions):
            raise ValueError("precondition keys must be unique")
        if len({p.key for p in self.postconditions}) != len(self.postconditions):
            raise ValueError("postcondition keys must be unique")

    @property
    def efficiency(self) -> EfficiencyDecision:
        return self.efficiency_gate.evaluate(self.baseline, self.candidate)


@dataclass(frozen=True, slots=True)
class HabitUseDecision:
    eligible: bool
    reason: str
    requires_approval: bool = False
    relative_gain: float = 0.0


def authorize_machine_habit(
    habit: MachineHabit,
    harness: HarnessProfile,
    state: Mapping[str, str],
    approved_operations: frozenset[str] = frozenset(),
) -> HabitUseDecision:
    """Return whether this verified machine optimization may run in this harness."""
    if habit.lifecycle is not MachineHabitStatus.ACTIVE:
        return HabitUseDecision(False, "habit_not_active")
    if (habit.harness_id, habit.harness_version) != (harness.harness_id, harness.version):
        return HabitUseDecision(False, "harness_version_mismatch")
    if (habit.environment_id, habit.context_id) != (harness.environment_id, harness.context_id):
        return HabitUseDecision(False, "environment_scope_mismatch")
    if not all(condition.matches(state) for condition in habit.trigger):
        return HabitUseDecision(False, "trigger_not_matched")
    if not all(condition.matches(state) for condition in habit.preconditions):
        return HabitUseDecision(False, "precondition_not_satisfied")
    if habit.efficiency.relative_gain < 0 or not habit.efficiency.accepted:
        return HabitUseDecision(False, habit.efficiency.reason, relative_gain=habit.efficiency.relative_gain)

    for operation in habit.operations:
        if operation.operation_ref not in harness.allowed_operations:
            return HabitUseDecision(False, "operation_not_allowed")
        if operation.max_attempts > harness.max_step_attempts:
            return HabitUseDecision(False, "harness_attempt_limit_exceeded")
        if operation.effect is OperationEffect.COMPENSATABLE and not harness.supports_compensation:
            return HabitUseDecision(False, "harness_lacks_compensation_support")
        if operation.operation_ref in harness.approval_required and operation.operation_ref not in approved_operations:
            return HabitUseDecision(False, "approval_required", True, habit.efficiency.relative_gain)
    return HabitUseDecision(True, "authorized", False, habit.efficiency.relative_gain)

class MachineExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEEDS_ATTENTION = "needs_attention"
    HANDOFF = "handoff"


@dataclass(frozen=True, slots=True)
class OperationExecutionRecord:
    operation_ref: str
    attempts: int
    idempotency_key: str
    outcome: OperationOutcome
    duration_ms: float
    resource_units: float
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class MachineHabitExecutionResult:
    status: MachineExecutionStatus
    reason: str
    final_state: tuple[tuple[str, str], ...]
    records: tuple[OperationExecutionRecord, ...]
    total_duration_ms: float
    total_resource_units: float


def execute_machine_habit(
    habit: MachineHabit,
    harness: HarnessAdapter,
    initial_state: Mapping[str, str],
    *,
    run_id: str,
    approved_operations: frozenset[str] = frozenset(),
) -> MachineHabitExecutionResult:
    """Execute one authorized machine habit through a provider-neutral harness.

    Retries reuse the same idempotency key for one logical operation step. Unknown
    outcomes and incomplete postconditions stop the habit for reconciliation.
    """
    state = dict(initial_state)
    records: list[OperationExecutionRecord] = []
    total_duration = 0.0
    total_resources = 0.0

    def result(status: MachineExecutionStatus, reason: str) -> MachineHabitExecutionResult:
        return MachineHabitExecutionResult(
            status, reason, tuple(sorted(state.items())), tuple(records),
            total_duration, total_resources,
        )

    if not run_id.strip():
        return result(MachineExecutionStatus.HANDOFF, "run_id_required")

    authorization = authorize_machine_habit(
        habit, harness.profile, state, approved_operations
    )
    if not authorization.eligible:
        return result(MachineExecutionStatus.HANDOFF, authorization.reason)

    for index, operation in enumerate(habit.operations):
        inputs: dict[str, str] = {}
        for name, source in operation.input_bindings:
            if source.startswith("$state."):
                state_key = source[len("$state."):]
                if state_key not in state:
                    return result(MachineExecutionStatus.HANDOFF, "input_binding_missing")
                inputs[name] = state[state_key]
            else:
                inputs[name] = source

        idempotency_key = f"{run_id}:{habit.habit_id}:{habit.version}:{index}"
        attempts_limit = min(operation.max_attempts, harness.profile.max_step_attempts)
        operation_succeeded = False

        for attempt in range(1, attempts_limit + 1):
            try:
                observed = harness.invoke(
                    operation, inputs, idempotency_key=idempotency_key
                )
            except Exception as exc:
                return result(
                    MachineExecutionStatus.NEEDS_ATTENTION,
                    f"harness_adapter_exception:{type(exc).__name__}",
                )
            total_duration += observed.duration_ms
            total_resources += observed.resource_units
            records.append(OperationExecutionRecord(
                operation.operation_ref, attempt, idempotency_key, observed.outcome,
                observed.duration_ms, observed.resource_units, observed.error_code,
            ))

            if observed.outcome is OperationOutcome.SUCCEEDED:
                state.update(dict(observed.outputs))
                operation_succeeded = True
                break
            if observed.outcome is OperationOutcome.UNKNOWN:
                return result(MachineExecutionStatus.NEEDS_ATTENTION, "operation_outcome_unknown")
            if operation.effect in (
                OperationEffect.NON_REPEATABLE, OperationEffect.COMPENSATABLE
            ):
                terminal = (
                    MachineExecutionStatus.NEEDS_ATTENTION
                    if operation.effect is OperationEffect.COMPENSATABLE
                    else MachineExecutionStatus.FAILED
                )
                return result(terminal, "operation_not_safely_retryable")
            if attempt == attempts_limit:
                return result(MachineExecutionStatus.FAILED, "operation_attempts_exhausted")

        if not operation_succeeded:
            return result(MachineExecutionStatus.FAILED, "operation_failed")

    failed_postconditions = [
        condition.key for condition in habit.postconditions if not condition.matches(state)
    ]
    if failed_postconditions:
        return result(
            MachineExecutionStatus.NEEDS_ATTENTION,
            "postconditions_not_satisfied:" + ",".join(failed_postconditions),
        )
    return result(MachineExecutionStatus.SUCCEEDED, "habit_completed_and_verified")

