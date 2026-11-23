import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from habitroute.security import (
    ActionRequest,
    ApprovalAuthority,
    CapabilityAuthority,
    CapabilityLease,
    HashChainAuditSink,
    PolicyDecision,
    PolicyEngine,
    RecoveryEvidence,
    RiskClass,
    merkle_root,
)


NOW = 1_800_000_000.0
NAMESPACE = UUID("e8e6a54b-12e2-4ad7-b5e4-5ac32f7f22b1")


def root_lease():
    return CapabilityLease(
        lease_id="root-1", subject="orchestrator", task_id="task-1",
        hosts=frozenset({"api.example.test"}),
        operations=frozenset({"read", "write", "delete"}),
        resources=frozenset({"repo/main", "db/customers"}),
        issued_at=NOW - 10, expires_at=NOW + 3600, budget_units=100,
    )


class CapabilityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.authority = CapabilityAuthority(b"a" * 32)
        self.approvals = ApprovalAuthority(b"b" * 32)
        self.policy = PolicyEngine(self.authority, NAMESPACE, self.approvals)
        self.lease = root_lease()
        self.signature = self.authority.sign(self.lease)

    def request(self, **changes):
        values = dict(
            task_id="task-1", host="api.example.test", operation="read",
            resource="repo/main", risk=RiskClass.READ,
        )
        values.update(changes)
        return ActionRequest(**values)

    def test_scoped_read_is_allowed(self):
        result = self.policy.evaluate(self.request(), self.lease, self.signature, now=NOW)
        self.assertEqual(result.decision, PolicyDecision.ALLOW)

    def test_invalid_signature_fails_closed(self):
        result = self.policy.evaluate(self.request(), self.lease, "bad", now=NOW)
        self.assertEqual(result.reason, "invalid_lease_signature")

    def test_host_operation_resource_task_and_budget_are_scoped(self):
        cases = [
            self.request(host="evil.example"),
            self.request(operation="admin"),
            self.request(resource="db/other"),
            self.request(task_id="other-task"),
            self.request(estimated_budget_units=101),
        ]
        for request in cases:
            with self.subTest(request=request):
                result = self.policy.evaluate(request, self.lease, self.signature, now=NOW)
                self.assertEqual(result.decision, PolicyDecision.DENY)

    def test_external_mutation_requires_bound_independent_approval(self):
        request = self.request(operation="write", risk=RiskClass.EXTERNAL_MUTATION)
        denied = self.policy.evaluate(request, self.lease, self.signature, now=NOW)
        self.assertEqual(denied.decision, PolicyDecision.APPROVAL_REQUIRED)
        receipt = self.approvals.issue(request, approver="security-reviewer", expires_at=NOW + 60)
        approved_request = self.request(
            operation="write", risk=RiskClass.EXTERNAL_MUTATION, approval_receipt=receipt,
            external_mutation=True,
        )
        result = self.policy.evaluate(approved_request, self.lease, self.signature, now=NOW)
        self.assertEqual(result.decision, PolicyDecision.ALLOW)
        self.assertTrue(result.idempotency_key)

    def test_approval_cannot_be_replayed_for_different_effect(self):
        request = self.request(operation="write", risk=RiskClass.EXTERNAL_MUTATION)
        receipt = self.approvals.issue(request, approver="reviewer", expires_at=NOW + 60)
        changed = self.request(
            operation="delete", risk=RiskClass.EXTERNAL_MUTATION, approval_receipt=receipt,
        )
        result = self.policy.evaluate(changed, self.lease, self.signature, now=NOW)
        self.assertEqual(result.decision, PolicyDecision.APPROVAL_REQUIRED)

    def test_expired_approval_is_rejected(self):
        request = self.request(operation="write", risk=RiskClass.EXTERNAL_MUTATION)
        receipt = self.approvals.issue(request, approver="reviewer", expires_at=NOW - 1)
        approved = self.request(
            operation="write", risk=RiskClass.EXTERNAL_MUTATION, approval_receipt=receipt,
        )
        result = self.policy.evaluate(approved, self.lease, self.signature, now=NOW)
        self.assertEqual(result.decision, PolicyDecision.APPROVAL_REQUIRED)

    def test_destructive_operation_requires_verified_recovery_checkpoint(self):
        request = self.request(operation="delete", risk=RiskClass.DESTRUCTIVE)
        result = self.policy.evaluate(request, self.lease, self.signature, now=NOW)
        self.assertEqual(result.decision, PolicyDecision.DENY)
        evidence = RecoveryEvidence("pitr", "snapshot-42", "repo/main", True, True, NOW - 1)
        request = self.request(
            operation="delete", risk=RiskClass.DESTRUCTIVE, recovery_evidence=evidence,
        )
        self.assertEqual(
            self.policy.evaluate(request, self.lease, self.signature, now=NOW).decision,
            PolicyDecision.APPROVAL_REQUIRED,
        )

    def test_idempotency_key_is_deterministic(self):
        request = self.request(operation="write", external_mutation=True)
        first = self.policy.evaluate(request, self.lease, self.signature, now=NOW)
        second = self.policy.evaluate(request, self.lease, self.signature, now=NOW)
        self.assertEqual(first.idempotency_key, second.idempotency_key)


class DelegationTests(unittest.TestCase):
    def setUp(self):
        self.authority = CapabilityAuthority(b"c" * 32)
        self.parent = root_lease()
        self.signature = self.authority.sign(self.parent)

    def delegate(self, **changes):
        args = dict(
            parent=self.parent, parent_signature=self.signature,
            child_id="child-1", subject="worker-1", task_id="task-1",
            hosts={"api.example.test"}, operations={"read"},
            resources={"repo/main"}, budget_units=10, now=NOW, ttl_seconds=900,
        )
        args.update(changes)
        return self.authority.delegate(**args)

    def test_delegation_attenuates_authority_and_ttl(self):
        child = self.delegate()
        self.assertEqual(child.depth, 1)
        self.assertEqual(child.expires_at, NOW + 900)
        self.assertEqual(child.operations, frozenset({"read"}))

    def test_cannot_expand_any_scope_or_budget(self):
        for changes in (
            {"hosts": {"api.example.test", "evil.example"}},
            {"operations": {"read", "delete"}},
            {"resources": {"repo/main", "db/customers"}},
            {"budget_units": 101},
        ):
            with self.subTest(changes=changes), self.assertRaises(PermissionError):
                self.delegate(**changes)

    def test_invalid_parent_signature_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.delegate(parent_signature="invalid")

    def test_child_ttl_is_bounded(self):
        with self.assertRaises(ValueError):
            self.delegate(ttl_seconds=901)

    def test_delegation_depth_is_bounded(self):
        current = self.parent
        signature = self.signature
        for depth in range(1, 4):
            current = self.authority.delegate(
                current, signature, child_id=f"child-{depth}", subject=f"worker-{depth}",
                task_id="task-1", hosts={"api.example.test"}, operations={"read"},
                resources={"repo/main"}, budget_units=1, now=NOW + depth,
                ttl_seconds=100,
            )
            signature = self.authority.sign(current)
            if depth == 3:
                with self.assertRaises(PermissionError):
                    self.authority.delegate(
                        current, signature, child_id="child-4", subject="worker-4",
                        task_id="task-1", hosts={"api.example.test"}, operations={"read"},
                        resources={"repo/main"}, budget_units=1, now=NOW + 4,
                        ttl_seconds=100,
                    )


class AuditTests(unittest.TestCase):
    def test_hash_chain_detects_tampering_and_produces_merkle_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            sink = HashChainAuditSink(path)
            sink.append({"action": "read", "task": "t1"})
            sink.append({"action": "write", "task": "t1"})
            self.assertTrue(sink.verify())
            self.assertEqual(len(sink.merkle_checkpoint()), 64)
            lines = path.read_text().splitlines()
            record = json.loads(lines[0])
            record["event"]["action"] = "delete"
            lines[0] = json.dumps(record)
            path.write_text("\n".join(lines) + "\n")
            self.assertFalse(sink.verify())

    def test_merkle_root_is_deterministic(self):
        leaves = ["00" * 32, "11" * 32, "22" * 32]
        self.assertEqual(merkle_root(leaves), merkle_root(leaves))


if __name__ == "__main__":
    unittest.main()
