"""First executable repository-verification habit binding.

This deliberately narrow habit composes one exact-version read-only Git
capability. It inspects immutable commit objects only; it does not run project
code, tests, CI, hooks, or mutate the working tree.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .git_repository import GitReadOnlyRepositoryAdapter, RepositoryChangeSnapshot
from .machine import OperationEffect
from .repertoire import (
    CapabilityEntry,
    CapabilityKind,
    CapabilityStatus,
    CompositionPolicy,
    CostDimension,
    CostEstimate,
    CompositionPlan,
    HabitDefinition,
    HostCapabilitySnapshot,
    OutcomeContract,
    PlanStatus,
    SituationFrame,
    compose_habit,
)


class RepositoryInspectionStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    PLAN_REJECTED = "plan_rejected"


@dataclass(frozen=True, slots=True)
class RepositoryInspectionRun:
    plan: CompositionPlan
    status: RepositoryInspectionStatus
    snapshot: RepositoryChangeSnapshot | None
    reason: str


def build_git_inspection_capability(
    adapter: GitReadOnlyRepositoryAdapter,
    *,
    harness_ref: str,
    environment_ref: str,
    evidence_digest: str,
    cost_estimate: CostEstimate,
    status: CapabilityStatus = CapabilityStatus.ACTIVE,
) -> CapabilityEntry:
    """Create the governed repertoire entry for a specific local Git adapter.

    The evidence digest must be supplied by the caller from its own verifier or
    release process. The adapter never self-asserts that it has been promoted.
    """
    if not evidence_digest.strip():
        raise ValueError("evidence_digest must be supplied by an external verifier")
    return CapabilityEntry(
        capability_id=adapter.CAPABILITY_ID,
        kind=CapabilityKind.TOOL,
        version=adapter.CAPABILITY_VERSION,
        provides=frozenset({"change_inventory", "changed_blob_observations"}),
        requires_inputs=frozenset({"repository", "base_commit", "target_commit"}),
        required_permissions=frozenset({"repository.read"}),
        compatible_harnesses=frozenset({harness_ref}),
        compatible_environments=frozenset({environment_ref}),
        effect=OperationEffect.READ_ONLY,
        status=status,
        evidence_digest=evidence_digest,
        context_requirements=(("repository_root", str(adapter.repository_root)),),
        cost=cost_estimate,
    )


def build_repository_verification_habit(
    capability: CapabilityEntry,
    *,
    habit_version: str = "0.3.0",
    max_situation_age_seconds: int = 300,
) -> HabitDefinition:
    """Build the first hand-designed repository inspection habit.

    Its outcome contract is deliberately limited to an immutable commit-range
    inventory and bounded blob observations. It does not claim test success,
    semantic correctness, or complete verification of the proposed change.
    """
    if capability.capability_id != GitReadOnlyRepositoryAdapter.CAPABILITY_ID:
        raise ValueError("repository verification requires the read-only Git capability")
    if capability.effect is not OperationEffect.READ_ONLY:
        raise ValueError("repository verification only accepts read-only capabilities")
    return HabitDefinition(
        habit_id="repo-change-verification",
        version=habit_version,
        purpose=(
            "Inventory a repository change between immutable commits and collect "
            "bounded, content-addressed blob observations without mutating the repository."
        ),
        capabilities=(capability,),
        outcome_contract=OutcomeContract(
            required_outcomes=frozenset({
                "change_inventory",
                "changed_blob_observations",
            }),
            required_inputs=frozenset({
                "repository",
                "base_commit",
                "target_commit",
            }),
            max_situation_age_seconds=max_situation_age_seconds,
            permitted_effects=frozenset({OperationEffect.READ_ONLY}),
        ),
        composition_policy=CompositionPolicy(
            primary_cost=CostDimension.CALLS,
            max_capabilities=1,
            max_search_states=32,
        ),
    )


def run_repository_verification_habit(
    habit: HabitDefinition,
    situation: SituationFrame,
    host: HostCapabilitySnapshot,
    adapter: GitReadOnlyRepositoryAdapter,
    *,
    now: datetime,
) -> RepositoryInspectionRun:
    """Compose the habit, then invoke its selected read-only Git capability.

    This is a real local adapter call after the planner has returned READY. The
    provided host snapshot is rechecked but is not authenticated here; the actual
    host process must enforce the same permission boundary. No other capability
    can be invoked by this first reference habit.
    """
    plan = compose_habit(habit, situation, host, now=now)
    if plan.status is not PlanStatus.READY:
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason=plan.reason,
        )

    selected = tuple(plan.selected)
    if len(selected) != 1:
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason="reference_habit_requires_exactly_one_selected_capability",
        )

    capability = selected[0]
    if (
        capability.capability_id != adapter.CAPABILITY_ID
        or capability.version != adapter.CAPABILITY_VERSION
    ):
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason="selected_capability_does_not_match_git_adapter",
        )

    # Re-check the host-supplied constraints immediately before invocation.
    if capability.version_ref not in host.available_capabilities:
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason="exact_capability_version_not_available_at_invocation",
        )
    if not capability.required_permissions.issubset(host.granted_permissions):
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason="host_permission_missing_at_invocation",
        )
    if (
        capability.effect not in habit.outcome_contract.permitted_effects
        or capability.effect not in host.allowed_effects
    ):
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason="read_only_effect_not_authorized_at_invocation",
        )

    facts = dict(situation.facts)
    required_facts = ("repository_root", "base_commit", "target_commit")
    missing_facts = tuple(key for key in required_facts if not facts.get(key))
    if missing_facts:
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason="situation_fact_missing:" + ",".join(missing_facts),
        )
    if facts["repository_root"] != str(adapter.repository_root):
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.PLAN_REJECTED,
            snapshot=None,
            reason="repository_root_does_not_match_adapter",
        )

    snapshot = adapter.inspect_commit_range(
        facts["base_commit"],
        facts["target_commit"],
    )
    if snapshot.inventory_complete and snapshot.content_complete:
        return RepositoryInspectionRun(
            plan=plan,
            status=RepositoryInspectionStatus.COMPLETE,
            snapshot=snapshot,
            reason="immutable_commit_inventory_and_bounded_blob_observations_collected",
        )
    return RepositoryInspectionRun(
        plan=plan,
        status=RepositoryInspectionStatus.INCOMPLETE,
        snapshot=snapshot,
        reason="inventory_collected_but_one_or_more_blob_contents_not_fully_read",
    )
