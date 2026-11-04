# Roadmap

## P0 — Preserve existing evidence

- [x] Preserve the synthetic step-savings experiment and reports.
- [x] Preserve legacy utility and savings policies.
- [ ] Add the complete raw per-seed artifact and reproducibility manifest.
- [ ] Verify the experiment from a clean clone.

## P1 — Establish the machine-habit model

- [x] Correct the product definition: machine execution optimization, not human habits or RL skills.
- [x] Separate Machine Habit, Execution Harness and Persistent Flow.
- [x] Define scope, triggers, operation patterns, postconditions, idempotency, baseline comparison and promotion gates.
- [x] Implement a dependency-free MachineHabit model and harness authorization.
- [x] Implement an efficiency evaluator using matched baseline/candidate cohorts and reliability lower bounds.
- [x] Add tests for wrong harness/scope, failed trigger/preconditions, approval, side-effect semantics, inadequate evidence and no efficiency gain.

**Gate:** no habit can become active without passing the declared correctness and efficiency gates in its harness scope.

## P2 — Persistent flow foundation

- [x] Define immutable flow definitions and version-pinned run instances; habit nodes pin an exact habit version.
- [x] Add append-only JSONL events and deterministic replay; snapshot compaction remains open.
- [x] Add sequence-checked local single-writer journal interface with fsync.
- [x] Add pause/resume, wait release, branch, bounded retry, cancellation and needs-attention states.
- [x] Define per-operation idempotency/deduplication/compensation/non-repeatable semantics and stable attempt keys.
- [x] Test event replay rebuilds identical control state; external side-effect deduplication remains the adapter's responsibility.

**Gate:** kill/restart fault-injection tests recover from the last committed journal event; external side-effect deduplication is not yet implemented.

## P3 — Harness architecture

- [x] Define a provider-neutral HarnessAdapter protocol and typed operation outcomes.
- [ ] Add environment/capability fingerprinting, allowlists, approval gates and budgets.
- [ ] Add input/output validation, independent postcondition checks and structured tracing.
- [ ] Add operation adapters for scripts, APIs, repositories, files and agent runtimes.
- [ ] Add deterministic test harness, fault injection and paired baseline/candidate runs.

**Gate:** the same habit/flow contract works with at least two distinct harness adapters without core changes.

## P4 — Discover and improve machine habits

- [ ] Ingest operation traces with provenance.
- [ ] Normalize repeated operations and parameter bindings.
- [ ] Discover duplicated calls, repeated computations and reusable subflows.
- [ ] Propose narrow candidate patterns with explicit trigger/preconditions.
- [ ] Run matched baseline/candidate comparison on correctness and cost.
- [ ] Add staged promotion, monitoring, quarantine and fallback.

**Gate:** show reproducible savings without violating output contracts or increasing unreported total cost.

## P5 — Revisit the synthetic route experiments

- [ ] Map route-memory concepts to machine operation traces only where applicable.
- [ ] Retest step-savings, dominated pruning and audit under machine operation cost vectors.
- [ ] Test repeated changes to APIs, tool schemas, harness versions and credentials/capabilities.
- [ ] Compare lookup/harness overhead against the savings from habit reuse.

## P6 — Integrate or release

- [ ] Evaluate owned persistence versus adapters to established durable workflow engines.
- [ ] Add type checking, linting, CI, docs and two example harness adapters.
- [ ] Choose a license before inviting reuse.
- [ ] Publish only after crash/restart, duplicate-delivery and end-to-end verification gates pass.

## Immediate next task

Implement the machine-habit record and harness authorization/efficiency gate first. Then implement the event-sourced persistent flow core. Do not extend the RL-style option prototype as the canonical habit model.