"""Adapter-facing execution sessions for validated HabitRoute options.

The runtime supplies observations as StateBelief values and executes returned actions.
This module does not call an environment or claim formal safety.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts import (
    AuthorizationPolicy,
    Certificate,
    ContextScope,
    FixedMacro,
    HabitSpec,
    ReactivePolicy,
    StateBelief,
    authorize_habit,
)


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    INTERRUPTED = "interrupted"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    UNKNOWN = "unknown"
    HANDOFF = "handoff"


@dataclass(frozen=True, slots=True)
class StepResult:
    status: ExecutionStatus
    action: str | None = None
    reason: str = ""


@dataclass(slots=True)
class ExecutionSession:
    """Closed-loop session that emits one action, then requires a fresh observation."""

    habit: HabitSpec
    scope: ContextScope
    steps: int = 0
    status: ExecutionStatus = ExecutionStatus.RUNNING
    _pending_action: bool = False

    @classmethod
    def start(
        cls,
        habit: HabitSpec,
        belief: StateBelief,
        current_scope: ContextScope,
        certificate: Certificate,
        policy: AuthorizationPolicy = AuthorizationPolicy(),
    ) -> tuple["ExecutionSession | None", StepResult]:
        authorization = authorize_habit(habit, belief, current_scope, certificate, policy)
        if not authorization.allowed:
            return None, StepResult(ExecutionStatus.HANDOFF, reason=authorization.reason)
        session = cls(habit=habit, scope=current_scope)
        return session, session.next_action(belief, current_scope)

    def _finish(self, status: ExecutionStatus, reason: str) -> StepResult:
        self.status = status
        self._pending_action = False
        return StepResult(status, reason=reason)

    def _scope_status(self, current_scope: ContextScope) -> StepResult | None:
        if (current_scope.environment_id, current_scope.context_id) != (
            self.scope.environment_id, self.scope.context_id
        ):
            return self._finish(ExecutionStatus.INTERRUPTED, "context_scope_changed")
        if (current_scope.representation_id, current_scope.representation_version) != (
            self.scope.representation_id, self.scope.representation_version
        ):
            return self._finish(ExecutionStatus.UNKNOWN, "representation_version_changed")
        return None

    def _belief_status(self, belief: StateBelief) -> StepResult | None:
        if (belief.representation_id, belief.representation_version) != (
            self.scope.representation_id, self.scope.representation_version
        ):
            return self._finish(ExecutionStatus.UNKNOWN, "belief_representation_mismatch")
        if belief.unknown_mass > self.habit.termination.max_unknown_mass:
            return self._finish(ExecutionStatus.UNKNOWN, "unknown_mass_exceeded")
        if belief.mass_in(self.habit.safety.forbidden_states) > 0.0:
            return self._finish(ExecutionStatus.FAILURE, "forbidden_state_observed")
        if belief.mass_in(self.habit.termination.success_states) >= self.habit.termination.min_success_mass:
            return self._finish(ExecutionStatus.SUCCESS, "goal_satisfied")
        return None

    def next_action(self, belief: StateBelief, current_scope: ContextScope) -> StepResult:
        if self.status is not ExecutionStatus.RUNNING:
            return StepResult(self.status, reason="session_not_running")
        if self._pending_action:
            return StepResult(ExecutionStatus.RUNNING, reason="awaiting_observation")
        scope_result = self._scope_status(current_scope)
        if scope_result is not None:
            return scope_result
        belief_result = self._belief_status(belief)
        if belief_result is not None:
            return belief_result
        if self.steps >= self.habit.termination.max_steps:
            return self._finish(ExecutionStatus.TIMEOUT, "step_budget_exhausted")

        controller = self.habit.controller
        if isinstance(controller, FixedMacro):
            if self.steps >= len(controller.actions):
                return self._finish(ExecutionStatus.HANDOFF, "macro_exhausted_without_goal")
            expected = controller.expected_states[self.steps]
            if belief.mass_in(frozenset({expected})) < controller.min_checkpoint_mass:
                return self._finish(ExecutionStatus.HANDOFF, "macro_checkpoint_not_satisfied")
            action = controller.actions[self.steps]
        elif isinstance(controller, ReactivePolicy):
            decision = controller.select_action(belief)
            if not decision.allowed:
                status = ExecutionStatus.UNKNOWN if decision.reason in (
                    "unknown_mass_exceeded",
                    "unclassified_mass_exceeded",
                    "representation_version_mismatch",
                ) else ExecutionStatus.HANDOFF
                return self._finish(status, decision.reason)
            action = decision.action
        else:
            return self._finish(ExecutionStatus.HANDOFF, "controller_artifact_not_executable")

        allowed = self.habit.safety.allowed_actions
        if allowed is not None and action not in allowed:
            return self._finish(ExecutionStatus.FAILURE, "action_violates_safety_allowlist")
        self._pending_action = True
        return StepResult(ExecutionStatus.RUNNING, action=action, reason="action_selected")

    def observe(self, belief: StateBelief, current_scope: ContextScope) -> StepResult:
        if self.status is not ExecutionStatus.RUNNING:
            return StepResult(self.status, reason="session_not_running")
        if not self._pending_action:
            return self._finish(ExecutionStatus.HANDOFF, "observation_without_pending_action")
        self._pending_action = False
        self.steps += 1
        scope_result = self._scope_status(current_scope)
        if scope_result is not None:
            return scope_result
        belief_result = self._belief_status(belief)
        if belief_result is not None:
            return belief_result
        if isinstance(self.habit.controller, FixedMacro):
            expected = self.habit.controller.expected_states[self.steps]
            if belief.mass_in(frozenset({expected})) < self.habit.controller.min_checkpoint_mass:
                return self._finish(ExecutionStatus.HANDOFF, "macro_checkpoint_mismatch")
        if self.steps >= self.habit.termination.max_steps:
            return self._finish(ExecutionStatus.TIMEOUT, "step_budget_exhausted")
        return StepResult(ExecutionStatus.RUNNING, reason="observation_accepted")

    def interrupt(self, reason: str = "external_interrupt") -> StepResult:
        if self.status is not ExecutionStatus.RUNNING:
            return StepResult(self.status, reason="session_not_running")
        return self._finish(ExecutionStatus.INTERRUPTED, reason)
