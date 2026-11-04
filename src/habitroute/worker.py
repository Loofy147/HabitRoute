"""Persistent flow worker that dispatches operation and machine-habit nodes.

The worker is provider-neutral: actual operations run only through HarnessAdapter.
It commits flow events after a known result and escalates ambiguous side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .flows import FlowNodeKind, FlowStatus, PersistentFlow
from .machine import (
    HarnessAdapter,
    MachineExecutionStatus,
    MachineHabit,
    MachineHabitStatus,
    OperationEffect,
    OperationOutcome,
    OperationStep,
    authorize_machine_habit,
    execute_machine_habit,
)


class DispatchStatus(str, Enum):
    ADVANCED = "advanced"
    WAITING = "waiting"
    PAUSED = "paused"
    TERMINAL = "terminal"
    NEEDS_ATTENTION = "needs_attention"


@dataclass(frozen=True, slots=True)
class FlowDispatchResult:
    status: DispatchStatus
    node_id: str
    reason: str
    attempts: int = 0


class HabitRegistry:
    """Exact-version registry. It never substitutes the latest version."""

    def __init__(self, habits: Iterable[MachineHabit] = ()) -> None:
        self._items: dict[tuple[str, int], MachineHabit] = {}
        for habit in habits:
            self.register(habit)

    def register(self, habit: MachineHabit) -> None:
        key = (habit.habit_id, habit.version)
        existing = self._items.get(key)
        if existing is not None and existing != habit:
            raise ValueError("immutable habit version already registered with different content")
        self._items[key] = habit

    def get(self, habit_id: str, version: int) -> MachineHabit:
        try:
            return self._items[(habit_id, version)]
        except KeyError as exc:
            raise KeyError(f"machine habit version not found: {habit_id}@{version}") from exc


class FlowWorker:
    """Dispatch exactly one flow node per call through the configured harness."""

    _TERMINAL = frozenset({
        FlowStatus.SUCCEEDED, FlowStatus.FAILED, FlowStatus.CANCELLED,
        FlowStatus.NEEDS_ATTENTION,
    })
    _SAFE_RETRY_EFFECTS = frozenset({
        OperationEffect.READ_ONLY, OperationEffect.IDEMPOTENT,
        OperationEffect.DEDUPLICATED,
    })

    def __init__(
        self,
        harness: HarnessAdapter,
        habit_registry: HabitRegistry | None = None,
        approved_operations: frozenset[str] = frozenset(),
    ) -> None:
        self.harness = harness
        self.habits = habit_registry or HabitRegistry()
        self.approved_operations = frozenset(approved_operations)

    def dispatch(self, flow: PersistentFlow) -> FlowDispatchResult:
        snapshot = flow.snapshot
        node = flow.current_node
        if snapshot.status in self._TERMINAL:
            return FlowDispatchResult(DispatchStatus.TERMINAL, node.node_id, snapshot.status.value)
        if snapshot.status is FlowStatus.PAUSED:
            return FlowDispatchResult(DispatchStatus.PAUSED, node.node_id, "awaiting_resume")
        if snapshot.status is FlowStatus.WAITING:
            return FlowDispatchResult(DispatchStatus.WAITING, node.node_id, "waiting_for_release")
        if snapshot.status is not FlowStatus.RUNNING:
            return self._attention(flow, "flow_not_ready")

        if node.kind is FlowNodeKind.BRANCH:
            flow.resolve_branch()
            return self._result_after_transition(flow, node.node_id, "branch_resolved")
        if node.kind is FlowNodeKind.WAIT:
            return FlowDispatchResult(DispatchStatus.WAITING, node.node_id, "waiting_for_release")
        if node.kind is FlowNodeKind.END:
            return self._attention(flow, "terminal_node_not_settled")
        if node.kind is FlowNodeKind.OPERATION:
            return self._dispatch_operation(flow)
        if node.kind is FlowNodeKind.HABIT:
            return self._dispatch_habit(flow)
        return self._attention(flow, "unsupported_flow_node")

    def _dispatch_operation(self, flow: PersistentFlow) -> FlowDispatchResult:
        node = flow.current_node
        profile = self.harness.profile
        if node.target_ref not in profile.allowed_operations:
            return self._attention(flow, "operation_not_allowed")
        if node.target_ref in profile.approval_required and node.target_ref not in self.approved_operations:
            flow.pause("approval_required")
            return FlowDispatchResult(DispatchStatus.PAUSED, node.node_id, "approval_required")
        if node.max_attempts > profile.max_step_attempts:
            return self._attention(flow, "harness_attempt_limit_exceeded")
        if node.effect is OperationEffect.COMPENSATABLE:
            return self._attention(flow, "compensation_adapter_not_implemented")

        inputs, missing = self._resolve_inputs(node.input_bindings, flow)
        if missing:
            return self._attention(flow, "input_binding_missing:" + ",".join(missing))

        operation = OperationStep(
            operation_ref=node.target_ref,
            effect=node.effect,
            max_attempts=node.max_attempts,
            input_bindings=node.input_bindings,
            idempotency_key_supported=node.idempotency_key_supported,
            compensation_ref=node.compensation_ref,
        )
        try:
            result = self.harness.invoke(
                operation, inputs, idempotency_key=flow.idempotency_key
            )
        except Exception as exc:
            flow.mark_outcome_unknown(
                "harness_adapter_exception",
                metadata={
                    "operation_ref": node.target_ref,
                    "exception_type": type(exc).__name__,
                    "idempotency_key": flow.idempotency_key,
                },
            )
            return self._result_after_transition(flow, node.node_id, "operation_outcome_unknown")

        metadata = {
            "operation_ref": node.target_ref,
            "idempotency_key": flow.idempotency_key,
            "duration_ms": str(result.duration_ms),
            "resource_units": str(result.resource_units),
            "external_cost": str(result.external_cost),
            "attempt": str(flow.snapshot.attempt_count(node.node_id) + 1),
        }
        if result.outcome is OperationOutcome.UNKNOWN:
            flow.mark_outcome_unknown(
                result.error_code or "operation_outcome_unknown", metadata=metadata
            )
            return self._result_after_transition(flow, node.node_id, "operation_outcome_unknown")
        if result.outcome is OperationOutcome.FAILED:
            flow.fail_step(result.error_code or "operation_failed", metadata=metadata)
            return self._result_after_transition(flow, node.node_id, "operation_failed")

        outputs = dict(result.outputs)
        merged = flow.snapshot.context_dict()
        merged.update(outputs)
        failed = [key for key, expected in node.postconditions if merged.get(key) != expected]
        if failed:
            flow.needs_attention(
                "postconditions_not_satisfied",
                evidence=outputs,
                metadata={**metadata, "failed_postconditions": ",".join(failed)},
            )
            return self._result_after_transition(flow, node.node_id, "postconditions_not_satisfied")
        flow.succeed_step(outputs, metadata)
        return self._result_after_transition(flow, node.node_id, "operation_succeeded")

    def _dispatch_habit(self, flow: PersistentFlow) -> FlowDispatchResult:
        node = flow.current_node
        try:
            habit = self.habits.get(node.target_ref or "", node.target_version or 0)
        except KeyError:
            return self._attention(flow, "pinned_habit_version_not_found")
        if habit.lifecycle is not MachineHabitStatus.ACTIVE:
            return self._attention(flow, "pinned_habit_not_active")

        # Check approval before any operation in the multi-step habit can run.
        for operation in habit.operations:
            if (
                operation.operation_ref in self.harness.profile.approval_required
                and operation.operation_ref not in self.approved_operations
            ):
                flow.pause("approval_required")
                return FlowDispatchResult(DispatchStatus.PAUSED, node.node_id, "approval_required")
        authorization = authorize_machine_habit(
            habit, self.harness.profile, flow.snapshot.context_dict(), self.approved_operations
        )
        if not authorization.eligible:
            if authorization.requires_approval:
                flow.pause("approval_required")
                return FlowDispatchResult(DispatchStatus.PAUSED, node.node_id, authorization.reason)
            return self._attention(flow, authorization.reason)

        run_key = flow.idempotency_key
        result = execute_machine_habit(
            habit, self.harness, flow.snapshot.context_dict(),
            run_id=run_key, approved_operations=self.approved_operations,
        )
        metadata = {
            "habit_id": habit.habit_id,
            "habit_version": str(habit.version),
            "operation_count": str(len(result.records)),
            "duration_ms": str(result.total_duration_ms),
            "resource_units": str(result.total_resource_units),
            "habit_idempotency_scope": run_key,
        }
        outputs = dict(result.final_state)
        if result.status is MachineExecutionStatus.SUCCEEDED:
            merged = flow.snapshot.context_dict()
            merged.update(outputs)
            failed = [key for key, expected in node.postconditions if merged.get(key) != expected]
            if failed:
                flow.needs_attention(
                    "flow_habit_postconditions_not_satisfied",
                    evidence=outputs,
                    metadata={**metadata, "failed_postconditions": ",".join(failed)},
                )
                return self._result_after_transition(flow, node.node_id, "postconditions_not_satisfied")
            flow.succeed_step(outputs, metadata)
            return self._result_after_transition(flow, node.node_id, "habit_succeeded")

        if result.status is MachineExecutionStatus.HANDOFF and result.reason == "approval_required":
            flow.pause("approval_required")
            return FlowDispatchResult(DispatchStatus.PAUSED, node.node_id, result.reason)

        if result.status is MachineExecutionStatus.FAILED:
            if all(operation.effect in self._SAFE_RETRY_EFFECTS for operation in habit.operations):
                flow.fail_step(result.reason, metadata)
                return self._result_after_transition(flow, node.node_id, "habit_failed_retryable")
            flow.needs_attention(result.reason, evidence=outputs, metadata=metadata)
            return self._result_after_transition(flow, node.node_id, "habit_failed_not_safely_retryable")

        flow.needs_attention(result.reason, evidence=outputs, metadata=metadata)
        return self._result_after_transition(flow, node.node_id, "habit_needs_attention")

    @staticmethod
    def _resolve_inputs(bindings, flow: PersistentFlow) -> tuple[dict[str, str], tuple[str, ...]]:
        context = flow.snapshot.context_dict()
        resolved: dict[str, str] = {}
        missing: list[str] = []
        for name, source in bindings:
            if source.startswith("$state."):
                key = source[len("$state."):]
                if key not in context:
                    missing.append(key)
                else:
                    resolved[name] = context[key]
            else:
                resolved[name] = source
        return resolved, tuple(missing)

    @staticmethod
    def _result_after_transition(
        flow: PersistentFlow, node_id: str, reason: str,
    ) -> FlowDispatchResult:
        status = flow.snapshot.status
        if status is FlowStatus.NEEDS_ATTENTION:
            return FlowDispatchResult(DispatchStatus.NEEDS_ATTENTION, node_id, reason)
        if status in FlowWorker._TERMINAL:
            return FlowDispatchResult(DispatchStatus.TERMINAL, node_id, reason)
        if status is FlowStatus.WAITING:
            return FlowDispatchResult(DispatchStatus.WAITING, node_id, reason)
        if status is FlowStatus.PAUSED:
            return FlowDispatchResult(DispatchStatus.PAUSED, node_id, reason)
        return FlowDispatchResult(
            DispatchStatus.ADVANCED, node_id, reason,
            flow.snapshot.attempt_count(node_id),
        )

    @staticmethod
    def _attention(flow: PersistentFlow, reason: str) -> FlowDispatchResult:
        node_id = flow.snapshot.current_node
        flow.needs_attention(reason)
        return FlowDispatchResult(DispatchStatus.NEEDS_ATTENTION, node_id, reason)
