# HabitRoute Core (experimental)

Canonical code is organized around **Machine Habits**, **Execution Harnesses** and **Persistent Flows**.

## Machine habits

`MachineHabit` is a reusable, versioned machine-operation optimization. It is scoped to a harness/environment/context, has triggers and preconditions, contains operation steps, declares postconditions and side-effect semantics, and carries baseline/candidate performance evidence.

`authorize_machine_habit` fails closed unless the exact harness/environment scope matches, trigger and preconditions pass, the efficiency gate passes, operations are allowed, approvals are supplied and retry limits fit the harness.

`execute_machine_habit` invokes the operation pattern using a `HarnessAdapter`. Input bindings can be literal values or `$state.key` references. The executor records operations, uses a stable idempotency key across retries of the same step, and checks postconditions before reporting success.

Compensatable operations currently fail closed: a compensation adapter is not implemented. Unknown side-effect outcomes return `NEEDS_ATTENTION`.

The historical 77/77 result applies to an earlier core baseline. Draft PR #12 currently passes 92/92 tests on Python 3.11–3.13; see the PR and its linked GitHub Actions run for the exact reviewed commit.

## Harnesses

`HarnessProfile` defines the policy/capability boundary. `HarnessAdapter` is the provider-neutral interface for invoking actual operations and returning typed outcomes. No production provider adapter is included yet.

## Persistent flows

`FlowDefinition` is immutable and versioned. A flow run is separate mutable state. Habit nodes pin an exact habit version. `PersistentFlow` appends events to a `FlowJournal`; `JsonlFlowJournal` provides a local append-only implementation with fsync and single-writer-per-run semantics.

Recovery uses `PersistentFlow.restore(...)` to replay the event history. The instance method `resume()` changes a paused flow back to its saved running/waiting state.

~~~python
from habitroute.flows import PersistentFlow, JsonlFlowJournal

journal = JsonlFlowJournal("./flow-data")
run = PersistentFlow.start(definition, "run-0001", journal, {"repo": "project-a"})

# A flow worker resolves and invokes the current node via a HarnessAdapter.
# It then records the actual result:
run.succeed_step({"checks.pass": "true"})

# After process restart:
run = PersistentFlow.restore(definition, "run-0001", journal)
~~~

## Important limits

`PersistentFlow` remains the event journal and state reducer; `FlowWorker` dispatches its current node through the configured harness. In draft PR #12, habit-node execution commits an intent and a typed result/checkpoint for each operation before dispatching the next operation. A restored run resumes from the next committed operation. If an operation intent exists without a result, the worker fails closed into `NEEDS_ATTENTION` rather than replaying the possibly completed effect. Provider-specific reconciliation is still required to resolve such cases. Persisting flow state does not make external effects exactly-once. Classify operations and supply idempotency, deduplication, compensation or manual reconciliation for uncertain outcomes.

JSONL is a local single-writer journal, not a distributed database. Use an appropriate transactional store/lease adapter before multi-worker production use.

## Legacy prototype

`contracts.py` and `execution.py` retain the earlier RL-style route/option experiment scaffolding. They are not the canonical machine-habit API.

## Install and test

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
~~~