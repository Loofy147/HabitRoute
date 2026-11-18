# HabitRoute Core — Implementation Status

**Status date:** 2026-11-06  
**Observed source baseline:** `43d714c8760a15026e0acb966919f483d893e7d0`  
**Package:** `habitroute` 0.1.0.dev0 (experimental; not a stable production runtime)

## Portfolio evidence overlay — 2026-11-18

This overlay updates cross-repository draft evidence without changing the historical default-branch source baseline above. It does not mean draft work is merged.

| Work | Current evidence | Status | Remaining boundary |
|---|---|---|---|
| Per-operation checkpoints | [PR #12](https://github.com/Loofy147/HabitRoute/pull/12), head `c505d96fe011f94af8eae90fab84f6ebcf317c81`; recorded run 42703942809, 93/93 each on Python 3.11–3.13 | IMPLEMENTED_ON_DRAFT; CI_VERIFIED | Unmerged; local JSONL; provider-side unknown-outcome reconciliation not implemented |
| Capability repertoire | [PR #10](https://github.com/Loofy147/HabitRoute/pull/10), head `dd9d88e45b2bfd2dfeaa0130439838181ccc8c15` | IMPLEMENTED_ON_DRAFT | Unmerged; planner output is not permission |
| M3 read-only repository review | [PR #14](https://github.com/Loofy147/HabitRoute/pull/14), head `b7055142e5d10d656161a667db150fc2fea487e7`; recorded run 43221871510 passed Python 3.11–3.13 and Windows journal qualification | IMPLEMENTED_ON_DRAFT; CI_VERIFIED | Unmerged; local-only; no live UWS retrieval/authorization/evidence registration; no semantic correctness or project-test claim |
| UWS integration | [Issue #13](https://github.com/Loofy147/HabitRoute/issues/13) | OPEN | UWS references are opaque; host capability snapshot is not cryptographically authenticated |
| Unknown-outcome reconciliation | [Issue #15](https://github.com/Loofy147/HabitRoute/issues/15) | OPEN | No provider-specific authority-bound receipt validation |
| CPM integration | [CPM integration plan](CPM_INTEGRATION_PLAN.md) | NOT_STARTED | Source provenance, complete notices, isolation and independent-installability gates remain |

### Current assessment

- The strongest verified HabitRoute result is a **local read-only repository-review slice on PR #14**, not an end-to-end UWS-connected product.
- PR #14 independently validates Git-object/inventory integrity and records incomplete content separately. It does not perform semantic code review, run project tests, or authenticate host authority.
- The PR #12 per-operation checkpoint implementation narrows the local crash-replay gap for machine-habit operations. It does not solve provider reconciliation, exactly-once effects or multi-host coordination.
- PR #10, #12 and #14 remain open draft PRs. The default branch remains experimental and must not be described as having these changes until merge and fresh default-branch verification.
- The review/merge dependency is #10 capability repertoire → #12 operation durability (review as a separate dependency) → #14 M3 integration, while UWS PR #23 HGSB read/authorization gates must be met before issue #13 can become a live cross-system flow.

The latest repository alignment and acceptance checklist is maintained in [Portfolio Alignment — UWS and HabitRoute](PORTFOLIO_ALIGNMENT_UWS.md). The cross-project review framework is in the [UWS portfolio roadmap and review checklist](https://github.com/Loofy147/unified-knowledge-work-system/blob/feat/human-machine-twin-foundation-v0.1/docs/PORTFOLIO_ROADMAP_AND_REVIEW_CHECKLIST_v0.1.md).

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
