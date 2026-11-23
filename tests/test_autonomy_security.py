import hashlib
import tempfile
import time
import unittest
from pathlib import Path

from habitroute.autonomy.capabilities import (
    DecisionKind, DelegationEdge, HmacCapabilityBroker,
    deterministic_idempotency_key, validate_delegation_dag,
)
from habitroute.autonomy.guards import (
    CandidatePatch, ControlPlaneApproval, REQUIRED_PROMOTION_INVARIANTS,
    ShadowReplayReport, SnapshotEvidence, evaluate_promotion, require_recovery_snapshot,
)
from habitroute.autonomy.ledger import (
    BudgetExceeded, IdempotencyConflict, ReconciliationEvidence,
    SQLiteFlowJournal, verify_merkle_inclusion,
)
from habitroute.autonomy.runtime import TriggerEnvelope, hydrate_trigger
from habitroute.autonomy.worker import (
    OperationDescriptor, PolicyEnforcedHarnessAdapter, RecoveryPlan,
)
from habitroute.flows import FlowDefinition, FlowNode, FlowNodeKind
from habitroute.machine import (
    HarnessOperationResult, HarnessProfile, OperationEffect, OperationNotExecuted,
    OperationOutcome, OperationStep,
)


class StubHarness:
    def __init__(self, operations, result=None, approval_required=()):
        self.profile = HarnessProfile(
            "test-harness", "1", "test", "security-suite",
            frozenset(operations), frozenset(approval_required), 3, False,
        )
        self.result = result or HarnessOperationResult(OperationOutcome.SUCCEEDED)
        self.calls = []

    def invoke(self, operation, inputs, *, idempotency_key):
        self.calls.append((operation.operation_ref, dict(inputs), idempotency_key))
        return self.result


class StubEgress:
    def __init__(self, result=None, fail=False):
        self.result = result or HarnessOperationResult(OperationOutcome.SUCCEEDED)
        self.fail = fail
        self.calls = []

    def invoke(self, descriptor, operation, inputs, *, idempotency_key, capability_token):
        self.calls.append((descriptor.operation_ref, idempotency_key))
        if self.fail:
            raise TimeoutError("transport lost after request dispatch")
        return self.result


class GoodSnapshotVerifier:
    def verify(self, evidence):
        return evidence.receipt == "verified-provider-receipt"


class GoodReconciliationVerifier:
    def verify(self, evidence):
        return evidence.receipt == "provider-signed-reconciliation"


class GoodApprovalVerifier:
    def verify(self, evidence, claims, descriptor, now):
        return evidence.signature == "valid-approval-signature"


class GoodControlPlane:
    def verify(self, approval):
        return approval.signature == "valid-control-plane-signature"


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.broker = HmacCapabilityBroker(b"x" * 32)

    def mint(self, **overrides):
        args = dict(
            subject="orchestrator", task_id="task-1",
            operations={"repo.read", "repo.delete"}, hosts={"api.example.test"},
            resource_prefixes={"https://api.example.test/v1/project"},
            ttl_seconds=600, max_calls=8, max_cost=20.0,
            approval_required={"repo.delete"},
        )
        args.update(overrides)
        return self.broker.mint_root(**args)

    def test_token_signature_expiry_scope_and_redacted_repr(self):
        token = self.mint()
        claims = self.broker.verify(token)
        self.assertIn("repo.read", claims.operations)
        self.assertNotIn(token.value, repr(token))
        with self.assertRaises(PermissionError):
            self.broker.verify(token, now=claims.expires_at)
        altered = token.value[:-1] + ("A" if token.value[-1] != "A" else "B")
        with self.assertRaises(PermissionError):
            self.broker.verify(altered)

    def test_delegation_attenuates_scopes_ttl_and_budget(self):
        root = self.mint()
        child = self.broker.delegate(
            root, subject="worker-1", operations={"repo.read"},
            hosts={"api.example.test"},
            resource_prefixes={"https://api.example.test/v1/project/src"},
            ttl_seconds=300, max_calls=2, max_cost=4.0,
        )
        claims = self.broker.verify(child)
        self.assertEqual(claims.depth, 1)
        self.assertEqual(claims.parent_id, self.broker.verify(root).capability_id)
        self.assertEqual(claims.operations, frozenset({"repo.read"}))
        self.assertEqual(claims.max_calls, 2)
        with self.assertRaises(PermissionError):
            self.broker.delegate(
                child, subject="worker-2", operations={"repo.delete"},
                hosts={"api.example.test"},
                resource_prefixes={"/v1/project"}, ttl_seconds=100,
                max_calls=1, max_cost=1.0,
            )

    def test_parent_approval_requirement_cannot_be_removed(self):
        with self.assertRaisesRegex(PermissionError, "cannot remove"):
            self.broker.delegate(
                self.mint(), subject="child", operations={"repo.delete"},
                hosts={"api.example.test"},
                resource_prefixes={"https://api.example.test/v1/project"},
                ttl_seconds=100, max_calls=1, max_cost=1.0,
            )

    def test_uuidv5_and_dag_limits(self):
        left = deterministic_idempotency_key("run-1:step-1", "repo.read")
        right = deterministic_idempotency_key("run-1:step-1", "repo.read")
        self.assertEqual(left, right)
        self.assertNotEqual(left, deterministic_idempotency_key("run-2:step-1", "repo.read"))
        self.assertEqual(validate_delegation_dag([
            DelegationEdge("root", "a"), DelegationEdge("root", "b"),
            DelegationEdge("a", "c"),
        ])["c"], 2)
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_delegation_dag([DelegationEdge("a", "b"), DelegationEdge("b", "a")])
        with self.assertRaisesRegex(ValueError, "depth"):
            validate_delegation_dag([
                DelegationEdge("r", "a"), DelegationEdge("a", "b"),
                DelegationEdge("b", "c"), DelegationEdge("c", "d"),
            ])


class JournalTests(unittest.TestCase):
    def test_merkle_proofs_for_odd_and_even_tree_sizes(self):
        for size in range(1, 18):
            leaves = tuple(hashlib.sha256(f"leaf-{i}".encode()).digest() for i in range(size))
            from habitroute.autonomy.ledger import merkle_root, merkle_inclusion_proof
            root = merkle_root(leaves)
            for index, leaf in enumerate(leaves):
                proof = merkle_inclusion_proof(leaves, index)
                self.assertTrue(verify_merkle_inclusion(leaf, index, size, proof, root))

    def test_flow_journal_audit_anchor_and_tamper_detection(self):
        class Anchor:
            def publish(self, head):
                return f"{head.tree_size}:{head.root_hash}"
            def verify(self, head, receipt):
                return receipt == f"{head.tree_size}:{head.root_hash}"

        with tempfile.TemporaryDirectory() as temp:
            journal = SQLiteFlowJournal(Path(temp) / "flows.sqlite3")
            journal.append_audit("audit-1", "test_event", {"operation": "read"})
            anchor = Anchor()
            journal.publish_audit_head(anchor)
            self.assertTrue(journal.has_current_external_anchor(anchor))
            journal.append_audit("audit-2", "later_event", {"operation": "write"})
            self.assertFalse(journal.has_current_external_anchor(anchor))
            self.assertTrue(journal.verify_integrity())

    def test_invocation_idempotency_binds_input_and_never_replays_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = SQLiteFlowJournal(Path(temp) / "ledger.sqlite3")
            params = dict(
                capability_id="cap-1", idempotency_key="uuid-key", operation_ref="repo.read",
                effect="idempotent", input_sha256=hashlib.sha256(b"{}").hexdigest(),
                estimated_cost=1.0, max_calls=3, max_cost=3.0,
            )
            first = journal.claim_invocation(**params)
            self.assertTrue(first.executable)
            journal.finish_invocation("uuid-key", "unknown", "transport_lost")
            replay = journal.claim_invocation(**params)
            self.assertFalse(replay.executable)
            with self.assertRaises(IdempotencyConflict):
                journal.claim_invocation(**{
                    **params, "input_sha256": hashlib.sha256(b'{"different":true}').hexdigest()
                })

    def test_sibling_workers_share_parent_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = SQLiteFlowJournal(Path(temp) / "ledger.sqlite3")
            parent = (("root", 1, 1.0),)
            common = dict(
                operation_ref="repo.read", effect="read_only",
                input_sha256=hashlib.sha256(b"{}").hexdigest(),
                estimated_cost=1.0, max_calls=1, max_cost=1.0,
                budget_chain=parent,
            )
            self.assertTrue(journal.claim_invocation(
                capability_id="child-a", idempotency_key="child-a-key", **common
            ).executable)
            with self.assertRaises(BudgetExceeded):
                journal.claim_invocation(
                    capability_id="child-b", idempotency_key="child-b-key", **common
                )

    def test_terminal_invocation_state_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = SQLiteFlowJournal(Path(temp) / "ledger.sqlite3")
            params = dict(
                capability_id="cap-1", idempotency_key="terminal-key",
                operation_ref="repo.read", effect="idempotent",
                input_sha256=hashlib.sha256(b"{}").hexdigest(),
                estimated_cost=1.0, max_calls=3, max_cost=3.0,
            )
            self.assertTrue(journal.claim_invocation(**params).executable)
            journal.finish_invocation("terminal-key", "succeeded")
            with self.assertRaisesRegex(ValueError, "running invocation"):
                journal.finish_invocation("terminal-key", "failed")

    def test_provider_verified_not_applied_can_resume_nonrepeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = SQLiteFlowJournal(Path(temp) / "ledger.sqlite3")
            params = dict(
                capability_id="cap-1", idempotency_key="reconcile-key",
                operation_ref="repo.delete", effect="non_repeatable",
                input_sha256=hashlib.sha256(b"{}").hexdigest(),
                estimated_cost=1.0, max_calls=3, max_cost=3.0,
            )
            self.assertTrue(journal.claim_invocation(**params).executable)
            journal.finish_invocation("reconcile-key", "unknown", "lost_ack")
            evidence = ReconciliationEvidence(
                "cap-1", "reconcile-key", "provider", "receipt:123",
                "verifier", False, int(time.time()), "provider-signed-reconciliation",
            )
            self.assertEqual(
                journal.reconcile_invocation(evidence, GoodReconciliationVerifier()),
                "not_applied",
            )
            self.assertTrue(journal.claim_invocation(**params).executable)

    def test_secret_bearing_context_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = SQLiteFlowJournal(Path(temp) / "ledger.sqlite3")
            with self.assertRaisesRegex(ValueError, "secret-bearing"):
                journal.claim_trigger(
                    trigger_id="event-1", payload_sha256=hashlib.sha256(b"x").hexdigest(),
                    run_id="run-1", flow_id="flow", definition_version=1,
                    initial_context={"access_token": "secret-value"},
                )


class TriggerTests(unittest.TestCase):
    def test_duplicate_and_new_wakeups_preserve_first_context(self):
        definition = FlowDefinition(
            "trigger-test", 1, "inspect",
            (FlowNode("inspect", FlowNodeKind.OPERATION, "repo.read", "done"),
             FlowNode("done", FlowNodeKind.END)),
        )
        with tempfile.TemporaryDirectory() as temp:
            journal = SQLiteFlowJournal(Path(temp) / "flows.sqlite3")
            digest = hashlib.sha256(b"event-payload").hexdigest()
            first = TriggerEnvelope("event-1", "run-1", "webhook", digest)
            one = hydrate_trigger(first, definition, journal, initial_context={"source": "first"})
            self.assertTrue(one.first_delivery)
            two = hydrate_trigger(first, definition, journal, initial_context={"source": "attacker"})
            self.assertFalse(two.first_delivery)
            other = TriggerEnvelope("event-2", "run-1", "webhook", hashlib.sha256(b"other").hexdigest())
            three = hydrate_trigger(other, definition, journal, initial_context={"source": "attacker"})
            self.assertFalse(three.first_delivery)
            self.assertEqual(three.flow.snapshot.context_dict(), {"source": "first"})
            self.assertTrue(journal.verify_integrity())


class HarnessBoundaryTests(unittest.TestCase):
    def make_adapter(self, temp, *, external=True, proxy=None, result=None,
                     destructive=False, recovery=False, profile_approval=False,
                     method_override=None, effect_override=None):
        op_ref = "repo.read" if not destructive else "repo.delete"
        host = "api.example.test" if external else "local"
        resource = "https://api.example.test/v1/project" if external else "/project/database"
        method = method_override or ("GET" if not destructive else "POST")
        profile = HarnessProfile(
            "inner", "1", "test", "runtime", frozenset({op_ref}),
            frozenset(), 3, False,
        )
        inner = StubHarness(
            {op_ref}, result, approval_required={op_ref} if profile_approval else (),
        )
        broker = HmacCapabilityBroker(b"z" * 32)
        token = broker.mint_root(
            subject="test-worker", task_id="task-1", operations={op_ref},
            hosts={host}, resource_prefixes={resource}, ttl_seconds=600,
            max_calls=5, max_cost=10.0,
        )
        descriptor = OperationDescriptor(
            op_ref, host, resource, external=external, method=method,
            destructive=destructive,
        )
        journal = SQLiteFlowJournal(Path(temp) / "security.sqlite3")
        recovery_plans = {}
        verifier = None
        if recovery:
            evidence = SnapshotEvidence(
                "workflow-1", "snapshot-1", "db", 7, "a" * 64,
                int(time.time()), "pitr:7", "verified-provider-receipt",
            )
            recovery_plans[op_ref] = RecoveryPlan(evidence, "workflow-1", 7, "a" * 64)
            verifier = GoodSnapshotVerifier()
        adapter = PolicyEnforcedHarnessAdapter(
            inner, broker=broker, capability_token=token,
            descriptors={op_ref: descriptor}, journal=journal,
            egress_proxy=proxy, recovery_plans=recovery_plans,
            snapshot_verifier=verifier,
        )
        step = OperationStep(
            op_ref,
            effect_override or (OperationEffect.NON_REPEATABLE if destructive else (
                OperationEffect.READ_ONLY if external else OperationEffect.IDEMPOTENT
            )),
            idempotency_key_supported=external,
        )
        return adapter, inner, step, journal

    def test_external_never_falls_back_when_egress_proxy_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter, inner, step, _ = self.make_adapter(temp)
            with self.assertRaises(OperationNotExecuted):
                adapter.invoke(step, {}, idempotency_key="run-1")
            self.assertEqual(inner.calls, [])

    def test_external_call_uses_only_egress_proxy(self):
        with tempfile.TemporaryDirectory() as temp:
            proxy = StubEgress()
            adapter, inner, step, _ = self.make_adapter(temp, proxy=proxy)
            result = adapter.invoke(step, {}, idempotency_key="run-1")
            self.assertEqual(result.outcome, OperationOutcome.SUCCEEDED)
            self.assertEqual(len(proxy.calls), 1)
            self.assertEqual(inner.calls, [])

    def test_unknown_dispatch_result_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as temp:
            proxy = StubEgress(fail=True)
            adapter, _, step, _ = self.make_adapter(temp, proxy=proxy)
            first = adapter.invoke(step, {}, idempotency_key="run-2")
            second = adapter.invoke(step, {}, idempotency_key="run-2")
            self.assertEqual(first.outcome, OperationOutcome.UNKNOWN)
            self.assertEqual(second.outcome, OperationOutcome.UNKNOWN)
            self.assertEqual(len(proxy.calls), 1)

    def test_destructive_operation_requires_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter, inner, step, _ = self.make_adapter(
                temp, external=False, destructive=True, recovery=False,
            )
            with self.assertRaises(OperationNotExecuted):
                adapter.invoke(step, {}, idempotency_key="delete-1")
            self.assertEqual(inner.calls, [])
        with tempfile.TemporaryDirectory() as temp:
            adapter, inner, step, _ = self.make_adapter(
                temp, external=False, destructive=True, recovery=True,
            )
            result = adapter.invoke(step, {}, idempotency_key="delete-2")
            self.assertEqual(result.outcome, OperationOutcome.SUCCEEDED)
            self.assertEqual(len(inner.calls), 1)

    def test_harness_profile_approval_cannot_be_bypassed_at_adapter_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            proxy = StubEgress()
            adapter, inner, step, _ = self.make_adapter(
                temp, proxy=proxy, profile_approval=True,
            )
            with self.assertRaises(OperationNotExecuted):
                adapter.invoke(step, {}, idempotency_key="profile-approval")
            self.assertEqual(proxy.calls, [])
            self.assertEqual(inner.calls, [])

    def test_reversible_external_post_does_not_require_destructive_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            proxy = StubEgress()
            adapter, inner, step, _ = self.make_adapter(
                temp, proxy=proxy, method_override="POST",
                effect_override=OperationEffect.IDEMPOTENT,
            )
            result = adapter.invoke(step, {"title": "new issue"}, idempotency_key="create-issue")
            self.assertEqual(result.outcome, OperationOutcome.SUCCEEDED)
            self.assertEqual(len(proxy.calls), 1)
            self.assertEqual(inner.calls, [])

    def test_secret_inputs_are_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            proxy = StubEgress()
            adapter, inner, step, _ = self.make_adapter(temp, proxy=proxy)
            with self.assertRaises(OperationNotExecuted):
                adapter.invoke(step, {"authorization": "Bearer abcdefghijklmnopqrstuvwxyz"}, idempotency_key="secret")
            self.assertEqual(proxy.calls, [])
            self.assertEqual(inner.calls, [])


class PromotionTests(unittest.TestCase):
    def test_candidate_requires_shadow_invariants_and_external_approval(self):
        patch = CandidatePatch(
            "v1", "v2", "b" * 64, "remove redundant request",
            "reduce calls without quality loss", "refs/heads/candidate/security-v2",
        )
        report = ShadowReplayReport(
            "v2", "b" * 64, 25, 0,
            tuple((name, True) for name in sorted(REQUIRED_PROMOTION_INVARIANTS)),
            "calls -12%; all postconditions stable",
        )
        approval = ControlPlaneApproval(
            "v2", "b" * 64, "allow", "approval-1",
            int(time.time()) + 300, "valid-control-plane-signature",
        )
        self.assertTrue(evaluate_promotion(
            patch, report, approval, GoodControlPlane(),
        ).promotable)
        self.assertFalse(evaluate_promotion(
            patch, report, None, GoodControlPlane(),
        ).promotable)


if __name__ == "__main__":
    unittest.main()
