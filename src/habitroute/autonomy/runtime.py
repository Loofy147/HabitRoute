"""Stateless trigger hydration over the durable flow ledger."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from ..flows import FlowDefinition, PersistentFlow
from .ledger import SQLiteFlowJournal

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class TriggerEnvelope:
    trigger_id: str
    run_id: str
    trigger_type: str
    payload_sha256: str

    def __post_init__(self) -> None:
        for field in ("trigger_id", "run_id", "trigger_type"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must be non-empty")
        if not _SHA256.fullmatch(self.payload_sha256):
            raise ValueError("payload_sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class TriggerHydration:
    flow: PersistentFlow
    first_delivery: bool


def hydrate_trigger(
    envelope: TriggerEnvelope, definition: FlowDefinition, journal: SQLiteFlowJournal,
    *, initial_context: Mapping[str, str] | None = None,
) -> TriggerHydration:
    """Atomically claim trigger and pin first context; reconstruct state from journal."""
    if not definition.flow_id or definition.version < 1:
        raise ValueError("invalid pinned flow definition")
    journal.claim_trigger(
        trigger_id=envelope.trigger_id,
        payload_sha256=envelope.payload_sha256,
        run_id=envelope.run_id,
        flow_id=definition.flow_id,
        definition_version=definition.version,
        initial_context=dict(initial_context or {}),
    )
    events = journal.load(envelope.run_id)
    if events:
        return TriggerHydration(
            PersistentFlow.restore(definition, envelope.run_id, journal), False,
        )
    pinned_context = journal.load_initial_context(
        envelope.run_id, definition.flow_id, definition.version,
    )
    try:
        flow = PersistentFlow.start(definition, envelope.run_id, journal, pinned_context)
    except Exception:
        # A concurrent trigger may have initialized the run after our read.
        committed = journal.load(envelope.run_id)
        if not committed:
            raise
        flow = PersistentFlow.restore(definition, envelope.run_id, journal)
    return TriggerHydration(flow, len(events) == 0)
