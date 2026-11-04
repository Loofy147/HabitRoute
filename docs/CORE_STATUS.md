# HabitRoute Core — implementation status

**Status date:** 2026-11-04  
**Package:** `habitroute` 0.1.0.dev0 (experimental; not a stable production runtime)

## Canonical machine-habit core

### `src/habitroute/machine.py`

- Immutable machine-habit identity and version.
- Harness/environment/context scope and trigger/precondition predicates.
- Operation steps with read-only, idempotent, deduplicated, compensatable and non-repeatable effect classes.
- Explicit idempotency-key and compensation requirements.
- Harness profile with operation allowlist, approval-required operations, maximum attempts and compensation capability.
- Provider-neutral `HarnessAdapter` protocol and typed operation result.
- Baseline/candidate performance profiles tied to the same cohort and sample count.
- Efficiency gate using Wilson lower bounds for success and postcondition reliability, plus a declared latency/call/resource/recovery cost improvement threshold.
- Fail-closed habit authorization for lifecycle, harness/version, environment/context, trigger, preconditions, efficiency evidence, operation allowlist, approval and retry limits.

### `src/habitroute/flows.py`

- Immutable, versioned flow definitions and typed operation, habit, branch, wait and terminal nodes.
- Habit nodes pin an exact machine-habit version.
- Event reducer with contiguous sequence validation and duplicate-event idempotency.
- `PersistentFlow` run controller for start, step success/failure, unknown outcome, branch resolution, wait release, pause/resume, cancellation and needs-attention escalation.
- Stable per-run/per-flow-version/per-node/per-attempt idempotency keys.
- Local append-only JSONL journal that validates sequence continuity and fsyncs committed events.
- Recovery by replaying the journal into the deterministic flow reducer.
- Single-writer-per-run contract.

## Verification

- Canonical machine-habit and persistent-flow tests are in `tests/test_machine_habits.py` and `tests/test_persistent_flows.py`.
- The earlier option/route contract tests remain in `tests/test_contracts.py` as historical prototype regression coverage.
- Legacy simulator tests remain under `experiments/step_savings_v1/`.
- GitHub Actions runs Python 3.11, 3.12 and 3.13, installs the package, runs the legacy regression suite and discovers all core tests. See the latest repository Actions run for the commit-specific result.

## What is not implemented

- No production adapter currently invokes external APIs, CLIs, repositories, scripts or agent runtimes; `HarnessAdapter` is an interface only.
- No central habit registry, trace-ingestion pipeline, automatic habit discovery or automated promotion workflow. Baseline and candidate performance profiles are supplied by the caller.
- No end-to-end habit runner that executes all `OperationStep` records and independently verifies postconditions. The current core defines the contract and authorization boundary.
- No external SQL/event-store adapter, multi-writer lease, distributed lock or clustered workflow execution. `JsonlFlowJournal` is a local filesystem journal with one writer per run.
- No snapshot compaction; recovery replays the complete event journal.
- No timer scheduler, callback receiver or approval service; a caller invokes wait-release/branch decisions.
- No transaction spanning the flow journal and an external operation. Exactly-once external effects are not guaranteed. Adapters need idempotency/deduplication/compensation or manual reconciliation.
- No automatic migration of a running flow to a new definition or habit version.
- The earlier `contracts.py` and `execution.py` remain an RL-style route/option prototype and are not the canonical machine-habit model.

## Immediate next build

Implement a concrete harness adapter and a small end-to-end worker that (1) loads a pinned flow run, (2) resolves a machine habit, (3) authorizes it under the current harness profile, (4) invokes one operation with the flow's idempotency key, (5) validates outputs/postconditions, and (6) commits the flow event before advancing. Add a crash-after-side-effect-before-acknowledgement test.