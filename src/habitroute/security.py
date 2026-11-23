"""Fail-closed, provider-neutral security primitives for autonomous execution.

This module is a local reference implementation, not a production credential broker,
network proxy, distributed consensus system, or independently administered control plane.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import threading
from typing import Iterable, Mapping
from uuid import UUID, uuid5


MAX_DELEGATION_DEPTH = 3
MAX_CHILD_TTL_SECONDS = 900


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class RiskClass(str, Enum):
    READ = "read"
    WRITE = "write"
    EXTERNAL_MUTATION = "external_mutation"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True, slots=True)
class CapabilityLease:
    lease_id: str
    subject: str
    task_id: str
    hosts: frozenset[str]
    operations: frozenset[str]
    resources: frozenset[str]
    expires_at: float
    issued_at: float
    budget_units: float
    depth: int = 0
    parent_lease_id: str | None = None

    def __post_init__(self) -> None:
        for field in ("lease_id", "subject", "task_id"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must be non-empty")
        for field in ("hosts", "operations", "resources"):
            values = frozenset(getattr(self, field))
            if not values or any(not v or not v.strip() for v in values):
                raise ValueError(f"{field} must contain non-empty values")
            object.__setattr__(self, field, values)
        if not (math.isfinite(self.issued_at) and math.isfinite(self.expires_at)):
            raise ValueError("lease timestamps must be finite")
        if self.expires_at <= self.issued_at:
            raise ValueError("lease expiry must follow issue time")
        if not math.isfinite(self.budget_units) or self.budget_units <= 0:
            raise ValueError("budget_units must be finite and positive")
        if not 0 <= self.depth <= MAX_DELEGATION_DEPTH:
            raise ValueError("delegation depth exceeds policy")
        if self.depth == 0 and self.parent_lease_id is not None:
            raise ValueError("root lease cannot have a parent")
        if self.depth > 0 and not self.parent_lease_id:
            raise ValueError("delegated lease requires parent_lease_id")


@dataclass(frozen=True, slots=True)
class RecoveryEvidence:
    kind: str
    snapshot_id: str
    resource: str
    committed: bool
    verified: bool
    committed_at: float

    def valid_for(self, resource: str, now: float) -> bool:
        return (
            self.kind in {"cow", "pitr"}
            and bool(self.snapshot_id)
            and self.resource == resource
            and self.committed
            and self.verified
            and math.isfinite(self.committed_at)
            and self.committed_at <= now
        )


@dataclass(frozen=True, slots=True)
class ActionRequest:
    task_id: str
    host: str
    operation: str
    resource: str
    risk: RiskClass
    estimated_budget_units: float = 0.0
    approval_receipt: str | None = None
    recovery_evidence: RecoveryEvidence | None = None
    external_mutation: bool = False

    def __post_init__(self) -> None:
        for field in ("task_id", "host", "operation", "resource"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must be non-empty")
        if not math.isfinite(self.estimated_budget_units) or self.estimated_budget_units < 0:
            raise ValueError("estimated budget must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str
    idempotency_key: str | None = None


class CapabilityAuthority:
    """HMAC-backed reference issuer; keep the key in an external secret manager."""

    def __init__(self, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise ValueError("signing_key must contain at least 256 bits")
        self._key = signing_key

    @staticmethod
    def _payload(lease: CapabilityLease) -> bytes:
        data = asdict(lease)
        for field in ("hosts", "operations", "resources"):
            data[field] = sorted(data[field])
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    def sign(self, lease: CapabilityLease) -> str:
        return hmac.new(self._key, self._payload(lease), hashlib.sha256).hexdigest()

    def verify(self, lease: CapabilityLease, signature: str) -> bool:
        return hmac.compare_digest(self.sign(lease), signature)

    def delegate(
        self,
        parent: CapabilityLease,
        *,
        child_id: str,
        subject: str,
        task_id: str,
        hosts: Iterable[str],
        operations: Iterable[str],
        resources: Iterable[str],
        budget_units: float,
        now: float,
        ttl_seconds: int,
    ) -> CapabilityLease:
        if parent.depth >= MAX_DELEGATION_DEPTH:
            raise PermissionError("maximum delegation depth reached")
        if ttl_seconds < 1 or ttl_seconds > MAX_CHILD_TTL_SECONDS:
            raise ValueError("child TTL must be between 1 and 900 seconds")
        if now >= parent.expires_at:
            raise PermissionError("parent lease expired")
        child_hosts, child_ops, child_resources = (
            frozenset(hosts), frozenset(operations), frozenset(resources)
        )
        if not child_hosts.issubset(parent.hosts):
            raise PermissionError("delegation cannot expand hosts")
        if not child_ops.issubset(parent.operations):
            raise PermissionError("delegation cannot expand operations")
        if not child_resources.issubset(parent.resources):
            raise PermissionError("delegation cannot expand resources")
        if not 0 < budget_units <= parent.budget_units:
            raise PermissionError("delegation cannot expand budget")
        expiry = min(now + ttl_seconds, parent.expires_at)
        return CapabilityLease(
            lease_id=child_id, subject=subject, task_id=task_id,
            hosts=child_hosts, operations=child_ops, resources=child_resources,
            expires_at=expiry, issued_at=now, budget_units=budget_units,
            depth=parent.depth + 1, parent_lease_id=parent.lease_id,
        )


class PolicyEngine:
    """Deterministic local policy decision point. Unknown conditions fail closed."""

    def __init__(self, authority: CapabilityAuthority, namespace: UUID) -> None:
        self.authority = authority
        self.namespace = namespace

    def evaluate(
        self,
        request: ActionRequest,
        lease: CapabilityLease,
        signature: str,
        *,
        now: float,
    ) -> PolicyResult:
        if not self.authority.verify(lease, signature):
            return PolicyResult(PolicyDecision.DENY, "invalid_lease_signature")
        if now < lease.issued_at or now >= lease.expires_at:
            return PolicyResult(PolicyDecision.DENY, "lease_not_current")
        if request.task_id != lease.task_id:
            return PolicyResult(PolicyDecision.DENY, "task_scope_mismatch")
        if request.host not in lease.hosts:
            return PolicyResult(PolicyDecision.DENY, "host_not_permitted")
        if request.operation not in lease.operations:
            return PolicyResult(PolicyDecision.DENY, "operation_not_permitted")
        if request.resource not in lease.resources:
            return PolicyResult(PolicyDecision.DENY, "resource_not_permitted")
        if request.estimated_budget_units > lease.budget_units:
            return PolicyResult(PolicyDecision.DENY, "budget_exceeded")
        if request.risk is RiskClass.DESTRUCTIVE:
            evidence = request.recovery_evidence
            if evidence is None or not evidence.valid_for(request.resource, now):
                return PolicyResult(PolicyDecision.DENY, "verified_recovery_checkpoint_required")
        if request.risk in {RiskClass.EXTERNAL_MUTATION, RiskClass.DESTRUCTIVE}:
            if not request.approval_receipt:
                return PolicyResult(PolicyDecision.APPROVAL_REQUIRED, "independent_approval_required")
        key = None
        if request.external_mutation:
            key = str(uuid5(
                self.namespace,
                "|".join((request.task_id, request.host, request.operation, request.resource)),
            ))
        return PolicyResult(PolicyDecision.ALLOW, "all_policy_checks_passed", key)


def merkle_root(hex_digests: Iterable[str]) -> str:
    """Return a deterministic SHA-256 Merkle root (RFC-9162-style odd-node promotion)."""
    level = [bytes.fromhex(item) for item in hex_digests]
    if not level:
        return hashlib.sha256(b"").hexdigest()
    if any(len(item) != 32 for item in level):
        raise ValueError("Merkle leaves must be SHA-256 digests")
    while len(level) > 1:
        next_level = []
        for index in range(0, len(level), 2):
            left = level[index]
            if index + 1 == len(level):
                next_level.append(hashlib.sha256(b"\x00" + left).digest())
            else:
                next_level.append(hashlib.sha256(b"\x01" + left + level[index + 1]).digest())
        level = next_level
    return level[0].hex()


class HashChainAuditSink:
    """Single-writer local append-only hash-chain journal with Merkle checkpoints.

    File permissions and append mode are not an independent tamper-proof guarantee.
    Production deployments must replicate receipts to an externally administered
    transparency service or immutable storage with independent witnesses.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: Mapping[str, object]) -> dict[str, str | int]:
        with self._lock:
            previous = self._last_hash()
            body = {
                "sequence": self._line_count() + 1,
                "previous_hash": previous,
                "event": dict(event),
            }
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            digest = hashlib.sha256(canonical).hexdigest()
            record = {**body, "record_hash": digest}
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return {"sequence": body["sequence"], "record_hash": digest}

    def verify(self) -> bool:
        previous = "0" * 64
        expected_sequence = 1
        if not self.path.exists():
            return True
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    return False
                record = json.loads(line)
                digest = record.pop("record_hash")
                if record.get("sequence") != expected_sequence:
                    return False
                if record.get("previous_hash") != previous:
                    return False
                canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
                actual = hashlib.sha256(canonical).hexdigest()
                if not hmac.compare_digest(actual, digest):
                    return False
                previous = digest
                expected_sequence += 1
        return True

    def merkle_checkpoint(self) -> str:
        leaves = []
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        leaves.append(json.loads(line)["record_hash"])
        return merkle_root(leaves)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        last = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = json.loads(line)["record_hash"]
        return last or "0" * 64

    def _line_count(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
