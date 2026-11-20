"""Policy-enforcing HarnessAdapter boundary for autonomous execution."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
import time
from typing import Mapping, Protocol
from urllib.parse import urlsplit

from ..machine import (
    HarnessAdapter, HarnessOperationResult, OperationEffect, OperationOutcome,
    OperationStep, OperationNotExecuted,
)
from .capabilities import (
    CapabilityBroker, CapabilityClaims, CapabilityToken, DecisionKind,
    PolicyRequest, canonical_json, deterministic_idempotency_key,
    evaluate_capability,
)
from .guards import SnapshotEvidence, SnapshotVerifier, require_recovery_snapshot
from .ledger import AuditAnchor, BudgetExceeded, IdempotencyConflict, SQLiteFlowJournal

_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:bearer\s+[A-Za-z0-9._~+/-]{16,})|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9_-]{24,}\b"
)
_SECRET_KEY = re.compile(
    r"(?:password|passwd|secret|token|private[_-]?key|authorization|api[_-]?key|access[_-]?key)",
    re.I,
)


def _secret_mapping(values: Mapping[str, str]) -> bool:
    return any(
        _SECRET_KEY.search(str(key)) or _SECRET.search(str(value))
        for key, value in values.items()
    )


@dataclass(frozen=True, slots=True)
class OperationDescriptor:
    operation_ref: str
    host: str
    resource: str
    external: bool
    cost_units: float = 1.0
    approval_required: bool = False
    destructive: bool = False
    method: str = "POST"

    def __post_init__(self) -> None:
        if not all(str(v).strip() for v in (self.operation_ref, self.host, self.resource)):
            raise ValueError("operation descriptor fields must be non-empty")
        method = self.method.upper().strip()
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("unsupported HTTP method")
        object.__setattr__(self, "method", method)
        parsed = urlsplit(self.resource)
        if self.external:
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                raise ValueError("external resources require absolute HTTPS URLs")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("external URLs cannot contain credentials, query or fragment")
            if parsed.netloc.lower() != self.host.lower():
                raise ValueError("external URL authority must exactly match host")
        elif parsed.scheme or parsed.netloc:
            raise ValueError("absolute network URLs must be marked external")
        if method in {"PUT", "PATCH", "DELETE"} and not self.destructive:
            raise ValueError("mutating HTTP methods require a destructive recovery gate")
        if method in {"GET", "HEAD"} and self.destructive:
            raise ValueError("destructive operation cannot use a read-only HTTP method")
        if not math.isfinite(self.cost_units) or self.cost_units < 0:
            raise ValueError("cost_units must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ApprovalEvidence:
    capability_id: str
    operation_ref: str
    host: str
    resource: str
    approver: str
    approval_id: str
    expires_at: int
    signature: str


class ApprovalVerifier(Protocol):
    def verify(
        self, evidence: ApprovalEvidence, claims: CapabilityClaims,
        descriptor: OperationDescriptor, now: int,
    ) -> bool: ...


class EgressProxy(Protocol):
    """Proxy owns external requests and credential exchange; worker never gets raw credentials."""
    def invoke(
        self, descriptor: OperationDescriptor, operation: OperationStep,
        inputs: Mapping[str, str], *, idempotency_key: str,
        capability_token: CapabilityToken | str,
    ) -> HarnessOperationResult: ...


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    evidence: SnapshotEvidence
    workflow_id: str
    required_sequence: int
    expected_state_sha256: str
    max_age_seconds: int = 3600


class PolicyEnforcedHarnessAdapter:
    """Drop-in adapter. External operations never fall back to the inner adapter."""

    def __init__(
        self, inner: HarnessAdapter, *, broker: CapabilityBroker,
        capability_token: CapabilityToken | str,
        descriptors: Mapping[str, OperationDescriptor],
        journal: SQLiteFlowJournal,
        egress_proxy: EgressProxy | None = None,
        approval_evidence: Mapping[str, ApprovalEvidence] | None = None,
        approval_verifier: ApprovalVerifier | None = None,
        audit_anchor: AuditAnchor | None = None,
        require_external_audit_anchor: bool = False,
        recovery_plans: Mapping[str, RecoveryPlan] | None = None,
        snapshot_verifier: SnapshotVerifier | None = None,
    ) -> None:
        self._inner = inner
        self._broker = broker
        self._token = capability_token
        self._descriptors = dict(descriptors)
        self._journal = journal
        self._egress = egress_proxy
        self._approvals = dict(approval_evidence or {})
        self._approval_verifier = approval_verifier
        self._anchor = audit_anchor
        self._require_anchor = require_external_audit_anchor
        self._recovery = dict(recovery_plans or {})
        self._snapshot_verifier = snapshot_verifier
        if set(self._descriptors) - set(inner.profile.allowed_operations):
            raise ValueError("descriptors must be within harness allowlist")
        if any(key != desc.operation_ref for key, desc in self._descriptors.items()):
            raise ValueError("descriptor map keys must match operation_ref")
        required = set(inner.profile.approval_required)
        required.update(ref for ref, desc in self._descriptors.items() if desc.approval_required)
        self._profile = type(inner.profile)(
            inner.profile.harness_id, inner.profile.version,
            inner.profile.environment_id, inner.profile.context_id,
            inner.profile.allowed_operations, frozenset(required),
            inner.profile.max_step_attempts, inner.profile.supports_compensation,
        )

    @property
    def profile(self):
        return self._profile

    def _deny(self, operation_ref: str, scope: str, reason: str) -> None:
        key = deterministic_idempotency_key(scope, operation_ref)
        digest = hashlib.sha256(reason.encode("utf-8")).hexdigest()[:16]
        self._journal.append_audit(
            f"deny:{key}:{digest}", "authorization_denied",
            {"operation_ref": operation_ref, "idempotency_key": key, "reason": reason},
        )
        raise OperationNotExecuted(reason)

    def invoke(
        self, operation: OperationStep, inputs: Mapping[str, str], *, idempotency_key: str,
    ) -> HarnessOperationResult:
        descriptor = self._descriptors.get(operation.operation_ref)
        if descriptor is None:
            self._deny(operation.operation_ref, idempotency_key, "operation_descriptor_missing")
        try:
            claims = self._broker.verify(self._token)
        except Exception as exc:
            self._deny(operation.operation_ref, idempotency_key, "capability_invalid:" + type(exc).__name__)
        ancestors = tuple(item.capability_id for item in claims.budget_chain)
        if self._journal.is_capability_revoked(claims.capability_id, ancestors):
            self._deny(operation.operation_ref, idempotency_key, "capability_or_ancestor_revoked")
        if descriptor.external and self._egress is None:
            self._deny(operation.operation_ref, idempotency_key, "egress_proxy_unavailable")
        if descriptor.external and self._require_anchor and self._anchor is None:
            self._deny(operation.operation_ref, idempotency_key, "external_audit_anchor_unavailable")
        if _secret_mapping(inputs):
            self._deny(operation.operation_ref, idempotency_key, "raw_secret_input_rejected_use_secret_reference")

        method_read = descriptor.method in {"GET", "HEAD"}
        if operation.effect is OperationEffect.READ_ONLY and not method_read:
            self._deny(operation.operation_ref, idempotency_key, "read_only_requires_get_or_head")
        if operation.effect is not OperationEffect.READ_ONLY and method_read:
            self._deny(operation.operation_ref, idempotency_key, "mutating_operation_cannot_use_get_or_head")

        if descriptor.destructive:
            plan = self._recovery.get(operation.operation_ref)
            if plan is None or self._snapshot_verifier is None:
                self._deny(operation.operation_ref, idempotency_key, "recovery_snapshot_or_verifier_missing")
            try:
                require_recovery_snapshot(
                    plan.evidence, self._snapshot_verifier,
                    workflow_id=plan.workflow_id, required_sequence=plan.required_sequence,
                    expected_state_sha256=plan.expected_state_sha256,
                    max_age_seconds=plan.max_age_seconds,
                )
            except Exception as exc:
                self._deny(operation.operation_ref, idempotency_key, "recovery_gate:" + type(exc).__name__)

        now = int(time.time())
        approval = self._approvals.get(operation.operation_ref)
        approval_ok = False
        if approval and self._approval_verifier:
            try:
                approval_ok = (
                    approval.capability_id == claims.capability_id
                    and approval.operation_ref == descriptor.operation_ref
                    and approval.host.lower() == descriptor.host.lower()
                    and approval.resource == descriptor.resource
                    and approval.expires_at > now
                    and bool(self._approval_verifier.verify(approval, claims, descriptor, now))
                )
            except Exception:
                approval_ok = False
        decision = evaluate_capability(
            claims,
            PolicyRequest(
                descriptor.operation_ref, descriptor.host, descriptor.resource,
                descriptor.cost_units, descriptor.approval_required,
            ),
            approval_verified=approval_ok,
        )
        if decision.kind is not DecisionKind.ALLOW:
            self._deny(operation.operation_ref, idempotency_key, decision.reason)

        key = deterministic_idempotency_key(idempotency_key, operation.operation_ref)
        input_digest = hashlib.sha256(canonical_json(dict(inputs))).hexdigest()
        try:
            claim = self._journal.claim_invocation(
                capability_id=claims.capability_id, idempotency_key=key,
                operation_ref=operation.operation_ref, effect=operation.effect.value,
                input_sha256=input_digest, estimated_cost=descriptor.cost_units,
                max_calls=claims.max_calls, max_cost=claims.max_cost,
                budget_chain=tuple(
                    (item.capability_id, item.max_calls, item.max_cost)
                    for item in claims.budget_chain
                ),
            )
        except (BudgetExceeded, IdempotencyConflict, PermissionError) as exc:
            self._deny(operation.operation_ref, idempotency_key, type(exc).__name__)
        if not claim.executable:
            return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code=claim.reason)

        if descriptor.external and self._require_anchor:
            try:
                self._journal.publish_audit_head(self._anchor)
            except Exception:
                self._journal.finish_invocation(key, "failed", "pre_execution_anchor_failed")
                return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="pre_execution_anchor_failed")

        try:
            if descriptor.external:
                result = self._egress.invoke(
                    descriptor, operation, inputs, idempotency_key=key,
                    capability_token=self._token,
                )
            else:
                result = self._inner.invoke(operation, inputs, idempotency_key=key)
        except Exception as exc:
            self._journal.finish_invocation(key, "unknown", "adapter_exception:" + type(exc).__name__)
            return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="operation_outcome_unknown")

        if not isinstance(result, HarnessOperationResult):
            self._journal.finish_invocation(key, "unknown", "invalid_adapter_result")
            return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="invalid_adapter_result")
        if _secret_mapping(dict(result.outputs)):
            self._journal.finish_invocation(key, "unknown", "raw_secret_output_rejected")
            return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="raw_secret_output_rejected")
        try:
            self._journal.finish_invocation(
                key, result.outcome.value, result.error_code,
            )
        except Exception:
            return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="result_audit_commit_failed")
        if descriptor.external and self._require_anchor:
            try:
                self._journal.publish_audit_head(self._anchor)
            except Exception:
                return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="post_execution_anchor_failed")
        return result
