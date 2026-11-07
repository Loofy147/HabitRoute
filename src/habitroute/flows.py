"""Event-sourced persistent flow definitions and local JSONL journal.

The journal provides durable local event append/replay with a single-writer-per-run
contract. It does not make external side effects exactly-once.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
import math
import os
from pathlib import Path
import re
import threading
from typing import Mapping, Protocol
from uuid import uuid4

from .machine import OperationEffect


class FlowNodeKind(str, Enum):
    OPERATION = "operation"
    HABIT = "habit"
    BRANCH = "branch"
    WAIT = "wait"
    END = "end"


class FlowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_ATTENTION = "needs_attention"


_TERMINAL = frozenset({
    FlowStatus.SUCCEEDED, FlowStatus.FAILED, FlowStatus.CANCELLED,
    FlowStatus.NEEDS_ATTENTION,
})


class FlowEventKind(str, Enum):
    STARTED = "started"
    STEP_SUCCEEDED = "step_succeeded"
    STEP_FAILED = "step_failed"
    STEP_OUTCOME_UNKNOWN = "step_outcome_unknown"
    BRANCH_RESOLVED = "branch_resolved"
    WAIT_RELEASED = "wait_released"
    PAUSED = "paused"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    NEEDS_ATTENTION = "needs_attention"
    OPERATION_INTENT = "operation_intent"
    OPERATION_SUCCEEDED = "operation_succeeded"
    OPERATION_FAILED = "operation_failed"
    OPERATION_OUTCOME_UNKNOWN = "operation_outcome_unknown"
    OPERATION_RECONCILED = "operation_reconciled"


@dataclass(frozen=True, slots=True)
class FlowNode:
    node_id: str
    kind: FlowNodeKind
    target_ref: str | None = None
    next_on_success: str | None = None
    next_on_failure: str | None = None
    max_attempts: int = 1
    effect: OperationEffect = OperationEffect.READ_ONLY
    idempotency_key_supported: bool = False
    compensation_ref: str | None = None
    branch_key: str | None = None
    branch_equals: str | None = None
    next_on_true: str | None = None
    next_on_false: str | None = None
    target_version: int | None = None
    end_status: FlowStatus = FlowStatus.SUCCEEDED
    input_bindings: tuple[tuple[str, str], ...] = ()
    postconditions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_bindings", tuple(sorted(self.input_bindings)))
        object.__setattr__(self, "postconditions", tuple(sorted(self.postconditions)))
        input_keys = [key for key, _ in self.input_bindings]
        condition_keys = [key for key, _ in self.postconditions]
        if len(input_keys) != len(set(input_keys)) or any(not key.strip() for key in input_keys):
            raise ValueError("flow node input bindings must have unique non-empty keys")
        if len(condition_keys) != len(set(condition_keys)) or any(not key.strip() for key in condition_keys):
            raise ValueError("flow node postconditions must have unique non-empty keys")
        if not self.node_id.strip():
            raise ValueError("flow node ID must be non-empty")
        if self.kind in (FlowNodeKind.OPERATION, FlowNodeKind.HABIT):
            if not self.target_ref or not self.target_ref.strip():
                raise ValueError("operation/habit nodes require target_ref")
            if self.kind is FlowNodeKind.HABIT and (
                self.target_version is None or self.target_version < 1
            ):
                raise ValueError("habit nodes must pin a positive machine-habit version")
            if self.kind is FlowNodeKind.OPERATION and self.target_version is not None:
                raise ValueError("operation nodes cannot carry a habit version")
            if not self.next_on_success:
                raise ValueError("operation/habit nodes require next_on_success")
            if self.max_attempts < 1:
                raise ValueError("max_attempts must be at least one")
            if self.effect is OperationEffect.NON_REPEATABLE and self.max_attempts > 1:
                raise ValueError("non-repeatable flow steps cannot be automatically retried")
            if self.effect is OperationEffect.DEDUPLICATED and not self.idempotency_key_supported:
                raise ValueError("deduplicated flow steps require idempotency-key support")
            if self.effect is OperationEffect.COMPENSATABLE and not (
                self.compensation_ref and self.compensation_ref.strip()
            ):
                raise ValueError("compensatable flow steps require compensation_ref")
        elif self.kind is FlowNodeKind.BRANCH:
            if not self.branch_key or not self.branch_key.strip() or self.branch_equals is None:
                raise ValueError("branch nodes require branch_key and branch_equals")
            if not self.next_on_true or not self.next_on_false:
                raise ValueError("branch nodes require true and false destinations")
        elif self.kind is FlowNodeKind.WAIT:
            if not self.next_on_success:
                raise ValueError("wait nodes require next_on_success")
        elif self.kind is FlowNodeKind.END:
            if self.end_status not in (
                FlowStatus.SUCCEEDED, FlowStatus.FAILED, FlowStatus.NEEDS_ATTENTION
            ):
                raise ValueError("end_status must be succeeded, failed or needs_attention")
            if any((self.next_on_success, self.next_on_failure, self.next_on_true, self.next_on_false)):
                raise ValueError("terminal nodes cannot have outgoing edges")


@dataclass(frozen=True, slots=True)
class FlowDefinition:
    flow_id: str
    version: int
    start_node: str
    nodes: tuple[FlowNode, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        if not self.flow_id.strip() or self.version < 1 or not self.start_node.strip():
            raise ValueError("flow identity, positive version and start node are required")
        ids = [node.node_id for node in self.nodes]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("flow nodes must be non-empty with unique IDs")
        if self.start_node not in set(ids):
            raise ValueError("start_node does not exist")
        known = set(ids)
        for node in self.nodes:
            for edge in (node.next_on_success, node.next_on_failure, node.next_on_true, node.next_on_false):
                if edge is not None and edge not in known:
                    raise ValueError(f"node {node.node_id} references unknown destination {edge}")

    def node(self, node_id: str) -> FlowNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)


@dataclass(frozen=True, slots=True)
class FlowEvent:
    run_id: str
    sequence: int
    event_id: str
    kind: FlowEventKind
    node_id: str | None = None
    payload: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", tuple(sorted(self.payload)))
        if not self.run_id.strip() or self.sequence < 1 or not self.event_id.strip():
            raise ValueError("flow event requires run ID, positive sequence and event ID")
        if len({key for key, _ in self.payload}) != len(self.payload):
            raise ValueError("flow event payload keys must be unique")

    def to_json(self) -> str:
        return json.dumps({
            "run_id": self.run_id,
            "sequence": self.sequence,
            "event_id": self.event_id,
            "kind": self.kind.value,
            "node_id": self.node_id,
            "payload": list(self.payload),
        }, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "FlowEvent":
        data = json.loads(raw)
        return cls(
            run_id=str(data["run_id"]),
            sequence=int(data["sequence"]),
            event_id=str(data["event_id"]),
            kind=FlowEventKind(data["kind"]),
            node_id=data.get("node_id"),
            payload=tuple((str(k), str(v)) for k, v in data.get("payload", [])),
        )


@dataclass(frozen=True, slots=True)
class OperationIntent:
    operation_index: int
    operation_ref: str
    effect: OperationEffect
    idempotency_key: str
    attempt: int
    input_sha256: str
    harness_id: str
    harness_version: str
    environment_id: str
    context_id: str
    idempotency_key_supported: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect", OperationEffect(self.effect))
        if self.operation_index < 0 or self.attempt < 1:
            raise ValueError("operation index must be non-negative and attempt positive")
        if not self.operation_ref.strip() or not self.idempotency_key.strip():
            raise ValueError("operation reference and idempotency key must be non-empty")
        for name in ("harness_id", "harness_version", "environment_id", "context_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if len(self.input_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.input_sha256.lower()
        ):
            raise ValueError("input_sha256 must be a SHA-256 hex digest")
        if self.effect is OperationEffect.DEDUPLICATED and not self.idempotency_key_supported:
            raise ValueError("deduplicated operations require idempotency-key support")


@dataclass(frozen=True, slots=True)
class OperationCheckpoint:
    operation_index: int
    operation_ref: str
    effect: OperationEffect
    idempotency_key: str
    attempt: int
    input_sha256: str
    harness_id: str
    harness_version: str
    environment_id: str
    context_id: str
    duration_ms: float | None
    resource_units: float | None
    external_cost: float | None
    outputs: tuple[tuple[str, str], ...] = ()
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect", OperationEffect(self.effect))
        object.__setattr__(self, "outputs", tuple(sorted(self.outputs)))
        if self.operation_index < 0 or self.attempt < 1:
            raise ValueError("checkpoint operation index must be non-negative and attempt positive")
        if not self.operation_ref.strip() or not self.idempotency_key.strip():
            raise ValueError("checkpoint operation reference and key must be non-empty")
        for name in ("harness_id", "harness_version", "environment_id", "context_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if len(self.input_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.input_sha256.lower()
        ):
            raise ValueError("checkpoint input_sha256 must be a SHA-256 hex digest")
        for name in ("duration_ms", "resource_units", "external_cost"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be non-negative or None")


@dataclass(frozen=True, slots=True)
class FlowSnapshot:
    run_id: str
    flow_id: str
    definition_version: int
    current_node: str
    status: FlowStatus
    context: tuple[tuple[str, str], ...] = ()
    attempts: tuple[tuple[str, int], ...] = ()
    completed_nodes: tuple[str, ...] = ()
    last_event_sequence: int = 0
    applied_event_ids: tuple[str, ...] = ()
    resume_status: FlowStatus | None = None
    pending_operation: OperationIntent | None = None
    completed_operations: tuple[OperationCheckpoint, ...] = ()
    operation_attempts: tuple[tuple[int, int], ...] = ()
    node_visits: tuple[tuple[str, int], ...] = ()

    @classmethod
    def initial(
        cls, definition: FlowDefinition, run_id: str,
        initial_context: Mapping[str, str] | None = None,
    ) -> "FlowSnapshot":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
            raise ValueError("run_id must be a safe 1-128 character identifier")
        return cls(
            run_id=run_id, flow_id=definition.flow_id,
            definition_version=definition.version, current_node=definition.start_node,
            status=FlowStatus.CREATED,
            context=tuple(sorted((initial_context or {}).items())),
            node_visits=((definition.start_node, 1),),
        )

    def context_dict(self) -> dict[str, str]:
        return dict(self.context)

    def attempt_count(self, node_id: str) -> int:
        return dict(self.attempts).get(node_id, 0)

    def operation_attempt_count(self, operation_index: int) -> int:
        return dict(self.operation_attempts).get(operation_index, 0)

    def completed_operation(self, operation_index: int) -> OperationCheckpoint | None:
        for checkpoint in self.completed_operations:
            if checkpoint.operation_index == operation_index:
                return checkpoint
        return None

    def node_visit_count(self, node_id: str) -> int:
        return dict(self.node_visits).get(node_id, 0)

    def operation_scope_key(self) -> str:
        """Unique scope for this node visit; stable across its retries and replay."""
        return (
            f"{self.idempotency_key()}:visit:{self.node_visit_count(self.current_node)}"
        )

    def idempotency_key(self) -> str:
        """Legacy run/node scope; prefer operation_scope_key for external calls."""
        return f"{self.run_id}:{self.flow_id}:{self.definition_version}:{self.current_node}"


def _validate_output_keys(outputs: Mapping[str, str]) -> None:
    if any(key.startswith(("$meta.", "$op.")) for key in outputs):
        raise ValueError("flow outputs cannot use reserved journal namespaces")


class FlowJournal(Protocol):
    def append(self, event: FlowEvent) -> None: ...
    def load(self, run_id: str) -> tuple[FlowEvent, ...]: ...


class JsonlFlowJournal:
    """Local append-only journal. Use one writer per run_id."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
            raise ValueError("unsafe run_id")
        return self.root / f"{run_id}.jsonl"

    def _truncate_unterminated_tail(self, path: Path) -> bool:
        """Remove only a final record lacking its newline commit delimiter.

        The worker invokes a provider only after append() has written the newline
        and fsynced it. Therefore an unterminated tail is an append that never
        returned successfully and is safe to discard. Newline-terminated corrupt
        records are not silently repaired.
        """
        if not path.exists() or path.stat().st_size == 0:
            return False
        with path.open("rb") as handle:
            handle.seek(-1, os.SEEK_END)
            if handle.read(1) == b"\n":
                return False
            handle.seek(0)
            raw = handle.read()
        last_delimiter = raw.rfind(b"\n")
        valid_length = last_delimiter + 1
        fd = os.open(path, os.O_WRONLY)
        try:
            os.ftruncate(fd, valid_length)
            os.fsync(fd)
        finally:
            os.close(fd)
        return True

    def load(self, run_id: str) -> tuple[FlowEvent, ...]:
        path = self._path(run_id)
        if not path.exists():
            return ()
        self._truncate_unterminated_tail(path)
        events: list[FlowEvent] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    event = FlowEvent.from_json(line)
                except Exception as exc:
                    raise ValueError(f"corrupt flow journal at line {line_number}") from exc
                if event.run_id != run_id:
                    raise ValueError(f"journal run_id mismatch at line {line_number}")
                expected = len(events) + 1
                if event.sequence != expected:
                    raise ValueError(f"journal sequence gap at line {line_number}")
                events.append(event)
        return tuple(events)

    def append(self, event: FlowEvent) -> None:
        with self._lock:
            path = self._path(event.run_id)
            existing = self.load(event.run_id)
            for prior in existing:
                if prior.event_id == event.event_id:
                    if prior == event:
                        return
                    raise ValueError("event_id reused with different event content")
            expected = len(existing) + 1
            if event.sequence != expected:
                raise ValueError(f"expected event sequence {expected}, got {event.sequence}")
            payload = (event.to_json() + "\n").encode("utf-8")
            file_was_absent = not path.exists()
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                view = memoryview(payload)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise OSError("journal append made no forward progress")
                    view = view[written:]
                # The intent/result line is durable before append returns.
                os.fsync(fd)
            finally:
                os.close(fd)

            # Persist the new directory entry on POSIX before a caller may invoke
            # an external operation based on the just-written intent.
            if file_was_absent and os.name == "posix":
                directory_fd = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)


def _settle_at_node(
    definition: FlowDefinition, snapshot: FlowSnapshot, node_id: str,
) -> FlowSnapshot:
    node = definition.node(node_id)
    # Every settlement begins a new node visit, including explicit self-loops.
    reset_operation_state = True
    visits = dict(snapshot.node_visits)
    visits[node_id] = visits.get(node_id, 0) + 1
    operation_state = (
        {
            "pending_operation": None,
            "completed_operations": (),
            "operation_attempts": (),
        }
        if reset_operation_state else {}
    )
    if node.kind is FlowNodeKind.END:
        return replace(
            snapshot, current_node=node_id, status=node.end_status,
            node_visits=tuple(sorted(visits.items())), **operation_state,
        )
    status = FlowStatus.WAITING if node.kind is FlowNodeKind.WAIT else FlowStatus.RUNNING
    return replace(
        snapshot, current_node=node_id, status=status,
        node_visits=tuple(sorted(visits.items())), **operation_state,
    )


def _pending_operation_from_payload(payload: Mapping[str, str]) -> OperationIntent:
    try:
        return OperationIntent(
            operation_index=int(payload["$op.index"]),
            operation_ref=payload["$op.operation_ref"],
            effect=OperationEffect(payload["$op.effect"]),
            idempotency_key=payload["$op.idempotency_key"],
            attempt=int(payload["$op.attempt"]),
            input_sha256=payload["$op.input_sha256"],
            harness_id=payload["$op.harness_id"],
            harness_version=payload["$op.harness_version"],
            environment_id=payload["$op.environment_id"],
            context_id=payload["$op.context_id"],
            idempotency_key_supported=payload.get("$op.idempotency_key_supported") == "true",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("operation intent payload is invalid") from exc


def _require_pending_match(
    snapshot: FlowSnapshot, event: FlowEvent, payload: Mapping[str, str],
) -> OperationIntent:
    pending = snapshot.pending_operation
    if pending is None or event.node_id != snapshot.current_node:
        raise ValueError("operation result has no matching pending intent")
    try:
        index = int(payload["$op.index"])
        key = payload["$op.idempotency_key"]
    except (KeyError, ValueError) as exc:
        raise ValueError("operation result identity is missing") from exc
    if index != pending.operation_index or key != pending.idempotency_key:
        raise ValueError("operation result does not match the pending intent")
    return pending


def _checkpoint_from_event(
    pending: OperationIntent, payload: Mapping[str, str], *, evidence_ref: str | None = None,
) -> OperationCheckpoint:
    def optional_float(name: str) -> float | None:
        value = payload.get(f"$meta.{name}")
        return None if value is None else float(value)

    outputs = tuple(sorted(
        (key, value) for key, value in payload.items()
        if not key.startswith("$meta.") and not key.startswith("$op.")
    ))
    return OperationCheckpoint(
        operation_index=pending.operation_index,
        operation_ref=pending.operation_ref,
        effect=pending.effect,
        idempotency_key=pending.idempotency_key,
        attempt=pending.attempt,
        input_sha256=pending.input_sha256,
        harness_id=pending.harness_id,
        harness_version=pending.harness_version,
        environment_id=pending.environment_id,
        context_id=pending.context_id,
        duration_ms=optional_float("duration_ms"),
        resource_units=optional_float("resource_units"),
        external_cost=optional_float("external_cost"),
        outputs=outputs,
        evidence_ref=evidence_ref,
    )


def apply_flow_event(
    definition: FlowDefinition, snapshot: FlowSnapshot, event: FlowEvent,
) -> FlowSnapshot:
    """Pure deterministic event reducer; duplicate event IDs are idempotent."""
    if event.run_id != snapshot.run_id:
        raise ValueError("event belongs to another flow run")
    if snapshot.flow_id != definition.flow_id or snapshot.definition_version != definition.version:
        raise ValueError("snapshot is pinned to a different flow definition")
    if event.event_id in snapshot.applied_event_ids:
        return snapshot
    if event.sequence != snapshot.last_event_sequence + 1:
        raise ValueError("flow event sequence is not contiguous")
    if snapshot.status in _TERMINAL and not (
        snapshot.status is FlowStatus.NEEDS_ATTENTION
        and event.kind is FlowEventKind.OPERATION_RECONCILED
    ):
        raise ValueError("cannot apply new events to a terminal flow")
    payload = dict(event.payload)
    updated = snapshot

    if event.kind is FlowEventKind.OPERATION_INTENT:
        if snapshot.status is not FlowStatus.RUNNING or event.node_id != snapshot.current_node:
            raise ValueError("operation intent does not match a running flow node")
        node = definition.node(snapshot.current_node)
        if node.kind not in (FlowNodeKind.OPERATION, FlowNodeKind.HABIT):
            raise ValueError("operation intent requires an operation or habit node")
        if snapshot.pending_operation is not None:
            raise ValueError("another operation intent is already pending")
        intent = _pending_operation_from_payload(payload)
        expected_operation_index = len(snapshot.completed_operations)
        if intent.operation_index != expected_operation_index:
            raise ValueError("operation intent must match the next sequential operation index")
        if snapshot.completed_operation(intent.operation_index) is not None:
            raise ValueError("operation index is already checkpointed")
        if intent.attempt != snapshot.operation_attempt_count(intent.operation_index) + 1:
            raise ValueError("operation attempt is not the next expected attempt")
        if node.kind is FlowNodeKind.OPERATION and (
            intent.operation_index != 0
            or intent.operation_ref != node.target_ref
            or intent.effect is not node.effect
            or intent.idempotency_key_supported != node.idempotency_key_supported
        ):
            raise ValueError("operation intent differs from the pinned flow node")
        attempts = dict(snapshot.operation_attempts)
        attempts[intent.operation_index] = intent.attempt
        updated = replace(
            snapshot, pending_operation=intent,
            operation_attempts=tuple(sorted(attempts.items())),
        )
    elif event.kind is FlowEventKind.OPERATION_SUCCEEDED:
        if snapshot.status is not FlowStatus.RUNNING:
            raise ValueError("operation success requires a running flow")
        pending = _require_pending_match(snapshot, event, payload)
        checkpoint = _checkpoint_from_event(pending, payload)
        context = snapshot.context_dict()
        context.update(dict(checkpoint.outputs))
        updated = replace(
            snapshot,
            context=tuple(sorted(context.items())),
            pending_operation=None,
            completed_operations=snapshot.completed_operations + (checkpoint,),
        )
    elif event.kind is FlowEventKind.OPERATION_FAILED:
        if snapshot.status is not FlowStatus.RUNNING:
            raise ValueError("operation failure requires a running flow")
        _require_pending_match(snapshot, event, payload)
        updated = replace(snapshot, pending_operation=None)
    elif event.kind is FlowEventKind.OPERATION_OUTCOME_UNKNOWN:
        if snapshot.status is not FlowStatus.RUNNING:
            raise ValueError("unknown operation outcome requires a running flow")
        _require_pending_match(snapshot, event, payload)
        updated = replace(snapshot, status=FlowStatus.NEEDS_ATTENTION)
    elif event.kind is FlowEventKind.OPERATION_RECONCILED:
        if snapshot.status is not FlowStatus.NEEDS_ATTENTION:
            raise ValueError("operation reconciliation requires needs_attention state")
        pending = _require_pending_match(snapshot, event, payload)
        evidence_ref = payload.get("$meta.evidence_ref", "").strip()
        reconciled_by = payload.get("$meta.reconciled_by", "").strip()
        if not evidence_ref or not reconciled_by:
            raise ValueError("operation reconciliation requires evidence_ref and reconciled_by")
        resolution = payload.get("$meta.resolution")
        if resolution == "applied":
            checkpoint = _checkpoint_from_event(pending, payload, evidence_ref=evidence_ref)
            context = snapshot.context_dict()
            context.update(dict(checkpoint.outputs))
            updated = replace(
                snapshot, status=FlowStatus.RUNNING,
                context=tuple(sorted(context.items())), pending_operation=None,
                completed_operations=snapshot.completed_operations + (checkpoint,),
            )
        elif resolution == "not_applied":
            updated = replace(snapshot, pending_operation=None)
        else:
            raise ValueError("operation reconciliation resolution must be applied or not_applied")
    elif event.kind is FlowEventKind.STARTED:
        if snapshot.status is not FlowStatus.CREATED or event.node_id != definition.start_node:
            raise ValueError("invalid flow start event")
        updated = replace(snapshot, status=FlowStatus.RUNNING,
                          context=tuple(sorted(payload.items())))
    elif event.kind is FlowEventKind.STEP_SUCCEEDED:
        if snapshot.status is not FlowStatus.RUNNING or event.node_id != snapshot.current_node:
            raise ValueError("success event does not match current flow node")
        if snapshot.pending_operation is not None:
            raise ValueError("cannot finish a flow node with a pending operation")
        node = definition.node(snapshot.current_node)
        if node.kind not in (FlowNodeKind.OPERATION, FlowNodeKind.HABIT):
            raise ValueError("only operation/habit nodes can complete as a step")
        context = snapshot.context_dict()
        context.update({key: value for key, value in payload.items()
                        if not key.startswith("$meta.") and not key.startswith("$op.")})
        updated = replace(
            snapshot, context=tuple(sorted(context.items())),
            completed_nodes=snapshot.completed_nodes + (node.node_id,),
        )
        updated = _settle_at_node(definition, updated, node.next_on_success)
    elif event.kind is FlowEventKind.STEP_FAILED:
        if snapshot.status is not FlowStatus.RUNNING or event.node_id != snapshot.current_node:
            raise ValueError("failure event does not match current flow node")
        if snapshot.pending_operation is not None:
            raise ValueError("cannot fail a flow node with a pending operation")
        node = definition.node(snapshot.current_node)
        if node.kind not in (FlowNodeKind.OPERATION, FlowNodeKind.HABIT):
            raise ValueError("only operation/habit nodes can fail as a step")
        attempts = snapshot.attempt_count(node.node_id) + 1
        counts = dict(snapshot.attempts)
        counts[node.node_id] = attempts
        updated = replace(snapshot, attempts=tuple(sorted(counts.items())))
        if attempts < node.max_attempts:
            updated = replace(updated, status=FlowStatus.RUNNING)
        elif node.next_on_failure is not None:
            updated = _settle_at_node(definition, updated, node.next_on_failure)
        else:
            updated = replace(updated, status=FlowStatus.FAILED)
    elif event.kind is FlowEventKind.STEP_OUTCOME_UNKNOWN:
        if snapshot.status is not FlowStatus.RUNNING or event.node_id != snapshot.current_node:
            raise ValueError("unknown outcome does not match current flow node")
        context = snapshot.context_dict()
        context.update({key: value for key, value in payload.items()
                        if not key.startswith("$meta.") and not key.startswith("$op.")})
        updated = replace(snapshot, status=FlowStatus.NEEDS_ATTENTION,
                          context=tuple(sorted(context.items())))
    elif event.kind is FlowEventKind.BRANCH_RESOLVED:
        if snapshot.status is not FlowStatus.RUNNING or event.node_id != snapshot.current_node:
            raise ValueError("branch event does not match current flow node")
        node = definition.node(snapshot.current_node)
        if node.kind is not FlowNodeKind.BRANCH:
            raise ValueError("current node is not a branch")
        if node.branch_key not in snapshot.context_dict():
            raise ValueError("branch key is missing from flow context")
        actual = snapshot.context_dict()[node.branch_key]
        expected_result = "true" if actual == node.branch_equals else "false"
        if payload.get("result") != expected_result:
            raise ValueError("branch result does not match recorded context")
        destination = node.next_on_true if expected_result == "true" else node.next_on_false
        updated = _settle_at_node(definition, snapshot, destination)
    elif event.kind is FlowEventKind.WAIT_RELEASED:
        if snapshot.status is not FlowStatus.WAITING or event.node_id != snapshot.current_node:
            raise ValueError("wait release does not match current wait node")
        node = definition.node(snapshot.current_node)
        if node.kind is not FlowNodeKind.WAIT:
            raise ValueError("current node is not a wait")
        updated = _settle_at_node(definition, snapshot, node.next_on_success)
    elif event.kind is FlowEventKind.PAUSED:
        if snapshot.status not in (FlowStatus.RUNNING, FlowStatus.WAITING):
            raise ValueError("only running/waiting flows can be paused")
        updated = replace(snapshot, status=FlowStatus.PAUSED, resume_status=snapshot.status)
    elif event.kind is FlowEventKind.RESUMED:
        if snapshot.status is not FlowStatus.PAUSED or snapshot.resume_status is None:
            raise ValueError("flow is not paused")
        updated = replace(snapshot, status=snapshot.resume_status, resume_status=None)
    elif event.kind is FlowEventKind.CANCELLED:
        if snapshot.pending_operation is not None:
            raise ValueError(
                "cannot cancel a flow with an unresolved external operation; reconcile first"
            )
        updated = replace(snapshot, status=FlowStatus.CANCELLED, resume_status=None)
    elif event.kind is FlowEventKind.NEEDS_ATTENTION:
        context = snapshot.context_dict()
        context.update({key: value for key, value in payload.items()
                        if not key.startswith("$meta.")})
        updated = replace(snapshot, status=FlowStatus.NEEDS_ATTENTION,
                          context=tuple(sorted(context.items())), resume_status=None)
    else:
        raise ValueError(f"unsupported flow event {event.kind}")

    return replace(
        updated,
        last_event_sequence=event.sequence,
        applied_event_ids=snapshot.applied_event_ids + (event.event_id,),
    )


class PersistentFlow:
    """Flow run that commits events before exposing updated in-memory state."""

    def __init__(
        self, definition: FlowDefinition, snapshot: FlowSnapshot, journal: FlowJournal,
    ) -> None:
        self.definition = definition
        self.snapshot = snapshot
        self.journal = journal

    @classmethod
    def start(
        cls, definition: FlowDefinition, run_id: str, journal: FlowJournal,
        initial_context: Mapping[str, str] | None = None,
    ) -> "PersistentFlow":
        _validate_output_keys(initial_context or {})
        initial = FlowSnapshot.initial(definition, run_id, initial_context)
        flow = cls(definition, initial, journal)
        flow._commit(FlowEventKind.STARTED, definition.start_node, initial_context or {})
        return flow

    @classmethod
    def restore(
        cls, definition: FlowDefinition, run_id: str, journal: FlowJournal,
    ) -> "PersistentFlow":
        events = journal.load(run_id)
        snapshot = FlowSnapshot.initial(definition, run_id)
        for event in events:
            snapshot = apply_flow_event(definition, snapshot, event)
        if not events:
            raise ValueError("no persisted events for flow run")
        return cls(definition, snapshot, journal)

    @property
    def idempotency_key(self) -> str:
        return self.snapshot.idempotency_key()

    @property
    def operation_scope_key(self) -> str:
        return self.snapshot.operation_scope_key()

    @property
    def current_node(self) -> FlowNode:
        return self.definition.node(self.snapshot.current_node)

    def _commit(
        self, kind: FlowEventKind, node_id: str | None = None,
        payload: Mapping[str, str] | None = None, event_id: str | None = None,
    ) -> FlowSnapshot:
        event = FlowEvent(
            run_id=self.snapshot.run_id,
            sequence=self.snapshot.last_event_sequence + 1,
            event_id=event_id or uuid4().hex,
            kind=kind,
            node_id=node_id,
            payload=tuple(sorted((payload or {}).items())),
        )
        candidate = apply_flow_event(self.definition, self.snapshot, event)
        self.journal.append(event)
        self.snapshot = candidate
        return candidate

    def begin_operation(
        self, *, operation_index: int, operation_ref: str, effect: OperationEffect,
        idempotency_key: str, attempt: int, input_sha256: str,
        harness_id: str, harness_version: str, environment_id: str, context_id: str,
        idempotency_key_supported: bool = False,
    ) -> FlowSnapshot:
        if type(idempotency_key_supported) is not bool:
            raise ValueError("idempotency_key_supported must be a boolean")
        payload = {
            "$op.index": str(operation_index),
            "$op.operation_ref": operation_ref,
            "$op.effect": OperationEffect(effect).value,
            "$op.idempotency_key": idempotency_key,
            "$op.attempt": str(attempt),
            "$op.input_sha256": input_sha256,
            "$op.harness_id": harness_id,
            "$op.harness_version": harness_version,
            "$op.environment_id": environment_id,
            "$op.context_id": context_id,
            "$op.idempotency_key_supported": str(idempotency_key_supported).lower(),
        }
        return self._commit(FlowEventKind.OPERATION_INTENT, self.snapshot.current_node, payload)

    def succeed_operation(
        self, outputs: Mapping[str, str] | None = None, *,
        duration_ms: float = 0.0, resource_units: float = 0.0, external_cost: float = 0.0,
    ) -> FlowSnapshot:
        pending = self.snapshot.pending_operation
        if pending is None:
            raise ValueError("no pending operation to complete")
        _validate_output_keys(outputs or {})
        payload = dict(outputs or {})
        payload.update({
            "$op.index": str(pending.operation_index),
            "$op.idempotency_key": pending.idempotency_key,
            "$meta.duration_ms": str(duration_ms),
            "$meta.resource_units": str(resource_units),
            "$meta.external_cost": str(external_cost),
        })
        return self._commit(FlowEventKind.OPERATION_SUCCEEDED, self.snapshot.current_node, payload)

    def fail_operation(self, reason: str, metadata: Mapping[str, str] | None = None) -> FlowSnapshot:
        pending = self.snapshot.pending_operation
        if pending is None:
            raise ValueError("no pending operation to fail")
        payload = {
            "$op.index": str(pending.operation_index),
            "$op.idempotency_key": pending.idempotency_key,
            "$meta.reason": reason,
        }
        payload.update({f"$meta.{key}": value for key, value in (metadata or {}).items()})
        return self._commit(FlowEventKind.OPERATION_FAILED, self.snapshot.current_node, payload)

    def mark_operation_outcome_unknown(
        self, reason: str, metadata: Mapping[str, str] | None = None,
    ) -> FlowSnapshot:
        pending = self.snapshot.pending_operation
        if pending is None:
            raise ValueError("no pending operation to mark unknown")
        payload = {
            "$op.index": str(pending.operation_index),
            "$op.idempotency_key": pending.idempotency_key,
            "$meta.reason": reason,
        }
        payload.update({f"$meta.{key}": value for key, value in (metadata or {}).items()})
        return self._commit(
            FlowEventKind.OPERATION_OUTCOME_UNKNOWN, self.snapshot.current_node, payload
        )

    def reconcile_pending_operation(
        self, *, applied: bool, evidence_ref: str, reconciled_by: str,
        outputs: Mapping[str, str] | None = None,
    ) -> FlowSnapshot:
        pending = self.snapshot.pending_operation
        if pending is None:
            raise ValueError("no pending operation to reconcile")
        if type(applied) is not bool:
            raise ValueError("applied must be a boolean")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            raise ValueError("reconciliation evidence_ref must be a non-empty string")
        if not isinstance(reconciled_by, str) or not reconciled_by.strip():
            raise ValueError("reconciliation reconciled_by must be a non-empty string")
        _validate_output_keys(outputs or {})
        payload = dict(outputs or {})
        payload.update({
            "$op.index": str(pending.operation_index),
            "$op.idempotency_key": pending.idempotency_key,
            "$meta.resolution": "applied" if applied else "not_applied",
            "$meta.evidence_ref": evidence_ref,
            "$meta.reconciled_by": reconciled_by,
        })
        return self._commit(FlowEventKind.OPERATION_RECONCILED, self.snapshot.current_node, payload)

    def succeed_step(
        self, outputs: Mapping[str, str] | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> FlowSnapshot:
        _validate_output_keys(outputs or {})
        payload = dict(outputs or {})
        payload.update({f"$meta.{key}": value for key, value in (metadata or {}).items()})
        return self._commit(FlowEventKind.STEP_SUCCEEDED, self.snapshot.current_node, payload)

    def fail_step(self, reason: str, metadata: Mapping[str, str] | None = None) -> FlowSnapshot:
        payload = {"$meta.reason": reason}
        payload.update({f"$meta.{key}": value for key, value in (metadata or {}).items()})
        return self._commit(FlowEventKind.STEP_FAILED, self.snapshot.current_node, payload)

    def mark_outcome_unknown(
        self, reason: str, metadata: Mapping[str, str] | None = None,
    ) -> FlowSnapshot:
        payload = {"$meta.reason": reason}
        payload.update({f"$meta.{key}": value for key, value in (metadata or {}).items()})
        return self._commit(
            FlowEventKind.STEP_OUTCOME_UNKNOWN, self.snapshot.current_node, payload
        )

    def resolve_branch(self) -> FlowSnapshot:
        node = self.current_node
        if node.kind is not FlowNodeKind.BRANCH:
            raise ValueError("current node is not a branch")
        context = self.snapshot.context_dict()
        if node.branch_key not in context:
            raise ValueError("branch key is missing")
        result = "true" if context[node.branch_key] == node.branch_equals else "false"
        return self._commit(FlowEventKind.BRANCH_RESOLVED, node.node_id, {"result": result})

    def release_wait(self) -> FlowSnapshot:
        return self._commit(FlowEventKind.WAIT_RELEASED, self.snapshot.current_node)

    def pause(self, reason: str = "requested") -> FlowSnapshot:
        return self._commit(
            FlowEventKind.PAUSED, self.snapshot.current_node, {"$meta.reason": reason}
        )

    def resume(self) -> FlowSnapshot:
        return self._commit(FlowEventKind.RESUMED, self.snapshot.current_node)

    def cancel(self, reason: str = "cancelled") -> FlowSnapshot:
        if self.snapshot.pending_operation is not None:
            raise ValueError(
                "cannot cancel a flow with an unresolved external operation; reconcile first"
            )
        return self._commit(FlowEventKind.CANCELLED, self.snapshot.current_node, {"reason": reason})

    def needs_attention(
        self, reason: str, evidence: Mapping[str, str] | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> FlowSnapshot:
        payload = dict(evidence or {})
        payload["$meta.reason"] = reason
        payload.update({f"$meta.{key}": value for key, value in (metadata or {}).items()})
        return self._commit(
            FlowEventKind.NEEDS_ATTENTION, self.snapshot.current_node, payload
        )
