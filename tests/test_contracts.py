import unittest

from habitroute.contracts import (
    AuthorizationPolicy, Certificate, CertificateStatus, ContextScope,
    FixedMacro, HabitLifecycle, HabitSpec, InitiationContract, SafetyContract,
    StateBelief, TerminationContract, authorize_habit,
)


class HabitContractTests(unittest.TestCase):
    def setUp(self):
        self.scope = ContextScope("maze-v1", "daylight", "latent-prototypes", "encoder-sha-1")
        self.habit = HabitSpec(
            habit_id="go-to-door", version=2, scope=self.scope,
            initiation=InitiationContract(frozenset({"hall", "hall-left"}), 0.95, 0.01),
            controller=FixedMacro(("forward", "left"), ("hall", "junction", "door")),
            termination=TerminationContract(frozenset({"door"}), max_steps=4),
            safety=SafetyContract(frozenset({"lava"}), frozenset({"forward", "left", "right"})),
            lifecycle=HabitLifecycle.ACTIVE,
        )
        self.certificate = Certificate(
            "go-to-door", 2, self.scope, CertificateStatus.VALID, 100, 98,
            ("run-001", "run-002"),
        )
        self.policy = AuthorizationPolicy(min_trials=20, min_success_lcb=0.80)

    def belief(self, probs, unknown=0.0, scope=None):
        scope = scope or self.scope
        return StateBelief.from_mapping(
            probs, unknown_mass=unknown,
            representation_id=scope.representation_id,
            representation_version=scope.representation_version,
        )

    def test_authorizes_when_scope_evidence_and_initiation_match(self):
        d = authorize_habit(self.habit, self.belief({"hall": 0.98, "corridor": 0.02}),
                            self.scope, self.certificate, self.policy)
        self.assertTrue(d.allowed)
        self.assertEqual(d.reason, "authorized")
        self.assertGreaterEqual(d.region_mass, 0.95)

    def test_unknown_or_ood_observation_fails_closed(self):
        d = authorize_habit(self.habit, self.belief({"corridor": 0.98}, unknown=0.02),
                            self.scope, self.certificate, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "unknown_mass_exceeded")

    def test_nearest_candidate_does_not_override_initiation_failure(self):
        d = authorize_habit(self.habit, self.belief({"hall": 0.60, "unseen": 0.40}),
                            self.scope, self.certificate, self.policy)
        self.assertFalse(d.allowed)

    def test_context_mismatch_fails_closed(self):
        other = ContextScope("maze-v1", "night", "latent-prototypes", "encoder-sha-1")
        d = authorize_habit(self.habit, self.belief({"hall": 1.0}), other,
                            self.certificate, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "context_scope_mismatch")

    def test_representation_version_mismatch_fails_closed(self):
        other = ContextScope("maze-v1", "daylight", "latent-prototypes", "encoder-sha-2")
        d = authorize_habit(self.habit, self.belief({"hall": 1.0}, scope=other), other,
                            self.certificate, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "representation_version_mismatch")

    def test_certificate_cannot_be_reused_for_another_version(self):
        d = authorize_habit(self.habit.with_version(3), self.belief({"hall": 1.0}),
                            self.scope, self.certificate, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "certificate_version_mismatch")

    def test_low_sample_certificate_is_not_enough(self):
        weak = Certificate("go-to-door", 2, self.scope, CertificateStatus.VALID,
                           2, 2, ("run-small",))
        d = authorize_habit(self.habit, self.belief({"hall": 1.0}), self.scope, weak, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "insufficient_evidence")

    def test_lower_confidence_bound_not_point_estimate_controls(self):
        uncertain = Certificate("go-to-door", 2, self.scope, CertificateStatus.VALID,
                                 20, 17, ("run-uncertain",))
        strict = AuthorizationPolicy(min_trials=20, min_success_lcb=0.85)
        d = authorize_habit(self.habit, self.belief({"hall": 1.0}), self.scope,
                            uncertain, strict)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "reliability_bound_not_met")

    def test_revoked_certificate_is_rejected(self):
        revoked = self.certificate.with_status(CertificateStatus.REVOKED)
        d = authorize_habit(self.habit, self.belief({"hall": 1.0}), self.scope,
                            revoked, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "certificate_not_valid")

    def test_inactive_habit_is_not_executable(self):
        inactive = self.habit.with_lifecycle(HabitLifecycle.QUARANTINED)
        d = authorize_habit(inactive, self.belief({"hall": 1.0}), self.scope,
                            self.certificate, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "habit_not_active")

    def test_invalid_belief_mass_is_rejected(self):
        with self.assertRaises(ValueError):
            StateBelief.from_mapping({"hall": 0.8, "corridor": 0.3},
                                     representation_id="latent",
                                     representation_version="v1")

    def test_macro_structure_is_validated(self):
        with self.assertRaises(ValueError):
            FixedMacro(("forward",), ("hall",))



    def test_certificate_scope_mismatch_is_rejected(self):
        other = ContextScope("maze-v1", "night", "latent-prototypes", "encoder-sha-1")
        wrong_scope = Certificate(
            "go-to-door", 2, other, CertificateStatus.VALID, 100, 98, ("run-other",),
        )
        d = authorize_habit(self.habit, self.belief({"hall": 1.0}), self.scope,
                            wrong_scope, self.policy)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "certificate_scope_mismatch")

    def test_macro_cannot_contain_disallowed_action(self):
        with self.assertRaises(ValueError):
            HabitSpec(
                habit_id="unsafe-macro", version=1, scope=self.scope,
                initiation=InitiationContract(frozenset({"hall"})),
                controller=FixedMacro(("teleport",), ("hall", "door")),
                termination=TerminationContract(frozenset({"door"}), max_steps=1),
                safety=SafetyContract(allowed_actions=frozenset({"forward"})),
            )

    def test_macro_cannot_cross_declared_forbidden_state(self):
        with self.assertRaises(ValueError):
            HabitSpec(
                habit_id="forbidden-route", version=1, scope=self.scope,
                initiation=InitiationContract(frozenset({"hall"})),
                controller=FixedMacro(("forward", "left"), ("hall", "lava", "door")),
                termination=TerminationContract(frozenset({"door"}), max_steps=2),
                safety=SafetyContract(forbidden_states=frozenset({"lava"})),
            )

    def test_controller_artifact_supports_non_macro_kinds(self):
        from habitroute.contracts import ControllerArtifact, ControllerKind
        artifact = ControllerArtifact(ControllerKind.REACTIVE_POLICY, "sha256:policy")
        self.assertEqual(artifact.kind, ControllerKind.REACTIVE_POLICY)

    def test_habit_versioning_does_not_mutate_existing_version(self):
        newer = self.habit.with_version(3)
        self.assertEqual(self.habit.version, 2)
        self.assertEqual(newer.version, 3)

    def test_lower_bound_improves_with_more_identical_success_evidence(self):
        from habitroute.contracts import wilson_lower_bound
        small = wilson_lower_bound(9, 10)
        large = wilson_lower_bound(90, 100)
        self.assertGreater(large, small)



    def test_macro_start_must_belong_to_initiation_region(self):
        with self.assertRaises(ValueError):
            HabitSpec(
                habit_id="wrong-start", version=1, scope=self.scope,
                initiation=InitiationContract(frozenset({"hall-left"})),
                controller=FixedMacro(("forward",), ("hall", "door")),
                termination=TerminationContract(frozenset({"door"}), max_steps=1),
                safety=SafetyContract(),
            )

    def test_macro_terminal_must_satisfy_success_contract(self):
        with self.assertRaises(ValueError):
            HabitSpec(
                habit_id="wrong-goal", version=1, scope=self.scope,
                initiation=InitiationContract(frozenset({"hall"})),
                controller=FixedMacro(("forward",), ("hall", "junction")),
                termination=TerminationContract(frozenset({"door"}), max_steps=1),
                safety=SafetyContract(),
            )

    def test_macro_must_fit_termination_budget(self):
        with self.assertRaises(ValueError):
            HabitSpec(
                habit_id="too-long", version=1, scope=self.scope,
                initiation=InitiationContract(frozenset({"hall"})),
                controller=FixedMacro(("forward", "left"), ("hall", "junction", "door")),
                termination=TerminationContract(frozenset({"door"}), max_steps=1),
                safety=SafetyContract(),
            )



    def test_reactive_policy_branches_on_observed_state(self):
        policy = ReactivePolicy.from_mapping({"state-a": "left", "state-b": "right"}, representation_id=self.scope.representation_id, representation_version=self.scope.representation_version)
        a = policy.select_action(self.belief({"state-a": 0.99, "state-b": 0.01}))
        b = policy.select_action(self.belief({"state-a": 0.01, "state-b": 0.99}))
        self.assertTrue(a.allowed)
        self.assertEqual(a.action, "left")
        self.assertTrue(b.allowed)
        self.assertEqual(b.action, "right")

    def test_reactive_policy_refuses_ambiguous_branch_belief(self):
        policy = ReactivePolicy.from_mapping({"state-a": "left", "state-b": "right"}, representation_id=self.scope.representation_id, representation_version=self.scope.representation_version)
        d = policy.select_action(self.belief({"state-a": 0.5, "state-b": 0.5}))
        self.assertFalse(d.allowed)
        self.assertIsNone(d.action)
        self.assertEqual(d.reason, "ambiguous_action_distribution")

    def test_reactive_policy_refuses_unknown_mass(self):
        policy = ReactivePolicy.from_mapping({"state-a": "left"}, representation_id=self.scope.representation_id, representation_version=self.scope.representation_version)
        d = policy.select_action(self.belief({"state-a": 0.98}, unknown=0.02))
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "unclassified_mass_exceeded")

    def test_habit_rejects_reactive_actions_outside_safety_allowlist(self):
        with self.assertRaises(ValueError):
            HabitSpec(
                habit_id="unsafe-reactive", version=1, scope=self.scope,
                initiation=InitiationContract(frozenset({"state-a"})),
                controller=ReactivePolicy.from_mapping({"state-a": "teleport"}, representation_id=self.scope.representation_id, representation_version=self.scope.representation_version),
                termination=TerminationContract(frozenset({"door"}), max_steps=3),
                safety=SafetyContract(allowed_actions=frozenset({"forward"})),
            )

    def test_habit_rejects_reactive_rules_in_forbidden_states(self):
        with self.assertRaises(ValueError):
            HabitSpec(
                habit_id="forbidden-reactive", version=1, scope=self.scope,
                initiation=InitiationContract(frozenset({"hall"})),
                controller=ReactivePolicy.from_mapping({"lava": "forward"}, representation_id=self.scope.representation_id, representation_version=self.scope.representation_version),
                termination=TerminationContract(frozenset({"door"}), max_steps=3),
                safety=SafetyContract(forbidden_states=frozenset({"lava"})),
            )



    def test_reactive_policy_rejects_representation_version_mismatch(self):
        policy = ReactivePolicy.from_mapping(
            {"state-a": "left"},
            representation_id=self.scope.representation_id,
            representation_version=self.scope.representation_version,
        )
        other = ContextScope("maze-v1", "daylight", "latent-prototypes", "encoder-sha-2")
        d = policy.select_action(self.belief({"state-a": 1.0}, scope=other))
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "representation_version_mismatch")


if __name__ == "__main__":
    unittest.main()
