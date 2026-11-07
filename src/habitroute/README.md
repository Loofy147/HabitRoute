# HabitRoute Core (experimental)

Canonical code is organized around **Machine Habits**, **Execution Harnesses** and **Persistent Flows**.

## Machine habits

`MachineHabit` is a reusable, versioned machine-operation optimization. It is scoped to a harness/environment/context, has triggers and preconditions, contains operation steps, declares postconditions and side-effect semantics, and carries baseline/candidate performance evidence.

`authorize_machine_habit` fails closed unless the exact harness/environment scope matches, trigger and preconditions pass, the efficiency gate passes, operations are allowed, approvals are supplied and retry limits fit the harness.

`execute_machine_habit` invokes the operation pattern using a `HarnessAdapter`. Input bindings can be literal values or `$state.key` references. This is an in-process convenience executor only; it does not persist operation intents/results or recover after process termination. Persistent flow execution must use `FlowWorker`, which records an `OPERATION_INTENT` before invoking the adapter and a result checkpoint after each operation. The operation key is stable across retries/recovery of one node visit and changes on a later loop visit. The committed intent/checkpoint also records harness ID/version and environment/context; recovery refuses pending replay if those declared scope values change.

Compensatable operations currently fail closed: a compensation adapter is not implemented. Unknown side-effect outcomes return `NEEDS_ATTENTION`.

PR #8's latest full CI run [42318850901](https://github.com/Loofy147/HabitRoute/actions/runs/42318850901) passed 124 core/contract tests on each of Python 3.11, 3.12 and 3.13; the same matrix also passed 10 legacy experiment and 13 paired-evaluation tests per version (147 total per version).

## Harnesses

`HarnessProfile` defines the policy/capability boundary. `HarnessAdapter` is the provider-neutral interface for invoking actual operations and returning typed outcomes. No production provider adapter is included yet.

## Persistent flows

`FlowDefinition` is immutable and versioned. A flow run is separate mutable state. Habit nodes pin an exact habit version. `PersistentFlow` appends events to a `FlowJournal`; `JsonlFlowJournal` provides a local append-only implementation with fsync and single-writer-per-run semantics.

Recovery uses `PersistentFlow.restore(...)` to replay the event history, including pending operation intents and completed operation checkpoints. The instance method `resume()` changes a paused flow back to its saved running/waiting state.

The worker checkpoints each operation inside a multi-operation habit. After restart, it skips the committed prefix. A pending READ_ONLY/IDEMPOTENT operation can be replayed; a DEDUPLICATED operation can be replayed only when the real provider durably enforces the supplied key. Pending NON_REPEATABLE/COMPENSATABLE operations stop for reconciliation. A pending operation is not replayed under a changed harness version or environment/context. Pending intents are pinned to harness and environment/context identity, and a changed profile stops recovery. The harness version is a declared identifier, not an independently measured build/configuration digest; adapter owners must increment it when the implementation or behavior changes. The journal truncates only an unterminated trailing record; newline-terminated corruption is rejected.

~~~python
from habitroute.flows import PersistentFlow, JsonlFlowJournal

journal = JsonlFlowJournal("./flow-data")
run = PersistentFlow.start(definition, "run-0001", journal, {"repo": "project-a"})

# A worker commits intent before calling the adapter and checkpoints each result.
from habitroute.worker import FlowWorker

worker = FlowWorker(harness_adapter, habit_registry)
result = worker.dispatch(run)

# After process restart, replay restores pending/completed operation state.
run = PersistentFlow.restore(definition, "run-0001", JsonlFlowJournal("./flow-data"))
result = worker.dispatch(run)
~~~

## Important limits

The flow engine now dispatches operations through `FlowWorker` with per-operation journal checkpoints. Persisting flow state still does not make external effects exactly-once. The local JSONL journal cannot commit atomically with a remote provider. A DEDUPLICATED operation is replay-safe only when a real provider durably enforces the supplied key. A pending non-repeatable outcome requires evidence-backed reconciliation.

The current reconciliation method is a core-library primitive, not an authenticated service. A production control plane must authenticate and authorize the operator and validate the evidence reference before calling it.

JSONL is a local single-writer journal, not a distributed database. The loader truncates an unterminated final append tail to the last newline-delimited record, but retains newline-terminated corruption as a hard error. This is not a guarantee against arbitrary media corruption or power loss on every filesystem. Use an appropriate transactional store/lease adapter before multi-worker production use. Target-filesystem power-loss testing and an independently measured adapter implementation fingerprint remain open.

## Legacy prototype

`contracts.py` and `execution.py` retain the earlier RL-style route/option experiment scaffolding. They are not the canonical machine-habit API.

## Install and test

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
~~~