# HabitRoute Core (experimental)

Canonical code is organized around **Machine Habits**, **Execution Harnesses** and **Persistent Flows**.

## Machine habits

`MachineHabit` is a reusable, versioned machine-operation optimization. It is scoped to a harness/environment/context, has triggers and preconditions, contains operation steps, declares postconditions and side-effect semantics, and carries baseline/candidate performance evidence.

`authorize_machine_habit` fails closed unless the exact harness/environment scope matches, trigger and preconditions pass, the efficiency gate passes, operations are allowed, approvals are supplied and retry limits fit the harness.

`execute_machine_habit` invokes the operation pattern using a `HarnessAdapter`. Input bindings can be literal values or `$state.key` references. The executor records operations, uses a stable idempotency key across retries of the same step, and checks postconditions before reporting success.

Compensatable operations currently fail closed: a compensation adapter is not implemented. Unknown side-effect outcomes return `NEEDS_ATTENTION`.

The 77/77 result is historical (commit `090fc7c3fddbc95c7b128045fa7a20ab3dd63400`). Current verification is recorded in `docs/CORE_STATUS.md` and the linked GitHub Actions run.

## Repertoire and composition planning

`CapabilityEntry` describes a versioned repertoire item (skill, tool, script, API, model, framework, service, dataset, context asset or sub-habit), its produced facts/outcomes, input requirements, situation predicates, permission requirements, compatible host versions, side-effect class, lifecycle/evidence reference and estimated cost.

`SituationFrame` records time-bound observations and context facts. `HostCapabilitySnapshot` supplies exact available capability references (`capability_id@version`), effective permissions and allowed effects. The host remains authoritative; these structures do not grant permissions.

`compose_habit` filters the repertoire and performs bounded, deterministic capability-chain planning. Outputs from one selected capability may satisfy the inputs of a later capability. It minimizes one explicitly declared cost dimension and reports other cost dimensions separately. The result is always a dry-run `CompositionPlan`; it never invokes tools or external providers.

A READY plan means a complete eligible composition exists, not that the task has executed or succeeded. Evidence digests must be independently validated before activation; the planner only checks that an ACTIVE entry has an evidence reference. See `docs/REPERTOIRE_COMPOSITION_V0.3.md`.

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

The flow engine does not automatically dispatch operations to the harness or commit results from `execute_machine_habit`. A worker must connect those components. Persisting flow state does not make external effects exactly-once. Classify operations and supply idempotency, deduplication, compensation or manual reconciliation for uncertain outcomes.

JSONL is a local single-writer journal, not a distributed database. Use an appropriate transactional store/lease adapter before multi-worker production use.

## Legacy prototype

`contracts.py` and `execution.py` retain the earlier RL-style route/option experiment scaffolding. They are not the canonical machine-habit API.

## Install and test

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
~~~