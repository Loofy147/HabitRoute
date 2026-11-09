"""Situation-aware capability repertoire and safe composition planning.

This module plans; it never invokes a capability. A host must supply the
availability and authorization snapshot used for each dry-run composition.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from typing import Iterable

from .machine import OperationEffect


class CapabilityKind(str, Enum):
    SKILL = "skill"
    TOOL = "tool"
    SCRIPT = "script"
    API = "api"
    LIBRARY = "library"
    FRAMEWORK = "framework"
    MODEL = "model"
    SERVICE = "service"
    DATASET = "dataset"
    SUB_HABIT = "sub_habit"
    CONTEXT = "context"


class CapabilityStatus(str, Enum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    ACTIVE = "active"
    AT_RISK = "at_risk"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"


class CostDimension(str, Enum):
    CALLS = "calls"
    LATENCY_MS = "latency_ms"
    TOKENS = "tokens"
    RESOURCE_UNITS = "resource_units"
    EXTERNAL_COST = "external_cost"


class PlanStatus(str, Enum):
    READY = "ready"
    NEEDS_INFORMATION = "needs_information"
    NEEDS_CAPABILITY = "needs_capability"
    BLOCKED_CONTEXT = "blocked_context"
    STALE_SITUATION = "stale_situation"


def _freeze_names(values: Iterable[str], field_name: str) -> frozenset[str]:
    frozen = frozenset(values)
    if any(not isinstance(value, str) or not value.strip() for value in frozen):
        raise ValueError(f"{field_name} must contain non-empty strings")
    return frozen


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Estimated cost for planning; each dimension remains independently visible."""

    calls: float = 0.0
    latency_ms: float = 0.0
    tokens: float = 0.0
    resource_units: float = 0.0
    external_cost: float = 0.0

    def __post_init__(self) -> None:
        for name in ("calls", "latency_ms", "tokens", "resource_units", "external_cost"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

    def value_for(self, dimension: CostDimension) -> float:
        return {
            CostDimension.CALLS: self.calls,
            CostDimension.LATENCY_MS: self.latency_ms,
            CostDimension.TOKENS: self.tokens,
            CostDimension.RESOURCE_UNITS: self.resource_units,
            CostDimension.EXTERNAL_COST: self.external_cost,
        }[dimension]

    @classmethod
    def total(cls, estimates: Iterable["CostEstimate"]) -> "CostEstimate":
        values = tuple(estimates)
        return cls(
            calls=math.fsum(item.calls for item in values),
            latency_ms=math.fsum(item.latency_ms for item in values),
            tokens=math.fsum(item.tokens for item in values),
            resource_units=math.fsum(item.resource_units for item in values),
            external_cost=math.fsum(item.external_cost for item in values),
        )


@dataclass(frozen=True, slots=True)
class CapabilityEntry:
    """One governed capability in a habit's repertoire.

    Compatibility references use the stable form ``id@version``. An ACTIVE
    entry must carry a digest/reference to the evidence that justified activation.
    """

    capability_id: str
    kind: CapabilityKind
    version: str
    provides: frozenset[str]
    requires_inputs: frozenset[str]
    required_permissions: frozenset[str]
    compatible_harnesses: frozenset[str]
    compatible_environments: frozenset[str]
    effect: OperationEffect
    status: CapabilityStatus
    evidence_digest: str | None
    cost: CostEstimate = CostEstimate()

    def __post_init__(self) -> None:
        for name in ("capability_id", "version"):
            _require_text(getattr(self, name), name)
        for name in (
            "provides", "requires_inputs", "required_permissions",
            "compatible_harnesses", "compatible_environments",
        ):
            frozen = _freeze_names(getattr(self, name), name)
            object.__setattr__(self, name, frozen)
        if not self.provides:
            raise ValueError("capability must provide at least one outcome")
        if not self.compatible_harnesses:
            raise ValueError("compatible_harnesses must not be empty")
        if not self.compatible_environments:
            raise ValueError("compatible_environments must not be empty")
        if self.status is CapabilityStatus.ACTIVE and not (
            isinstance(self.evidence_digest, str) and self.evidence_digest.strip()
        ):
            raise ValueError("ACTIVE capability requires evidence_digest")
        if self.evidence_digest is not None and not self.evidence_digest.strip():
            raise ValueError("evidence_digest must be non-empty when provided")

    @property
    def harness_ref(self) -> str:
        return f"{self.capability_id}@{self.version}"


@dataclass(frozen=True, slots=True)
class SituationFrame:
    """Time-bound, provenance-addressed observation of the current situation."""

    situation_id: str
    observed_at: datetime
    harness_id: str
    harness_version: str
    environment_id: str
    environment_version: str
    available_inputs: frozenset[str]
    context_digest: str

    def __post_init__(self) -> None:
        for name in (
            "situation_id", "harness_id", "harness_version",
            "environment_id", "environment_version", "context_digest",
        ):
            _require_text(getattr(self, name), name)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(
            self, "available_inputs", _freeze_names(self.available_inputs, "available_inputs")
        )

    @property
    def harness_ref(self) -> str:
        return f"{self.harness_id}@{self.harness_version}"

    @property
    def environment_ref(self) -> str:
        return f"{self.environment_id}@{self.environment_version}"


@dataclass(frozen=True, slots=True)
class HostCapabilitySnapshot:
    """Host-attested capability availability and effective permission snapshot.

    This is input to planning, not a mechanism for granting permissions. The
    host remains responsible for producing an authentic snapshot and enforcing it.
    """

    harness_id: str
    harness_version: str
    environment_id: str
    environment_version: str
    available_capabilities: frozenset[str]
    granted_permissions: frozenset[str]
    allowed_effects: frozenset[OperationEffect]
    snapshot_digest: str

    def __post_init__(self) -> None:
        for name in (
            "harness_id", "harness_version", "environment_id",
            "environment_version", "snapshot_digest",
        ):
            _require_text(getattr(self, name), name)
        object.__setattr__(
            self, "available_capabilities",
            _freeze_names(self.available_capabilities, "available_capabilities"),
        )
        object.__setattr__(
            self, "granted_permissions",
            _freeze_names(self.granted_permissions, "granted_permissions"),
        )
        object.__setattr__(self, "allowed_effects", frozenset(self.allowed_effects))

    @property
    def harness_ref(self) -> str:
        return f"{self.harness_id}@{self.harness_version}"

    @property
    def environment_ref(self) -> str:
        return f"{self.environment_id}@{self.environment_version}"


@dataclass(frozen=True, slots=True)
class OutcomeContract:
    required_outcomes: frozenset[str]
    required_inputs: frozenset[str]
    max_situation_age_seconds: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_outcomes", _freeze_names(self.required_outcomes, "required_outcomes")
        )
        object.__setattr__(
            self, "required_inputs", _freeze_names(self.required_inputs, "required_inputs")
        )
        if not self.required_outcomes:
            raise ValueError("outcome contract requires at least one outcome")
        if self.max_situation_age_seconds < 1:
            raise ValueError("max_situation_age_seconds must be positive")


@dataclass(frozen=True, slots=True)
class CompositionPolicy:
    """Transparent single-metric objective; other costs are still reported."""

    primary_cost: CostDimension = CostDimension.CALLS
    max_capabilities: int = 8

    def __post_init__(self) -> None:
        if self.max_capabilities < 1:
            raise ValueError("max_capabilities must be positive")


@dataclass(frozen=True, slots=True)
class HabitDefinition:
    habit_id: str
    version: str
    purpose: str
    capabilities: tuple[CapabilityEntry, ...]
    outcome_contract: OutcomeContract
    composition_policy: CompositionPolicy = CompositionPolicy()

    def __post_init__(self) -> None:
        for name in ("habit_id", "version", "purpose"):
            _require_text(getattr(self, name), name)
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        if not self.capabilities:
            raise ValueError("habit repertoire must contain at least one capability")
        ids = [item.capability_id for item in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("capability IDs must be unique")


@dataclass(frozen=True, slots=True)
class CapabilityRejection:
    capability_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompositionPlan:
    habit_id: str
    habit_version: str
    situation_id: str
    status: PlanStatus
    selected: tuple[CapabilityEntry, ...]
    covered_outcomes: frozenset[str]
    missing_outcomes: frozenset[str]
    missing_inputs: frozenset[str]
    rejected: tuple[CapabilityRejection, ...]
    estimated_cost: CostEstimate
    primary_cost: CostDimension
    reason: str
    dry_run: bool = True

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(item.capability_id for item in self.selected)


def _rejection(item: CapabilityEntry, reasons: list[str]) -> CapabilityRejection:
    return CapabilityRejection(item.capability_id, tuple(sorted(set(reasons))))


def compose_habit(
    habit: HabitDefinition,
    situation: SituationFrame,
    host: HostCapabilitySnapshot,
    *,
    now: datetime,
) -> CompositionPlan:
    """Build an explainable, dry-run capability plan for the supplied situation.

    The planner performs no I/O and calls no tools. It only selects capabilities
    whose evidence, availability, compatibility, input requirements, effects and
    permissions satisfy the explicit situation and host snapshot.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    contract = habit.outcome_contract
    empty_cost = CostEstimate()

    def empty_plan(
        status: PlanStatus,
        reason: str,
        *,
        missing_inputs: frozenset[str] = frozenset(),
        missing_outcomes: frozenset[str] | None = None,
    ) -> CompositionPlan:
        return CompositionPlan(
            habit_id=habit.habit_id,
            habit_version=habit.version,
            situation_id=situation.situation_id,
            status=status,
            selected=(),
            covered_outcomes=frozenset(),
            missing_outcomes=(
                contract.required_outcomes if missing_outcomes is None else missing_outcomes
            ),
            missing_inputs=missing_inputs,
            rejected=(),
            estimated_cost=empty_cost,
            primary_cost=habit.composition_policy.primary_cost,
            reason=reason,
        )

    # A host snapshot and the situation must identify the same actual boundary.
    if (
        situation.harness_ref != host.harness_ref
        or situation.environment_ref != host.environment_ref
    ):
        return empty_plan(PlanStatus.BLOCKED_CONTEXT, "host_situation_identity_mismatch")

    age_seconds = (now - situation.observed_at).total_seconds()
    if age_seconds < 0:
        return empty_plan(PlanStatus.BLOCKED_CONTEXT, "future_situation_timestamp")
    if age_seconds > contract.max_situation_age_seconds:
        return empty_plan(PlanStatus.STALE_SITUATION, "situation_expired")

    missing_inputs = contract.required_inputs - situation.available_inputs
    if missing_inputs:
        return empty_plan(
            PlanStatus.NEEDS_INFORMATION,
            "required_situation_inputs_missing",
            missing_inputs=missing_inputs,
        )

    eligible: list[CapabilityEntry] = []
    rejected: list[CapabilityRejection] = []
    required = contract.required_outcomes

    for item in sorted(habit.capabilities, key=lambda entry: entry.capability_id):
        reasons: list[str] = []
        if item.status is not CapabilityStatus.ACTIVE:
            reasons.append("capability_not_active")
        if item.capability_id not in host.available_capabilities:
            reasons.append("capability_unavailable_in_host")
        if situation.harness_ref not in item.compatible_harnesses:
            reasons.append("harness_incompatible")
        if situation.environment_ref not in item.compatible_environments:
            reasons.append("environment_incompatible")
        if not item.requires_inputs.issubset(situation.available_inputs):
            for name in sorted(item.requires_inputs - situation.available_inputs):
                reasons.append(f"situation_input_missing:{name}")
        for permission in sorted(item.required_permissions - host.granted_permissions):
            reasons.append(f"host_permission_missing:{permission}")
        if item.effect not in host.allowed_effects:
            reasons.append(f"effect_not_authorized:{item.effect.value}")
        if not (item.provides & required):
            reasons.append("no_required_outcome_coverage")

        if reasons:
            rejected.append(_rejection(item, reasons))
        else:
            eligible.append(item)

    # Exact dynamic-programming set cover. Cost is optimized only on the one
    # explicitly declared primary dimension; count and IDs are deterministic
    # tie-breakers. Other cost dimensions are reported, never silently weighted.
    outcome_names = tuple(sorted(required))
    outcome_index = {name: index for index, name in enumerate(outcome_names)}
    full_mask = (1 << len(outcome_names)) - 1
    states: dict[int, tuple[CapabilityEntry, ...]] = {0: ()}
    primary = habit.composition_policy.primary_cost
    maximum = habit.composition_policy.max_capabilities

    def score(items: tuple[CapabilityEntry, ...]) -> tuple[float, int, tuple[str, ...]]:
        primary_total = math.fsum(item.cost.value_for(primary) for item in items)
        return primary_total, len(items), tuple(item.capability_id for item in items)

    for item in eligible:
        mask = 0
        for outcome in item.provides & required:
            mask |= 1 << outcome_index[outcome]
        updated = dict(states)
        for current_mask, chosen in states.items():
            if len(chosen) >= maximum:
                continue
            candidate = chosen + (item,)
            next_mask = current_mask | mask
            incumbent = updated.get(next_mask)
            if incumbent is None or score(candidate) < score(incumbent):
                updated[next_mask] = candidate
        states = updated

    chosen = states.get(full_mask)
    if chosen is None:
        covered_mask = 0
        for item in eligible:
            for outcome in item.provides & required:
                covered_mask |= 1 << outcome_index[outcome]
        covered = frozenset(
            name for name, index in outcome_index.items() if covered_mask & (1 << index)
        )
        missing = required - covered
        reason = (
            "capability_limit_prevents_coverage"
            if not missing
            else "no_eligible_capability_set_covers_outcome_contract"
        )
        return CompositionPlan(
            habit_id=habit.habit_id,
            habit_version=habit.version,
            situation_id=situation.situation_id,
            status=PlanStatus.NEEDS_CAPABILITY,
            selected=(),
            covered_outcomes=covered,
            missing_outcomes=missing,
            missing_inputs=frozenset(),
            rejected=tuple(rejected),
            estimated_cost=empty_cost,
            primary_cost=primary,
            reason=reason,
        )

    selected = tuple(sorted(chosen, key=lambda entry: entry.capability_id))
    selected_ids = {item.capability_id for item in selected}
    for item in eligible:
        if item.capability_id not in selected_ids:
            rejected.append(
                _rejection(item, ["not_selected_by_primary_cost_objective"])
            )
    covered = frozenset().union(*(item.provides for item in selected))
    return CompositionPlan(
        habit_id=habit.habit_id,
        habit_version=habit.version,
        situation_id=situation.situation_id,
        status=PlanStatus.READY,
        selected=selected,
        covered_outcomes=covered & required,
        missing_outcomes=frozenset(),
        missing_inputs=frozenset(),
        rejected=tuple(rejected),
        estimated_cost=CostEstimate.total(item.cost for item in selected),
        primary_cost=primary,
        reason="minimum_primary_cost_sufficient_composition",
    )
