"""Scoped, short-lived capabilities for autonomous execution.

The HMAC broker in this module is a local reference implementation. Production
systems should implement CapabilityBroker with an external KMS/HSM-backed
Credential Broker and durable revocation. Tokens are bearer credentials: never
log them, persist them, or place them in workflow context.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import base64
import hashlib
import hmac
import json
import math
import posixpath
import re
import time
from typing import Iterable, Protocol
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4, uuid5

MAX_DELEGATION_DEPTH = 3
MAX_CHILD_TTL_SECONDS = 900
MAX_CAPABILITY_TTL_SECONDS = 900
IDEMPOTENCY_NAMESPACE = UUID("d8f48f42-34b9-5d68-9a35-96b17757a0f1")


def _decode_canonical_b64url(value: bytes) -> bytes:
    if not value or re.fullmatch(rb"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("invalid base64url component")
    decoded = base64.urlsafe_b64decode(value + b"=" * (-len(value) % 4))
    if base64.urlsafe_b64encode(decoded).rstrip(b"=") != value:
        raise ValueError("non-canonical base64url component")
    return decoded


def canonical_json(value: object) -> bytes:
    """Stable UTF-8 JSON encoding for signatures, hashes and idempotency names."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_resource(value: str) -> str:
    value = _nonempty(value, "resource")
    if "\\" in value or "\x00" in value:
        raise ValueError("resource contains an invalid path character")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("resource URI must use http or https")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("resource URI must not contain userinfo, query or fragment")
        decoded_path = unquote(parsed.path)
        if decoded_path != parsed.path or any(part in (".", "..") for part in decoded_path.split("/")):
            raise ValueError("resource URI contains encoded or dot-segment path components")
        path = posixpath.normpath("/" + decoded_path.lstrip("/"))
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    if any(part == ".." for part in value.split("/")):
        raise ValueError("resource path traversal is not allowed")
    return posixpath.normpath("/" + value.lstrip("/"))


def resource_is_within(resource: str, allowed_prefix: str) -> bool:
    """Boundary-aware resource-prefix matching (no '/repo2' for '/repo')."""
    candidate = _normalize_resource(resource)
    prefix = _normalize_resource(allowed_prefix).rstrip("/") or "/"
    return candidate == prefix or prefix == "/" or candidate.startswith(prefix + "/")


@dataclass(frozen=True, slots=True)
class BudgetGrant:
    """Signed ancestor budget ceiling charged by every descendant invocation."""
    capability_id: str
    max_calls: int
    max_cost: float

    def __post_init__(self) -> None:
        _nonempty(self.capability_id, "budget capability_id")
        if self.max_calls < 1 or not math.isfinite(self.max_cost) or self.max_cost < 0:
            raise ValueError("ancestor budget grant is invalid")


@dataclass(frozen=True, slots=True)
class CapabilityClaims:
    capability_id: str
    subject: str
    task_id: str
    operations: frozenset[str]
    hosts: frozenset[str]
    resource_prefixes: tuple[str, ...]
    issued_at: int
    expires_at: int
    max_calls: int
    max_cost: float
    approval_required: frozenset[str] = frozenset()
    depth: int = 0
    parent_id: str | None = None
    budget_chain: tuple[BudgetGrant, ...] = ()

    def __post_init__(self) -> None:
        for field in ("capability_id", "subject", "task_id"):
            _nonempty(getattr(self, field), field)
        operations = frozenset(_nonempty(x, "operation") for x in self.operations)
        hosts = frozenset(_nonempty(x, "host").lower() for x in self.hosts)
        approvals = frozenset(_nonempty(x, "approval operation") for x in self.approval_required)
        resources = tuple(sorted({_normalize_resource(x) for x in self.resource_prefixes}))
        if not operations or not hosts or not resources:
            raise ValueError("capability must constrain operations, hosts and resources")
        if not approvals.issubset(operations):
            raise ValueError("approval requirements must be a subset of allowed operations")
        if self.issued_at < 0 or self.expires_at <= self.issued_at:
            raise ValueError("capability timestamps are invalid")
        if self.expires_at - self.issued_at > MAX_CAPABILITY_TTL_SECONDS:
            raise ValueError("capability TTL exceeds the 900-second ceiling")
        if self.max_calls < 1:
            raise ValueError("max_calls must be positive")
        if not math.isfinite(self.max_cost) or self.max_cost < 0:
            raise ValueError("max_cost must be finite and non-negative")
        if not 0 <= self.depth <= MAX_DELEGATION_DEPTH:
            raise ValueError("delegation depth exceeds the configured maximum")
        if self.depth == 0 and self.parent_id is not None:
            raise ValueError("root capability cannot have a parent")
        if self.depth > 0 and not self.parent_id:
            raise ValueError("delegated capability requires a parent capability")
        object.__setattr__(self, "operations", operations)
        object.__setattr__(self, "hosts", hosts)
        object.__setattr__(self, "approval_required", approvals)
        chain = tuple(self.budget_chain)
        if len(chain) != self.depth:
            raise ValueError("budget chain length must equal delegation depth")
        if len({grant.capability_id for grant in chain}) != len(chain):
            raise ValueError("budget chain capability IDs must be unique")
        if self.capability_id in {grant.capability_id for grant in chain}:
            raise ValueError("capability cannot appear in its own ancestor budget chain")
        if chain and self.parent_id != chain[-1].capability_id:
            raise ValueError("parent_id must identify the final ancestor budget grant")
        for parent_grant, child_grant in zip(chain, chain[1:]):
            if (child_grant.max_calls > parent_grant.max_calls
                or child_grant.max_cost > parent_grant.max_cost):
                raise ValueError("ancestor budget chain cannot increase a delegated budget")
        if chain and (self.max_calls > chain[-1].max_calls or self.max_cost > chain[-1].max_cost):
            raise ValueError("child budget cannot exceed its immediate parent budget")
        object.__setattr__(self, "resource_prefixes", resources)
        object.__setattr__(self, "budget_chain", chain)

    def to_payload(self) -> dict[str, object]:
        return {
            "approval_required": sorted(self.approval_required),
            "budget_chain": [
                {"capability_id": grant.capability_id, "max_calls": grant.max_calls,
                 "max_cost": grant.max_cost} for grant in self.budget_chain
            ],
            "capability_id": self.capability_id, "depth": self.depth,
            "expires_at": self.expires_at, "hosts": sorted(self.hosts),
            "issued_at": self.issued_at, "max_calls": self.max_calls,
            "max_cost": self.max_cost, "operations": sorted(self.operations),
            "parent_id": self.parent_id, "resource_prefixes": list(self.resource_prefixes),
            "subject": self.subject, "task_id": self.task_id,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "CapabilityClaims":
        expected = {
            "approval_required", "budget_chain", "capability_id", "depth", "expires_at", "hosts",
            "issued_at", "max_calls", "max_cost", "operations", "parent_id",
            "resource_prefixes", "subject", "task_id",
        }
        if set(payload) != expected:
            raise ValueError("capability token has an unexpected claim shape")
        return cls(
            capability_id=str(payload["capability_id"]), subject=str(payload["subject"]),
            task_id=str(payload["task_id"]),
            operations=frozenset(str(x) for x in payload["operations"]),  # type: ignore[arg-type]
            hosts=frozenset(str(x) for x in payload["hosts"]),  # type: ignore[arg-type]
            resource_prefixes=tuple(str(x) for x in payload["resource_prefixes"]),  # type: ignore[arg-type]
            issued_at=int(payload["issued_at"]), expires_at=int(payload["expires_at"]),
            max_calls=int(payload["max_calls"]), max_cost=float(payload["max_cost"]),
            approval_required=frozenset(str(x) for x in payload["approval_required"]),  # type: ignore[arg-type]
            depth=int(payload["depth"]),
            parent_id=None if payload["parent_id"] is None else str(payload["parent_id"]),
            budget_chain=tuple(
                BudgetGrant(str(item["capability_id"]), int(item["max_calls"]), float(item["max_cost"]))
                for item in payload["budget_chain"]  # type: ignore[union-attr]
            ),
        )


@dataclass(frozen=True, slots=True, repr=False)
class CapabilityToken:
    """Opaque bearer token with deliberately redacted representation."""
    value: str

    def __repr__(self) -> str:
        return "CapabilityToken(<redacted>)"


class CapabilityBroker(Protocol):
    def verify(self, token: CapabilityToken | str, *, now: int | None = None) -> CapabilityClaims: ...
    def mint_root(self, **kwargs: object) -> CapabilityToken: ...
    def delegate(self, parent_token: CapabilityToken | str, **kwargs: object) -> CapabilityToken: ...


class HmacCapabilityBroker:
    """Local HMAC signer for tests/single-process prototypes, not a remote broker.

    The key is injected at construction and retained only in process memory. A
    production adapter should delegate issuance, rotation and revocation to a
    KMS/HSM-backed service and should not export signing material to workers.
    """
    __slots__ = ("__key", "_revoked")

    def __init__(self, signing_key: bytes) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("signing_key must contain at least 32 random bytes")
        self.__key = signing_key
        self._revoked: set[str] = set()

    def __repr__(self) -> str:
        return "HmacCapabilityBroker(<signing-key-redacted>)"

    def _encode(self, claims: CapabilityClaims) -> CapabilityToken:
        payload = canonical_json(claims.to_payload())
        body = base64.urlsafe_b64encode(payload).rstrip(b"=")
        signature = hmac.new(self.__key, body, hashlib.sha256).digest()
        encoded_sig = base64.urlsafe_b64encode(signature).rstrip(b"=")
        return CapabilityToken((body + b"." + encoded_sig).decode("ascii"))

    def verify(self, token: CapabilityToken | str, *, now: int | None = None) -> CapabilityClaims:
        raw = token.value if isinstance(token, CapabilityToken) else token
        if not isinstance(raw, str) or raw.count(".") != 1:
            raise PermissionError("invalid capability token")
        try:
            body_text, signature_text = raw.encode("ascii").split(b".", 1)
            expected = hmac.new(self.__key, body_text, hashlib.sha256).digest()
            supplied = _decode_canonical_b64url(signature_text)
            if not hmac.compare_digest(expected, supplied):
                raise PermissionError("invalid capability signature")
            payload_raw = _decode_canonical_b64url(body_text)
            payload = json.loads(payload_raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            claims = CapabilityClaims.from_payload(payload)
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError("malformed capability token") from exc
        current = int(time.time()) if now is None else int(now)
        if claims.expires_at <= current:
            raise PermissionError("capability expired")
        if claims.issued_at > current + 30:
            raise PermissionError("capability issued in the future")
        ancestor_ids = {grant.capability_id for grant in claims.budget_chain}
        if claims.capability_id in self._revoked or ancestor_ids.intersection(self._revoked):
            raise PermissionError("capability or ancestor revoked")
        return claims

    def revoke(self, capability_id: str) -> None:
        self._revoked.add(_nonempty(capability_id, "capability_id"))

    def mint_root(
        self, *, subject: str, task_id: str, operations: Iterable[str],
        hosts: Iterable[str], resource_prefixes: Iterable[str], ttl_seconds: int = 600,
        max_calls: int = 100, max_cost: float = 100.0,
        approval_required: Iterable[str] = (), now: int | None = None,
    ) -> CapabilityToken:
        current = int(time.time()) if now is None else int(now)
        if not 1 <= ttl_seconds <= MAX_CAPABILITY_TTL_SECONDS:
            raise ValueError("root capability TTL must be between 1 and 900 seconds")
        claims = CapabilityClaims(
            capability_id=str(uuid4()), subject=subject, task_id=task_id,
            operations=frozenset(operations), hosts=frozenset(hosts),
            resource_prefixes=tuple(resource_prefixes), issued_at=current,
            expires_at=current + ttl_seconds, max_calls=max_calls, max_cost=max_cost,
            approval_required=frozenset(approval_required), depth=0, parent_id=None,
            budget_chain=(),
        )
        return self._encode(claims)

    def delegate(
        self, parent_token: CapabilityToken | str, *, subject: str,
        operations: Iterable[str], hosts: Iterable[str],
        resource_prefixes: Iterable[str], ttl_seconds: int = 600,
        max_calls: int, max_cost: float, approval_required: Iterable[str] = (),
        now: int | None = None,
    ) -> CapabilityToken:
        current = int(time.time()) if now is None else int(now)
        parent = self.verify(parent_token, now=current)
        child_ops = frozenset(operations)
        child_hosts = frozenset(str(host).lower() for host in hosts)
        child_resources = tuple(sorted({_normalize_resource(x) for x in resource_prefixes}))
        child_approvals = frozenset(approval_required)
        if not child_ops or not child_ops.issubset(parent.operations):
            raise PermissionError("delegated operations must be a non-empty subset of parent scope")
        if not child_hosts or not child_hosts.issubset(parent.hosts):
            raise PermissionError("delegated hosts must be a non-empty subset of parent scope")
        if not child_resources or any(
            not any(resource_is_within(child, allowed) for allowed in parent.resource_prefixes)
            for child in child_resources
        ):
            raise PermissionError("delegated resources must be contained by parent scope")
        inherited_approvals = parent.approval_required.intersection(child_ops)
        if not inherited_approvals.issubset(child_approvals):
            raise PermissionError("delegation cannot remove an approval requirement for delegated operations")
        if not child_approvals.issubset(child_ops):
            raise PermissionError("approval requirements must be within delegated operations")
        if max_calls < 1 or max_calls > parent.max_calls:
            raise PermissionError("delegated call budget must be positive and no greater than parent")
        if not math.isfinite(max_cost) or max_cost < 0 or max_cost > parent.max_cost:
            raise PermissionError("delegated cost budget must not exceed parent")
        ttl_limit = min(MAX_CHILD_TTL_SECONDS, parent.expires_at - current)
        if not 1 <= ttl_seconds <= ttl_limit:
            raise PermissionError("child TTL must be positive, <= 900 seconds and <= parent remaining TTL")
        depth = parent.depth + 1
        if depth > MAX_DELEGATION_DEPTH:
            raise PermissionError("maximum delegation depth exceeded")
        child = CapabilityClaims(
            capability_id=str(uuid4()), subject=subject, task_id=parent.task_id,
            operations=child_ops, hosts=child_hosts, resource_prefixes=child_resources,
            issued_at=current, expires_at=current + ttl_seconds,
            max_calls=max_calls, max_cost=max_cost, approval_required=child_approvals,
            depth=depth, parent_id=parent.capability_id,
            budget_chain=parent.budget_chain + (
                BudgetGrant(parent.capability_id, parent.max_calls, parent.max_cost),
            ),
        )
        return self._encode(child)


class DecisionKind(str, Enum):
    ALLOW = "allow"
    APPROVAL_REQUIRED = "approval_required"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    operation: str
    host: str
    resource: str
    estimated_cost: float = 0.0
    approval_required: bool = False

    def __post_init__(self) -> None:
        _nonempty(self.operation, "operation")
        host = _nonempty(self.host, "host").lower()
        normalized_resource = _normalize_resource(self.resource)
        parsed = urlsplit(normalized_resource)
        if parsed.netloc and parsed.netloc.lower() != host:
            raise ValueError("resource URI authority must match the policy host")
        if not math.isfinite(self.estimated_cost) or self.estimated_cost < 0:
            raise ValueError("estimated_cost must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    kind: DecisionKind
    reason: str


def evaluate_capability(
    claims: CapabilityClaims, request: PolicyRequest, *, used_calls: int = 0,
    used_cost: float = 0.0, approval_verified: bool = False,
) -> PolicyDecision:
    """Pure policy-decision-point function; callers must enforce its result."""
    if request.operation not in claims.operations:
        return PolicyDecision(DecisionKind.DENY, "operation_outside_capability")
    if request.host.lower() not in claims.hosts:
        return PolicyDecision(DecisionKind.DENY, "host_outside_capability")
    if not any(resource_is_within(request.resource, prefix) for prefix in claims.resource_prefixes):
        return PolicyDecision(DecisionKind.DENY, "resource_outside_capability")
    if used_calls >= claims.max_calls:
        return PolicyDecision(DecisionKind.DENY, "call_budget_exhausted")
    if used_cost + request.estimated_cost > claims.max_cost + 1e-12:
        return PolicyDecision(DecisionKind.DENY, "cost_budget_exhausted")
    if (request.approval_required or request.operation in claims.approval_required) and not approval_verified:
        return PolicyDecision(DecisionKind.APPROVAL_REQUIRED, "independent_approval_required")
    return PolicyDecision(DecisionKind.ALLOW, "capability_permits_operation")


def deterministic_idempotency_key(logical_scope: str, operation_ref: str) -> str:
    """UUIDv5 for one logical operation; retries must reuse the same logical_scope."""
    name = canonical_json({
        "logical_scope": _nonempty(logical_scope, "logical_scope"),
        "operation_ref": _nonempty(operation_ref, "operation_ref"),
    }).decode("utf-8")
    return str(uuid5(IDEMPOTENCY_NAMESPACE, name))


@dataclass(frozen=True, slots=True)
class DelegationEdge:
    parent: str
    child: str


def validate_delegation_dag(
    edges: Iterable[DelegationEdge], *, max_depth: int = MAX_DELEGATION_DEPTH,
) -> dict[str, int]:
    """Validate a delegation DAG and return longest root-relative node depths."""
    if not 0 <= max_depth <= MAX_DELEGATION_DEPTH:
        raise ValueError("max_depth may not exceed 3")
    adjacency: dict[str, set[str]] = {}
    nodes: set[str] = set()
    for edge in edges:
        parent = _nonempty(edge.parent, "parent")
        child = _nonempty(edge.child, "child")
        if parent == child:
            raise ValueError("delegation graph contains a self-cycle")
        adjacency.setdefault(parent, set()).add(child)
        adjacency.setdefault(child, set())
        nodes.update((parent, child))
    visiting: set[str] = set()
    visited: set[str] = set()
    topological: list[str] = []

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("delegation graph contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for child in sorted(adjacency[node]):
            visit(child)
        visiting.remove(node)
        visited.add(node)
        topological.append(node)

    for node in sorted(nodes):
        visit(node)
    incoming = {child for children in adjacency.values() for child in children}
    roots = nodes - incoming
    if nodes and not roots:
        raise ValueError("delegation graph has no root")
    depths = {node: 0 for node in roots}
    for node in reversed(topological):
        if node not in depths:
            continue
        for child in adjacency[node]:
            depths[child] = max(depths.get(child, 0), depths[node] + 1)
            if depths[child] > max_depth:
                raise ValueError("maximum delegation depth exceeded")
    if set(depths) != nodes:
        raise ValueError("delegation graph contains unreachable nodes")
    return depths
