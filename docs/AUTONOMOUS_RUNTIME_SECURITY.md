# Autonomous Runtime Security Constitution

**Status:** implemented reference layer; production adapters remain deployment work.  
**Scope:** HabitRoute execution authorization, delegation, durable state, audit, recovery, triggers and candidate-promotion gates.

This document describes executable controls in `src/habitroute/autonomy/`. It does not claim that an external credential broker, egress proxy, scheduler, Control Plane, snapshot provider or transparency service is already deployed.

## 1. Security model

An autonomous worker is not its own policy authority. A task requests an operation; a policy-enforcing adapter checks it; a bounded executor performs it; an independent verifier checks the outcome; and an append-only audit ledger records the evidence.

The policy decision is ternary:

- `ALLOW`: all scoped capability, resource, budget, approval and recovery predicates pass.
- `APPROVAL_REQUIRED`: independent, operation-specific approval is missing or invalid.
- `DENY`: any required predicate fails, the capability is expired/revoked, or a mandatory control is unavailable.

An allow decision is not a credential. The execution adapter must still route external requests through the configured egress proxy.

## 2. Capability tokens and delegation

`autonomy.capabilities` provides immutable signed claims and an injectable `CapabilityBroker` interface. The local `HmacCapabilityBroker` is a reference/test implementation; it is not a remote Credential Broker or KMS/HSM integration.

Every capability is bounded by:

- exact operation names;
- allowed hosts and segment-bounded resource prefixes;
- a call budget and cost budget;
- optional operation-specific approval requirements;
- an expiration no more than 900 seconds after issue;
- delegation depth no greater than three.

Delegation attenuates operations, hosts, resources, budgets and TTL. Approval requirements cannot be removed. Each child carries signed ancestor budget ceilings, and every invocation charges all ancestors in one ledger transaction. This prevents sibling agents from each consuming the parent's entire allowance. Revoking an ancestor blocks descendants on their next authorization check.

The DAG validator rejects cycles and depth overflow. It validates a supplied graph; it does not launch worker processes. A runtime-specific agent launcher still needs to enforce the validated edges and pass only the child token and bounded task data.

Tokens are bearer credentials. Do not log, serialize to workflow context, or persist token values. The HMAC key is injected into process memory and must not be reused as production key management. A production broker should keep signing keys in a KMS/HSM, bind tokens to workload identity/audience, support rotation and durable revocation, and issue resource-scoped short-lived credentials to the egress proxy.

## 3. Deterministic idempotency and external effects

`deterministic_idempotency_key` returns a UUIDv5 derived from a stable logical operation scope and operation reference. UUIDv5 makes a repeatable identifier; it is not an authenticator, encryption mechanism, or authorization proof. External providers must actually honor their idempotency contract.

`SQLiteFlowJournal.claim_invocation` reserves an invocation before dispatch. The global key is bound to the capability, operation, effect and input digest. Reusing a key with changed inputs or a different capability is rejected. A successful or unknown outcome is never dispatched again automatically. A known failure can retry only when the operation effect is read-only, idempotent or provider-deduplicated. The same logical key and original input digest are required.

If the process stops after reservation but before a durable result, the ledger conservatively records a running invocation. A later worker receives a reconciliation-required result rather than replaying it. `reconcile_invocation` can resolve a running/unknown result only with evidence accepted by a provider-specific `ReconciliationVerifier`. A verified `not_applied` outcome can safely be retried, including a non-repeatable operation, because the provider has proven that the original effect did not occur. A verified `applied` outcome is terminal. Reconciliation does not dispatch an operation.

UUIDv5 plus local state does not create exactly-once external effects. Correctness still depends on the provider's idempotency/reconciliation semantics and on the egress adapter enforcing them.

## 4. Durable flow store and external triggers

`SQLiteFlowJournal` implements HabitRoute's `FlowJournal` append/load contract. It uses SQLite WAL, `synchronous=FULL`, transactions, private local file modes and append-only guards for event/audit/receipt records. A flow event and its audit leaf are committed in the same transaction.

The ledger is a local durable store for one trust boundary. It is not a distributed workflow database, distributed lease service, multi-region consensus system or scheduler. Run one authorized writer per workflow unless a separate distributed coordinator/lease adapter is added and tested.

`hydrate_trigger` treats each wake-up as a trigger envelope, durably claims it, then reconstructs state from committed events. The first claimed context for a run is stored immutably alongside the trigger receipt in the same transaction. Later or duplicate deliveries cannot replace that initial context. Raw webhook payloads are represented by a SHA-256 digest, not stored. Context fields are checked for obvious secret-bearing names and common token/private-key patterns before persistence; this is defense in depth, not a complete secret detector.

The pinned `FlowDefinition` must be supplied on hydration. A mismatched flow identity/version fails rather than silently loading a newer definition.

## 5. Merkle audit and external anchoring

Each audit record is canonicalized and hashed as a domain-separated Merkle leaf. Internal nodes use a separate domain prefix. `merkle_root`, `inclusion_proof` and `verify_inclusion` support inclusion proofs for the current local tree. `verify_integrity` checks leaf hashes, current root, flow-event/audit correspondence, trigger/context binding and stored anchor receipt digests.

SQLite append-only triggers protect ordinary application paths; they do not make a local database tamper-proof against an administrator who can replace the entire database or alter its schema. `AuditAnchor` is a protocol for an independently operated append-only transparency service. High-risk external execution can require an external anchor before and after the side effect. A caller should re-verify the remote receipt (`has_current_external_anchor(anchor)` / `require_current_external_anchor`) rather than treating a local receipt row as proof of external publication.

A production anchor should prevent tree-head rollback/equivocation and provide independently verifiable signed receipts and consistency proofs. The repository currently supplies the interface and local receipt verification, not a hosted transparency service.

## 6. Egress and credential boundary

`PolicyEnforcedHarnessAdapter` wraps the existing `HarnessAdapter`. For `external=True`, it never calls the inner adapter; it requires `EgressProxy.invoke`. Absolute network URLs cannot be labelled local to bypass this boundary. External descriptors require absolute HTTPS URLs with exact host/port matching and reject userinfo, query strings and fragments. A read-only operation requires GET/HEAD; non-read-only operations cannot use GET/HEAD. The operation catalogue explicitly classifies destructive effects: only operations marked `destructive=True` require provider-verified CoW/PITR evidence. POST/PUT/PATCH are not automatically destructive; reversible creates and updates can proceed with scoped authorization, idempotency and any operation-specific approval. Bulk deletes, irreversible changes and other destructive operations remain snapshot-gated.

The production egress proxy must, at minimum:

- exchange the task capability for short-lived, scope-attenuated credentials without returning those credentials to the worker;
- enforce method, exact host and path on every request;
- resolve DNS and block loopback, private, link-local and cloud metadata ranges, with rebinding defenses;
- verify TLS; disable redirects or re-authorize every redirect target;
- block proxy tunnelling and unapproved protocols;
- enforce request/response size, rate, timeout and destination budgets;
- redact credentials and sensitive response fields from logs.

No production egress proxy is included. Until one is injected, external operations fail closed. The secret scanner is heuristic: applications must pass vault/secret references, not raw credentials, and should apply provider-specific structured redaction.

## 7. Destructive operations and recovery

An `OperationDescriptor` marks destructive effects. `RecoveryPlan` supplies a `SnapshotEvidence` for an exact workflow, state sequence and state hash. `require_recovery_snapshot` rejects missing, stale, future-dated, mismatched or provider-unverified evidence. A production `SnapshotVerifier` must query the underlying provider and validate its signed receipt. Merely constructing a `SnapshotEvidence` object is not proof that a snapshot exists.

A provider adapter for CoW/PITR is not included. Until a verifier and provider-backed snapshot source are configured, destructive operations fail closed. The operation catalogue must correctly mark every destructive or bulk mutation; the guard cannot infer business-level destructiveness from a method name alone.

## 8. Candidate policy evolution and promotion

`CandidatePatch` describes a candidate version, diff digest, rationale, expected telemetry delta and candidate branch reference. `ShadowReplayReport` must target the exact candidate/diff, meet the configured replay minimum, have zero failures and report all required invariants as true. `evaluate_promotion` additionally requires a non-expired signed approval verified by an independent `ControlPlaneVerifier`.

This is a promotion decision function only. It does not merge a branch, alter production policy or deploy. A production Control Plane and shadow-replay runner must be provided independently. Candidate branches should be protected by repository rules and CI; the candidate patch must not target a protected production branch.

Required promotion invariants include capability-scope enforcement, bounded delegation, external egress enforcement, no replay of unknown outcomes, recovery before destructive operations, valid audit integrity and no raw secrets persisted.

## 9. Integration

The local security layer is intentionally an adapter around the existing HabitRoute API:

```python
from habitroute.autonomy import (
    HmacCapabilityBroker,
    OperationDescriptor,
    PolicyEnforcedHarnessAdapter,
    SQLiteFlowJournal,
)

# Prototype only. Use an external KMS/HSM-backed CapabilityBroker in production.
broker = HmacCapabilityBroker(signing_key_from_secure_runtime_memory)
token = broker.mint_root(
    subject="repo-worker",
    task_id="repo-review-001",
    operations={"repo.inspect", "repo.test"},
    hosts={"github.example.test"},
    resource_prefixes={"https://github.example.test/repos/team/project"},
    ttl_seconds=600,
    max_calls=20,
    max_cost=10.0,
)
journal = SQLiteFlowJournal("/secure/runtime/flow-ledger.sqlite3")
secured_harness = PolicyEnforcedHarnessAdapter(
    existing_harness,
    broker=broker,
    capability_token=token,
    descriptors={
        "repo.inspect": OperationDescriptor(
            "repo.inspect", "github.example.test",
            "https://github.example.test/repos/team/project", external=True,
            method="GET",
        ),
        "repo.test": OperationDescriptor(
            "repo.test", "github.example.test",
            "https://github.example.test/repos/team/project/checks", external=True,
            method="POST", approval_required=False,
        ),
    },
    journal=journal,
    egress_proxy=production_egress_proxy,
)
```

The names `signing_key_from_secure_runtime_memory`, `existing_harness` and `production_egress_proxy` are deployment-provided values, not built-ins in HabitRoute. The code above is an integration shape, not a runnable out-of-box production configuration.

Use `hydrate_trigger(envelope, pinned_definition, journal, initial_context=...)` for stateless trigger handling. Use `reconcile_invocation` only with a real independent provider verifier. Use `evaluate_promotion` only after collecting exact shadow replay and Control Plane evidence.

## 10. Verification and known limits

The security layer includes unit tests for signature tampering, expiry, attenuation, ancestor budgets, revocation, DAG depth/cycles, URL/path boundaries, UUIDv5 stability, atomic journaling, idempotency conflicts, retry/reconciliation, Merkle proofs over odd/even tree sizes, audit-anchor tampering, duplicate triggers, untrusted wake-up context, egress routing, approval, secret rejection, recovery snapshots and promotion gates.

The local suite is a focused module suite. The repository's Python 3.11–3.13 CI must run against the real HabitRoute core before merge. The currently pending draft PR #12 separately contains per-operation checkpoints and flow-level recovery for multi-operation habits; this security layer does not silently duplicate or merge that branch.

Production adapters still required:

1. KMS/HSM-backed Credential Broker with key rotation, audience/workload identity and durable revocation.
2. Policy-enforcing network egress proxy with SSRF/DNS/TLS/redirect controls.
3. Independent approval service and signed evidence verifier.
4. Provider CoW/PITR snapshot source and verifier.
5. Independently operated audit transparency anchor with signed heads and consistency proofs.
6. External Control Plane and shadow-replay runner, with protected promotion controls.
7. A durable distributed workflow store/lease service and scheduler for multi-process execution.
8. A runtime agent launcher that enforces the validated delegation DAG and child-token isolation.

Until the relevant adapter is installed and independently verified, its corresponding high-risk operation remains unavailable by design. This is a reference security boundary, not a claim of production readiness or an autonomous system with unrestricted authority.
