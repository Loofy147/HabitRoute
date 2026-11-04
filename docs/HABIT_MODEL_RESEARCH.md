# HabitRoute research: machine execution, harnesses and durable flows

**Research date:** 2026-11-04  
**Scope:** reusable machine-operation optimization, execution harness design, durable workflow state and failure semantics.  
**Not in scope:** human habit psychology as a design foundation or RL skill/options as HabitRoute's canonical model.

## 1. Findings

### 1.1 A harness is an execution system, not a prompt

OpenAI's harness-engineering article describes a repository-centered system in which agent work is supported by structured knowledge, tests, CI, observability, internal tooling, plans and recurring cleanup. Its central engineering lesson is that reliable agent execution depends on the scaffolding and feedback loops around the model, not only model capability.

OpenAI's Agents API architecture makes a useful system boundary explicit:

- **Harness:** manages the model/tool loop and session.
- **Environment:** supplies compute, commands, files and execution resources.
- **Application server:** submits work, handles tools/events and owns product-side integration.

That separation supports HabitRoute's provider-neutral design: the harness controls execution; the environment adapter performs operations; the flow system owns durable orchestration state.

Sources:
- https://openai.com/index/harness-engineering/
- https://developers.openai.com/api/docs/guides/agents-api/architecture
- https://developers.openai.com/blog/codex-as-a-platform

### 1.2 Workflows are state machines with distinct task and flow steps

AWS Step Functions models workflows as event-driven state machines. Task states perform work; flow states make decisions, wait, fan out or coordinate parallel execution. An execution instance has observable status and history, and some failed executions can be redriven.

This separation is directly useful:

- A **machine habit** is a reusable optimization used by a task step.
- A **persistent flow** orchestrates ordinary task steps, habits, branches, waits and terminal states.
- An **execution harness** invokes the actual operation and validates its effects.

Do not store a whole flow run inside a habit. Do not treat a reusable procedure as the persistent workflow instance.

Sources:
- https://docs.aws.amazon.com/step-functions/latest/dg/concepts-statemachines.html
- https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html
- https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html

### 1.3 Persistent state and delivery guarantees must be explicit

AWS distinguishes Standard and Express workflow execution semantics. Standard workflows persist execution state and history with a different delivery model than Express workflows. The precise semantics depend on workflow type and retry configuration; a generic 'exactly once' statement is not safe.

Camunda documents worker execution as at-least-once: a worker may receive the same job again after failure or timeout. The worker therefore must make side effects idempotent or otherwise deduplicated.

AWS durable-execution guidance likewise highlights that retries and replay can run an operation more than once. The durable workflow record and an external API/database effect normally do not share one atomic transaction.

**HabitRoute consequence:** a flow journal can persist which step was committed, but it cannot by itself guarantee exactly-once external side effects. Every operation must be classified as read-only, idempotent, deduplicated-by-key, compensatable or non-repeatable. A non-repeatable operation with an unknown outcome must stop for reconciliation rather than blind retry.

Sources:
- https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html
- https://docs.camunda.io/docs/components/best-practices/development/dealing-with-problems-and-exceptions/
- https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/

### 1.4 Durable execution requires deterministic replay or recorded activity results

Workflow recovery reconstructs state from previously committed history. Decisions that depend on wall-clock time, random values, external responses or model output must be recorded as event/activity results rather than silently recomputed differently during replay.

Temporal's retry guidance distinguishes workflow executions from activities and explains why retrying a whole deterministic workflow is often wrong when the underlying activity/dependency failure has not changed. Retrying a bounded activity is more targeted.

**HabitRoute consequence:** replay should rebuild control state; it must not repeat committed operation side effects. The flow engine must record operation results and make retry policy specific to the failing operation.

Source: https://docs.temporal.io/encyclopedia/retry-policies

## 2. What the research does not establish

- These sources do not prove that HabitRoute's machine-habit discovery algorithm will find valuable optimizations.
- They do not establish a universal persistent-flow engine design or require HabitRoute to adopt AWS, Temporal, Camunda or OpenAI infrastructure.
- The machine-habit promotion gate and trace-discovery loop are project design inferences that must be experimentally validated.
- A local JSONL event journal is useful for a first implementation, but it is not a distributed database, multi-writer event store or production-grade workflow service.
- Durable flow replay does not establish exactly-once external operations.

## 3. Proposed HabitRoute synthesis

### Machine Habit

A reusable operation pattern with trigger/input scope, preconditions, operations, postconditions, side-effect semantics, fallback and matched baseline/candidate performance evidence.

### Execution Harness

A capability and policy boundary around operation execution, validation, approvals, budgets, tracing, retries, idempotency, compensation and recovery.

### Persistent Flow

A versioned orchestration definition and a separate run instance with append-only events, current cursor, committed outputs, waiting/approval state, retries, pause/resume and recovery metadata.

### Promotion rule

An optimization is promoted only when it passes the output/postcondition gate and shows a predeclared improvement in a cost dimension on a comparable input cohort. Success, quality, latency, calls, compute, external charges, recovery and intervention remain separately visible.

## 4. Relevance to the existing experiment

The synthetic step-savings study remains useful for one narrow question: whether verified route fragments reduce repeated transition-planning work under capacity limits and environmental changes.

It does not yet test real machine-operation traces, API/tool cost, durable workflow recovery, duplicate worker delivery, idempotent side effects or multi-harness portability. Those require new benchmarks rather than extrapolating the old result.

## 5. References

1. OpenAI, *Harness engineering: leveraging Codex in an agent-first world* (2026-02-11): https://openai.com/index/harness-engineering/
2. OpenAI Developers, *Agents API architecture*: https://developers.openai.com/api/docs/guides/agents-api/architecture
3. OpenAI Developers, *Codex as a platform: build on the open agent harness* (2026-08-19): https://developers.openai.com/blog/codex-as-a-platform
4. AWS, *Learn about state machines in Step Functions*: https://docs.aws.amazon.com/step-functions/latest/dg/concepts-statemachines.html
5. AWS, *Choosing workflow type in Step Functions*: https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html
6. Camunda, *Dealing with problems and exceptions*: https://docs.camunda.io/docs/components/best-practices/development/dealing-with-problems-and-exceptions/
7. AWS, *Idempotency and retries*: https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/
8. Temporal, *Retry policies*: https://docs.temporal.io/encyclopedia/retry-policies