"""Independent recovery and candidate-promotion gates."""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Protocol

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_PROMOTION_INVARIANTS = frozenset({
    "capability_scope_enforced",
    "delegation_dag_bounded",
    "external_mutations_via_egress",
    "unknown_outcomes_never_replayed",
    "recovery_snapshot_precedes_destructive_operation",
    "audit_chain_valid",
    "no_raw_secrets_persisted",
})


@dataclass(frozen=True, slots=True)
class SnapshotEvidence:
    workflow_id: str
    snapshot_id: str
    provider: str
    state_sequence: int
    state_sha256: str
    committed_at: int
    recovery_point_ref: str
    receipt: str

    def __post_init__(self) -> None:
        for field in ("workflow_id", "snapshot_id", "provider", "recovery_point_ref", "receipt"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must be non-empty")
        if self.state_sequence < 0 or self.committed_at < 1:
            raise ValueError("snapshot sequence and commit time are invalid")
        if not _SHA256.fullmatch(self.state_sha256):
            raise ValueError("snapshot state_sha256 must be a lowercase SHA-256 digest")


class SnapshotVerifier(Protocol):
    """Provider-specific verifier for an independently committed CoW/PITR point."""
    def verify(self, evidence: SnapshotEvidence) -> bool: ...


def require_recovery_snapshot(
    evidence: SnapshotEvidence | None, verifier: SnapshotVerifier, *,
    workflow_id: str, required_sequence: int, expected_state_sha256: str,
    max_age_seconds: int = 3600, now: int | None = None,
) -> SnapshotEvidence:
    """Fail closed unless a provider-verified recovery point covers current state."""
    current = int(time.time()) if now is None else int(now)
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    if not _SHA256.fullmatch(expected_state_sha256):
        raise ValueError("expected_state_sha256 must be a lowercase SHA-256 digest")
    if evidence is None:
        raise PermissionError("destructive operation blocked: recovery snapshot is missing")
    if evidence.workflow_id != workflow_id:
        raise PermissionError("recovery snapshot belongs to another workflow")
    if evidence.state_sequence != required_sequence:
        raise PermissionError("recovery snapshot sequence does not match the exact pre-mutation state")
    if evidence.state_sha256 != expected_state_sha256:
        raise PermissionError("recovery snapshot state hash does not match the exact pre-mutation state")
    if evidence.committed_at > current or current - evidence.committed_at > max_age_seconds:
        raise PermissionError("recovery snapshot is future-dated or too old")
    if not verifier.verify(evidence):
        raise PermissionError("recovery snapshot receipt failed independent verification")
    return evidence


@dataclass(frozen=True, slots=True)
class CandidatePatch:
    base_version: str
    candidate_version: str
    diff_sha256: str
    rationale: str
    expected_telemetry_delta: str
    candidate_ref: str

    def __post_init__(self) -> None:
        for field in ("base_version", "candidate_version", "rationale", "expected_telemetry_delta", "candidate_ref"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must be non-empty")
        if not _SHA256.fullmatch(self.diff_sha256):
            raise ValueError("diff_sha256 must be a lowercase SHA-256 digest")
        if self.base_version == self.candidate_version:
            raise ValueError("candidate version must differ from base version")
        ref = self.candidate_ref.removeprefix("refs/heads/")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", ref):
            raise ValueError("candidate_ref must identify a valid branch reference")
        if ref.lower() in {"main", "master", "production", "prod", "release"}:
            raise ValueError("candidate_ref must not target a protected production branch")


@dataclass(frozen=True, slots=True)
class ShadowReplayReport:
    candidate_version: str
    diff_sha256: str
    replay_count: int
    failures: int
    invariant_results: tuple[tuple[str, bool], ...]
    observed_telemetry: str

    def __post_init__(self) -> None:
        if self.replay_count < 1 or not 0 <= self.failures <= self.replay_count:
            raise ValueError("shadow replay counts are invalid")
        names = [name for name, _ in self.invariant_results]
        if not names or len(names) != len(set(names)):
            raise ValueError("shadow replay must report each named invariant exactly once")


@dataclass(frozen=True, slots=True)
class ControlPlaneApproval:
    candidate_version: str
    diff_sha256: str
    decision: str
    approval_id: str
    expires_at: int
    signature: str


class ControlPlaneVerifier(Protocol):
    """Verifies approval issued outside the candidate being evaluated."""
    def verify(self, approval: ControlPlaneApproval) -> bool: ...


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    promotable: bool
    reason: str


def evaluate_promotion(
    patch: CandidatePatch, shadow: ShadowReplayReport,
    approval: ControlPlaneApproval | None, verifier: ControlPlaneVerifier,
    *, min_replays: int = 20, now: int | None = None,
) -> PromotionDecision:
    """Evaluate promotion evidence; this function never deploys or changes a ref."""
    current = int(time.time()) if now is None else int(now)
    if min_replays < 1:
        raise ValueError("min_replays must be positive")
    if shadow.candidate_version != patch.candidate_version or shadow.diff_sha256 != patch.diff_sha256:
        return PromotionDecision(False, "shadow_replay_does_not_match_candidate_diff")
    if shadow.replay_count < min_replays:
        return PromotionDecision(False, "insufficient_shadow_replays")
    if shadow.failures:
        return PromotionDecision(False, "shadow_replay_failures_present")
    observed_invariants = {name for name, _ in shadow.invariant_results}
    missing = REQUIRED_PROMOTION_INVARIANTS - observed_invariants
    if missing:
        return PromotionDecision(False, "required_promotion_invariants_missing:" + ",".join(sorted(missing)))
    if not all(result for _, result in shadow.invariant_results):
        return PromotionDecision(False, "runtime_invariant_failed")
    if approval is None:
        return PromotionDecision(False, "external_control_plane_approval_missing")
    if (approval.candidate_version, approval.diff_sha256) != (
        patch.candidate_version, patch.diff_sha256
    ):
        return PromotionDecision(False, "control_plane_approval_targets_different_candidate")
    if approval.decision != "allow" or approval.expires_at <= current:
        return PromotionDecision(False, "control_plane_approval_denied_or_expired")
    if not approval.approval_id.strip() or not approval.signature.strip():
        return PromotionDecision(False, "control_plane_approval_signature_invalid")
    try:
        verified = verifier.verify(approval)
    except Exception:
        verified = False
    if not verified:
        return PromotionDecision(False, "control_plane_approval_signature_invalid")
    return PromotionDecision(True, "shadow_replay_invariants_and_external_approval_passed")
