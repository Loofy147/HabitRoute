**Historical design notice (2026-11-08):** This document records the earlier v0.2 operation-pattern model. It is retained for provenance and reusable engineering details, but it is no longer the canonical product definition. The proposed integrated model is [Machine Habit Model v0.3](MACHINE_HABIT_MODEL_V0.3.md), with topology in [Architecture](ARCHITECTURE.md) and prior-art analysis in [Research Reassessment v0.3](RESEARCH_REASSESSMENT_V0.3.md). Do not interpret the older separation of habit, harness and flow as the v0.3 ownership model.

# HabitRoute: Machine Habits, Harnesses and Persistent Flows

**Date:** 2026-11-04  
**Status:** corrected canonical product model  
**Decision:** HabitRoute studies machine execution habits. It is not a human-habit simulator, a reinforcement-learning skill library, or a biological analogy.

## 1. Corrected definition

A **machine habit** is a reusable, verified execution pattern that performs a recurring machine operation more efficiently than the applicable baseline while preserving required outputs, invariants and operational constraints.

It may be a fixed sequence, a parameterized procedure, a guarded branch, a cached/reused intermediate result, a reduced set of tool/API calls, or a more efficient combination of recurring operations. It is not a capability or general-purpose skill. Its value is measured by the execution it avoids, compresses or improves.

Machine habits should be discovered from machine traces and operational evidence: tool calls, API requests, scripts, repository actions, file operations, agent harness runs, workflow steps, retries, waiting and recovery. Human behavioral habit theory is not the project's design foundation.

## 2. The three primary entities

### 2.1 Machine Habit

A reusable optimization artifact. It records:

- stable identity and immutable version;
- the machine/harness/context scope where it applies;
- trigger and input/precondition contract;
- the optimized operation pattern and parameter bindings;
- required postconditions and output-equivalence checks;
- side-effect and idempotency classifications;
- operational limits and fallback behavior;
- baseline-vs-habit measurements, sample cohort and efficiency gate;
- provenance and revocable verification evidence.

A habit is promoted only when the candidate preserves the agreed correctness/quality floor and improves at least one declared cost measure on comparable work. Cost dimensions stay separate: latency, operation/tool/API calls, compute, tokens, memory, external charges, retries, recovery and human intervention.

### 2.2 Execution Harness

A harness is the controlled environment and execution wrapper around machine operations and habits. It supplies:

- machine/environment identity and capability inventory;
- allowed operations, credentials boundary and approval requirements;
- input/output validation and pre/postcondition checks;
- timeouts, concurrency and resource budgets;
- retries, idempotency keys and compensation rules;
- structured tracing, metrics and evidence capture;
- interruption, failure handling and fallback;
- test/evaluation mode and production execution mode.

The harness does not decide what a habit means. It applies the same execution contract to baseline procedures and candidate habits, captures outcomes, and prevents optimizations from bypassing controls.

An experimental/test harness and a production/runtime harness may share the same interface but have different capabilities and policies. A test harness can inject faults, replay fixtures and compare paired runs; a production harness must enforce the live authorization and side-effect boundary.

### 2.3 Persistent Flow

A persistent flow is a durable orchestration instance that can include ordinary operations, machine habits, branches, waits, approvals, retries, subflows and terminal outcomes.

It owns progress, not the habit. It retains:

- flow definition identity and exact version;
- run identity and current node/step;
- input and persistent business context;
- committed checkpoints and completed-step results;
- attempt counts, idempotency keys and retry state;
- timers, waits, external callbacks and approval state;
- append-only execution events and provenance;
- pause, resume, cancellation and recovery state.

A flow may pause and resume after a process restart or deployment. It may select a different habit version on a future run, but an active run pins the flow definition and each habit node pins the exact habit version it uses.

## 3. Relationship

~~~text
Persistent Flow
  ├── ordinary operation
  ├── invoke Machine Habit vN
  ├── branch / wait / approval
  ├── invoke Machine Habit vM
  └── terminal result

Execution Harness
  ├── validates the current flow step
  ├── enforces the operation and habit policy
  ├── invokes the machine/API/tool/script
  ├── captures result, cost and side effects
  ├── records an idempotency key and checkpoint
  └── returns success / retryable failure / terminal failure

Machine Habit
  ├── trigger and preconditions
  ├── optimized operation pattern
  ├── expected outputs and postconditions
  ├── idempotency / compensation semantics
  └── paired baseline-vs-habit efficiency evidence
~~~

A habit can be called by many flows. A flow can contain many habits. A harness can execute flows and standalone habits. The persistence layer stores flow progress and execution evidence; the habit library stores reusable optimization artifacts.

## 4. What makes a habit genuinely more efficient?

A lower step count is not sufficient. A candidate may reduce tool calls while increasing latency, failure rate, compute or recovery cost.

Promotion requires:

1. **Comparable cohort:** baseline and candidate are evaluated on the same task/input cohort or an explicitly justified matched design.
2. **Correctness gate:** required outputs, side effects and postconditions remain within the declared equivalence/tolerance contract.
3. **Reliability gate:** success and failure rates do not regress beyond an explicit allowed margin; sample size and uncertainty are reported.
4. **Efficiency gain:** at least one declared metric improves by a minimum amount.
5. **No hidden regression:** all important cost dimensions are still reported, including retries, recovery, verification, harness overhead and human intervention.
6. **Reproducibility:** code, harness, environment, data, configuration and habit version are identified.

Useful cost measures include:

| Dimension | Examples |
|---|---|
| Latency | Median and p95 wall-clock time |
| Calls | Tool/API/service requests and planner/model calls |
| Compute | CPU/GPU time, tokens, memory and storage |
| External cost | API spend, cloud spend, metered operations |
| Reliability | Success, contract violations, retry rate, failure severity |
| Recovery | Restart time, compensating actions, manual intervention |
| Orchestration | Checkpoint, serialization, lookup, audit and scheduler overhead |

Do not combine these into a single score until the decision policy explicitly defines the trade-offs.

## 5. Harness protocol

An execution harness should expose a small capability-neutral contract:

1. **Preflight:** identify the environment, harness version, capabilities and current policy.
2. **Authorize:** check the flow/operation/habit scope, input, approvals and resource budget.
3. **Prepare:** validate inputs and compute a stable operation identity/idempotency key.
4. **Execute:** invoke the operation using the narrowest required capability.
5. **Observe:** capture output, side effects, duration, usage and errors.
6. **Verify:** evaluate output contracts and postconditions independently from the operation's own success response.
7. **Commit:** write the event and checkpoint before advancing the persistent flow.
8. **Recover:** classify retryability, resume from a committed checkpoint, compensate or escalate.

The harness should be replaceable. HabitRoute must not be coupled to one agent framework, provider, cloud, operating system, database or tool protocol.

## 6. Persistent flow semantics

### 6.1 Definitions versus instances

A `FlowDefinition` is versioned and immutable. A `FlowRun` pins a definition version and carries mutable execution state. Updating a flow definition must not silently rewrite an already-running instance.

### 6.2 Checkpoint boundaries

Persist after every completed side-effecting step and before advancing the flow cursor. A checkpoint includes the operation identity, result reference, attempt count, idempotency key and flow revision.

An in-flight external operation is not assumed to have been rolled back after worker failure. Recovery must determine whether to query the external system, retry with the same idempotency key, compensate, or require manual intervention.

### 6.3 Retry and idempotency

Replay and retry can repeat activity code. Every operation must be classified as read-only, idempotent, deduplicated-by-key, compensatable, or non-repeatable. Automatic retries of non-idempotent effects are prohibited unless the harness has a verified deduplication or compensation mechanism.

Never claim exactly-once side effects merely because the flow journal is durable. The workflow store and an external service generally do not share one atomic transaction. The operation adapter must supply the required idempotency/outbox/compensation behavior.

### 6.4 Deterministic replay

Replay reconstructs the flow's control state from committed events. It must not repeat completed external operations. Time, random values, model responses and external observations used by flow decisions must be captured as event data or injected through recorded activity results.

### 6.5 Flow lifecycle

`CREATED → RUNNING ↔ WAITING/PAUSED → SUCCEEDED | FAILED | CANCELLED | NEEDS_ATTENTION`

`NEEDS_ATTENTION` is used when safe automated continuation cannot be justified. It is not converted into success or an unbounded retry loop.

## 7. Discovery and improvement loop

1. Observe recurring baseline executions through a harness.
2. Normalize traces into operation identities, parameters, outcomes and costs.
3. Find repeated subflows and redundancy: duplicate reads, repeated computation, repeated planning, avoidable round trips or unnecessary verification.
4. Propose a candidate machine habit with narrow applicability conditions.
5. Run the baseline and candidate through the same evaluation harness on matched inputs.
6. Verify output/side-effect equivalence and measure per-dimension efficiency.
7. Promote the immutable habit version only after passing the declared gate.
8. Deploy gradually; retain a baseline fallback and monitor drift.
9. Quarantine or revoke the affected habit when its context, harness, dependency or postconditions change.
10. Feed new traces back into discovery without mutating historical evidence.

## 8. What the current implementation contributes

The canonical package now includes a machine-habit/harness policy model in `src/habitroute/machine.py` and an event-sourced persistent-flow definition, reducer, run controller and local JSONL journal in `src/habitroute/flows.py`. These are initial contracts and control-plane primitives. A production HarnessAdapter implementation and a worker that invokes actual operations are still future work. See `docs/CORE_STATUS.md`.

## 9. What the earlier prototype contributes

The existing `experiments/step_savings_v1/` remains valuable as a narrow machine-memory experiment: it tests verified transition-sequence reuse, adaptive audit, route pruning, capacity and action-step savings in a synthetic world.

The later `src/habitroute/contracts.py` and `execution.py` were drafted using an RL-style option/skill abstraction. They are retained as a research prototype and compatibility reference, but they are **not the canonical machine-habit model**. New development should use machine-operation, harness and persistent-flow concepts.

The original result that usage-based retention can preserve detours while step-savings can improve some capacity-limited routes remains relevant. It does not yet demonstrate real API/tool workflow efficiency or durability.

## 10. Research basis and interpretation

### Harness engineering

OpenAI's harness-engineering write-up treats the harness as the surrounding system of repository knowledge, tests, tools, CI, observability and feedback that lets agents do reliable work. This supports designing HabitRoute's harness as a replaceable execution and verification boundary, not as a prompt or a habit itself.

Source: https://openai.com/index/harness-engineering/

OpenAI's Agents API architecture explicitly separates the harness, the execution environment and the application server. It describes the harness as owning the model/tool loop and session, while the environment owns compute/files and the application server connects the workflow to the product.

Source: https://developers.openai.com/api/docs/guides/agents-api/architecture

### Durable workflow semantics

AWS Step Functions models workflows as event-driven state machines with task states, choice/branch states, waits, execution history and redrive. Its Standard and Express workflow types have different persistence and delivery guarantees; those semantics must not be blurred into a generic exactly-once promise.

Sources:
- https://docs.aws.amazon.com/step-functions/latest/dg/concepts-statemachines.html
- https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html

Camunda documents workers as at-least-once: a worker may be invoked again after a timeout or failure, so side-effecting job handlers need idempotency or deduplication.

Source: https://docs.camunda.io/docs/components/best-practices/development/dealing-with-problems-and-exceptions/

AWS's durable execution guidance likewise explains that retry/replay may repeat side effects and recommends idempotency mechanisms. This is why HabitRoute must record operation semantics and idempotency keys instead of promising exactly-once external effects.

Source: https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/

### What is engineering inference

The three-entity model (Machine Habit, Execution Harness, Persistent Flow), the promotion gate, trace-discovery loop and proposed schema are HabitRoute design decisions inferred from these engineering patterns. The cited sources establish useful mechanisms and failure modes; they do not validate HabitRoute's eventual performance.