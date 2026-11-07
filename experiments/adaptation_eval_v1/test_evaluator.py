from __future__ import annotations

import unittest

from evaluator import Arm, CostObservation, Trial, evaluate_pairs, exact_mcnemar_two_sided_p

D = "a" * 64
B = "b" * 64
C = "c" * 64
E = "e" * 64
A = "d" * 64


def make_trial(
    pair: str,
    arm: Arm,
    *,
    opportunity: bool | None = True,
    action: bool | None = False,
    loaded: bool | None = None,
    adaptation_digest: str = A,
    task_success: bool | None = True,
    contract_passed: bool | None = True,
    environment: str = C,
    trace_complete: bool = True,
    violations: tuple[str, ...] = (),
    unrelated: int | None = 0,
    costs: tuple[CostObservation, ...] = (),
) -> Trial:
    adapted = arm is Arm.ADAPTED
    return Trial(
        pair_id=pair, case_id=f"case-{pair}", arm=arm,
        input_sha256=D, task_signature_sha256=B,
        base_harness_sha256=C,
        effective_harness_sha256=(C if loaded is False else E) if adapted else C,
        environment_sha256=environment, agent_sha256=D, model_sha256=B,
        opportunity_present=opportunity, target_action_observed=action,
        task_success=task_success, contract_passed=contract_passed,
        adaptation_digest=adaptation_digest if adapted else None,
        adaptation_loaded=loaded if adapted else None,
        trace_complete=trace_complete, constraint_violations=violations,
        unrelated_work_count=unrelated, costs=costs,
    )


class PairedEvaluationTests(unittest.TestCase):
    def pair(self, pair_id, baseline_action, adapted_action, **adapted_kwargs):
        return (
            make_trial(pair_id, Arm.BASELINE, action=baseline_action),
            make_trial(pair_id, Arm.ADAPTED, action=adapted_action, **adapted_kwargs),
        )

    def test_paired_contingency_table_counts_all_four_cells(self):
        trials = (
            *self.pair("1", True, False),
            *self.pair("2", True, True),
            *self.pair("3", False, True),
            *self.pair("4", False, False),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=4)
        self.assertEqual(result.eligible_opportunity_pairs, 4)
        self.assertEqual((result.both_recur, result.baseline_only_recur,
                          result.adapted_only_recur, result.neither_recur), (1, 1, 1, 1))
        self.assertEqual((result.baseline_recurrences, result.adapted_recurrences), (2, 2))
        self.assertEqual(result.risk_difference_adapted_minus_baseline, 0.0)
        self.assertTrue(result.minimum_opportunity_pairs_met)

    def test_exact_mcnemar_uses_only_discordant_pairs(self):
        self.assertEqual(exact_mcnemar_two_sided_p(4, 0), 0.125)
        self.assertEqual(exact_mcnemar_two_sided_p(0, 0), 1.0)
        self.assertEqual(exact_mcnemar_two_sided_p(10, 0), 0.001953125)

    def test_absent_opportunity_is_not_counted_as_prevention(self):
        trials = (
            make_trial("1", Arm.BASELINE, opportunity=False, action=False),
            make_trial("1", Arm.ADAPTED, opportunity=False, action=False),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        self.assertEqual(result.eligible_opportunity_pairs, 0)
        self.assertEqual(dict(result.exclusion_counts)["no_opportunity"], 1)
        self.assertIsNone(result.baseline_rate)

    def test_unknown_opportunity_or_action_is_not_relabelled_as_absence(self):
        trials = (
            make_trial("unknown-opportunity", Arm.BASELINE, opportunity=None, action=False),
            make_trial("unknown-opportunity", Arm.ADAPTED, opportunity=None, action=False),
            make_trial("unknown-action", Arm.BASELINE, action=None),
            make_trial("unknown-action", Arm.ADAPTED, action=False),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        self.assertEqual(result.eligible_opportunity_pairs, 0)
        self.assertEqual(dict(result.exclusion_counts)["opportunity_unknown"], 1)
        self.assertEqual(dict(result.exclusion_counts)["target_action_unknown"], 1)

    def test_unloaded_adaptation_stays_in_intention_to_treat_denominator(self):
        trials = self.pair("1", True, False, loaded=False)
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        self.assertEqual(result.eligible_opportunity_pairs, 1)
        self.assertEqual(result.baseline_recurrences, 1)
        self.assertEqual(result.adapted_recurrences, 0)
        self.assertEqual(result.adaptation_load_observed, 1)
        self.assertEqual(result.adaptation_loaded, 0)
        self.assertEqual(result.adaptation_loading_rate, 0.0)

    def test_mismatched_environment_is_excluded_and_named(self):
        trials = (
            make_trial("1", Arm.BASELINE, action=True),
            make_trial("1", Arm.ADAPTED, action=False, environment=E),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        self.assertEqual(result.eligible_opportunity_pairs, 0)
        self.assertEqual(dict(result.exclusion_counts)["pair_identity_mismatch"], 1)

    def test_duplicate_arm_and_invalid_action_opportunity_pair_fail_closed(self):
        baseline = make_trial("1", Arm.BASELINE)
        with self.assertRaisesRegex(ValueError, "duplicate baseline"):
            evaluate_pairs((baseline, baseline), minimum_opportunity_pairs=1)
        with self.assertRaisesRegex(ValueError, "cannot be observed"):
            make_trial("2", Arm.BASELINE, opportunity=False, action=True)

    def test_cost_dimensions_remain_separate_and_unit_scoped(self):
        base_costs = (
            CostObservation("provider_tokens", 100, "tokens"),
            CostObservation("tool_calls", 5, "calls"),
        )
        adapted_costs = (
            CostObservation("provider_tokens", 80, "tokens"),
            CostObservation("tool_calls", 6, "calls"),
        )
        trials = (
            make_trial("1", Arm.BASELINE, costs=base_costs),
            make_trial("1", Arm.ADAPTED, costs=adapted_costs),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        costs = {item.metric: item for item in result.cost_summaries}
        self.assertEqual(set(costs), {"provider_tokens", "tool_calls"})
        self.assertEqual(costs["provider_tokens"].adapted_minus_baseline, -20.0)
        self.assertEqual(costs["tool_calls"].adapted_minus_baseline, 1.0)
        self.assertNotEqual(costs["provider_tokens"].unit, costs["tool_calls"].unit)

    def test_constraints_are_reported_as_hard_signals_not_offset_by_savings(self):
        trials = (
            make_trial("1", Arm.BASELINE, action=True),
            make_trial("1", Arm.ADAPTED, action=False, violations=("approval_bypass",)),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        self.assertEqual(result.adapted_pairs_with_constraint_violations, 1)
        self.assertEqual(result.adapted_constraint_violation_count, 1)
        self.assertIsNone(getattr(result, "promotion_verdict", None))

    def test_adaptation_digest_is_fixed_for_one_evaluation(self):
        first = self.pair("1", True, False)
        second = (
            make_trial("2", Arm.BASELINE, action=True),
            make_trial("2", Arm.ADAPTED, action=False, adaptation_digest="f" * 64),
        )
        with self.assertRaisesRegex(ValueError, "mix different adaptation digests"):
            evaluate_pairs((*first, *second), minimum_opportunity_pairs=1)
        with self.assertRaisesRegex(ValueError, "does not match"):
            evaluate_pairs(first, minimum_opportunity_pairs=1,
                           expected_adaptation_digest="f" * 64)

    def test_explicit_loading_state_must_match_effective_harness_fingerprint(self):
        with self.assertRaisesRegex(ValueError, "unloaded adaptation"):
            Trial(
                pair_id="x", case_id="case-x", arm=Arm.ADAPTED,
                input_sha256=D, task_signature_sha256=B, base_harness_sha256=C,
                effective_harness_sha256=E, environment_sha256=C, agent_sha256=D,
                model_sha256=B, opportunity_present=True, target_action_observed=False,
                task_success=True, contract_passed=True, adaptation_digest=A,
                adaptation_loaded=False,
            )
        with self.assertRaisesRegex(ValueError, "loaded adaptation"):
            Trial(
                pair_id="x", case_id="case-x", arm=Arm.ADAPTED,
                input_sha256=D, task_signature_sha256=B, base_harness_sha256=C,
                effective_harness_sha256=C, environment_sha256=C, agent_sha256=D,
                model_sha256=B, opportunity_present=True, target_action_observed=False,
                task_success=True, contract_passed=True, adaptation_digest=A,
                adaptation_loaded=True,
            )

    def test_cost_missingness_is_not_silently_dropped(self):
        base_costs = (CostObservation("tool_calls", 5, "calls"),)
        trials = (
            make_trial("1", Arm.BASELINE, costs=base_costs),
            make_trial("1", Arm.ADAPTED, costs=()),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        summary = result.cost_summaries[0]
        self.assertEqual(summary.metric, "tool_calls")
        self.assertEqual(summary.paired_samples, 0)
        self.assertEqual(summary.missing_pairs, 1)
        self.assertEqual(result.unrelated_work_unknown, 0)

    def test_incomplete_trace_is_excluded_without_erasing_its_assignment(self):
        trials = (
            make_trial("1", Arm.BASELINE, trace_complete=False),
            make_trial("1", Arm.ADAPTED, trace_complete=True, loaded=True),
        )
        result = evaluate_pairs(trials, minimum_opportunity_pairs=1)
        self.assertEqual(result.adapted_trials_assigned, 1)
        self.assertEqual(result.eligible_opportunity_pairs, 0)
        self.assertEqual(dict(result.exclusion_counts)["incomplete_trace"], 1)


if __name__ == "__main__":
    unittest.main()
