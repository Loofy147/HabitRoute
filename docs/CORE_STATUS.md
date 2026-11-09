# HabitRoute Core — Implementation Status

**Status date:** 2026-11-06  
**Observed source baseline:** `43d714c8760a15026e0acb966919f483d893e7d0`  
**Package:** `habitroute` 0.1.0.dev0 (experimental; not a stable production runtime)

## Canonical machine-habit core

### `src/habitroute/machine.py`

- Immutable machine-habit identity/version and harness/environment/context scope.
- Trigger and precondition predicates, input bindings and postconditions.
- Operation steps classified as read-only, idempotent, deduplicated, compensatable or non-repeatable.
- Harness profile with operation allowlist, approval-required operations, attempt ceiling and compensation capability declaration.
- Provider-neutral `HarnessAdapter` protocol and typed operation outcomes/results.
- Baseline/candidate aggregate performance profiles tied to a cohort label and sample count.
- Efficiency gate using Wilson lower bounds for success and postcondition reliability, plus improvement in a declared latency/call/resource/recovery metric.
- Fail-closed machine-habit authorization.
- Adapter-driven machine-habit executor with input binding, stable logical-step idempotency key across retries, execution records, postcondition checks and unknown-outcome handoff.
- Compensatable steps remain unavailable until a real compensation adapter/API exists.

### `src/habitroute/flows.py`

- Immutable versioned flow definitions and typed operation, habit, branch, wait and terminal nodes.
- Habit nodes pin an exact machine-habit version.
- Deterministic event reducer with contiguous sequence validation and duplicate-event idempotency.
- Persistent run controller for start, step success/failure, unknown outcome, branch resolution, wait release, pause/resume, cancellation and needs-attention escalation.
- Stable per-run/per-flow-version/per-node/per-attempt idempotency keys.
- Local append-only JSONL journal with sequence validation and fsync.
- Recovery by replaying the journal into the flow reducer.
- Single-writer-per-run contract.

### `src/habitroute/worker.py`

- `FlowWorker.dispatch()` dispatches one current flow node per call.
- Handles ordinary operation nodes and exact-version machine-habit nodes.
- Checks operation allowlist, approval and attempt ceiling before ordinary operation invocation.
- Records operation outcome/cost metadata and checks postconditions for ordinary operation nodes.
- Uses `HabitRegistry` for exact-version lookup; the registry is in memory, not durable.
- Routes ambiguous adapter outcomes to `NEEDS_ATTENTION`.
- Tests use a `StubHarness`; no production provider adapter was found.

## Important execution boundary

The worker exists; older status text and issue bodies that say it is missing are stale. However, the ordinary operation-node path and multi-operation habit path have different checkpoint granularity.

For a multi-operation habit, the worker calls the sequence executor and commits the flow event after that sequence returns. It does not currently commit an independent flow event/checkpoint after each individual operation. A crash after one external side effect but before the sequence result is committed can therefore leave partial effects without per-operation flow progress. This is the highest-priority durability gap.

## Verification

- GitHub Actions workflow: `.github/workflows/tests.yml`.
- Latest observed run: [41841168040](https://github.com/Loofy147/HabitRoute/actions/runs/41841168040).
- Commit: `43d714c8760a15026e0acb966919f483d893e7d0`.
- Conclusion: success on Python 3.11, 3.12 and 3.13.
- Exact latest test count was not captured.
- Historical 77/77 count applies to commit `090fc7c3fddbc95c7b128045fa7a20ab3dd63400`, not the latest commit.
- Legacy simulator tests remain under `experiments/step_savings_v1/`.

## Not implemented or not proven

- No production adapter invokes external APIs, CLIs, repositories, scripts or agent runtimes.
- No production-grade provider enforcement for credentials, egress, hard resource/time budgets, cancellation or output limits.
- No per-operation durable checkpoints inside a multi-operation habit invocation.
- No transactional coordination between external operations and the local flow journal.
- No guarantee of exactly-once external side effects.
- No durable habit registry; current registry is in-memory exact-version lookup.
- No trace-ingestion pipeline, automatic candidate discovery, paired-trial evidence system or automated promotion/quarantine.
- Efficiency profiles are caller-supplied aggregates; cohort label equality does not prove matching raw case identities or independent verification.
- Cost propagation is incomplete across multi-operation habit records and flow metadata; token, context, compute and memory measurements are not comprehensive.
- No external SQL/event store, distributed lock/lease or multi-worker-per-run support.
- No snapshot compaction; replay reads the full local event journal.
- No timer scheduler, callback receiver or approval service.
- No automatic migration of a running flow to a new definition or habit version.
- The earlier `contracts.py` and `execution.py` remain an RL-style route/option prototype and are not canonical.

## Immediate engineering priorities

1. Add operation-level intent/result/checkpoint records for multi-operation habits.
2. Define idempotency/reconciliation semantics and inject crashes around provider side effects.
3. Replace caller-supplied aggregates as the sole efficiency evidence with raw paired trial records and independent verification.
4. Propagate a typed cost vector from operation through habit and flow.
5. Add a concrete read-only harness adapter and prove actual policy enforcement.
6. Add durable exact-version habit storage and staged discovery/promotion only after evidence controls are in place.


## Update — per-operation checkpoint patch (2026-11-09)

**Review branch:** `feat/per-operation-checkpoints-v0.1`  
**Draft PR:** https://github.com/Loofy147/HabitRoute/pull/12  
**Issue:** https://github.com/Loofy147/HabitRoute/issues/11  
**Verified commit:** `aa15c8136b29a99ca666dc77f783322bda7f69b2`  
**GitHub Actions:** https://github.com/Loofy147/HabitRoute/actions/runs/42703296651

The draft patch adds four operation-level flow events (intent, succeeded, failed, unknown), a persisted operation cursor and attempt counts, and worker callbacks that append the result before invoking the next operation. The worker resumes from the next committed operation after restart. If an intent exists without a result, the worker preserves the pending operation and moves the flow to `NEEDS_ATTENTION`; it does not invoke that operation again.

Verification on the PR head:
- Python 3.11: 92/92 tests passed.
- Python 3.12: 92/92 tests passed.
- Python 3.13: 92/92 tests passed.
- The new regression cases cover per-operation intent/result ordering, crash after operation effect before result acknowledgement, safe retry with a stable idempotency key, and resume after an operation checkpoint.

**Scope and remaining limits:** this is still a draft branch, not merged into `main`. The journal is local JSONL with a single-writer-per-run contract. A pending/unknown external outcome is preserved and escalated; provider-specific query/reconciliation, distributed workers, production adapters, exactly-once external effects and broad autonomy are not implemented or claimed. A human/operator must resolve ambiguous external outcomes before continuation.

## Updated immediate engineering priorities

1. Review and merge PR #12 only after reviewing the operation event contract and recovery behavior.
2. Add provider-specific reconciliation adapters and tests for each real external effect class; keep unknown outcomes fail-closed until that exists.
3. Replace caller-supplied aggregates as the sole efficiency evidence with raw paired trial records and independent verification.
4. Propagate a typed cost vector from operation through habit and flow.
5. Add a concrete read-only provider adapter and prove policy enforcement at the provider boundary.
6. Add durable exact-version habit storage and staged discovery/promotion only after evidence controls are in place.
