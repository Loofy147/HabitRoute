# Production Security Adapters and Completion Plan

## Status

This document distinguishes the implemented local reference boundary from production infrastructure that still must be deployed and verified.

**Implemented in the security branch**
- Capability claims, HMAC reference signing, expiry, scope attenuation, parent budget ceilings, revocation checks, and DAG validation.
- A policy-enforcing harness adapter that fails closed for external calls without an egress proxy.
- Transactional local invocation accounting and conservative unknown-outcome handling.
- Action-bound approval evidence: the signed approval digest covers the operation, destination, route, method, effect, cost, input digest, idempotency identity, and recovery identity.
- SQLite WAL/FULL journal, local Merkle audit structure, optional external audit-head anchoring, trigger hydration, recovery verification interfaces, and shadow-replay promotion gates.
- Reversible writes are separated from explicitly destructive operations so routine POST/PUT operations are not incorrectly forced through snapshot gates.

**Not implemented or not yet deployment-verified**
- Production KMS/HSM-backed capability signing and a real external credential broker.
- A deployed egress proxy and network-level prevention of direct worker egress.
- Process/container isolation that prevents callers from bypassing the Python adapter and invoking an inner adapter directly.
- A distributed transactional ledger, durable scheduler, and production worker launcher.
- An independent approval service, remote transparency service/witnesses, provider-specific snapshot/PITR integrations, and an external Control Plane.
- Production DNS/SSRF protections, provider idempotency reconciliation, and restore drills.

The local reference implementation must not be represented as providing these deployment guarantees.

## Recommended production composition

| Boundary | Recommended implementation | Enforcement requirement |
|---|---|---|
| Workload identity | SPIFFE/SPIRE with short-lived X.509-SVIDs and mTLS between workloads | Authenticate the workload, not a user-supplied agent name. Prefer X.509-SVID over replayable bearer identity tokens where possible. |
| Credential exchange | Credential Broker backed by KMS/HSM and OAuth 2.0 Token Exchange (RFC 8693) | Issue resource/audience-restricted, scope-attenuated, short-lived credentials. Never return provider credentials to the model or worker process. Use sender-constrained tokens (mTLS/DPoP) where supported. |
| Policy decision | OPA/Rego or Cedar as an independently deployed PDP | Default deny; evaluate principal, task, resource, operation, environment, budget, expiry, risk, and policy revision. Record decision ID and policy revision. |
| Network enforcement | Envoy egress proxy with OPA external-authorization filter | Route all external traffic through the proxy. Disable direct egress at the network namespace/firewall layer. Enforce destination, resolved IP, SNI, method, path, headers, body limits, redirects, and rate/budget limits. Fail closed if authorization is unavailable. |
| Execution isolation | Separate worker process/container per trust boundary; read-only root filesystem; scoped writable mounts; seccomp/AppArmor or equivalent; CPU, memory, PID and time limits | The model must not hold a reference to an unrestricted inner adapter. The proxy and policy service must be outside the worker's control domain. |
| Durable orchestration | Temporal for long-lived workflow history, timers, retries and recovery; PostgreSQL transactional ledger for capability use, idempotency, approvals, budgets and external-effect state | Treat workflow replay and activity retry as at-least-once execution. Every external activity still needs a stable idempotency key and reconciliation path. |
| Audit transparency | Local structured journal plus signed remote append-only transparency log (for example, a private Rekor deployment) | Publish event digests and minimal metadata, not secrets or sensitive payloads. Verify signed checkpoints, inclusion proofs and consistency proofs. Operate independent witnesses in a separate trust domain. |
| Destructive recovery | Provider-specific CoW/PITR adapter with snapshot identity, timestamp, scope and state hash | Verify the snapshot is committed and restorable before dispatch. Bind its identity to the action digest. Run scheduled restore drills. |
| Approval | Independent approval service signing the exact action digest | Approval is single-action, time-limited, actor-bound and consumed atomically with the invocation claim. Any change to inputs, target, cost, method, route, idempotency key or recovery state invalidates it. |
| Delegation | Broker-issued child capability via token exchange or equivalent signed caveated claims | Child authority is a strict subset of parent authority. Enforce TTL <= 900 seconds, depth <= 3, acyclic lineage, aggregate ancestor budgets, and explicit host/operation/resource scopes. |
| Promotion | External Control Plane plus CI, shadow replay and signed policy bundles | The runtime may propose a candidate diff; it cannot approve or deploy its own policy changes. |

## Important implementation details

### Identity and credential flow

Use SPIFFE/SPIRE to give each runtime component a cryptographic workload identity. The Credential Broker authenticates the calling workload using mTLS and exchanges that identity plus the parent capability for a short-lived credential intended for one provider/resource and a narrow set of scopes.

For OAuth-compatible providers, use RFC 8693 token exchange with explicit `resource`/audience and scope restriction. Follow OAuth Security BCP (RFC 9700): prefer audience-restricted and sender-constrained access tokens where supported. The worker receives only a non-secret operation handle; the egress proxy performs the credential exchange and injects the provider credential upstream.

### Authorization and egress

The worker submits a structured operation intent. The PDP returns one of:
- `DENY`
- `APPROVAL_REQUIRED`
- `ALLOW`

The PEP (Envoy) enforces the result on the actual network request. Do not treat a successful in-process policy check as sufficient network enforcement. Disable direct worker egress at the network layer. Normalize paths consistently between authorization and upstream routing; reject redirects unless each redirect target is independently re-authorized. Resolve DNS at connection time, reject private/link-local/metadata IP ranges unless explicitly allowed, and pin the validated destination for the connection to prevent DNS rebinding.

OPA decision logs should include decision ID, trace ID, policy bundle revision and the decision result. Configure masking before export so secrets and sensitive request bodies never enter the audit stream.

### Persistence and exactly-once semantics

Use Temporal for durable workflow progression, waits, signals and retries. Use PostgreSQL transactions and unique constraints for idempotency claims, approval consumption, budgets and operation state. A unique operation identity should include workflow run, operation reference, and stable logical effect identity.

No framework can guarantee exactly-once behavior for arbitrary external APIs without cooperation from the provider. Model external effects as:
1. `NOT_DISPATCHED`
2. `DISPATCHED_OUTCOME_UNKNOWN`
3. `CONFIRMED_APPLIED`
4. `CONFIRMED_NOT_APPLIED`
5. `RECONCILIATION_REQUIRED`

On timeout after dispatch, query the provider by idempotency key or external operation ID before retrying. If the provider offers neither idempotency nor reconciliation, block automatic retry for non-repeatable effects and require a human or compensating workflow.

### Audit design

Keep full sensitive event payloads in a private access-controlled store. Send only canonical event digests, policy revision, actor/workload identity, action identity, result and timestamp to the transparency log. Retain signed checkpoints and verify consistency against previously trusted checkpoints. A Merkle log without independent witnesses is tamper-evident only to parties who retain and compare trusted checkpoints; it is not magically immutable.

### Approval semantics

The current local adapter binds approval to an exact action digest. Production approval must additionally be signed by an independent approval authority and consumed atomically with the idempotency claim in the transactional ledger. A generic approval for an operation class is insufficient for high-impact actions.

## Executable egress proof

`deploy/security-lab/compose.yaml` provides a local integration lab with an agent attached only to an internal agent network, Envoy attached to the agent/policy/upstream networks, OPA reachable only from Envoy on the policy network, and a mock upstream reachable only from Envoy on the upstream network. Envoy uses the OPA external-authorization gRPC filter with `failure_mode_allow: false`. The agent test proves the two allowlisted operations work, denied methods/paths return 403, and direct access to the upstream, OPA and public internet fails. Containers are read-only, drop Linux capabilities, use `no-new-privileges`, and have resource/PID limits. This lab proves the network PEP topology; it does not yet prove workload mTLS, production capability-token verification, or credential exchange.

Run it with:

```sh
docker compose -f deploy/security-lab/compose.yaml up --build --abort-on-container-exit --exit-code-from agent
docker compose -f deploy/security-lab/compose.yaml down --volumes --remove-orphans
```

## Delivery sequence

1. **Reference enforcement (current PR):** local capability/policy adapter, action-bound approval, transactional local ledger, audit proofs, recovery and promotion interfaces.
2. **Production identity and PEP:** deploy SPIRE, broker, Envoy egress and OPA; enforce network isolation; test credential non-disclosure and SSRF/DNS-rebinding resistance.
3. **Distributed durability:** PostgreSQL ledger plus Temporal workflow execution; implement leases/fencing, event migration, crash-window and duplicate-trigger tests.
4. **Independent audit and approvals:** remote transparency log with witnesses; independent approval signer and atomic one-time consumption.
5. **Provider recovery adapters:** implement snapshots/PITR and reconciliation for each supported provider; test restore and ambiguous-outcome paths.
6. **External promotion control:** signed policy bundles, shadow replay, canary promotion, rollback and independent authorization.

## Release gates

Do not label the runtime production-ready until all are true:
- Worker network isolation proves direct egress is impossible.
- Credential tests prove raw provider credentials never enter model context, worker logs, traces or persistent state.
- A child agent cannot exceed parent host, operation, resource, TTL or budget constraints.
- Concurrent duplicate invocation tests prove a single provider dispatch or a reconciled result.
- Crash injection at every dispatch/checkpoint boundary proves no blind replay of unknown effects.
- Approval replay and altered-input tests are rejected by the independent signer and transactional ledger.
- Audit witnesses detect truncation, mutation and split views.
- Destructive-operation tests prove snapshot identity, restore viability and rollback.
- Promotion is denied unless external shadow-replay and invariant checks pass.

## Primary references

- OAuth 2.0 Token Exchange, RFC 8693: https://www.rfc-editor.org/rfc/rfc8693
- OAuth 2.0 Security Best Current Practice, RFC 9700: https://www.rfc-editor.org/rfc/rfc9700
- SPIFFE SVIDs and workload identity: https://spiffe.io/docs/latest/deploying/svids/
- OPA-Envoy external authorization: https://www.openpolicyagent.org/docs/envoy
- OPA decision logs: https://www.openpolicyagent.org/docs/management-decision-logs
- Temporal event history and durable replay: https://docs.temporal.io/encyclopedia/event-history
- Temporal retry policy and activity idempotency: https://docs.temporal.io/encyclopedia/retry-policies
- Sigstore Rekor transparency log: https://docs.sigstore.dev/logging/overview/
- Rekor transparency and Merkle proof design: https://github.com/sigstore/architecture-docs/blob/main/rekor-spec.md
