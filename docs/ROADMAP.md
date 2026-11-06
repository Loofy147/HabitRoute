# Roadmap

This roadmap separates the existing HabitRoute core from the broader Unified Agent Runtime integration. Checkboxes reflect the inspected 2026-11-06 snapshot; future completion requires evidence.

## Precondition for discovery — hand-design before mining

**Design status: COMPLETE ON DRAFT PR #4. Runtime enforcement: NOT IMPLEMENTED.**

- [x] Hand-design `repo-change-verification/v1` before mining any execution traces.
- [x] Define one-sentence intent, invariants, decision points, evidence requirements and constraints.
- [x] Define complete inspection, per-path validation and safe-skip fingerprint rules.
- [x] Separate immutable decision-time records from later decision outcomes.
- [x] Define typed trace, decision, decision-outcome and flow-verdict schemas.
- [x] Define `VERIFIED_AT_END` versus later same-digest `SUCCESS_HELD`.
- [x] Add schema, graph and negative held-success contract tests; CI passed 97 tests on Python 3.11, 3.12 and 3.13 in run [42231017168](https://github.com/Loofy147/HabitRoute/actions/runs/42231017168).
- [ ] Implement the schemas in the runtime, durable trace/decision stores and semantic validators.
- [ ] Enforce budgets, evidence completeness, intervention observability and later revalidation.
- [ ] Execute this habit across independent read-only repository tasks and retain verifiable records.

**Gate:** no mining until runtime-produced traces and separate decision/outcome records are complete, independently verified, budgeted, and revalidated. PR #4 contains design and schema tests only; it does not activate the habit.

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

Complete review of the architecture preparation PR and the dependent hand-design PR. Then implement the trace and separate decision/outcome persistence contracts with semantic validation and replay tests. In the same runtime phase, close the per-operation checkpoint and crash/reconciliation gaps before enabling side-effecting multi-step habits. Import CPM unchanged only after its source manifest and notices are reviewed. Do not mine historical conversation/log material or build an autonomous side-effecting runtime before these gates pass.
