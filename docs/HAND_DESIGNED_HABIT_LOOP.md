# Hand-Designed Habit Loop — Execution Order

**Decision:** hand design precedes trace mining. Mining is a downstream evidence operation, not a way to discover the original intent.

## 1. Architecture boundary

- Context Package Manager (CPM) owns progressive disclosure, context selection, context manifests, retrieval and context accounting.
- HabitRoute owns machine-habit definitions, operation-effect semantics, flow progress and execution evidence.
- Unified Agent Runtime is the composition layer only.
- The packages remain independently installable. Neither imports the other's private modules or shares a mutable store.
- Independent verification remains separate from the executor's success assertion.

This is an accepted architecture decision, not a claim that the packages are integrated. See [UNIFIED_RUNTIME_DECISION.md](UNIFIED_RUNTIME_DECISION.md), [PACKAGE_BOUNDARIES.md](PACKAGE_BOUNDARIES.md) and [CPM_INTEGRATION_PLAN.md](CPM_INTEGRATION_PLAN.md).

## 2. Sequence

| Stage | Work | Exit condition |
|---|---|---|
| A — Source baseline | Reconcile HabitRoute implementation and docs; pin CPM source and preserve its package identity | Source digests, repository baseline and independent package boundaries recorded |
| B — Hand design | Specify one habit's intent, invariants, decisions, evidence, constraints, validation matrix and failure behavior | Reviewable immutable v1 spec + declarative flow + contract schemas |
| C — Enforce | Implement trace/decision persistence, success gates, complete budgets, intervention observability and operation-level recovery | Acceptance and fault-injection tests prove the contract |
| D — Observe | Run the hand-designed habit under its pinned policy and capture traces plus separate decision records | Multiple independent, complete, verified executions |
| E — Retrospect | Analyse only eligible held-success traces; classify proposals and preserve event-level provenance | Narrow, non-executable proposals with target action, opportunity, scope, hypothesis, risks and rollback |
| F — Transfer-test | Compare baseline and adapted harnesses on fresh matched cases with a preregistered plan | Raw paired trials, opportunity/action/loading observations, quality gates, cost deltas and uncertainty |
| G — Redesign | Human reviews evidence and authors a new immutable version; no automatic rewrite or promotion | New version passes original and expanded acceptance tests |
| H — Revalidate | Shadow/stage the new version, monitor drift and side effects, then explicitly approve or quarantine | Independent evidence supports activation and rollback remains available |

No stage is implied complete by a document alone. Every exit condition needs a checkable artifact.

## 3. First hand-designed habit

The initial reference is [Repo Change Verification v1](../habits/repo-change-verification/v1/HABIT_SPEC.md).

It is read-only: it inspects repository state and changed files, selects and runs applicable checks, validates evidence, verifies the target stayed unchanged, and then waits for independent same-digest revalidation. It does not repair files, commit, push, merge or deploy.

The machine-readable flow is [flow.json](../habits/repo-change-verification/v1/flow.json). The contract schemas are under [shared/contracts/v0.1](../shared/contracts/v0.1/README.md). The research-grounded proposal and transfer-test extension is [Retrospective Adaptation Protocol](RETROSPECTIVE_ADAPTATION_PROTOCOL.md), with draft records under [shared/contracts/adaptation/v0.1](../shared/contracts/adaptation/v0.1/README.md).

## 4. Why mining remains blocked

HabitRoute already has a machine-habit executor, persistent flow reducer/journal, worker and exact-version in-memory registry. Those foundations do not yet supply the new contract end to end:

- A multi-operation habit is executed as a sequence and the flow event is committed after the sequence. There is no durable per-operation checkpoint for every side effect.
- The local JSONL flow journal is not transactionally coupled to external provider effects.
- Flow events use generic string payloads; they do not yet implement the structured trace schema.
- Decisions have no separate immutable decision ledger and later outcome stream.
- The habit efficiency gate uses caller-supplied aggregate profiles, not the required raw paired trial ledger and independent verifier evidence.
- Budget, evidence completeness, intervention and later-hold conditions are not enforced as a single flow-success contract.
- No trace-backed discovery, shadow evaluation, promotion, drift quarantine or anti-habit pipeline is implemented.

Therefore existing runs and chat history are not a valid mining dataset. Do not infer missing trace fields from conversational summaries.

## 5. Transfer-evaluation controls

The paper's mechanism is adopted with stronger controls, not copied mechanically:

- A candidate is a hypothesis, not a code/configuration change to the live harness.
- Baseline and adapted arms use fresh matched cases; the adaptation is the only planned difference.
- Environmental opportunity, target-action observation, adaptation loading and task outcome are recorded separately.
- The primary comparison is intention-to-treat by assigned arms. Loading is a diagnostic, not a filter for discarding treatment runs.
- Target recurrence is not a success metric by itself. Correctness, constraints, unrelated work, overhead and all material cost dimensions are separate gates.
- Sample size is justified and preregistered; five sessions per arm is not a universal deployment threshold.
- Inconclusive, harmful and rejected proposals remain in the ledger. Only net-benefit results may be sent for human approval.

## 6. Next engineering order

1. Review/settle the architecture preparation and hand-design PRs in dependency order.
2. Validate the hand-designed artifacts and schemas, including mutation/negative tests.
3. Implement append-only trace and decision/outcome persistence with replay and integrity tests.
4. Fix HabitRoute per-operation checkpoints and crash/reconciliation behavior before side-effecting multi-step runs.
5. Implement a machine-enforced verdict evaluator and hard budget/intervention accounting.
6. Run the hand-designed habit on read-only repository tasks and verify the resulting artifacts independently.
7. Only after enough independent, verified runs exist, implement candidate mining as proposal-only.
8. Transfer-test each candidate and require human-authored, versioned redesign before activation.

## 7. External source baseline

The CPM 0.5.0 source archive was inspected from the project Library and its SHA-256 was reproduced as:

9824b6ca364bac9f5634e9d05fa5731735fa937d74b23f8eb030af8e5aad83f0

The archive contains both src/contextpm/ and src/cheg/, plus the cpm and cheg entry points. It also includes a generated .cpm-runtime-cache/index.sqlite3; that cache is runtime state and must be excluded from a source import. The archive verification report says 183 tests passed and compile/wheel install checks passed. It explicitly records real container isolation and live-model quality parity as NOT_RUN. These limits remain attached to the baseline.

CPM must be imported unchanged before local integration work, preserving upstream tests, docs, skills, registry data and notices. Do not add CPM imports to HabitRoute core or move HabitRoute files merely to make the tree symmetrical.
