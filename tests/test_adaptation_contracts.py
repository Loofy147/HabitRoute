"""Schema-level tests for retrospective adaptation design contracts.

These tests validate draft shapes and selected fail-closed schema conditions.
They do not claim runtime trace emission, paired-trial semantic validation,
statistical analysis, or candidate promotion.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / 'shared' / 'contracts' / 'adaptation' / 'v0.1'
DIGEST = 'a' * 64

def schema(name: str) -> dict:
    with (CONTRACTS / name).open(encoding='utf-8') as stream:
        value = json.load(stream)
    Draft202012Validator.check_schema(value)
    return value

def valid_proposal() -> dict:
    return {
        'schema_version': 'adaptation/0.1', 'proposal_id': 'p-1',
        'created_at': '2026-11-07T10:00:00Z',
        'target': {'kind': 'harness_asset', 'id': 'repo-guidance', 'version': '1',
                   'definition_sha256': DIGEST, 'harness_id': 'readonly-repo',
                   'harness_version': '3', 'environment_fingerprint_sha256': DIGEST,
                   'task_signature_sha256': DIGEST},
        'source_basis': {'origin': 'experience_driven', 'eligible_held_run_refs': ['held-1'],
                         'observed_event_refs': ['event-1'], 'prior_basis_refs': [],
                         'causal_link': 'The verified trace records the same failed runner attempt.',
                         'all_held_runs_revalidated': True},
        'mechanism': 'instruction',
        'target_behavior': {'action_signature': 'invoke-unavailable-runner',
                            'opportunity_definition': 'The pinned environment lacks that runner.',
                            'unit_of_analysis': 'matched_task_pair', 'expected_direction': 'reduce'},
        'hypothesis': {'statement': 'A repository-scoped runner pointer reduces unnecessary attempts.',
                       'minimum_absolute_rate_change': 0.1, 'quality_noninferiority_margin': 0.01,
                       'predicted_side_effects': ['Additional instruction-read overhead.']},
        'delta': {'change_summary': 'Add one verified runner pointer.', 'mechanism': 'instruction',
                  'artifact_ref': 'artifact:instructions-v1', 'artifact_sha256': DIGEST,
                  'changed_paths': ['AGENTS.md'], 'atomic_change_unit': True,
                  'rollback_ref': 'revert:commit-1'},
        'evaluation_plan': {'design_id': 'transfer-1', 'design': 'matched_randomized',
                            'min_total_pairs': 20, 'min_opportunity_pairs': 12, 'alpha': 0.05,
                            'familywise_comparisons': 1,
                            'sample_size_rationale': 'Pre-registered matched design based on a minimum useful effect.',
                            'primary_metric': 'target_action_recurrence', 'plan_sha256': DIGEST,
                            'preregistered_at': '2026-11-07T09:00:00Z'},
        'state': 'ready_for_evaluation'
    }

def valid_trial(arm: str) -> dict:
    adapted = arm == 'adapted'
    return {
        'schema_version': 'adaptation/0.1', 'trial_id': 't-' + arm, 'pair_id': 'pair-1',
        'proposal_id': 'p-1', 'arm': arm, 'case_id': 'case-1',
        'case_input_sha256': DIGEST, 'task_signature_sha256': DIGEST,
        'harness_id': 'readonly-repo', 'base_harness_version': '3',
        'base_harness_fingerprint_sha256': DIGEST,
        'effective_harness_fingerprint_sha256': ('b' * 64) if adapted else DIGEST,
        'environment_fingerprint_sha256': DIGEST, 'agent_fingerprint_sha256': DIGEST,
        'model_fingerprint_sha256': DIGEST, 'started_at': '2026-11-07T11:00:00Z',
        'finished_at': '2026-11-07T11:01:00Z', 'target_opportunity_present': True,
        'opportunity_evidence_ref': 'evidence:opportunity-1',
        'target_action_observed': False if adapted else True, 'trace_completeness': 'complete',
        'adaptation_digest': ('b' * 64) if adapted else None,
        'adaptation_loaded': True if adapted else None, 'task_outcome': 'success',
        'contract_outcome': 'passed', 'constraint_violations': [],
        'intervention_observability': 'complete', 'intervention_count': 0,
        'cost_observations': [{'metric': 'tool_calls', 'value': 4, 'unit': 'calls',
                              'measurement_kind': 'observed'}],
        'evidence_refs': ['evidence:trace-' + arm, 'evidence:outcome-' + arm]
    }

def valid_evaluation() -> dict:
    return {
        'schema_version': 'adaptation/0.1', 'evaluation_id': 'eval-1', 'proposal_id': 'p-1',
        'evaluation_plan_sha256': DIGEST, 'derived_at': '2026-11-07T12:00:00Z',
        'evaluator': {'name': 'adaptation-evaluator', 'version': '0.1', 'implementation_sha256': DIGEST},
        'raw_trial_refs': ['trial:baseline-1', 'trial:adapted-1'], 'raw_trials_sha256': DIGEST,
        'counts': {'attempted_pairs': 20, 'complete_pairs': 20, 'opportunity_pairs': 12,
                   'baseline_recurrences': 8, 'adapted_recurrences': 4,
                   'baseline_only_recurrences': 5, 'adapted_only_recurrences': 1},
        'primary_effect': {'metric': 'target_action_recurrence', 'baseline_rate': 0.67,
                           'adapted_rate': 0.33, 'risk_difference': -0.34,
                           'interval_low': -0.6, 'interval_high': -0.08,
                           'confidence_level': 0.95, 'method': 'paired-exact',
                           'adjusted_alpha': 0.05, 'p_value': 0.04, 'directional_evidence': True},
        'quality_gate': {'baseline_successes': 20, 'adapted_successes': 20, 'evaluated_pairs': 20,
                         'observed_success_difference': 0.0, 'noninferiority_margin': 0.02,
                         'lower_confidence_bound': -0.01, 'passed': True},
        'constraint_gate': {'passed': True, 'adapted_violation_count': 0,
                            'unobserved_intervention_pairs': 0, 'details': []},
        'adaptation_loading': {'adapted_trials': 20, 'loaded_trials': 19,
                               'unknown_load_trials': 0, 'loading_rate': 0.95},
        'cost_effects': [{'metric': 'tool_calls', 'unit': 'calls', 'paired_samples': 20,
                          'baseline_mean': 8, 'adapted_mean': 7, 'relative_change': -0.125,
                          'interpretation': 'improved'}],
        'unrelated_work': {'new_action_count': 0, 'new_action_evidence_refs': [],
                           'material_overhead_observed': False},
        'verdict': 'NET_BENEFIT', 'promotion_recommendation': 'human_review'
    }

class AdaptationContractTests(unittest.TestCase):
    def test_all_schemas_are_valid_draft_2020_12(self):
        for name in ('proposal.schema.json', 'trial.schema.json', 'evaluation.schema.json'):
            with self.subTest(name=name):
                schema(name)

    def test_experience_driven_proposal_requires_held_runs_and_events(self):
        value = valid_proposal()
        Draft202012Validator(schema('proposal.schema.json')).validate(value)
        value['source_basis']['eligible_held_run_refs'] = []
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema('proposal.schema.json')).validate(value)

    def test_prior_driven_proposal_must_retain_prior_basis(self):
        value = valid_proposal()
        value['source_basis'] = {'origin': 'prior_driven', 'eligible_held_run_refs': [],
                                 'observed_event_refs': [], 'prior_basis_refs': [],
                                 'causal_link': 'External research motivates a testable hypothesis.',
                                 'all_held_runs_revalidated': False}
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema('proposal.schema.json')).validate(value)

    def test_baseline_trial_has_no_adaptation_digest_or_loaded_state(self):
        value = valid_trial('baseline')
        Draft202012Validator(schema('trial.schema.json')).validate(value)
        value['adaptation_loaded'] = True
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema('trial.schema.json')).validate(value)

    def test_adapted_trial_requires_pinned_adaptation_digest(self):
        value = valid_trial('adapted')
        Draft202012Validator(schema('trial.schema.json')).validate(value)
        value['adaptation_digest'] = None
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema('trial.schema.json')).validate(value)

    def test_complete_trace_cannot_claim_unknown_action_observation(self):
        value = valid_trial('baseline')
        value['target_action_observed'] = None
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema('trial.schema.json')).validate(value)

    def test_net_benefit_can_only_recommend_human_review(self):
        value = valid_evaluation()
        Draft202012Validator(schema('evaluation.schema.json')).validate(value)
        value['promotion_recommendation'] = 'not_recommended'
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema('evaluation.schema.json')).validate(value)

if __name__ == '__main__':
    unittest.main()
