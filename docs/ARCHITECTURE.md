# Architecture

## Scope

HabitRoute is a machine-execution optimization system. It discovers, verifies, versions and reuses more efficient patterns for recurring machine operations. It is not a human-habit model, reinforcement-learning skill learner, general planner or environment simulator.

The canonical architecture has three primary entities:

1. **Machine Habit** — a reusable optimized operation pattern with explicit scope, pre/postconditions and matched efficiency evidence.
2. **Execution Harness** — the replaceable environment wrapper that authorizes operations, applies controls, invokes tools/APIs/scripts, observes results and records evidence.
3. **Persistent Flow** — a durable, versioned orchestration instance that stores progress, checkpoints, retries, waits and exact habit versions used.

## Runtime topology

~~~text
Persistent Flow Run
  -> resolves current immutable Flow Definition node
  -> asks Habit Registry for applicable Machine Habits
  -> applies Harness authorization and preflight
  -> executes baseline or selected habit through Harness Adapter
  -> verifies postconditions and captures cost/evidence
  -> appends event and commits checkpoint
  -> advances, branches, waits, retries, pauses or terminates
~~~

The flow owns progress. The habit owns reusable execution optimization. The harness owns execution boundaries and evidence capture.

## Components

### Machine Habit Registry

Stores immutable habit versions, indexes by operation/trigger signature and scope, validates preconditions, and exposes active/at-risk/quarantined/revoked states. Candidate retrieval does not authorize execution.

### Baseline and efficiency evaluator

Compares baseline and candidate procedures on the same input cohort and harness policy. Checks required outputs/postconditions and reports latency, calls, compute, tokens, external charges, retries, recovery and operator intervention separately. Promotion requires correctness plus a declared efficiency improvement.

### Execution Harness

Defines or wraps environment capabilities, operation allowlists, approvals, credentials boundaries, resource/time limits, validation, instrumentation, retry/idempotency semantics, interruption and fallback. Test and production harnesses share interfaces but need not share policies.

### Harness Adapter

Performs the actual operation through an API, CLI, script, repository service, agent runtime or another machine interface. It accepts an explicit operation identity and idempotency key where supported. HabitRoute must not bind itself to a particular provider.

### Persistent Flow Definition

Immutable, versioned state-machine/DAG definition containing operations, habit invocations, branches, waits, approvals, retries, subflows and terminal nodes.

### Persistent Flow Run

Mutable run instance pinned to one flow-definition version. Stores its run ID, current node, inputs/context, attempt state, committed outputs, waiting state and exact habit versions used.

### Flow Journal and Checkpoint Store

Append-only events plus snapshots/checkpoints. The current local JSONL implementation uses a single-writer-per-run contract, complete-write loops, fsync of each event and POSIX parent-directory fsync on first run-file creation.

Provider operations are recorded as individual intent/result pairs. The intent includes a stable idempotency key, operation index, attempt, input digest, and pinned harness/environment/context identity; it is fsynced before adapter invocation. A successful result records outputs and cost observations as a durable checkpoint. A flow node cannot complete while an operation intent remains pending. Multi-operation habits commit every step separately and resume after the last completed checkpoint.

Recovery behavior depends on the operation contract. READ_ONLY and IDEMPOTENT effects may be reissued. DEDUPLICATED effects may be reissued only if the actual adapter/provider durably enforces the supplied key. Pending NON_REPEATABLE or COMPENSATABLE effects stop for reconciliation. Node-visit-scoped keys prevent a later loop visit being confused with an earlier visit.

Recovery rejects a pending intent if the active harness/environment/context identity differs from the one that created it. The journal truncates an unterminated final record while preserving earlier committed records, and refuses to repair newline-terminated corruption. This local journal cannot atomically commit with arbitrary remote providers. It does not establish exactly-once external effects, distributed multi-writer safety, or power-loss safety across all target filesystems. The loader truncates only an unterminated final append tail; newline-terminated corrupt records remain errors. The declared harness version is not yet an independently measured adapter build digest. See [OPERATION_CHECKPOINTS_AND_RECOVERY.md](OPERATION_CHECKPOINTS_AND_RECOVERY.md).

### Evidence and provenance

Every run/event records flow/definition version, node, habit version, harness/environment version, operation identity, idempotency key, timestamps, outputs, postcondition results, status and cost measurements. Historical evidence is immutable; lifecycle changes append new events.

## Machine habit lifecycle

`CANDIDATE -> EVALUATED -> VERIFIED -> ACTIVE -> AT_RISK -> QUARANTINED -> REVALIDATED`

`REVOKED` and `SUPERSEDED` are terminal lifecycle outcomes for that version.

Candidate generation is not activation. An active habit must satisfy its context/input/harness contract and have evidence that the optimization preserves required behavior while improving the declared cost objective.

## Persistent execution semantics

- Definitions are immutable/versioned; active runs pin their definition version.
- Commit an operation intent before any provider call and a separate result checkpoint before advancing the operation cursor.
- An in-flight external operation may have completed even if the worker lost its response or its result checkpoint failed.
- Recovery may replay only effects whose read-only/idempotent/deduplication contract makes replay safe; reuse the same idempotency key for the same node visit and logical operation.
- A pending non-repeatable or compensatable operation requires evidence-backed reconciliation; do not infer non-execution from the lack of a result event.
- Later loop visits to the same flow node receive a new operation scope.
- Never promise exactly-once effects from a local durable journal alone.
- Store external observations, time, random outcomes and model/tool responses needed for deterministic replay.
- Pin pending operation recovery to a stable harness ID/version and environment/context; provider adapters must change their declared version when behavior or implementation changes.
- If safe continuation cannot be established, move the run to `NEEDS_ATTENTION` rather than guessing or retrying indefinitely.

## Core invariants

1. Machine habits are operation optimizations, not general skills.
2. Harness policy is authoritative; a habit cannot widen its capabilities or bypass approvals.
3. A candidate runs only within its declared environment, harness, trigger, input and precondition scope.
4. A habit is promoted only after behavior/postconditions pass and declared efficiency improves.
5. Baseline execution remains available for fallback and matched comparison.
6. A persistent flow owns run progress; a habit does not own durable workflow state.
7. A flow run pins the exact definition and habit versions it used.
8. Checkpoints and event sequence are committed before a flow advances.
9. Replays do not repeat committed side effects.
10. Non-idempotent actions are not automatically retried without verified deduplication or compensation.
11. Cost dimensions and correctness measures remain separately inspectable.
12. All evidence is reproducible from run, code, harness, input cohort and dependency provenance.

## Relationship to the earlier experiment

`experiments/step_savings_v1/` remains a useful synthetic experiment on transition-route reuse, adaptive audit and capacity-limited retention. It is a narrow baseline for one form of machine execution memory, not a proof of durable machine habits or general tool-workflow efficiency.

The option-oriented `src/habitroute/contracts.py` and `execution.py` are retained as prototype/compatibility code. The canonical product model is in `docs/MACHINE_HABITS_AND_FLOWS.md` and `docs/HABIT_SPEC_v0.1.md` (machine-habit spec v0.2). New core work should be added in machine-operation and persistent-flow modules.