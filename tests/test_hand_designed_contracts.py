"""Executable shape and gate tests for the hand-designed habit contracts.

These tests validate the draft schemas. They do not claim that HabitRoute's
runtime emits or enforces these records yet.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "shared" / "contracts" / "v0.1"
HABIT = ROOT / "habits" / "repo-change-verification" / "v1"
DIGEST = "a" * 64


def read_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def held_verdict():
    return {
        "schema_version": "0.1",
        "flow_id": "repo-change-verification",
        "flow_version": "1.0.0",
        "run_id": "run-example-001",
        "habit_id": "repo-change-verification",
        "habit_version": "1.0.0",
        "constraint_policy": {
            "policy_id": "repo-read-only",
            "version": "1",
            "sha256": DIGEST,
        },
        "target_digest": DIGEST,
        "status": "SUCCESS_HELD",
        "issued_at": "2026-11-06T12:00:00Z",
        "budget_audit": {
            "within_limits": True,
            "dimensions": [
                {"metric": "tokens", "limit": 50000, "observed": 12000, "unit": "provider_tokens", "measurement_kind": "provider_reported", "within_limit": True},
                {"metric": "elapsed_time_ms", "limit": 1800000, "observed": 180000, "unit": "ms", "measurement_kind": "observed", "within_limit": True},
                {"metric": "tool_calls", "limit": 100, "observed": 18, "unit": "calls", "measurement_kind": "observed", "within_limit": True},
                {"metric": "retries", "limit": 2, "observed": 0, "unit": "retries", "measurement_kind": "observed", "within_limit": True},
            ],
        },
        "constraint_audit": {
            "all_constraints_held": True,
            "violations": [],
            "audit_evidence_refs": ["evidence-policy-audit"],
        },
        "evidence_audit": {
            "complete": True,
            "all_digests_valid": True,
            "independent_verification_passed": True,
            "required_artifacts": 4,
            "missing_artifacts": [],
            "evidence_refs": ["evidence-diff", "evidence-tests", "evidence-source", "evidence-ci"],
        },
        "intervention_audit": {
            "observability": "complete",
            "human_interventions": [],
            "unrecorded_interventions": [],
            "autonomous": True,
        },
        "source_stability_audit": {
            "unchanged_during_run": True,
            "initial_digest": DIGEST,
            "terminal_digest": DIGEST,
            "digest_equality_verified": True,
        },
        "immediate_gates_passed": True,
        "success": True,
        "mining_eligible": True,
        "revalidation": {
            "required": True,
            "status": "passed",
            "verifier_id": "ci-check",
            "verifier_version": "1",
            "same_target_digest_confirmed": True,
            "evidence_ref": "evidence-ci",
            "observed_at": "2026-11-06T11:59:00Z",
        },
    }


def trace_event():
    return {
        "schema_version": "0.1",
        "canonicalization": "habitroute-json-v1",
        "event_id": "event-0001",
        "flow_id": "repo-change-verification",
        "flow_version": "1.0.0",
        "run_id": "run-example-001",
        "habit_id": "repo-change-verification",
        "habit_version": "1.0.0",
        "constraint_policy": {"policy_id": "repo-read-only", "version": "1", "sha256": DIGEST},
        "sequence": 1,
        "occurred_at": "2026-11-06T12:00:00Z",
        "event_type": "flow_started",
        "step_id": "bind_task",
        "branch_id": None,
        "decision_id": None,
        "actor": {"kind": "agent", "id": "test-agent"},
        "source": {"kind": "runtime", "name": "habitroute-test", "version": "0.1"},
        "source_binding": {
            "repository_id": "owner/repository",
            "base_revision": "base-sha",
            "target_revision": "target-sha",
            "tree_sha256": DIGEST,
            "inventory_sha256": None,
            "validation_fingerprint_sha256": None,
            "environment_fingerprint_sha256": DIGEST,
        },
        "evidence_refs": [],
        "cost_observations": [
            {"metric": "tool_calls", "value": 1, "unit": "calls", "measurement_kind": "observed", "measurement_source": "runtime-counter"}
        ],
        "intervention": {"occurred": False, "kind": None},
        "event_payload": {
            "payload_schema_id": "habitroute://repo-change-verification/v1/payloads/flow-started",
            "payload_schema_version": "0.1",
            "payload_schema_sha256": DIGEST,
            "data": {"objective": "verify changed source"},
        },
        "previous_event_digest": None,
        "event_digest": DIGEST,
    }


def decision_record():
    return {
        "schema_version": "0.1",
        "decision_id": "decision-0001",
        "flow_id": "repo-change-verification",
        "run_id": "run-example-001",
        "habit_id": "repo-change-verification",
        "habit_version": "1.0.0",
        "constraint_policy": {"policy_id": "repo-read-only", "version": "1", "sha256": DIGEST},
        "decided_at": "2026-11-06T12:01:00Z",
        "decision_type": "validation_selection",
        "options_considered": [
            {"option_id": "run-full-suite", "description": "Run the required suite", "eligible": True, "eligibility_basis": "Changed source behavior requires tests", "tradeoffs": ["Higher immediate cost"], "evidence_refs": ["evidence-diff"]},
            {"option_id": "skip-suite", "description": "Reuse previous result", "eligible": False, "eligibility_basis": "No matching complete fingerprint", "tradeoffs": ["Would save time but is unsupported"], "evidence_refs": []},
        ],
        "selected_option_id": "run-full-suite",
        "rationale": "The changed source and test configuration do not match any prior verified validation fingerprint.",
        "evidence_available_at_decision": [
            {"evidence_id": "evidence-diff", "sha256": DIGEST, "observed_at": "2026-11-06T12:00:30Z", "description": "Captured diff and changed path inventory"}
        ],
        "uncertainties": [{"question": "Whether CI will run on this exact target", "impact": "medium", "resolution_needed_before_execution": False}],
        "reversibility": "reversible",
        "reversal_cost": {"value": 0, "unit": "person-hours", "basis": "No repository mutation", "estimate_kind": "qualitative"},
        "decision_maker": {"kind": "agent", "id": "test-agent"},
        "approval": {"required": False, "status": "not_required", "approver_id": None, "approval_evidence_ref": None},
    }


def decision_outcome():
    return {
        "schema_version": "0.1",
        "outcome_event_id": "decision-outcome-0001",
        "decision_id": "decision-0001",
        "flow_id": "repo-change-verification",
        "run_id": "run-example-001",
        "observed_at": "2026-11-07T12:00:00Z",
        "outcome_status": "held",
        "outcome_summary": "The same immutable target passed the later independent CI check.",
        "evidence_refs": ["evidence-ci"],
        "causal_assessment": "decision_related",
        "reversal": {"performed": False, "reversible": True, "cost": {"value": 0, "unit": "person-hours", "basis": "No reversal required"}},
        "follow_up_decision_id": None,
    }


class HandDesignedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {
            path.name.removesuffix(".schema.json"): read_json(path)
            for path in CONTRACTS.glob("*.schema.json")
        }
        cls.flow_schema = read_json(HABIT / "flow.schema.json")
        cls.flow = read_json(HABIT / "flow.json")

    def test_all_schemas_are_valid_draft_2020_12(self):
        for name, schema in {**self.schemas, "flow": self.flow_schema}.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_hand_designed_flow_matches_its_schema(self):
        Draft202012Validator(self.flow_schema).validate(self.flow)

    def test_flow_has_unique_node_ids_and_closed_transitions(self):
        nodes = self.flow["nodes"]
        ids = [node["id"] for node in nodes]
        self.assertEqual(len(ids), len(set(ids)))
        known = set(ids) | set(self.flow["terminal_states"])
        transition_fields = {
            "on_pass", "on_all_pass", "on_all_skipped_or_some_execute",
            "on_unknown_or_fail", "on_deterministic_failure",
            "on_transient_safe_failure_with_budget", "on_unknown_or_unsafe_failure",
            "on_fail_or_unknown", "on_drift_or_unrecorded_intervention",
            "on_unknown_intervention_or_budget", "on_failure",
            "on_missing_or_different_digest",
        }
        for node in nodes:
            for field in transition_fields.intersection(node):
                with self.subTest(node=node["id"], transition=field):
                    self.assertIn(node[field], known)

    def test_flow_requires_all_four_budget_dimensions(self):
        candidate = copy.deepcopy(self.flow)
        candidate["policy_requirements"]["budget_contract"]["required_dimensions"].remove("retries")
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.flow_schema).validate(candidate)

    def test_mining_is_not_an_execution_side_effect(self):
        self.assertEqual(self.flow["status"], "hand_designed_not_runtime_enforced")
        self.assertEqual(self.flow["mode"], "read_only")
        self.assertIn("No mining or active-version mutation during execution.", self.flow["global_constraints"])
        success = self.flow["terminal_states"]["SUCCESS_HELD"]
        self.assertTrue(success["mining_eligible"])
        provisional = self.flow["terminal_states"]["VERIFIED_AT_END"]
        self.assertFalse(provisional["mining_eligible"])

    def test_trace_event_validates_and_rejects_inconsistent_intervention(self):
        validator = Draft202012Validator(self.schemas["trace-event"])
        validator.validate(trace_event())
        invalid = trace_event()
        invalid["intervention"] = {"occurred": False, "kind": "RESCUE"}
        with self.assertRaises(ValidationError):
            validator.validate(invalid)
        unversioned_payload = trace_event()
        unversioned_payload["event_payload"] = {"data": {"objective": "verify changed source"}}
        with self.assertRaises(ValidationError):
            validator.validate(unversioned_payload)

    def test_decision_and_later_outcome_are_separate_records(self):
        Draft202012Validator(self.schemas["decision-record"]).validate(decision_record())
        Draft202012Validator(self.schemas["decision-outcome"]).validate(decision_outcome())
        contaminated = decision_record()
        contaminated["later_outcome"] = {"status": "held"}
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.schemas["decision-record"]).validate(contaminated)

    def test_held_success_requires_every_gate(self):
        validator = Draft202012Validator(self.schemas["flow-verdict"])
        validator.validate(held_verdict())

        mutations = {
            "estimated_token_usage": lambda value: value["budget_audit"]["dimensions"][0].update(measurement_kind="estimated"),
            "unknown_token_usage": lambda value: value["budget_audit"]["dimensions"][0].update(measurement_kind="unknown", observed=None, within_limit=False),
            "missing_retry_budget": lambda value: value["budget_audit"]["dimensions"].pop(),
            "constraint_violation": lambda value: value["constraint_audit"]["violations"].append("write operation attempted"),
            "missing_evidence": lambda value: value["evidence_audit"]["missing_artifacts"].append("test-log"),
            "empty_evidence_set": lambda value: value["evidence_audit"].update(required_artifacts=0, evidence_refs=[]),
            "unobserved_intervention": lambda value: value["intervention_audit"].update(observability="unknown", unrecorded_interventions=["manual edit"], autonomous=False),
            "digest_equality_unverified": lambda value: value["source_stability_audit"].update(terminal_digest="b" * 64, digest_equality_verified=False),
            "wrong_revalidation_target": lambda value: value["revalidation"].update(same_target_digest_confirmed=False),
            "success_claim_without_held_state": lambda value: value.update(status="VERIFIED_AT_END", success=True),
        }
        for name, mutate in mutations.items():
            candidate = copy.deepcopy(held_verdict())
            mutate(candidate)
            with self.subTest(mutation=name):
                with self.assertRaises(ValidationError):
                    validator.validate(candidate)

    def test_local_pass_is_not_mining_eligible(self):
        candidate = held_verdict()
        candidate.update(
            status="VERIFIED_AT_END",
            success=False,
            mining_eligible=False,
        )
        candidate["revalidation"].update(status="unavailable", same_target_digest_confirmed=None, evidence_ref=None)
        Draft202012Validator(self.schemas["flow-verdict"]).validate(candidate)

        candidate["mining_eligible"] = True
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.schemas["flow-verdict"]).validate(candidate)


if __name__ == "__main__":
    unittest.main()
