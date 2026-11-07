# Roadmap

This roadmap separates the existing HabitRoute core from the broader Unified Agent Runtime integration. Checkboxes distinguish completed research/probes from runtime implementation; future completion requires evidence.

## Precondition for discovery — hand-design before mining

**Design status: COMPLETE ON DRAFT PR #4. Runtime enforcement: NOT IMPLEMENTED.**

- [x] Hand-design repo-change-verification/v1 before mining any execution traces.
- [x] Define one-sentence intent, invariants, decision points, evidence requirements and constraints.
- [x] Define complete inspection, per-path validation and safe-skip fingerprint rules.
- [x] Separate immutable decision-time records from later decision outcomes.
- [x] Define typed trace, decision, decision-outcome and flow-verdict schemas.
- [x] Define VERIFIED_AT_END versus later same-digest SUCCESS_HELD.
- [x] Add schema, graph and negative held-success contract tests; CI passed 97 tests on Python 3.11, 3.12 and 3.13 in run [42231017168](https://github.com/Loofy147/HabitRoute/actions/runs/42231017168).
- [x] Specify proposal provenance, matched transfer evaluation, opportunity/action/loading separation and no-auto-activation rules in [RETROSPECTIVE_ADAPTATION_PROTOCOL.md](RETROSPECTIVE_ADAPTATION_PROTOCOL.md).
- [x] Add draft proposal, trial and evaluation schemas plus schema-level negative tests.
- [ ] Implement the schemas in the runtime, durable trace/decision stores and semantic validators.
- [ ] Enforce budgets, evidence completeness, intervention observability and later revalidation.
- [ ] Execute this habit across independent read-only repository tasks and retain verifiable records.

**Gate:** no mining until runtime-produced traces and separate decision/outcome records are complete, independently verified, budgeted and revalidated. The adaptation protocol and its schemas are design artifacts only; they do not activate the habit or authorize mining.

## Research synthesis and probes

- [x] Document cross-disciplinary findings, evidence status, limits and the staged experimental program in [RESEARCH_SYNTHESIS_AND_EXPERIMENT_PROGRAM.md](RESEARCH_SYNTHESIS_AND_EXPERIMENT_PROGRAM.md).
- [x] Add a dependency-free paired-trial analysis probe under `experiments/adaptation_eval_v1/`.
- [x] Test paired recurrence cells, opportunity/action missingness, intention-to-treat loading, digest consistency, cost dimensions and hard-constraint reporting.
- [x] Add deterministic crash-window characterization tests against the actual flow worker.
- [x] Include the new test suite in the Python CI matrix.
- [ ] Obtain passing CI for the extension branch and review findings.
- [ ] Replace characterization expectations with safe-recovery tests after implementing durable operation checkpoints and provider reconciliation.

**Interpretation:** the crash tests deliberately reproduce duplicate external effects after abrupt termination; they do not close HR-01/HR-02. The paired evaluator validates analysis mechanics only; it does not provide production trial evidence or a promotion decision.

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
- [x] Add fault injection after external side effects but before event acknowledgement to reproduce the current duplicate-effect window.
- [ ] Add intent/result/checkpoint persistence before and after every provider operation; replace the characterization tests with recovery guarantees under explicit provider idempotency/reconciliation contracts.

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

## P4 — Evidence-backed retrospective adaptation and habit promotion

- [ ] Ingest structured traces with immutable provenance; accept only eligible held-success runs as experience-driven evidence.
- [ ] Classify every proposal as experience-driven, prior-driven, weak or mixed; retain exact event/prior references and a causal link.
- [ ] Normalize repeated target actions and parameter bindings; define the environmental opportunity separately from action recurrence.
- [ ] Propose narrow, non-executable candidates with explicit target scope, mechanism, hypothesis, side effects and rollback.
- [ ] Keep each candidate to one logical change unit so transfer effects remain attributable.
- [ ] Preregister matched baseline/adapted task pairs, sample-size rationale, non-inferiority margin, uncertainty method and multiple-comparison handling.
- [ ] Store raw paired trials with identical case/input/task/environment/agent/model/base-harness fingerprints.
- [ ] Record target opportunity, target action observation, adaptation loading and task outcome as separate fields.
- [ ] Use intention-to-treat recurrence comparisons; report adaptation loading as a diagnostic rather than filtering unexposed treatment sessions.
- [ ] Independently verify outputs and side effects; retain unknowns, failed trials, intervention evidence and exclusions.
- [ ] Measure unrelated work and separate cost dimensions including tokens, context, calls, latency, compute, money, retries, recovery and verification overhead.
- [x] Add a research-only deterministic paired-trial summarizer for synthetic cases; reject duplicate, incomplete, mismatched and unobservable data while preserving treatment assignment.
- [ ] Build a durable, provenance-checked trial ledger and independent evaluator with sample-size/power rationale, quality non-inferiority intervals and pre-registered multiple-comparison controls.
- [ ] Permit only NET_BENEFIT to reach human review; never auto-activate a retrospective proposal.
- [ ] Add shadow evaluation, staged human approval, monitoring, drift detection, quarantine, rollback and a durable exact-version HabitRegistry.

**Gate:** target-action recurrence reduction alone is insufficient. Promotion requires quality non-inferiority, hard constraints, evidence integrity, cost/side-effect checks, human approval and a rollback path. Inconclusive or harmful candidates remain recorded and cannot be silently discarded.

## P5 — Expand machine-operation economics research

- [ ] Keep the legacy route simulator unchanged as its own baseline.
- [ ] Add machine-operation experiments for calls, latency, resource usage, retries and recovery overhead.
- [ ] Test regime/schema/provider/harness changes and revalidation.
- [ ] Compare retrieval, context assembly and verification overhead against savings.
- [ ] Include paired uncertainty and pre-registered analysis.

## P6 — Unified Agent Runtime integration

- [ ] Import CPM v0.5.0 under packages/contextpm/, preserving contextpm and cheg.
- [ ] Keep CPM and HabitRoute independently installable and free of circular imports.
- [ ] Freeze shared contracts under shared/contracts/.
- [ ] Add runtime composition under runtime/unified_agent_runtime/.
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

Continue in dependency order: review and settle the architecture preparation and hand-design PRs; implement runtime trace plus separate decision/outcome persistence and semantic validation; close per-operation checkpoint and crash/reconciliation gaps; enforce and independently revalidate the read-only reference habit. Only then run retrospective collection and matched transfer trials. Import CPM unchanged only after its source manifest and notices are reviewed. Do not mine historical conversation/log material or build an autonomous side-effecting runtime before these gates pass.
