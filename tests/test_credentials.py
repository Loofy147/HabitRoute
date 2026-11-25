import tempfile
import time
import unittest
from pathlib import Path

from habitroute.autonomy.capabilities import HmacCapabilityBroker
from habitroute.autonomy.ledger import SQLiteFlowJournal
from habitroute.autonomy.credentials import (
    BrokeredEgressProxy,
    CredentialExchangeError,
    EphemeralAccessToken,
    OAuthTokenExchangeClient,
    WorkloadJWT,
)
from habitroute.autonomy.worker import (
    ApprovalEvidence, OperationDescriptor, approval_request_sha256,
)
from habitroute.machine import (
    HarnessOperationResult,
    OperationEffect,
    OperationNotExecuted,
    OperationOutcome,
    OperationStep,
)


class FakeWorkloadJWTSource:
    def __init__(self, token="header.payload.signature", expires_at=None):
        self.token = token
        self.expires_at = expires_at or int(time.time()) + 120
        self.audiences = []

    def fetch_jwt_svid(self, audience):
        self.audiences.append(audience)
        return WorkloadJWT(
            self.token,
            "spiffe://example.org/ns/habitroute/sa/egress",
            self.expires_at,
        )


class FakeFormTransport:
    def __init__(self, response=None):
        self.response = response or {
            "access_token": "upstream-secret-value-123",
            "token_type": "Bearer",
            "expires_in": 120,
            "scope": "repo.read",
        }
        self.calls = []

    def post_form(self, endpoint, form):
        self.calls.append((endpoint, dict(form)))
        return self.response


class GoodApprovalVerifier:
    def verify(self, evidence, claims, descriptor, now):
        return evidence.signature == "independent-approval-signature"


class FakeUpstreamTransport:
    def __init__(self, result=None):
        self.result = result or HarnessOperationResult(OperationOutcome.SUCCEEDED)
        self.calls = []

    def send(self, descriptor, operation, inputs, *, idempotency_key, authorization_header):
        self.calls.append({
            "operation_ref": descriptor.operation_ref,
            "idempotency_key": idempotency_key,
            "authorization_header": authorization_header,
        })
        return self.result


class TokenExchangeTests(unittest.TestCase):
    def make_client(self, response=None, *, source=None):
        source = source or FakeWorkloadJWTSource()
        form = FakeFormTransport(response)
        client = OAuthTokenExchangeClient(
            token_endpoint="https://broker.example.test/oauth/token",
            broker_audience="spiffe://example.org/credential-broker",
            workload_identity=source,
            expected_spiffe_id="spiffe://example.org/ns/habitroute/sa/egress",
            transport=form,
            max_token_lifetime_seconds=300,
        )
        return client, source, form

    def test_exchange_binds_one_resource_audience_and_scope(self):
        client, source, form = self.make_client()
        credential = client.exchange(
            resource="https://api.example.test",
            audience="urn:example:api",
            scopes=frozenset({"repo.read"}),
        )
        self.assertEqual(source.audiences, ["spiffe://example.org/credential-broker"])
        endpoint, request = form.calls[0]
        self.assertEqual(endpoint, "https://broker.example.test/oauth/token")
        self.assertEqual(request["grant_type"], "urn:ietf:params:oauth:grant-type:token-exchange")
        self.assertEqual(request["subject_token_type"], "urn:ietf:params:oauth:token-type:jwt")
        self.assertEqual(request["subject_token"], "header.payload.signature")
        self.assertEqual(request["resource"], "https://api.example.test")
        self.assertEqual(request["audience"], "urn:example:api")
        self.assertEqual(request["scope"], "repo.read")
        self.assertNotIn("refresh_token", request)
        self.assertNotIn("upstream-secret-value-123", repr(credential))
        self.assertNotIn("upstream-secret-value-123", str(credential))
        self.assertEqual(
            credential._authorization_header(),
            "Bearer upstream-secret-value-123",
        )

    def test_scope_expansion_is_rejected(self):
        client, _, form = self.make_client({
            "access_token": "upstream-secret-value-123",
            "token_type": "Bearer",
            "expires_in": 120,
            "scope": "repo.read repo.write",
        })
        with self.assertRaisesRegex(CredentialExchangeError, "scope does not exactly match"):
            client.exchange(
                resource="https://api.example.test",
                audience="urn:example:api",
                scopes=frozenset({"repo.read"}),
            )
        self.assertEqual(len(form.calls), 1)

    def test_overlong_token_and_refresh_token_are_rejected(self):
        for response in (
            {
                "access_token": "long-lived",
                "token_type": "Bearer",
                "expires_in": 301,
                "scope": "repo.read",
            },
            {
                "access_token": "short-lived",
                "token_type": "Bearer",
                "expires_in": 120,
                "scope": "repo.read",
                "refresh_token": "refresh-secret",
            },
        ):
            client, _, _ = self.make_client(response)
            with self.assertRaises(CredentialExchangeError):
                client.exchange(
                    resource="https://api.example.test",
                    audience="urn:example:api",
                    scopes=frozenset({"repo.read"}),
                )

    def test_expired_workload_identity_fails_before_token_exchange(self):
        source = FakeWorkloadJWTSource(expires_at=int(time.time()) - 1)
        client, _, form = self.make_client(source=source)
        with self.assertRaisesRegex(CredentialExchangeError, "expired or invalid identity"):
            client.exchange(
                resource="https://api.example.test",
                audience="urn:example:api",
                scopes=frozenset({"repo.read"}),
            )
        self.assertEqual(form.calls, [])

    def test_wrong_spiffe_principal_fails_before_token_exchange(self):
        source = FakeWorkloadJWTSource()
        source.fetch_jwt_svid = lambda audience: WorkloadJWT(
            "header.payload.signature",
            "spiffe://example.org/ns/habitroute/sa/unrelated",
            int(time.time()) + 120,
        )
        client, _, form = self.make_client(source=source)
        with self.assertRaisesRegex(CredentialExchangeError, "does not match"):
            client.exchange(
                resource="https://api.example.test",
                audience="urn:example:api",
                scopes=frozenset({"repo.read"}),
            )
        self.assertEqual(form.calls, [])

    def test_invalid_resource_or_empty_scope_is_rejected(self):
        client, _, form = self.make_client()
        with self.assertRaises(ValueError):
            client.exchange(
                resource="http://api.example.test",
                audience="urn:example:api",
                scopes=frozenset({"repo.read"}),
            )
        with self.assertRaises(ValueError):
            client.exchange(
                resource="https://api.example.test",
                audience="urn:example:api",
                scopes=frozenset(),
            )
        self.assertEqual(form.calls, [])


class BrokeredEgressProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = SQLiteFlowJournal(Path(self.temp.name) / "proxy.sqlite3")
        self.capabilities = HmacCapabilityBroker(b"q" * 32)
        self.token = self.capabilities.mint_root(
            subject="spiffe://example.org/ns/habitroute/sa/worker",
            task_id="task-1",
            operations={"repo.read"},
            hosts={"api.example.test"},
            resource_prefixes={"https://api.example.test/v1/project"},
            ttl_seconds=300,
            max_calls=3,
            max_cost=5.0,
        )
        self.descriptor = OperationDescriptor(
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            external=True, method="GET",
        )
        self.operation = OperationStep(
            "repo.read", OperationEffect.READ_ONLY,
            idempotency_key_supported=True,
        )
        self.source = FakeWorkloadJWTSource()
        self.form = FakeFormTransport()
        self.exchange = OAuthTokenExchangeClient(
            token_endpoint="https://broker.example.test/oauth/token",
            broker_audience="spiffe://example.org/credential-broker",
            workload_identity=self.source,
            expected_spiffe_id="spiffe://example.org/ns/habitroute/sa/egress",
            transport=self.form,
        )
        self.upstream = FakeUpstreamTransport()

    def make_proxy(
        self, descriptor=None, transport=None, scopes=None,
        approval_verifier=None, operation_effect=None,
    ):
        trusted = descriptor or self.descriptor
        effect = operation_effect or self.operation.effect
        return BrokeredEgressProxy(
            capability_broker=self.capabilities,
            token_exchange=self.exchange,
            transport=transport or self.upstream,
            journal=self.journal,
            operation_descriptors={trusted.operation_ref: trusted},
            operation_steps={
                trusted.operation_ref: OperationStep(
                    trusted.operation_ref, effect,
                    idempotency_key_supported=True,
                )
            },
            audience_by_host={trusted.host: "urn:example:api"},
            scopes_by_operation=scopes or {trusted.operation_ref: frozenset({"repo.read"})},
            approval_verifier=approval_verifier,
        )

    def test_proxy_rechecks_capability_and_sends_token_only_upstream(self):
        proxy = self.make_proxy()
        result = proxy.invoke(
            self.descriptor, self.operation, {"path": "src"},
            idempotency_key="stable-key",
            capability_token=self.token,
        )
        self.assertEqual(result.outcome, OperationOutcome.SUCCEEDED)
        self.assertEqual(len(self.upstream.calls), 1)
        self.assertEqual(
            self.upstream.calls[0]["authorization_header"],
            "Bearer upstream-secret-value-123",
        )
        self.assertEqual(self.form.calls[0][1]["scope"], "repo.read")

    def test_proxy_denies_wrong_resource_before_requesting_credentials(self):
        denied = OperationDescriptor(
            "repo.read", "other.example.test",
            "https://other.example.test/v1/project",
            external=True, method="GET",
        )
        proxy = self.make_proxy(descriptor=denied)
        with self.assertRaises(OperationNotExecuted):
            proxy.invoke(
                denied, self.operation, {},
                idempotency_key="denied-key",
                capability_token=self.token,
            )
        self.assertEqual(self.form.calls, [])
        self.assertEqual(self.upstream.calls, [])

    def test_action_approval_is_reverified_at_proxy_boundary(self):
        protected = OperationDescriptor(
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            external=True, method="GET", approval_required=True,
        )
        evidence = ApprovalEvidence(
            self.capabilities.verify(self.token).capability_id,
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            "operator", "approval-1", int(time.time()) + 120,
            approval_request_sha256(
                protected, self.operation, {"path": "different"}, "approved-action-key",
            ),
            "independent-approval-signature",
        )
        proxy = BrokeredEgressProxy(
            capability_broker=self.capabilities,
            token_exchange=self.exchange,
            transport=self.upstream,
            journal=self.journal,
            operation_descriptors={"repo.read": protected},
            operation_steps={"repo.read": self.operation},
            audience_by_host={"api.example.test": "urn:example:api"},
            scopes_by_operation={"repo.read": frozenset({"repo.read"})},
            approval_verifier=GoodApprovalVerifier(),
        )
        with self.assertRaises(OperationNotExecuted):
            proxy.invoke(
                protected, self.operation, {"path": "src"},
                idempotency_key="approved-action-key",
                capability_token=self.token,
                approval_evidence=evidence,
            )
        self.assertEqual(self.form.calls, [])
        self.assertEqual(self.upstream.calls, [])

    def test_valid_single_action_approval_is_accepted_by_proxy(self):
        protected = OperationDescriptor(
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            external=True, method="GET", approval_required=True,
        )
        action_inputs = {"path": "src"}
        action_key = "valid-approved-action"
        evidence = ApprovalEvidence(
            self.capabilities.verify(self.token).capability_id,
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            "operator", "approval-2", int(time.time()) + 120,
            approval_request_sha256(protected, self.operation, action_inputs, action_key),
            "independent-approval-signature",
        )
        proxy = BrokeredEgressProxy(
            capability_broker=self.capabilities,
            token_exchange=self.exchange,
            transport=self.upstream,
            journal=self.journal,
            operation_descriptors={"repo.read": protected},
            operation_steps={"repo.read": self.operation},
            audience_by_host={"api.example.test": "urn:example:api"},
            scopes_by_operation={"repo.read": frozenset({"repo.read"})},
            approval_verifier=GoodApprovalVerifier(),
        )
        result = proxy.invoke(
            protected, self.operation, action_inputs,
            idempotency_key=action_key,
            capability_token=self.token,
            approval_evidence=evidence,
        )
        self.assertEqual(result.outcome, OperationOutcome.SUCCEEDED)
        self.assertEqual(len(self.upstream.calls), 1)

    def test_proxy_invocation_ledger_prevents_duplicate_provider_dispatch(self):
        proxy = self.make_proxy()
        first = proxy.invoke(
            self.descriptor, self.operation, {},
            idempotency_key="proxy-single-dispatch",
            capability_token=self.token,
        )
        second = proxy.invoke(
            self.descriptor, self.operation, {},
            idempotency_key="proxy-single-dispatch",
            capability_token=self.token,
        )
        self.assertEqual(first.outcome, OperationOutcome.SUCCEEDED)
        self.assertEqual(second.outcome, OperationOutcome.UNKNOWN)
        self.assertEqual(len(self.upstream.calls), 1)
        self.assertEqual(len(self.form.calls), 1)

    def test_worker_cannot_clear_destructive_flag_in_descriptor(self):
        trusted = OperationDescriptor(
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            external=True, method="POST", destructive=True,
        )
        forged = OperationDescriptor(
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            external=True, method="POST", destructive=False,
        )
        operation = OperationStep(
            "repo.read", OperationEffect.NON_REPEATABLE,
            idempotency_key_supported=True,
        )
        proxy = self.make_proxy(
            descriptor=trusted, operation_effect=OperationEffect.NON_REPEATABLE,
        )
        with self.assertRaisesRegex(OperationNotExecuted, "untrusted_operation_descriptor"):
            proxy.invoke(
                forged, operation, {},
                idempotency_key="forged-destructive-flag",
                capability_token=self.token,
            )
        self.assertEqual(self.form.calls, [])
        self.assertEqual(self.upstream.calls, [])

    def test_worker_cannot_downgrade_operation_effect(self):
        proxy = self.make_proxy()
        forged_step = OperationStep(
            "repo.read", OperationEffect.IDEMPOTENT,
            idempotency_key_supported=True,
        )
        with self.assertRaisesRegex(OperationNotExecuted, "untrusted_operation_step"):
            proxy.invoke(
                self.descriptor, forged_step, {},
                idempotency_key="forged-effect-classification",
                capability_token=self.token,
            )
        self.assertEqual(self.form.calls, [])
        self.assertEqual(self.upstream.calls, [])

    def test_destructive_request_without_provider_snapshot_is_denied(self):
        destructive_descriptor = OperationDescriptor(
            "repo.read", "api.example.test",
            "https://api.example.test/v1/project",
            external=True, method="POST", destructive=True,
        )
        destructive_step = OperationStep(
            "repo.read", OperationEffect.NON_REPEATABLE,
            idempotency_key_supported=True,
        )
        proxy = self.make_proxy(
            descriptor=destructive_descriptor,
            operation_effect=OperationEffect.NON_REPEATABLE,
        )
        with self.assertRaises(OperationNotExecuted):
            proxy.invoke(
                destructive_descriptor, destructive_step, {},
                idempotency_key="destructive-without-snapshot",
                capability_token=self.token,
            )
        self.assertEqual(self.form.calls, [])
        self.assertEqual(self.upstream.calls, [])

    def test_upstream_credential_reflection_is_never_returned(self):
        self.upstream.result = HarnessOperationResult(
            OperationOutcome.SUCCEEDED,
            outputs=(("debug", "upstream-secret-value-123"),),
        )
        proxy = self.make_proxy()
        result = proxy.invoke(
            self.descriptor, self.operation, {},
            idempotency_key="reflection-key",
            capability_token=self.token,
        )
        self.assertEqual(result.outcome, OperationOutcome.UNKNOWN)
        self.assertEqual(result.error_code, "upstream_credential_disclosure")
        self.assertEqual(result.outputs, ())


if __name__ == "__main__":
    unittest.main()
