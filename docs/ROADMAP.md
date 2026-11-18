# Roadmap

This roadmap separates the existing HabitRoute core from the broader Unified Agent Runtime integration. Main-branch checkboxes reflect merged default-branch state; draft-only implementation is recorded separately. Last portfolio reconciliation: 2026-11-18.

## Portfolio status reconciliation — 2026-11-18

The original 2026-11-06 roadmap snapshot is retained as the baseline. Subsequent draft work must not silently change the default-branch checkboxes.

- **IMPLEMENTED_ON_DRAFT:** PR #12 (`feat/per-operation-checkpoints-v0.1`, head `c505d96fe011f94af8eae90fab84f6ebcf317c81`) implements per-operation intent/result/unknown checkpoints, cursor recovery and fail-closed pending-intent behavior. Its recorded matrix run reports 93/93 on Python 3.11–3.13. It is not merged.
- **IMPLEMENTED_ON_DRAFT:** PR #14 (`integration/m3-readonly-persistent-repo-review-v0.1`, head `b7055142e5d10d656161a667db150fc2fea487e7`) implements a local read-only Git review flow, content-addressed evidence, independent object/inventory verification, and additional journal fault/Windows qualification. It is not merged.
- **OPEN:** Issue #13 remains open because UWS task/goal retrieval, live authorization and evidence registration are not connected. The local host capability snapshot is not cryptographically authenticated.
- **OPEN:** Issue #15's authority-bound provider reconciliation remains required before ambiguous non-repeatable effects can be resumed.
- **OPEN:** PR #10, #12 and #14 are draft/unmerged. Their exact dependency lineage must be reviewed before merge.
- **NOT_STARTED:** CPM v0.5.0 import and the thin Unified Agent Runtime composition remain future work. See [CPM integration plan](CPM_INTEGRATION_PLAN.md) and [portfolio alignment review](PORTFOLIO_ALIGNMENT_UWS.md).

**Interpretation:** keep default-branch checkboxes unchecked until the implementation is merged. A draft PR test pass is evidence for that branch/ref only; it is not main-branch completion, production deployment or multi-host readiness.

## P0 — Preserve and reproduce existing research

- [x] Preserve the synthetic step-savings experiment and reports.
- [x] Preserve legacy usage-utility and step-savings policies.
- [ ] Add complete raw per-seed artifacts and a reproducibility manifest.
- [ ] Verify the experiment from a clean clone.

## P1 — Machine-habit model

- [x] Correct the product definition: machine execution optimization, not human habits or RL skills.
- [x] Separate Machine Habit, Execution Harness and Persistent Flow.
- [x] Define scope, triggers, operation patterns, postconditions, idempotency and baseline comparison.
- [x] Implement the dependency-free MachineHabit model and harness authorization.
- [x] Implement the adapter-driven machine-habit executor.
- [x] Implement aggregate efficiency evaluation using cohort labels and Wilson reliability lower bounds.
- [x] Add tests for scope, trigger, preconditions, approvals, side-effect semantics and efficiency-gate behavior.

**Gate:** no habit may be activated unless its declared correctness and efficiency gates pass. Independent raw paired-trial evidence remains future work.

## P2 — Persistent flow and worker foundation

- [x] Define immutable flow definitions and version-pinned run instances.
- [x] Add append-only JSONL events, deterministic replay and sequence validation.
- [x] Add local single-writer journal with fsync.
- [x] Add pause/resume, wait release, branch, bounded retry, cancellation and needs-attention states.
- [x] Define operation-effect classes and stable idempotency keys.
- [x] Implement a worker that dispatches operation nodes and exact-version habit nodes through a HarnessAdapter.
- [x] Add worker tests for success, retry-key reuse, approval pause/resume, unknown outcomes, postcondition failure and exact-version habit lookup.
- [ ] Commit a durable event/checkpoint after each operation inside a multi-operation habit.
- [ ] Add fault injection after external side effects but before event acknowledgement.

**Gate:** ordinary flow state replays from committed events; per-operation durability for multi-step habits remains an open critical gate.

## P3 — Harness enforcement and recovery

- [x] Define provider-neutral HarnessAdapter protocol and typed operation outcomes.
- [x] Add contract-level allowlist, approval and attempt checks.
- [ ] Add actual provider-backed credential boundaries, egress controls, hard budgets, timeouts, cancellation and output limits.
- [ ] Add independent environment/capability fingerprinting.
- [ ] Add durable idempotency/deduplication or provider reconciliation.
- [ ] Implement and test compensation before enabling compensatable operations.
- [ ] Add deterministic test harness and crash-window fault injection.
- [ ] Add at least one concrete read-only external adapter.

**Gate:** a harness control is only marked enforced after deny-path tests prove the provider boundary rejects prohibited actions.

## P4 — Evidence-backed habit discovery and promotion

- [ ] Ingest operation traces with immutable provenance.
- [ ] Normalize repeated operations and parameter bindings.
- [ ] Discover repeated subflows, redundant calls and reusable patterns.
- [ ] Propose narrow candidates with explicit triggers/preconditions.
- [ ] Store raw paired baseline/candidate trial records and exact input/case digests.
- [ ] Independently verify outputs and side effects.
- [ ] Add shadow evaluation, staged promotion, monitoring, drift detection and quarantine.
- [ ] Make a durable exact-version HabitRegistry.

**Gate:** mutation-tested promotion cannot pass on empty, incomplete, mismatched or unverified evidence.

## P5 — Expand machine-operation economics research

- [ ] Keep the legacy route simulator unchanged as its own baseline.
- [ ] Add machine-operation experiments for calls, latency, resource usage, retries and recovery overhead.
- [ ] Test regime/schema/provider/harness changes and revalidation.
- [ ] Compare retrieval, context assembly and verification overhead against savings.
- [ ] Include paired uncertainty and pre-registered analysis.

## P6 — Unified Agent Runtime integration

- [ ] Import CPM v0.5.0 under `packages/contextpm/`, preserving `contextpm` and `cheg`.
- [ ] Keep CPM and HabitRoute independently installable and free of circular imports.
- [ ] Freeze shared contracts under `shared/contracts/`.
- [ ] Add runtime composition under `runtime/unified_agent_runtime/`.
- [ ] Start with read-only context-to-habit planning and explainable dry-run output.
- [ ] Pin package/source versions and context manifest digests per run.
- [ ] Add component-absence tests proving each package works alone.
- [ ] Benchmark context-only, habit-only and combined factorial conditions.

**Gate:** no side-effecting combined execution until P2/P3 critical durability and recovery tests pass.

## P7 — Release readiness

- [ ] SBOM, dependency/license scan and provenance record.
- [ ] Security review and permission-denial tests for every adapter.
- [ ] Crash/restart, duplicate delivery, reconciliation and rollback evidence.
- [ ] CI matrix and integration tests for supported Python versions.
- [ ] Deployment-specific operational review; do not label the entire project production-ready without scope-specific evidence.

## Immediate next task

Begin with per-operation checkpoints and crash/recovery semantics in HabitRoute. In parallel, import CPM unchanged into the monorepo only after its source manifest and notices are reviewed. Do not build an autonomous side-effecting runtime before the durability gate passes.
