# Integration Contracts — Draft v0.1

These are boundaries for independent packages. They do not create runtime behavior until implemented and tested. Schemas should be placed under `shared/contracts/v0.1/` during the source-import phase.

## Rules

- JSON-compatible and provider-neutral.
- IDs are opaque; versions and content digests are immutable references.
- Large context and output bodies are referenced by ID/digest, not copied into telemetry by default.
- Time is UTC RFC 3339. Durations and resource quantities include units.
- Missing values are unknown, not zero.
- Cost dimensions remain separate.
- Authorization and outcome verification are different contracts.

## TaskEnvelope

Runtime-owned task identity, objective, explicit constraints, requested capabilities and budget policy. Inputs are references with media type and digest. The envelope is not an authorization token and must never contain raw credentials.

## ContextManifest

CPM-owned output describing the selected package/skill references, versions, dependency closure, source digests, residency level (index/detail), load reason, deferrals, eviction decisions, accounting method and budget outcome. Context content itself is excluded from execution evidence by default.

Token fields must identify tokenizer/provider and method. UTF-8 byte estimates, configured tokenizer counts and provider-reported usage are different types.

## HabitDescriptor and HabitSelection

HabitRoute owns immutable habit identity/version, definition digest, applicable triggers/preconditions, harness/environment compatibility, operation-effect semantics, lifecycle status, verification summary and evidence references.

The runtime selects an exact version and records why it was selected or rejected. Optional `required_context_refs` reference CPM skill/package IDs; they do not embed skill bodies. HabitRoute must not import CPM.

## ExecutionEvent

HabitRoute remains the authority for flow transition semantics. The runtime may correlate events with a task ID and context manifest digest but may not rewrite event outcomes.

An operation record should identify run, flow/version, node, habit/version, operation, attempt, side-effect class, input digest, idempotency-key reference, adapter identity/version, invocation times, outcome certainty, output digest/reference, postcondition/verifier reference and per-dimension cost.

Never store raw secrets or reusable credentials in evidence.

## CostVector

Record independent dimensions, for example:

- context occupancy (unit + accounting method);
- context retrieval/cache reads and writes;
- provider-reported model input/output usage;
- operation/tool/API call counts;
- wall-clock latency;
- CPU/memory/other resource units;
- external cost (amount + currency + pricing basis);
- retries, recovery, reconciliation and human intervention.

Do not combine unlike dimensions into one total without an explicit unit conversion and declared objective.

## VerificationRecord

Identify verifier implementation/version, target digest, contract/postcondition IDs, test or measurement method, observed values, verdict and evidence references. A successful executor return is not by itself proof of correctness.

## Compatibility

Schema version is independent of package version. Additive optional fields can be compatible; changing meanings or required fields requires a major schema revision. Readers must preserve unknown archival fields but fail closed for unknown authorization/side-effect semantics.

## Not guaranteed by these contracts

These contracts do not provide cross-system transactionality, exactly-once external effects, distributed locking, authentication, schema hosting, or cryptographic attestation. Those need explicit implementations and tests.
