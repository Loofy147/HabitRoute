"""Dependency-free, fail-closed contracts for versioned reusable habits.

This module defines authorization semantics only. It does not execute controllers,
prove safety, or estimate state beliefs; those are supplied by runtime adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Mapping, TypeAlias


class ControllerKind(str, Enum):
    FIXED_MACRO = "fixed_macro"
    GUARDED_SEQUENCE = "guarded_sequence"
    REACTIVE_POLICY = "reactive_policy"
    GOAL_CONDITIONED_POLICY = "goal_conditioned_policy"


class HabitLifecycle(str, Enum):
    CANDIDATE = "candidate"
    PROBATION = "probation"
    ACTIVE = "active"
    AT_RISK = "at_risk"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class CertificateStatus(str, Enum):
    VALID = "valid"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class ContextScope:
    environment_id: str
    context_id: str
    representation_id: str
    representation_version: str

    def __post_init__(self) -> None:
        for name in ("environment_id", "context_id", "representation_id", "representation_version"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True, slots=True)
class StateBelief:
    """Probability mass over abstract states plus explicit unclassified mass."""
    probabilities: tuple[tuple[str, float], ...]
    unknown_mass: float
    representation_id: str
    representation_version: str

    def __post_init__(self) -> None:
        if not self.representation_id.strip() or not self.representation_version.strip():
            raise ValueError("belief representation identity/version must be non-empty")
        if not math.isfinite(self.unknown_mass) or not 0.0 <= self.unknown_mass <= 1.0:
            raise ValueError("unknown_mass must be finite and in [0, 1]")
        seen: set[str] = set()
        total = self.unknown_mass
        for state, probability in self.probabilities:
            if not state.strip() or state in seen:
                raise ValueError("belief states must be non-empty and unique")
            seen.add(state)
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError("state probabilities must be finite and in [0, 1]")
            total += probability
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("known state mass plus unknown_mass must equal 1")

    @classmethod
    def from_mapping(
        cls, probabilities: Mapping[str, float], *, unknown_mass: float = 0.0,
        representation_id: str, representation_version: str,
    ) -> "StateBelief":
        normalized = tuple(sorted((str(state), float(prob)) for state, prob in probabilities.items()))
        return cls(normalized, float(unknown_mass), representation_id, representation_version)

    def mass_in(self, states: frozenset[str]) -> float:
        return sum(probability for state, probability in self.probabilities if state in states)


@dataclass(frozen=True, slots=True)
class InitiationContract:
    accepted_states: frozenset[str]
    min_region_mass: float = 0.95
    max_unknown_mass: float = 0.01

    def __post_init__(self) -> None:
        object.__setattr__(self, "accepted_states", frozenset(self.accepted_states))
        if not self.accepted_states:
            raise ValueError("initiation region cannot be empty")
        if not 0.0 <= self.min_region_mass <= 1.0:
            raise ValueError("min_region_mass must be in [0, 1]")
        if not 0.0 <= self.max_unknown_mass <= 1.0:
            raise ValueError("max_unknown_mass must be in [0, 1]")

    def evaluate(self, belief: StateBelief) -> tuple[bool, float, str]:
        region_mass = belief.mass_in(self.accepted_states)
        if belief.unknown_mass > self.max_unknown_mass:
            return False, region_mass, "unknown_mass_exceeded"
        if region_mass < self.min_region_mass:
            return False, region_mass, "initiation_region_not_satisfied"
        return True, region_mass, "initiation_satisfied"


@dataclass(frozen=True, slots=True)
class FixedMacro:
    actions: tuple[str, ...]
    expected_states: tuple[str, ...]

    @property
    def kind(self) -> ControllerKind:
        return ControllerKind.FIXED_MACRO

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "expected_states", tuple(self.expected_states))
        if not self.actions or any(not action.strip() for action in self.actions):
            raise ValueError("fixed macro must contain non-empty actions")
        if len(self.expected_states) != len(self.actions) + 1:
            raise ValueError("expected_states must contain one initial state plus one state per action")
        if any(not state.strip() for state in self.expected_states):
            raise ValueError("expected states must be non-empty")


@dataclass(frozen=True, slots=True)
class PolicyActionDecision:
    allowed: bool
    action: str | None
    reason: str
    action_mass: float = 0.0
    unclassified_mass: float = 1.0


@dataclass(frozen=True, slots=True)
class ReactivePolicy:
    """Finite state-conditioned controller with conservative belief handling."""
    actions_by_state: tuple[tuple[str, str], ...]
    representation_id: str
    representation_version: str
    min_action_mass: float = 0.95
    max_unclassified_mass: float = 0.01

    @property
    def kind(self) -> ControllerKind:
        return ControllerKind.REACTIVE_POLICY

    @classmethod
    def from_mapping(
        cls, actions_by_state: Mapping[str, str], *, representation_id: str,
        representation_version: str, min_action_mass: float = 0.95,
        max_unclassified_mass: float = 0.01,
    ) -> "ReactivePolicy":
        entries = tuple(sorted((str(state), str(action)) for state, action in actions_by_state.items()))
        return cls(entries, representation_id, representation_version,
                   min_action_mass, max_unclassified_mass)

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions_by_state", tuple(sorted(self.actions_by_state)))
        if not self.representation_id.strip() or not self.representation_version.strip():
            raise ValueError("reactive policy requires a representation identity/version")
        if not self.actions_by_state:
            raise ValueError("reactive policy requires at least one state/action rule")
        states = [state for state, _ in self.actions_by_state]
        if len(states) != len(set(states)):
            raise ValueError("reactive policy has duplicate state rules")
        if any(not state.strip() or not action.strip() for state, action in self.actions_by_state):
            raise ValueError("reactive policy states and actions must be non-empty")
        if not 0.0 <= self.min_action_mass <= 1.0:
            raise ValueError("min_action_mass must be in [0, 1]")
        if not 0.0 <= self.max_unclassified_mass <= 1.0:
            raise ValueError("max_unclassified_mass must be in [0, 1]")

    def select_action(self, belief: StateBelief) -> PolicyActionDecision:
        """Choose only when one action covers enough belief mass; otherwise refuse."""
        if (belief.representation_id, belief.representation_version) != (
            self.representation_id, self.representation_version
        ):
            return PolicyActionDecision(False, None, "representation_version_mismatch",
                                        unclassified_mass=belief.unknown_mass)
        rules = dict(self.actions_by_state)
        unclassified = belief.unknown_mass + sum(
            probability for state, probability in belief.probabilities if state not in rules
        )
        if unclassified > self.max_unclassified_mass:
            return PolicyActionDecision(False, None, "unclassified_mass_exceeded",
                                        unclassified_mass=unclassified)
        action_mass: dict[str, float] = {}
        for state, probability in belief.probabilities:
            action = rules.get(state)
            if action is not None:
                action_mass[action] = action_mass.get(action, 0.0) + probability
        if not action_mass:
            return PolicyActionDecision(False, None, "no_supported_action",
                                        unclassified_mass=unclassified)
        action, mass = max(action_mass.items(), key=lambda item: (item[1], item[0]))
        if mass < self.min_action_mass:
            return PolicyActionDecision(False, None, "ambiguous_action_distribution",
                                        action_mass=mass, unclassified_mass=unclassified)
        return PolicyActionDecision(True, action, "action_selected",
                                    action_mass=mass, unclassified_mass=unclassified)


@dataclass(frozen=True, slots=True)
class ControllerArtifact:
    """Reference to a guarded/reactive controller that a runtime can load."""
    kind: ControllerKind
    artifact_ref: str

    def __post_init__(self) -> None:
        if self.kind is ControllerKind.FIXED_MACRO:
            raise ValueError("use FixedMacro for fixed_macro controllers")
        if not self.artifact_ref.strip():
            raise ValueError("controller artifact reference must be non-empty")


Controller: TypeAlias = FixedMacro | ReactivePolicy | ControllerArtifact


@dataclass(frozen=True, slots=True)
class TerminationContract:
    success_states: frozenset[str]
    max_steps: int
    failure_conditions: tuple[str, ...] = ()
    interrupt_conditions: tuple[str, ...] = ("context_change", "safety_guard")

    def __post_init__(self) -> None:
        object.__setattr__(self, "success_states", frozenset(self.success_states))
        object.__setattr__(self, "failure_conditions", tuple(self.failure_conditions))
        object.__setattr__(self, "interrupt_conditions", tuple(self.interrupt_conditions))
        if not self.success_states:
            raise ValueError("termination contract requires at least one success state")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")


@dataclass(frozen=True, slots=True)
class SafetyContract:
    forbidden_states: frozenset[str] = frozenset()
    allowed_actions: frozenset[str] | None = None
    max_risk: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "forbidden_states", frozenset(self.forbidden_states))
        if self.allowed_actions is not None:
            object.__setattr__(self, "allowed_actions", frozenset(self.allowed_actions))
        if self.max_risk is not None and (not math.isfinite(self.max_risk) or not 0.0 <= self.max_risk <= 1.0):
            raise ValueError("max_risk must be None or finite and in [0, 1]")
        if self.allowed_actions is not None and not self.allowed_actions:
            raise ValueError("allowed_actions must be None or non-empty")


@dataclass(frozen=True, slots=True)
class HabitSpec:
    habit_id: str
    version: int
    scope: ContextScope
    initiation: InitiationContract
    controller: Controller
    termination: TerminationContract
    safety: SafetyContract
    lifecycle: HabitLifecycle = HabitLifecycle.CANDIDATE

    def __post_init__(self) -> None:
        if not self.habit_id.strip() or self.version <= 0:
            raise ValueError("habit identity and positive version are required")
        if self.safety.forbidden_states.intersection(self.termination.success_states):
            raise ValueError("a success state cannot also be forbidden")
        if isinstance(self.controller, FixedMacro):
            if self.controller.expected_states[0] not in self.initiation.accepted_states:
                raise ValueError("macro start state must belong to the initiation region")
            if self.controller.expected_states[-1] not in self.termination.success_states:
                raise ValueError("macro terminal state must satisfy the success contract")
            if len(self.controller.actions) > self.termination.max_steps:
                raise ValueError("macro length exceeds the termination step budget")
            if self.safety.allowed_actions is not None:
                disallowed = set(self.controller.actions) - self.safety.allowed_actions
                if disallowed:
                    raise ValueError(f"macro contains disallowed actions: {sorted(disallowed)}")
            if set(self.controller.expected_states).intersection(self.safety.forbidden_states):
                raise ValueError("macro expected path contains a forbidden state")
        elif isinstance(self.controller, ReactivePolicy):
            if (self.controller.representation_id, self.controller.representation_version) != (
                self.scope.representation_id, self.scope.representation_version
            ):
                raise ValueError("reactive policy representation must match habit scope")
            states = {state for state, _ in self.controller.actions_by_state}
            actions = {action for _, action in self.controller.actions_by_state}
            if states.intersection(self.safety.forbidden_states):
                raise ValueError("reactive policy defines actions in forbidden states")
            if self.safety.allowed_actions is not None:
                disallowed = actions - self.safety.allowed_actions
                if disallowed:
                    raise ValueError(f"reactive policy contains disallowed actions: {sorted(disallowed)}")

    def with_version(self, version: int) -> "HabitSpec":
        return replace(self, version=version)

    def with_lifecycle(self, lifecycle: HabitLifecycle) -> "HabitSpec":
        return replace(self, lifecycle=lifecycle)


@dataclass(frozen=True, slots=True)
class Certificate:
    """Empirical evidence summary for one immutable habit version and scope."""
    habit_id: str
    habit_version: int
    scope: ContextScope
    status: CertificateStatus
    trials: int
    successes: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        if not self.habit_id.strip() or self.habit_version <= 0:
            raise ValueError("certificate must identify a habit and positive version")
        if self.trials < 0 or self.successes < 0 or self.successes > self.trials:
            raise ValueError("certificate counts are invalid")
        if any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence references must be non-empty")

    def with_status(self, status: CertificateStatus) -> "Certificate":
        return replace(self, status=status)


@dataclass(frozen=True, slots=True)
class AuthorizationPolicy:
    min_trials: int = 20
    min_success_lcb: float = 0.80
    z_value: float = 1.96

    def __post_init__(self) -> None:
        if self.min_trials <= 0 or not 0.0 <= self.min_success_lcb <= 1.0:
            raise ValueError("invalid authorization thresholds")
        if not math.isfinite(self.z_value) or self.z_value <= 0.0:
            raise ValueError("z_value must be positive and finite")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    region_mass: float = 0.0
    unknown_mass: float = 1.0
    reliability_lcb: float | None = None


def wilson_lower_bound(successes: int, trials: int, z_value: float = 1.96) -> float:
    """Two-sided Wilson lower confidence bound for a Bernoulli success rate."""
    if trials <= 0:
        return 0.0
    if successes < 0 or successes > trials or not math.isfinite(z_value) or z_value <= 0.0:
        raise ValueError("invalid Wilson interval inputs")
    n = float(trials)
    p = successes / n
    z2 = z_value * z_value
    denominator = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    radius = z_value * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return max(0.0, (centre - radius) / denominator)


def authorize_habit(
    habit: HabitSpec, belief: StateBelief, current_scope: ContextScope,
    certificate: Certificate, policy: AuthorizationPolicy = AuthorizationPolicy(),
) -> AuthorizationDecision:
    """Authorize only when identity, scope, evidence and initiation all pass."""
    if habit.lifecycle is not HabitLifecycle.ACTIVE:
        return AuthorizationDecision(False, "habit_not_active", unknown_mass=belief.unknown_mass)
    if (habit.scope.environment_id, habit.scope.context_id) != (
        current_scope.environment_id, current_scope.context_id
    ):
        return AuthorizationDecision(False, "context_scope_mismatch", unknown_mass=belief.unknown_mass)
    if (habit.scope.representation_id, habit.scope.representation_version) != (
        current_scope.representation_id, current_scope.representation_version
    ) or (belief.representation_id, belief.representation_version) != (
        current_scope.representation_id, current_scope.representation_version
    ):
        return AuthorizationDecision(False, "representation_version_mismatch", unknown_mass=belief.unknown_mass)
    if certificate.habit_id != habit.habit_id:
        return AuthorizationDecision(False, "certificate_habit_mismatch", unknown_mass=belief.unknown_mass)
    if certificate.habit_version != habit.version:
        return AuthorizationDecision(False, "certificate_version_mismatch", unknown_mass=belief.unknown_mass)
    if certificate.scope != habit.scope:
        return AuthorizationDecision(False, "certificate_scope_mismatch", unknown_mass=belief.unknown_mass)
    if certificate.status is not CertificateStatus.VALID:
        return AuthorizationDecision(False, "certificate_not_valid", unknown_mass=belief.unknown_mass)
    if certificate.trials < policy.min_trials or not certificate.evidence_refs:
        return AuthorizationDecision(False, "insufficient_evidence", unknown_mass=belief.unknown_mass)
    lcb = wilson_lower_bound(certificate.successes, certificate.trials, policy.z_value)
    if lcb < policy.min_success_lcb:
        return AuthorizationDecision(False, "reliability_bound_not_met",
                                     unknown_mass=belief.unknown_mass, reliability_lcb=lcb)
    ok, mass, reason = habit.initiation.evaluate(belief)
    if not ok:
        return AuthorizationDecision(False, reason, region_mass=mass,
                                     unknown_mass=belief.unknown_mass, reliability_lcb=lcb)
    return AuthorizationDecision(True, "authorized", region_mass=mass,
                                 unknown_mass=belief.unknown_mass, reliability_lcb=lcb)
