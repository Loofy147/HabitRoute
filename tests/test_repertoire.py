from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from habitroute.machine import OperationEffect
from habitroute.repertoire import (
    CapabilityEntry,
    CapabilityKind,
    CapabilityStatus,
    CompositionPolicy,
    CostDimension,
    CostEstimate,
    HabitDefinition,
    HostCapabilitySnapshot,
    OutcomeContract,
    PlanStatus,
    SituationFrame,
    compose_habit,
)


NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def capability(
    capability_id: str,
    provides: set[str],
    *,
    cost: CostEstimate | None = None,
    inputs: set[str] | None = None,
    permissions: set[str] | None = None,
    status: CapabilityStatus = CapabilityStatus.ACTIVE,
    evidence_digest: str | None = "sha256:verified",
    harnesses: set[str] | None = None,
    environments: set[str] | None = None,
    effect: OperationEffect = OperationEffect.READ_ONLY,
) -> CapabilityEntry:
    return CapabilityEntry(
        capability_id=capability_id,
        kind=CapabilityKind.TOOL,
        version="1.0.0",
        provides=frozenset(provides),
        requires_inputs=frozenset(inputs or set()),
        required_permissions=frozenset(permissions or set()),
        compatible_harnesses=frozenset(harnesses or {"local@1"}),
        compatible_environments=frozenset(environments or {"repo@1"}),
        effect=effect,
        status=status,
        evidence_digest=evidence_digest,
        cost=cost or CostEstimate(calls=1),
    )


def situation(
    *,
    observed_at: datetime = NOW,
    available_inputs: set[str] | None = None,
    harness_id: str = "local",
    harness_version: str = "1",
    environment_id: str = "repo",
    environment_version: str = "1",
) -> SituationFrame:
    return SituationFrame(
        situation_id="situation-001",
        observed_at=observed_at,
        harness_id=harness_id,
        harness_version=harness_version,
        environment_id=environment_id,
        environment_version=environment_version,
        available_inputs=frozenset(available_inputs or {"repository", "diff"}),
        context_digest="sha256:context",
    )


def host(
    *,
    available: set[str],
    permissions: set[str] | None = None,
    allowed_effects: set[OperationEffect] | None = None,
) -> HostCapabilitySnapshot:
    return HostCapabilitySnapshot(
        harness_id="local",
        harness_version="1",
        environment_id="repo",
        environment_version="1",
        available_capabilities=frozenset(available),
        granted_permissions=frozenset(permissions or set()),
        allowed_effects=frozenset(allowed_effects or {OperationEffect.READ_ONLY}),
        snapshot_digest="sha256:host-snapshot",
    )


def habit(
    capabilities: tuple[CapabilityEntry, ...],
    *,
    outcomes: set[str] | None = None,
    inputs: set[str] | None = None,
    max_age: int = 300,
    objective: CostDimension = CostDimension.CALLS,
) -> HabitDefinition:
    return HabitDefinition(
        habit_id="repo-change-verification",
        version="0.3.0",
        purpose="Verify repository changes with the minimum sufficient read-only capabilities.",
        capabilities=capabilities,
        outcome_contract=OutcomeContract(
            required_outcomes=frozenset(outcomes or {"scope", "tests"}),
            required_inputs=frozenset(inputs or {"repository", "diff"}),
            max_situation_age_seconds=max_age,
        ),
        composition_policy=CompositionPolicy(primary_cost=objective, max_capabilities=8),
    )


class RepertoireCompositionTests(unittest.TestCase):
    def test_composes_lowest_cost_sufficient_capability_set(self) -> None:
        entries = (
            capability("git-scope", {"scope"}, cost=CostEstimate(calls=1, latency_ms=20)),
            capability("test-map", {"tests"}, cost=CostEstimate(calls=1, latency_ms=30)),
            capability("expensive-suite", {"scope", "tests"}, cost=CostEstimate(calls=5, latency_ms=5)),
            capability("irrelevant", {"formatting"}, cost=CostEstimate(calls=0.1)),
        )
        result = compose_habit(habit(entries), situation(), host(available={e.capability_id for e in entries}), now=NOW)

        self.assertEqual(result.status, PlanStatus.READY)
        self.assertEqual([item.capability_id for item in result.selected], ["git-scope", "test-map"])
        self.assertEqual(result.covered_outcomes, frozenset({"scope", "tests"}))
        self.assertEqual(result.estimated_cost.calls, 2)
        self.assertTrue(result.dry_run)
        self.assertIn("expensive-suite", {item.capability_id for item in result.rejected})
        self.assertIn("irrelevant", {item.capability_id for item in result.rejected})

    def test_selects_one_capability_when_it_is_cheaper_than_composition(self) -> None:
        entries = (
            capability("combined", {"scope", "tests"}, cost=CostEstimate(calls=1)),
            capability("scope-only", {"scope"}, cost=CostEstimate(calls=1)),
            capability("tests-only", {"tests"}, cost=CostEstimate(calls=1)),
        )
        result = compose_habit(habit(entries), situation(), host(available={e.capability_id for e in entries}), now=NOW)

        self.assertEqual(result.status, PlanStatus.READY)
        self.assertEqual([item.capability_id for item in result.selected], ["combined"])
        self.assertEqual(result.estimated_cost.calls, 1)

    def test_inactive_or_unverified_capability_is_not_selected(self) -> None:
        inactive = capability(
            "draft-tool", {"scope"}, status=CapabilityStatus.CANDIDATE, evidence_digest=None
        )
        active = capability("verified-tool", {"scope"})
        test_tool = capability("test-tool", {"tests"})
        result = compose_habit(
            habit((inactive, active, test_tool)),
            situation(),
            host(available={"draft-tool", "verified-tool", "test-tool"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.READY)
        self.assertNotIn("draft-tool", [item.capability_id for item in result.selected])
        rejected = {item.capability_id: item.reasons for item in result.rejected}
        self.assertIn("capability_not_active", rejected["draft-tool"])

    def test_rejects_missing_host_permission_and_missing_context_input(self) -> None:
        restricted = capability(
            "dependency-scanner",
            {"dependencies"},
            inputs={"lockfile"},
            permissions={"repository.read", "process.execute"},
        )
        result = compose_habit(
            habit((restricted,), outcomes={"dependencies"}, inputs={"repository", "diff"}),
            situation(available_inputs={"repository", "diff", "lockfile"}),
            host(available={"dependency-scanner"}, permissions={"repository.read"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        self.assertEqual(result.missing_outcomes, frozenset({"dependencies"}))
        rejected = {item.capability_id: item.reasons for item in result.rejected}
        self.assertIn("host_permission_missing:process.execute", rejected["dependency-scanner"])

    def test_rejects_capability_when_required_input_is_absent(self) -> None:
        requires = capability("diff-parser", {"scope"}, inputs={"complete_diff"})
        test_tool = capability("test-map", {"tests"})
        result = compose_habit(
            habit((requires, test_tool)),
            situation(available_inputs={"repository", "diff"}),
            host(available={"diff-parser", "test-map"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        rejected = {item.capability_id: item.reasons for item in result.rejected}
        self.assertIn("situation_input_missing:complete_diff", rejected["diff-parser"])

    def test_rejects_unavailable_and_incompatible_capabilities(self) -> None:
        unavailable = capability("not-installed", {"scope"})
        incompatible = capability("wrong-host", {"scope"}, harnesses={"other@9"})
        tests = capability("test-map", {"tests"})
        result = compose_habit(
            habit((unavailable, incompatible, tests)),
            situation(),
            host(available={"wrong-host", "test-map"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        rejected = {item.capability_id: item.reasons for item in result.rejected}
        self.assertIn("capability_unavailable_in_host", rejected["not-installed"])
        self.assertIn("harness_incompatible", rejected["wrong-host"])

    def test_fails_closed_when_environment_or_harness_snapshot_mismatches(self) -> None:
        entries = (capability("scope", {"scope"}), capability("tests", {"tests"}))
        result = compose_habit(
            habit(entries),
            situation(),
            HostCapabilitySnapshot(
                harness_id="different",
                harness_version="9",
                environment_id="repo",
                environment_version="1",
                available_capabilities=frozenset({"scope", "tests"}),
                granted_permissions=frozenset(),
                allowed_effects=frozenset({OperationEffect.READ_ONLY}),
                snapshot_digest="sha256:other-host",
            ),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.BLOCKED_CONTEXT)
        self.assertEqual(result.selected, ())

    def test_stale_situation_is_not_used(self) -> None:
        entries = (capability("scope", {"scope"}), capability("tests", {"tests"}))
        result = compose_habit(
            habit(entries, max_age=60),
            situation(observed_at=NOW - timedelta(seconds=61)),
            host(available={"scope", "tests"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.STALE_SITUATION)
        self.assertEqual(result.selected, ())

    def test_required_information_missing_is_distinct_from_missing_capability(self) -> None:
        entries = (capability("scope", {"scope"}), capability("tests", {"tests"}))
        result = compose_habit(
            habit(entries, inputs={"repository", "diff", "acceptance_criteria"}),
            situation(),
            host(available={"scope", "tests"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_INFORMATION)
        self.assertEqual(result.missing_inputs, frozenset({"acceptance_criteria"}))

    def test_read_only_snapshot_rejects_mutating_capability(self) -> None:
        entries = (
            capability("scope", {"scope"}, effect=OperationEffect.READ_ONLY),
            capability("repair", {"tests"}, effect=OperationEffect.IDEMPOTENT),
        )
        result = compose_habit(
            habit(entries),
            situation(),
            host(available={"scope", "repair"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        rejected = {item.capability_id: item.reasons for item in result.rejected}
        self.assertIn("effect_not_authorized:idempotent", rejected["repair"])

    def test_missing_outcome_is_explicit_and_no_partial_plan_is_ready(self) -> None:
        entries = (capability("scope", {"scope"}),)
        result = compose_habit(
            habit(entries),
            situation(),
            host(available={"scope"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        self.assertEqual(result.missing_outcomes, frozenset({"tests"}))
        self.assertEqual(result.selected, ())

    def test_tie_breaking_is_deterministic(self) -> None:
        entries = (
            capability("z-tool", {"scope"}, cost=CostEstimate(calls=1)),
            capability("a-tool", {"scope"}, cost=CostEstimate(calls=1)),
            capability("test-tool", {"tests"}),
        )
        result = compose_habit(
            habit(entries),
            situation(),
            host(available={e.capability_id for e in entries}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.READY)
        self.assertEqual([item.capability_id for item in result.selected], ["a-tool", "test-tool"])

    def test_rejects_duplicate_capability_ids(self) -> None:
        item = capability("duplicate", {"scope"})
        with self.assertRaisesRegex(ValueError, "unique"):
            habit((item, item))

    def test_active_capability_requires_evidence_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence_digest"):
            capability("unproven-active", {"scope"}, evidence_digest=None)

    def test_future_situation_time_is_not_accepted(self) -> None:
        entries = (capability("scope", {"scope"}), capability("tests", {"tests"}))
        result = compose_habit(
            habit(entries),
            situation(observed_at=NOW + timedelta(seconds=1)),
            host(available={"scope", "tests"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.BLOCKED_CONTEXT)
        self.assertEqual(result.selected, ())


if __name__ == "__main__":
    unittest.main()
