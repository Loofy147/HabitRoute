# Autonomous Runtime Security Constitution

**Status:** Reference implementation in progress  
**Scope:** HabitRoute execution boundary and future Unified Agent Runtime composition  
**Principle:** The agent may request authority; it must not grant or expand authority to itself.

## Enforcement model

Every consequential operation passes through a deterministic policy decision point before the adapter performs it:

`DENY`, `APPROVAL_REQUIRED`, or `ALLOW`.

The execution adapter is the policy-enforcement point. It must not execute an operation unless the decision is `ALLOW`. A decision is not proof that the downstream service enforced it; the adapter and receiving service must independently enforce their own authorization.

## Implemented reference primitives

| Invariant | Current implementation | Limitation |
|---|---|---|
| Task-scoped capability | Immutable `CapabilityLease`, HMAC signature verification, exact host/operation/resource/task checks, expiry and budget checks | HMAC key custody is external; local object is not a workload identity provider |
| Delegation | Child scope is subset of parent; parent signature verified; depth capped at 3; child TTL capped at 900 seconds | No distributed revocation registry or cross-process lease exchange |
| Approval | Separate `ApprovalAuthority`; signed receipt bound to task, host, operation, resource, risk, budget and recovery snapshot | Reference HMAC issuer; production approver identity must come from an independent IdP/workflow |
| External mutation | Deterministic UUIDv5 idempotency key derived from task, host, operation and resource | The downstream provider must actually honor and persist the key; UUIDv5 does not itself guarantee idempotency |
| Destructive operations | Requires committed, verified CoW/PITR evidence for the exact resource and independent approval | Evidence is a typed claim; production adapter must verify the snapshot with the storage provider |
| Audit | Fsynced JSONL hash chain and deterministic Merkle checkpoint | Local file is not tamper-proof against privileged host compromise; root must be signed/witnessed externally |
| Fail-closed policy | Unknown/invalid lease, scope mismatch, expired approval or missing recovery evidence is denied or escalated | All execution paths must be routed through the policy enforcement point |

## Security invariants

1. No adapter invocation before policy evaluation.
2. Every lease is bound to a subject and task and has explicit host, operation, resource, budget and expiry bounds.
3. A child lease cannot expand any parent scope or budget.
4. Delegation depth never exceeds 3; child lease TTL never exceeds 900 seconds.
5. Approval receipts are bound to the exact effect and expire.
6. External mutations receive a stable UUIDv5 key. A provider adapter must pass it through and reconcile ambiguous outcomes rather than blindly retry.
7. Destructive actions require independently verified recovery evidence for the exact target resource.
8. Audit records are append-only at the application interface, sequence-checked, hash-chained and fsynced.
9. Agent code cannot alter the policy authority, approval authority, audit store or production policy bundle.
10. Candidate policy/code changes are staged and must pass shadow replay, regression, invariant and recovery tests before independent promotion.

## Integration contract

A provider adapter should implement this sequence:

1. Resolve task, subject, immutable operation descriptor and current capability lease.
2. Ask the policy decision point to evaluate the exact request.
3. Emit the request and decision to the independent audit sink.
4. If `DENY`, stop. If `APPROVAL_REQUIRED`, persist the pending request and stop.
5. If `ALLOW`, pass the returned idempotency key to the receiving provider for external mutations.
6. Capture provider receipt, observed effect, output digest and postcondition results.
7. Append the effect receipt to the audit sink before advancing the flow checkpoint.
8. If the result is ambiguous, mark the flow `NEEDS_ATTENTION`; do not assume failure and repeat.

The policy decision point and audit sink must run outside the agent's writable trust boundary. The receiving API must perform final authorization. A prompt instruction or in-process boolean is not an enforcement boundary.

## Required production adapters (not yet implemented)

- **Identity / credential broker:** SPIFFE/SPIRE workload identity or cloud workload identity plus Vault/STS-style short-lived credential exchange. Credentials are injected into the adapter, never returned to the model.
- **Egress enforcement:** default-deny network policy or a dedicated proxy that validates destination, method, request schema, byte/rate budgets and policy decision. Direct sockets from the agent runtime must be blocked.
- **Durable ledger:** transactional event store with compare-and-swap sequence numbers, unique event IDs, durable checkpoints and distributed leases. The current local JSONL flow journal is not a distributed ledger.
- **Independent policy plane:** out-of-process OPA/Cedar or equivalent deterministic policy service; signed policy bundles and controlled promotion.
- **Audit transparency:** external append-only transparency service or WORM/object-lock storage; signed Merkle roots, independent witnesses and verifiable inclusion/consistency proofs.
- **Recovery provider:** adapter that queries storage/provider APIs and verifies snapshot ID, resource identity, commit state, timestamp and restore test evidence.
- **Approval workflow:** independent identity, approver role separation, exact request digest, expiry, replay prevention and durable decision record.

## Deliberate non-guarantees

This reference layer does not claim to provide distributed exactly-once effects, secure hardware identity, network isolation, cryptographic non-repudiation, tamper-proof local storage, automatic revocation across replicas, or production credential brokerage. Those guarantees require external systems and deployment configuration.

## Verification

Run the core suite:

```bash
python -m unittest discover -s tests -v
```

Security tests must include forged/expired leases, task and resource confusion, delegation escalation, TTL/depth overflow, replayed approvals, missing/stale recovery snapshots, deterministic idempotency, audit tampering, crash injection around provider effects, and recovery replay.

## Research basis

- NIST NCCoE, *Securing the Agentic Lifecycle* (2026): agent identity, ephemeral task-scoped credentials, contextual authorization and verifiable audit.
- CNCF, *Cloud native agentic standards* (2026): unique workload identities, short-lived credentials, per-action authorization and network boundaries.
- OWASP, *Securing Agentic Applications Guide*: separate control/data planes and just-in-time credentials.
- Microsoft Agent Governance Toolkit ACS security model: deterministic, stateless policy decisions; explicit warning that the policy runtime does not replace host enforcement, backend authorization or durable audit.
- IETF WIMSE Agent Identity Management draft: reconstructable identity, delegation and action chains.

These sources inform the design; they do not certify this implementation.
