"""Persistent worker with per-provider-operation intent/result checkpoints.

A journaled intent always precedes an external invocation. After restart, only
read-only, idempotent, or provider-deduplicated pending operations may be retried
automatically. Ambiguous non-repeatable effects require evidence-backed reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping

from .flows import (
    FlowNodeKind,
    FlowStatus,
    OperationCheckpoint,
    PersistentFlow,
)
from .machine import (
    HarnessAdapter,
    MachineHabit,
    MachineHabitStatus,
    OperationEffect,
    OperationOutcome,
    OperationStep,
    authorize_machine_habit,
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
    _SAFE_RECOVERY_EFFECTS = frozenset({
        OperationEffect.READ_ONLY,
        OperationEffect.IDEMPOTENT,
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
        if snapshot.status is FlowStatus.NEEDS_ATTENTION:
            return FlowDispatchResult(DispatchStatus.NEEDS_ATTENTION, node.node_id, snapshot.status.value)
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

    @staticmethod
    def _input_digest(inputs: Mapping[str, str]) -> str:
        canonical = json.dumps(
            dict(sorted(inputs.items())), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def _recovery_is_safe(cls, effect: OperationEffect, key_supported: bool) -> bool:
        if effect is OperationEffect.DEDUPLICATED:
            return key_supported
        return effect in (OperationEffect.READ_ONLY, OperationEffect.IDEMPOTENT)

    def _pending_for(
        self, flow: PersistentFlow, *, operation_index: int, operation: OperationStep,
        idempotency_key: str, inputs: Mapping[str, str],
    ):
        pending = flow.snapshot.pending_operation
        if pending is None:
            return None
        if (
            pending.operation_index != operation_index
            or pending.operation_ref != operation.operation_ref
            or pending.effect is not operation.effect
            or pending.idempotency_key != idempotency_key
            or pending.input_sha256 != self._input_digest(inputs)
            or pending.idempotency_key_supported != operation.idempotency_key_supported
            or (pending.harness_id, pending.harness_version,
                pending.environment_id, pending.context_id) != (
                self.harness.profile.harness_id, self.harness.profile.version,
                self.harness.profile.environment_id, self.harness.profile.context_id,
            )
        ):
            self._attention(flow, "pending_operation_does_not_match_pinned_step")
            return False
        if not self._recovery_is_safe(pending.effect, pending.idempotency_key_supported):
            flow.mark_operation_outcome_unknown(
                "recovered_pending_non_repeatable_operation_requires_reconciliation",
                metadata={"operation_ref": pending.operation_ref,
                          "idempotency_key": pending.idempotency_key,
                          "attempt": str(pending.attempt)},
            )
            return False
        return pending

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

        operation = OperationStep(
            operation_ref=node.target_ref or "",
            effect=node.effect,
            max_attempts=node.max_attempts,
            input_bindings=node.input_bindings,
            idempotency_key_supported=node.idempotency_key_supported,
            compensation_ref=node.compensation_ref,
        )
        inputs, missing = self._resolve_inputs(operation.input_bindings, flow)
        if missing:
            return self._attention(flow, "input_binding_missing:" + ",".join(missing))

        completed = flow.snapshot.completed_operation(0)
        if completed is not None:
            return self._finish_operation_node(flow, node.node_id, completed)

        key = flow.operation_scope_key
        pending = self._pending_for(
            flow, operation_index=0, operation=operation,
            idempotency_key=key, inputs=inputs,
        )
        if pending is False:
            return self._result_after_transition(
                flow, node.node_id, "pending_operation_requires_attention"
            )

        attempt = (
            pending.attempt if pending is not None
            else flow.snapshot.operation_attempt_count(0) + 1
        )
        if attempt > node.max_attempts:
            flow.fail_step("operation_attempt_limit_exhausted", {
                "operation_ref": operation.operation_ref,
            })
            return self._result_after_transition(flow, node.node_id, "operation_attempt_limit_exhausted")

        if pending is None:
            flow.begin_operation(
                operation_index=0, operation_ref=operation.operation_ref,
                effect=operation.effect, idempotency_key=key, attempt=attempt,
                input_sha256=self._input_digest(inputs),
                harness_id=profile.harness_id, harness_version=profile.version,
                environment_id=profile.environment_id, context_id=profile.context_id,
                idempotency_key_supported=operation.idempotency_key_supported,
            )

        try:
            result = self.harness.invoke(operation, inputs, idempotency_key=key)
        except Exception as exc:
            flow.mark_operation_outcome_unknown(
                "harness_adapter_exception",
                metadata={"operation_ref": operation.operation_ref,
                          "exception_type": type(exc).__name__,
                          "idempotency_key": key, "attempt": str(attempt)},
            )
            return self._result_after_transition(flow, node.node_id, "operation_outcome_unknown")

        metadata = {
            "operation_ref": operation.operation_ref,
            "idempotency_key": key,
            "attempt": str(attempt),
        }
        if result.outcome is OperationOutcome.UNKNOWN:
            flow.mark_operation_outcome_unknown(
                result.error_code or "operation_outcome_unknown", metadata=metadata
            )
            return self._result_after_transition(flow, node.node_id, "operation_outcome_unknown")
        if result.outcome is OperationOutcome.FAILED:
            flow.fail_operation(result.error_code or "operation_failed", metadata)
            flow.fail_step(result.error_code or "operation_failed", metadata)
            return self._result_after_transition(flow, node.node_id, "operation_failed")

        flow.succeed_operation(
            dict(result.outputs), duration_ms=result.duration_ms,
            resource_units=result.resource_units, external_cost=result.external_cost,
        )
        checkpoint = flow.snapshot.completed_operation(0)
        assert checkpoint is not None
        return self._finish_operation_node(flow, node.node_id, checkpoint)

    def _finish_operation_node(
        self, flow: PersistentFlow, node_id: str, checkpoint: OperationCheckpoint,
    ) -> FlowDispatchResult:
        node = flow.current_node
        state = flow.snapshot.context_dict()
        failed = [key for key, expected in node.postconditions if state.get(key) != expected]
        if failed:
            flow.needs_attention(
                "postconditions_not_satisfied",
                metadata={
                    "operation_ref": checkpoint.operation_ref,
                    "failed_postconditions": ",".join(failed),
                    "operation_checkpointed": "true",
                },
            )
            return self._result_after_transition(flow, node_id, "postconditions_not_satisfied")
        flow.succeed_step(metadata={
            "operation_ref": checkpoint.operation_ref,
            "idempotency_key": checkpoint.idempotency_key,
            "attempt": str(checkpoint.attempt),
            **self._checkpoint_cost_metadata((checkpoint,)),
        })
        return self._result_after_transition(flow, node_id, "operation_succeeded")

    def _dispatch_habit(self, flow: PersistentFlow) -> FlowDispatchResult:
        node = flow.current_node
        try:
            habit = self.habits.get(node.target_ref or "", node.target_version or 0)
        except KeyError:
            return self._attention(flow, "pinned_habit_version_not_found")
        if habit.lifecycle is not MachineHabitStatus.ACTIVE:
            return self._attention(flow, "pinned_habit_not_active")

        progressing = bool(flow.snapshot.completed_operations or flow.snapshot.pending_operation)
        if progressing:
            authorization = self._authorize_habit_resume(habit)
            if authorization is not None:
                return self._attention(flow, authorization)
        else:
            authorization = authorize_machine_habit(
                habit, self.harness.profile, flow.snapshot.context_dict(),
                self.approved_operations,
            )
            if not authorization.eligible:
                if authorization.requires_approval:
                    flow.pause("approval_required")
                    return FlowDispatchResult(DispatchStatus.PAUSED, node.node_id, authorization.reason)
                return self._attention(flow, authorization.reason)

        # Approval is checked for the complete sequence before any operation runs.
        for operation in habit.operations:
            if (
                operation.operation_ref in self.harness.profile.approval_required
                and operation.operation_ref not in self.approved_operations
            ):
                flow.pause("approval_required")
                return FlowDispatchResult(DispatchStatus.PAUSED, node.node_id, "approval_required")

        for index, operation in enumerate(habit.operations):
            if flow.snapshot.completed_operation(index) is not None:
                continue

            if operation.effect is OperationEffect.COMPENSATABLE:
                return self._attention(flow, "compensation_adapter_not_implemented")

            inputs, missing = self._resolve_inputs(operation.input_bindings, flow)
            if missing:
                return self._attention(flow, "input_binding_missing:" + ",".join(missing))

            key = f"{flow.operation_scope_key}:{habit.habit_id}:{habit.version}:{index}"
            pending = self._pending_for(
                flow, operation_index=index, operation=operation,
                idempotency_key=key, inputs=inputs,
            )
            if pending is False:
                return self._result_after_transition(
                    flow, node.node_id, "pending_operation_requires_attention"
                )

            attempt_limit = min(operation.max_attempts, self.harness.profile.max_step_attempts)
            attempt = (
                pending.attempt if pending is not None
                else flow.snapshot.operation_attempt_count(index) + 1
            )
            if attempt > attempt_limit:
                flow.fail_step("operation_attempt_limit_exhausted", {
                    "habit_id": habit.habit_id, "operation_ref": operation.operation_ref,
                    "operation_index": str(index),
                })
                return self._result_after_transition(flow, node.node_id, "operation_attempt_limit_exhausted")

            while attempt <= attempt_limit:
                if flow.snapshot.pending_operation is None:
                    flow.begin_operation(
                        operation_index=index, operation_ref=operation.operation_ref,
                        effect=operation.effect, idempotency_key=key, attempt=attempt,
                        input_sha256=self._input_digest(inputs),
                        harness_id=self.harness.profile.harness_id,
                        harness_version=self.harness.profile.version,
                        environment_id=self.harness.profile.environment_id,
                        context_id=self.harness.profile.context_id,
                        idempotency_key_supported=operation.idempotency_key_supported,
                    )
                try:
                    result = self.harness.invoke(operation, inputs, idempotency_key=key)
                except Exception as exc:
                    flow.mark_operation_outcome_unknown(
                        "harness_adapter_exception",
                        metadata={"habit_id": habit.habit_id,
                                  "operation_ref": operation.operation_ref,
                                  "operation_index": str(index),
                                  "exception_type": type(exc).__name__,
                                  "idempotency_key": key, "attempt": str(attempt)},
                    )
                    return self._result_after_transition(flow, node.node_id, "operation_outcome_unknown")

                operation_metadata = {
                    "habit_id": habit.habit_id,
                    "operation_ref": operation.operation_ref,
                    "operation_index": str(index),
                    "idempotency_key": key,
                    "attempt": str(attempt),
                }
                if result.outcome is OperationOutcome.UNKNOWN:
                    flow.mark_operation_outcome_unknown(
                        result.error_code or "operation_outcome_unknown",
                        metadata=operation_metadata,
                    )
                    return self._result_after_transition(flow, node.node_id, "operation_outcome_unknown")
                if result.outcome is OperationOutcome.FAILED:
                    flow.fail_operation(result.error_code or "operation_failed", operation_metadata)
                    retry_safe = self._recovery_is_safe(
                        operation.effect, operation.idempotency_key_supported
                    )
                    if retry_safe and attempt < attempt_limit:
                        attempt += 1
                        continue
                    flow.fail_step(result.error_code or "operation_failed", {
                        **operation_metadata,
                        "operation_count": str(len(flow.snapshot.completed_operations)),
                    })
                    return self._result_after_transition(flow, node.node_id, "habit_operation_failed")

                flow.succeed_operation(
                    dict(result.outputs), duration_ms=result.duration_ms,
                    resource_units=result.resource_units, external_cost=result.external_cost,
                )
                break

        # Every operation result is now durably checkpointed; final node completion is separate.
        state = flow.snapshot.context_dict()
        failed_habit = [
            condition.key for condition in habit.postconditions
            if not condition.matches(state)
        ]
        failed_node = [
            key for key, expected in node.postconditions if state.get(key) != expected
        ]
        if failed_habit or failed_node:
            flow.needs_attention(
                "habit_postconditions_not_satisfied",
                metadata={
                    "habit_id": habit.habit_id,
                    "failed_habit_postconditions": ",".join(failed_habit),
                    "failed_flow_postconditions": ",".join(failed_node),
                },
            )
            return self._result_after_transition(flow, node.node_id, "postconditions_not_satisfied")

        checkpoints = tuple(sorted(
            flow.snapshot.completed_operations, key=lambda item: item.operation_index
        ))
        flow.succeed_step(metadata={
            "habit_id": habit.habit_id,
            "habit_version": str(habit.version),
            "operation_count": str(len(checkpoints)),
            **self._checkpoint_cost_metadata(checkpoints),
            "habit_idempotency_scope": flow.operation_scope_key,
        })
        return self._result_after_transition(flow, node.node_id, "habit_succeeded")

    def _authorize_habit_resume(self, habit: MachineHabit) -> str | None:
        """Recheck static scope/authority without re-evaluating consumed start predicates."""
        profile = self.harness.profile
        if (habit.harness_id, habit.harness_version) != (profile.harness_id, profile.version):
            return "harness_version_mismatch"
        if (habit.environment_id, habit.context_id) != (profile.environment_id, profile.context_id):
            return "environment_scope_mismatch"
        if not habit.efficiency.accepted:
            return habit.efficiency.reason
        for operation in habit.operations:
            if operation.operation_ref not in profile.allowed_operations:
                return "operation_not_allowed"
            if operation.max_attempts > profile.max_step_attempts:
                return "harness_attempt_limit_exceeded"
            if operation.effect is OperationEffect.COMPENSATABLE and not profile.supports_compensation:
                return "harness_lacks_compensation_support"
        return None

    @staticmethod
    def _checkpoint_cost_metadata(
        checkpoints: tuple[OperationCheckpoint, ...],
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for field, label in (
            ("duration_ms", "duration_ms"),
            ("resource_units", "resource_units"),
            ("external_cost", "external_cost"),
        ):
            values = [getattr(item, field) for item in checkpoints]
            result[label] = (
                str(sum(value for value in values if value is not None))
                if all(value is not None for value in values)
                else "unknown"
            )
        result["cost_observations_complete"] = str(all(
            getattr(item, field) is not None
            for item in checkpoints
            for field in ("duration_ms", "resource_units", "external_cost")
        )).lower()
        return result

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
            return FlowDispatchResult(DispatchStatus.NEEDS_ATTENTION, node_id, reason,
                                      flow.snapshot.attempt_count(node_id))
        if status in FlowWorker._TERMINAL:
            return FlowDispatchResult(DispatchStatus.TERMINAL, node_id, reason,
                                      flow.snapshot.attempt_count(node_id))
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
