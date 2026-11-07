# Open Risks and Blockers

**Status:** 2026-11-07, PR #8 implementation branch. A risk is closed only with reproducible evidence at the claimed boundary. "Implemented in a draft PR" is not equivalent to released or provider-verified.

| ID | Severity | Status | Risk | Required closure evidence |
|---|---|---|---|---|
| HR-01 | High | PARTIALLY CLOSED IN PR #8 | Local flow runs persist per-operation intents/results; the loader truncates only an unterminated final record and rejects newline-terminated corruption. Production durability across all supported filesystems and providers is not established. | Full crash matrix on target filesystems; file/directory fsync and power-loss validation; broader corruption handling; crash after each transition; replay equivalence; external adapter tests. |
| HR-02 | Critical | OPEN | A local JSONL journal cannot be atomically committed with an arbitrary remote provider effect. A pending intent can represent either "provider never received it" or "provider applied it and acknowledgement was lost." | Provider-specific idempotency/deduplication contract or authoritative lookup/reconciliation; adapter conformance tests for lost acknowledgements, duplicate delivery and stable-key behavior. |
| HR-03 | High | OPEN | EfficiencyGate accepts caller-supplied aggregate profiles. | Raw paired trial ledger, exact matched case IDs, independent verifier and mutation-tested promotion gate. |
| HR-04 | High | PARTIALLY OPEN | Per-operation duration/resource/external-cost observations are now checkpointed. Total cost propagation across provider tokens, context assembly, compute, memory and human recovery is still incomplete. | Typed per-step/flow/context cost vector, explicit unknown/missing values and aggregation tests. |
| HR-05 | High | OPEN | Harness profile can describe controls not actually enforced by a provider. | Concrete adapters with deny tests for allowlist, credentials, approvals, timeout, egress and budgets. |
| HR-06 | High | OPEN | No automated habit discovery/promotion/quarantine. | Trace provenance, candidate generation, shadow evaluation, promotion/quarantine state-machine tests. |
| HR-07 | High | OPEN | HabitRegistry is in-memory only. | Durable exact-version store with immutable-content conflict tests. |
| HR-08 | Medium | OPEN | Local JSONL journal assumes one writer per run. | Explicit lock/lease or transactional store before multiple workers. |
| HR-09 | Medium | OPEN | No journal snapshot/compaction. | Replay equivalence tests and crash-safe snapshot rotation. |
| HR-10 | High | OPEN | CPM v0.5 quality/footprint evidence has limits. | Provider-reported metrics and live semantic quality tests; don't infer from fixture scores or bytes. |
| HR-11 | Medium | OPEN | Legacy simulation has narrow synthetic scope. | Raw seed artifacts, clean-clone reproduction, broader environment/stochastic tests. |
| HR-12 | High | OPEN | Package integration could introduce circular coupling. | Import-graph checks and component-absence tests in CI. |
| HR-13 | High | OPEN | License compatibility/provenance of imported material. | File-level license inventory, dependency/SBOM scan and preserved notices. |
| HR-14 | High | OPEN | Reconciliation records accept a caller-supplied `reconciled_by` string and evidence reference; the core library does not authenticate the caller or validate the external evidence. | Put reconciliation behind an authenticated/authorized operator boundary; bind evidence to an immutable provider query/result; audit actor identity from trusted credentials. |
| HR-15 | High | OPEN | Operation intents pin harness ID/version and environment/context, but there is no independently measured adapter implementation digest. A provider adapter could change while reusing the same declared version. | Require honest immutable adapter-versioning and add a source/build/configuration fingerprint to the harness contract and operation provenance; reject replay on fingerprint mismatch. |

## What PR #8 establishes

The latest full matrix run on the current PR #8 head [42318974329](https://github.com/Loofy147/HabitRoute/actions/runs/42318974329) passed 10 legacy experiment tests, 124 core/contract tests and 13 paired-evaluation tests (147 per version) on Python 3.11, 3.12 and 3.13. This is local deterministic test evidence, not production-provider evidence.

The worker now follows this local sequence for each provider operation:

1. Append and fsync `OPERATION_INTENT` before invoking the adapter. The intent pins harness ID/version plus environment/context IDs.
2. Invoke the adapter using the operation-specific idempotency key.
3. Append and fsync `OPERATION_SUCCEEDED`, `OPERATION_FAILED`, or `OPERATION_OUTCOME_UNKNOWN`.
4. Advance the flow node only after required operation checkpoints exist.

The JSONL journal now writes until the complete record has been appended, fsyncs the file, and fsyncs the parent directory when creating the run file on POSIX. On load, it truncates an unterminated final tail to the previous newline delimiter; newline-terminated corrupt records remain hard failures. A machine-habit worker checkpoints each operation and resumes from the committed prefix. Pending-operation replay is rejected if harness ID/version or environment/context differs from the committed intent. The reducer also rejects skipped operation indexes and refuses to cancel a flow while an unresolved external operation remains pending, so the reconciliation path is not discarded by a terminal cancellation.

Recovery behavior is conservative:

- `READ_ONLY` and `IDEMPOTENT` pending operations may be re-invoked with the same key and input digest.
- `DEDUPLICATED` may be re-invoked with the same key only when the adapter/provider contract actually performs durable deduplication. HabitRoute cannot prove that merely from a boolean declaration.
- `NON_REPEATABLE` and `COMPENSATABLE` pending operations are not automatically reissued. They move to `NEEDS_ATTENTION` and require explicit reconciliation.
- Confirming an operation as applied records an evidence reference and resumes from its checkpoint. Confirming it was not applied clears the pending intent but leaves the flow in `NEEDS_ATTENTION`; it does not automatically retry.

Crash tests cover failure before the intent append, process termination after a provider effect but before acknowledgement, result-checkpoint write failure, provider-side deduplicated retry with a stable key, completed-prefix recovery, the no-auto-retry result of a not-applied reconciliation, cross-harness/environment replay refusal, torn unterminated-tail preservation and newline-terminated corruption refusal.

## Stop conditions

- A side-effecting non-repeatable operation with an unknown outcome must stop for reconciliation.
- A missing/invalid permission or approval must fail closed.
- An unknown operation-effect class must not be retried.
- A pending operation whose identity, effect, input digest, idempotency key, harness ID/version or environment/context differs from the committed intent must stop.
- A DEDUPLICATED effect must not be considered safe unless the real provider enforces the supplied key.
- A changed adapter implementation must use a new immutable harness version or implementation fingerprint before pending work is replayed.
- A not-applied reconciliation must not silently authorize a second call.
- An evidence-gate input with no trials or incomplete cases must not pass vacuously.
- A source/version mismatch invalidates habit eligibility until revalidated.
- A cost claim with missing dimensions must state what is unknown.
- No release claim may promote a plan, mock adapter or simulated test into production evidence.
- No "exactly once" claim may be made from local journaling alone.
