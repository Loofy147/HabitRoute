# HabitRoute Core — implementation status

**Status date:** 2026-11-04  
**Package:** `habitroute` 0.1.0.dev0 (experimental; not a stable production runtime)

## Canonical machine-habit core

### `src/habitroute/machine.py`

- Immutable machine-habit identity/version and harness/environment/context scope.
- Trigger and precondition predicates, parameter bindings and postconditions.
- Operation steps classified as read-only, idempotent, deduplicated, compensatable or non-repeatable.
- Harness profile with operation allowlist, approval-required operations, attempt ceiling and compensation capability declaration.
- Provider-neutral `HarnessAdapter` protocol and typed operation outcomes/results.
- Baseline/candidate performance profiles tied to the same cohort and sample count.
- Efficiency gate using Wilson lower bounds for success and postcondition reliability, plus improvement in a declared latency/call/resource/recovery metric.
- Fail-closed machine-habit authorization.
- `execute_machine_habit`: invokes a sequence through the harness adapter, resolves literal or `$state.key` inputs, reuses a logical-step idempotency key across retries, collects execution records, verifies postconditions, and stops on unknown outcomes.

### `src/habitroute/flows.py`

- Immutable versioned flow definitions and typed operation, habit, branch, wait and terminal nodes.
- Habit nodes pin an exact machine-habit version.
- Deterministic event reducer with contiguous sequence validation and duplicate-event idempotency.
- Persistent run controller for start, step success/failure, unknown outcome, branch resolution, wait release, pause/resume, cancellation and needs-attention escalation.
- Stable per-run/per-flow-version/per-node/per-attempt idempotency keys.
- Local append-only JSONL journal that validates sequence continuity and fsyncs committed events.
- Recovery by replaying the journal into the flow reducer.
- Single-writer-per-run contract.

## Verification

- Core suites are `tests/test_contracts.py` (historical prototype), `tests/test_machine_habits.py` and `tests/test_persistent_flows.py`.
- Legacy simulator tests remain under `experiments/step_savings_v1/`.
- GitHub Actions runs Python 3.11, 3.12 and 3.13, installs the package, runs the legacy regression suite and discovers all core tests. Check the latest run on the repository Actions page for the commit-specific result.

## What is not implemented

- No production adapter invokes external APIs, CLIs, repositories, scripts or agent runtimes. The protocol and test adapters exist, but real providers are not connected.
- No flow worker yet dispatches each persistent-flow node to the harness and commits the returned result automatically. The run controller and machine-habit executor are separate primitives.
- No central habit registry, trace-ingestion pipeline, automatic habit discovery or automated promotion workflow. Baseline and candidate performance profiles are caller-supplied.
- No transactional coordination between external operations and the flow journal.
- Compensatable operations are represented, but `execute_machine_habit` currently fails closed before invoking them because a compensation adapter/API is not yet implemented.
- No external SQL/event store, multi-writer lease, distributed lock or clustered workflow execution. `JsonlFlowJournal` is a local filesystem journal with one writer per run.
- No snapshot compaction; recovery replays the complete event journal.
- No timer scheduler, callback receiver or approval service; a caller invokes wait-release and supplies approvals.
- Exactly-once external side effects are not guaranteed. Adapters need idempotency/deduplication or manual reconciliation for uncertain outcomes.
- No automatic migration of a running flow to a new definition or habit version.
- The earlier `contracts.py` and `execution.py` remain an RL-style route/option prototype and are not the canonical machine-habit model.

## Immediate next build

Build a flow worker that loads a pinned run, resolves its current operation/habit node, authorizes and invokes the machine habit through a harness adapter, independently verifies outputs, and commits the flow event before advancing. Then add crash-after-side-effect-before-acknowledgement fault injection and provider-specific idempotency/reconciliation tests.