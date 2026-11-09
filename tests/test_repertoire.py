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
    context_requirements: tuple[tuple[str, str], ...] = (),
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
        context_requirements=context_requirements,
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
    facts: dict[str, str] | None = None,
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
        facts=tuple(sorted((facts or {}).items())),
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
        available_capabilities=frozenset(f"{name}@1.0.0" for name in available),
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
    max_capabilities: int = 8,
    max_search_states: int = 10000,
    permitted_effects: set[OperationEffect] | None = None,
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
            permitted_effects=frozenset(
                permitted_effects or {OperationEffect.READ_ONLY}
            ),
        ),
        composition_policy=CompositionPolicy(
            primary_cost=objective,
            max_capabilities=max_capabilities,
            max_search_states=max_search_states,
        ),
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
        self.assertEqual(result.missing_inputs, frozenset({"complete_diff"}))

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

    def test_situation_conditions_select_context_appropriate_capability(self) -> None:
        docs_checker = capability(
            "docs-checker", {"validation"},
            context_requirements=(("change_kind", "documentation"),),
        )
        source_checker = capability(
            "source-checker", {"validation"},
            context_requirements=(("change_kind", "source"),),
        )
        result = compose_habit(
            habit((docs_checker, source_checker), outcomes={"validation"}),
            situation(facts={"change_kind": "documentation"}),
            host(available={"docs-checker", "source-checker"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.READY)
        self.assertEqual(result.selected_ids, ("docs-checker",))
        rejected = {item.capability_id: item.reasons for item in result.rejected}
        self.assertIn("situation_condition_mismatch:change_kind", rejected["source-checker"])

    def test_missing_situation_condition_blocks_specialized_capability(self) -> None:
        specialized = capability(
            "dependency-checker", {"validation"},
            context_requirements=(("dependency_changed", "true"),),
        )
        result = compose_habit(
            habit((specialized,), outcomes={"validation"}),
            situation(),
            host(available={"dependency-checker"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        rejected = {item.capability_id: item.reasons for item in result.rejected}
        self.assertIn("situation_condition_missing:dependency_changed", rejected["dependency-checker"])
        self.assertEqual(result.missing_inputs, frozenset({"dependency_changed"}))

    def test_composes_capability_chain_using_outputs_as_later_inputs(self) -> None:
        snapshot_reader = capability(
            "snapshot-reader", {"repository_snapshot"}, inputs={"repository"},
        )
        diff_parser = capability(
            "diff-parser", {"change_inventory"}, inputs={"repository_snapshot"},
        )
        test_index = capability(
            "test-index", {"tests"}, inputs={"change_inventory"},
        )
        result = compose_habit(
            habit(
                (snapshot_reader, diff_parser, test_index),
                outcomes={"tests"},
                inputs={"repository"},
            ),
            situation(available_inputs={"repository"}),
            host(available={"snapshot-reader", "diff-parser", "test-index"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.READY)
        self.assertEqual(
            result.selected_ids,
            ("snapshot-reader", "diff-parser", "test-index"),
        )
        self.assertEqual(result.covered_outcomes, frozenset({"tests"}))

    def test_primary_cost_dimension_is_explicit_not_blended(self) -> None:
        entries = (
            capability(
                "combined",
                {"scope", "tests"},
                cost=CostEstimate(calls=1, tokens=100),
            ),
            capability("scope-only", {"scope"}, cost=CostEstimate(calls=1, tokens=1)),
            capability("tests-only", {"tests"}, cost=CostEstimate(calls=1, tokens=1)),
        )

        call_plan = compose_habit(
            habit(entries, objective=CostDimension.CALLS),
            situation(),
            host(available={item.capability_id for item in entries}),
            now=NOW,
        )
        token_plan = compose_habit(
            habit(entries, objective=CostDimension.TOKENS),
            situation(),
            host(available={item.capability_id for item in entries}),
            now=NOW,
        )

        self.assertEqual(call_plan.selected_ids, ("combined",))
        self.assertEqual(token_plan.selected_ids, ("scope-only", "tests-only"))
        self.assertEqual(call_plan.estimated_cost.tokens, 100)
        self.assertEqual(token_plan.estimated_cost.calls, 2)

    def test_capability_limit_prevents_partial_ready_plan(self) -> None:
        entries = (
            capability("scope-only", {"scope"}),
            capability("tests-only", {"tests"}),
        )
        result = compose_habit(
            habit(entries, max_capabilities=1),
            situation(),
            host(available={"scope-only", "tests-only"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        self.assertEqual(result.reason, "capability_limit_prevents_coverage")
        self.assertEqual(result.selected, ())

    def test_search_state_limit_fails_closed(self) -> None:
        entries = (capability("combined", {"scope", "tests"}),)
        result = compose_habit(
            habit(entries, max_search_states=1),
            situation(),
            host(available={"combined"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        self.assertEqual(result.reason, "planning_state_limit_exceeded")
        self.assertEqual(result.selected, ())

    def test_dependency_cycle_does_not_produce_ready_plan(self) -> None:
        first = capability("first", {"first_result"}, inputs={"second_result"})
        second = capability("second", {"second_result"}, inputs={"first_result"})
        result = compose_habit(
            habit((first, second), outcomes={"first_result"}, inputs={"repository"}),
            situation(available_inputs={"repository"}),
            host(available={"first", "second"}),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        self.assertEqual(result.selected, ())
        self.assertIn("first_result", result.missing_outcomes)

    def test_host_snapshot_must_pin_exact_capability_version(self) -> None:
        item = capability("repo-reader", {"scope"})
        stale_host = HostCapabilitySnapshot(
            harness_id="local",
            harness_version="1",
            environment_id="repo",
            environment_version="1",
            available_capabilities=frozenset({"repo-reader@0.9.0"}),
            granted_permissions=frozenset(),
            allowed_effects=frozenset({OperationEffect.READ_ONLY}),
            snapshot_digest="sha256:stale-capability-version",
        )
        result = compose_habit(
            habit((item,), outcomes={"scope"}),
            situation(),
            stale_host,
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        rejected = {entry.capability_id: entry.reasons for entry in result.rejected}
        self.assertIn("capability_unavailable_in_host", rejected["repo-reader"])

    def test_habit_contract_can_forbid_effect_allowed_by_host(self) -> None:
        mutating = capability(
            "mutating-check",
            {"tests"},
            effect=OperationEffect.IDEMPOTENT,
        )
        result = compose_habit(
            habit(
                (mutating,),
                outcomes={"tests"},
                permitted_effects={OperationEffect.READ_ONLY},
            ),
            situation(),
            host(
                available={"mutating-check"},
                allowed_effects={OperationEffect.READ_ONLY, OperationEffect.IDEMPOTENT},
            ),
            now=NOW,
        )

        self.assertEqual(result.status, PlanStatus.NEEDS_CAPABILITY)
        rejected = {entry.capability_id: entry.reasons for entry in result.rejected}
        self.assertIn("effect_not_permitted_by_habit:idempotent", rejected["mutating-check"])

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
