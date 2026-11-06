"""Research-only paired-trial analysis helpers.

This module is deliberately not a promotion gate. It summarizes validated matched
trial records, preserves unknowns/exclusions, and never activates a habit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from math import comb, isfinite
from typing import Iterable


class Arm(str, Enum):
    BASELINE = "baseline"
    ADAPTED = "adapted"


@dataclass(frozen=True, slots=True)
class CostObservation:
    metric: str
    value: float | None
    unit: str
    measurement_kind: str = "observed"

    def __post_init__(self) -> None:
        if not self.metric.strip() or not self.unit.strip() or not self.measurement_kind.strip():
            raise ValueError("cost metric, unit and measurement_kind must be non-empty")
        if self.value is not None and (not isfinite(self.value) or self.value < 0):
            raise ValueError("cost value must be finite and non-negative, or None for unknown")


def _validate_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class Trial:
    pair_id: str
    case_id: str
    arm: Arm
    input_sha256: str
    task_signature_sha256: str
    base_harness_sha256: str
    effective_harness_sha256: str
    environment_sha256: str
    agent_sha256: str
    model_sha256: str
    opportunity_present: bool | None
    target_action_observed: bool | None
    task_success: bool | None
    contract_passed: bool | None
    adaptation_digest: str | None = None
    adaptation_loaded: bool | None = None
    trace_complete: bool = True
    constraint_violations: tuple[str, ...] = ()
    unrelated_work_count: int | None = 0
    costs: tuple[CostObservation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arm", Arm(self.arm))
        object.__setattr__(self, "constraint_violations", tuple(self.constraint_violations))
        object.__setattr__(self, "costs", tuple(self.costs))
        if not self.pair_id.strip() or not self.case_id.strip():
            raise ValueError("pair_id and case_id must be non-empty")
        for name in (
            "input_sha256", "task_signature_sha256", "base_harness_sha256",
            "effective_harness_sha256", "environment_sha256", "agent_sha256", "model_sha256",
        ):
            _validate_digest(name, getattr(self, name))
        for name in ("opportunity_present", "target_action_observed", "task_success",
                     "contract_passed", "adaptation_loaded", "trace_complete"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"{name} must be bool or None")
        if self.unrelated_work_count is not None and self.unrelated_work_count < 0:
            raise ValueError("unrelated_work_count must be non-negative or None")
        if any(not item.strip() for item in self.constraint_violations):
            raise ValueError("constraint violation labels must be non-empty")
        cost_keys = [(c.metric, c.unit, c.measurement_kind) for c in self.costs]
        if len(cost_keys) != len(set(cost_keys)):
            raise ValueError("a trial cannot contain duplicate cost metric/unit/measurement rows")

        if self.arm is Arm.BASELINE:
            if self.adaptation_digest is not None or self.adaptation_loaded is not None:
                raise ValueError("baseline trials cannot claim an adaptation digest or loading state")
            if self.effective_harness_sha256 != self.base_harness_sha256:
                raise ValueError("baseline effective harness must equal its base harness")
        else:
            if self.adaptation_digest is None:
                raise ValueError("adapted trials require the assigned adaptation digest")
            _validate_digest("adaptation_digest", self.adaptation_digest)

        if self.opportunity_present is False and self.target_action_observed is True:
            raise ValueError("target action cannot be observed when its opportunity was absent")


@dataclass(frozen=True, slots=True)
class CostSummary:
    metric: str
    unit: str
    measurement_kind: str
    paired_samples: int
    baseline_mean: float
    adapted_mean: float
    adapted_minus_baseline: float


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    supplied_pairs: int
    eligible_opportunity_pairs: int
    baseline_recurrences: int
    adapted_recurrences: int
    both_recur: int
    baseline_only_recur: int
    adapted_only_recur: int
    neither_recur: int
    baseline_rate: float | None
    adapted_rate: float | None
    risk_difference_adapted_minus_baseline: float | None
    exact_mcnemar_two_sided_p: float | None
    exclusion_counts: tuple[tuple[str, int], ...]
    adapted_trials_assigned: int
    adaptation_load_observed: int
    adaptation_loaded: int
    adaptation_loading_rate: float | None
    task_quality_pairs: int
    task_success_risk_difference: float | None
    contract_quality_pairs: int
    contract_pass_risk_difference: float | None
    adapted_pairs_with_constraint_violations: int
    adapted_constraint_violation_count: int
    unrelated_work_observed: int
    unrelated_work_total: int
    cost_summaries: tuple[CostSummary, ...]
    minimum_opportunity_pairs: int
    minimum_opportunity_pairs_met: bool


def exact_mcnemar_two_sided_p(baseline_only: int, adapted_only: int) -> float:
    """Exact two-sided McNemar p-value from discordant matched binary pairs."""
    if baseline_only < 0 or adapted_only < 0:
        raise ValueError("discordant pair counts cannot be negative")
    discordant = baseline_only + adapted_only
    if discordant == 0:
        return 1.0
    tail = sum(comb(discordant, k) for k in range(min(baseline_only, adapted_only) + 1))
    return min(1.0, 2.0 * tail / (2 ** discordant))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def evaluate_pairs(
    trials: Iterable[Trial], *, minimum_opportunity_pairs: int,
) -> EvaluationSummary:
    """Summarize matched trials without making a promotion or safety decision.

    The primary denominator is complete matched pairs where the externally
    defined target opportunity was present in both arms and the target action
    was observable in both. Treatment assignment is retained even when the
    adaptation was not loaded (intention-to-treat); loading is diagnostic only.
    """
    if minimum_opportunity_pairs < 0:
        raise ValueError("minimum_opportunity_pairs cannot be negative")

    grouped: dict[str, dict[Arm, Trial]] = defaultdict(dict)
    all_trials = tuple(trials)
    for trial in all_trials:
        arm_map = grouped[trial.pair_id]
        if trial.arm in arm_map:
            raise ValueError(f"duplicate {trial.arm.value} trial for pair {trial.pair_id}")
        arm_map[trial.arm] = trial

    exclusions: Counter[str] = Counter()
    eligible: list[tuple[Trial, Trial]] = []
    for pair_id, arms in grouped.items():
        baseline = arms.get(Arm.BASELINE)
        adapted = arms.get(Arm.ADAPTED)
        if baseline is None or adapted is None:
            exclusions["missing_arm"] += 1
            continue
        identity_fields = (
            "case_id", "input_sha256", "task_signature_sha256", "base_harness_sha256",
            "environment_sha256", "agent_sha256", "model_sha256",
        )
        if any(getattr(baseline, field) != getattr(adapted, field) for field in identity_fields):
            exclusions["pair_identity_mismatch"] += 1
            continue
        if not baseline.trace_complete or not adapted.trace_complete:
            exclusions["incomplete_trace"] += 1
            continue
        if baseline.opportunity_present is None or adapted.opportunity_present is None:
            exclusions["opportunity_unknown"] += 1
            continue
        if baseline.opportunity_present != adapted.opportunity_present:
            exclusions["opportunity_mismatch"] += 1
            continue
        if not baseline.opportunity_present:
            exclusions["no_opportunity"] += 1
            continue
        if baseline.target_action_observed is None or adapted.target_action_observed is None:
            exclusions["target_action_unknown"] += 1
            continue
        eligible.append((baseline, adapted))

    both = baseline_only = adapted_only = neither = 0
    for baseline, adapted in eligible:
        base_action = bool(baseline.target_action_observed)
        adapted_action = bool(adapted.target_action_observed)
        if base_action and adapted_action:
            both += 1
        elif base_action:
            baseline_only += 1
        elif adapted_action:
            adapted_only += 1
        else:
            neither += 1

    n = len(eligible)
    base_recur = both + baseline_only
    adapted_recur = both + adapted_only
    baseline_rate = base_recur / n if n else None
    adapted_rate = adapted_recur / n if n else None
    risk_difference = adapted_rate - baseline_rate if n else None
    p_value = exact_mcnemar_two_sided_p(baseline_only, adapted_only) if n else None

    adapted_trials = [trial for trial in all_trials if trial.arm is Arm.ADAPTED]
    loaded_observed = sum(trial.adaptation_loaded is not None for trial in adapted_trials)
    loaded_count = sum(trial.adaptation_loaded is True for trial in adapted_trials)
    loading_rate = loaded_count / loaded_observed if loaded_observed else None

    quality_pairs = [
        (base, adapted) for base, adapted in eligible
        if base.task_success is not None and adapted.task_success is not None
    ]
    task_diff = (
        sum(bool(adapted.task_success) for _, adapted in quality_pairs) / len(quality_pairs)
        - sum(bool(base.task_success) for base, _ in quality_pairs) / len(quality_pairs)
        if quality_pairs else None
    )
    contract_pairs = [
        (base, adapted) for base, adapted in eligible
        if base.contract_passed is not None and adapted.contract_passed is not None
    ]
    contract_diff = (
        sum(bool(adapted.contract_passed) for _, adapted in contract_pairs) / len(contract_pairs)
        - sum(bool(base.contract_passed) for base, _ in contract_pairs) / len(contract_pairs)
        if contract_pairs else None
    )

    violation_pair_ids = {
        adapted.pair_id for _, adapted in eligible if adapted.constraint_violations
    }
    # Count violations over every assigned adapted arm, including excluded pairs.
    violation_total = sum(len(trial.constraint_violations) for trial in adapted_trials)
    unrelated_known = [
        trial.unrelated_work_count for trial in adapted_trials
        if trial.unrelated_work_count is not None
    ]

    cost_values: dict[tuple[str, str, str], tuple[list[float], list[float]]] = {}
    for baseline, adapted in eligible:
        base_costs = {
            (item.metric, item.unit, item.measurement_kind): item.value
            for item in baseline.costs
        }
        adapted_costs = {
            (item.metric, item.unit, item.measurement_kind): item.value
            for item in adapted.costs
        }
        for key in base_costs.keys() & adapted_costs.keys():
            base_value, adapted_value = base_costs[key], adapted_costs[key]
            if base_value is None or adapted_value is None:
                continue
            base_list, adapted_list = cost_values.setdefault(key, ([], []))
            base_list.append(base_value)
            adapted_list.append(adapted_value)

    cost_summaries = tuple(
        CostSummary(
            metric=key[0], unit=key[1], measurement_kind=key[2],
            paired_samples=len(values[0]), baseline_mean=_mean(values[0]),
            adapted_mean=_mean(values[1]),
            adapted_minus_baseline=_mean(values[1]) - _mean(values[0]),
        )
        for key, values in sorted(cost_values.items())
        if values[0]
    )

    return EvaluationSummary(
        supplied_pairs=len(grouped),
        eligible_opportunity_pairs=n,
        baseline_recurrences=base_recur,
        adapted_recurrences=adapted_recur,
        both_recur=both,
        baseline_only_recur=baseline_only,
        adapted_only_recur=adapted_only,
        neither_recur=neither,
        baseline_rate=baseline_rate,
        adapted_rate=adapted_rate,
        risk_difference_adapted_minus_baseline=risk_difference,
        exact_mcnemar_two_sided_p=p_value,
        exclusion_counts=tuple(sorted(exclusions.items())),
        adapted_trials_assigned=len(adapted_trials),
        adaptation_load_observed=loaded_observed,
        adaptation_loaded=loaded_count,
        adaptation_loading_rate=loading_rate,
        task_quality_pairs=len(quality_pairs),
        task_success_risk_difference=task_diff,
        contract_quality_pairs=len(contract_pairs),
        contract_pass_risk_difference=contract_diff,
        adapted_pairs_with_constraint_violations=len(violation_pair_ids),
        adapted_constraint_violation_count=violation_total,
        unrelated_work_observed=len(unrelated_known),
        unrelated_work_total=sum(unrelated_known),
        cost_summaries=cost_summaries,
        minimum_opportunity_pairs=minimum_opportunity_pairs,
        minimum_opportunity_pairs_met=n >= minimum_opportunity_pairs,
    )
