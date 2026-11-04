# HabitRoute Core (experimental)

Canonical code is organized around **Machine Habits**, **Execution Harnesses** and **Persistent Flows**.

## Machine habits

`MachineHabit` represents a reusable, versioned machine-operation optimization. It is scoped to a harness/environment/context, has triggers and preconditions, contains operation steps, declares postconditions and side-effect semantics, and carries baseline/candidate performance evidence.

`authorize_machine_habit` fails closed unless the habit is active, its exact harness/environment scope matches, trigger and preconditions pass, the efficiency gate passes, operations are allowed, approval requirements are met and retry/compensation limits fit the harness.

The efficiency gate requires a comparable input cohort and sample count, protects success/postcondition reliability using Wilson lower bounds, and requires an improvement in a predeclared cost metric.

## Harnesses

`HarnessProfile` defines the policy/capability boundary. `HarnessAdapter` is the provider-neutral interface for invoking actual operations and returning typed outcomes. No production adapter is included yet.

## Persistent flows

`FlowDefinition` is immutable and versioned. `FlowRun` is separate mutable state. Habit nodes pin an exact habit version. `PersistentFlow` appends events to a `FlowJournal`; `JsonlFlowJournal` provides a local append-only implementation with fsync and single-writer-per-run semantics.

Recovery uses `PersistentFlow.restore(...)` to replay the event history. The instance method `resume()` changes a paused flow back to its saved running/waiting state.

Example lifecycle:

~~~python
from habitroute.flows import PersistentFlow, JsonlFlowJournal

journal = JsonlFlowJournal("./flow-data")
run = PersistentFlow.start(definition, "run-0001", journal, {"repo": "project-a"})

# A worker executes the current node using run.idempotency_key.
# It then records the actual result:
run.succeed_step({"checks.pass": "true"})

# After process restart:
run = PersistentFlow.restore(definition, "run-0001", journal)
~~~

## Important limits

The flow engine does not execute the external operation. Your worker/harness adapter does that. Persisting flow state does not make external effects exactly-once. Classify operations and supply idempotency, deduplication, compensation or manual reconciliation for uncertain outcomes.

JSONL is a local single-writer journal, not a distributed database. Use an appropriate transactional store/lease adapter before multi-worker production use.

## Legacy prototype

`contracts.py` and `execution.py` retain the earlier RL-style route/option experiment scaffolding. They are not the canonical machine-habit API.

## Install and test

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
~~~