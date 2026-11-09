# HabitRoute Core — Implementation Status

**Status date:** 2026-11-09  
**Runtime implementation commit:** `18a387c61cb2a5f2d19fa9a21fedaea969f310dc`  
**Architecture base:** PR #9 branch `architecture/durable-machine-habit-v0.3`  
**Implementation PR:** #10 `feat/habit-repertoire-composition-v0.3`  
**Package:** `habitroute` 0.1.0.dev0 (experimental; not a stable production runtime)

## Implemented core

### `src/habitroute/machine.py`

- Immutable operation-pattern machine-habit identity and harness/environment/context scope.
- Trigger and precondition predicates, operation bindings, postconditions and side-effect classes.
- Harness profile and provider-neutral adapter protocol.
- Baseline/candidate aggregate efficiency gate with Wilson reliability lower bounds.
- Fail-closed authorization and adapter-driven executor.
- The executor is not a durable HabitEpisode runtime; persistent worker execution must use the flow path.

### `src/habitroute/flows.py` and `worker.py`

- Immutable versioned flow definitions, typed operation/habit/branch/wait/terminal nodes and pinned habit versions.
- Deterministic event reducer, local append-only JSONL journal, fsync and replay.
- Worker dispatch for ordinary operations and exact-version MachineHabit nodes.
- Existing limitations remain: local single-writer journal, no provider-atomic side effects and no durable HabitRelease registry.

### `src/habitroute/repertoire.py` — first executable v0.3 slice

- Typed capability kinds: skill, tool, script, API, library, framework, model, service, dataset, sub-habit and context.
- Immutable `CapabilityEntry` with exact version, provided facts/outcomes, input requirements, situation predicates, required permissions, compatible harness/environment versions, effect class, lifecycle/evidence reference and separate cost estimates.
- Typed `SituationFrame` with offset-aware observation time, context digest, available inputs and situation facts.
- `HostCapabilitySnapshot` with exact `capability_id@version` availability references, host permissions and allowed operation effects.
- `OutcomeContract` with required outcomes/inputs, freshness and habit-permitted effects.
- `CompositionPolicy` with one explicit primary cost metric, maximum selected capabilities and bounded search-state limit.
- `compose_habit()` filters incompatible, unavailable, inactive, stale, unauthorized or context-inapplicable capabilities.
- Bounded deterministic Dijkstra-style composition supports dependency chains: one capability's outputs can satisfy later capabilities' input requirements.
- A complete plan returns the selected capability chain in execution order, rejected alternatives, missing outcomes/inputs and estimated cost dimensions.
- Search-bound, capability-count, missing-input, missing-outcome and dependency-cycle cases fail closed.

**Execution boundary:** this module is a dry-run planner only. It does not invoke adapters, tools, APIs, scripts, models or external providers. `READY` means an eligible composition exists; it does not prove execution success or outcome correctness. Evidence digests are references, not cryptographic verification. The host must authenticate its snapshot and enforce permissions at execution time.

## Current verification

- GitHub Actions run [42635404943](https://github.com/Loofy147/HabitRoute/actions/runs/42635404943).
- Tested runtime commit: `18a387c61cb2a5f2d19fa9a21fedaea969f310dc`.
- Python 3.11, 3.12 and 3.13: all matrix jobs passed.
- Each job ran 10 legacy experiment tests and 112 core tests.
- The prior 77/77 count is historical and does not describe the current suite.

The subsequent changes to README, source README and documentation do not change runtime code. The CI matrix will run again on the final PR head.

## Still not implemented or not proven

- No durable immutable HabitRelease/capability registry or complete manifest import/export.
- No authenticated host snapshot producer; the planner trusts the typed snapshot supplied to it.
- No real capability adapters for Git, file reading, tests, linters, CI or model providers.
- No actual repository-verification habit wired to the planner.
- No HabitEpisode event stream tying situation, selected capability versions, operation intents/results and verification evidence together.
- No operation-level durable checkpoints on main; PR #8 remains a separate unmerged draft.
- No transactional coordination between arbitrary external effects and the local flow journal; no exactly-once external side-effect guarantee.
- No durable memory consolidation, trace ingestion, candidate discovery, whole-habit learning, shadow promotion, drift monitoring or rollback workflow.
- No independent validator for capability evidence digests or the truth of cost estimates.
- No general planner for loops, parallel branches, non-monotonic state changes, retries, compensation or resource contention.
- No proven cross-harness portability; compatibility fields are declarations that require adapter-level tests.
- No production credential, egress, sandbox, budget or cancellation enforcement supplied by this package.

## Open PR dependencies

- PR #9 introduces the v0.3 documentation model and remains a draft base for this implementation PR.
- PR #10 implements the repertoire/composition planning slice and remains a draft.
- PRs #4–#8 are older design/implementation drafts on separate branches. They are not silently merged by PR #9 or #10. In particular, PR #4's hand-designed repository verifier and PR #8's per-operation checkpoint work still require explicit mapping/reconciliation.

## Immediate next engineering priorities

1. Bind the planner to the hand-designed read-only repository-verification habit using real, version-pinned capability manifests.
2. Implement at least one read-only capability adapter and prove that its host permission-denial path is enforced outside the planner.
3. Introduce a durable HabitRelease registry and validate content/dependency digests.
4. Map selection, capability versions and operation progress to a durable HabitEpisode; reconcile PR #8's checkpoint protocol with it.
5. Record independent outcome verification and raw cost observations before enabling learning or promotion.
6. Keep all non-read-only execution disabled until provider-side idempotency/reconciliation and crash tests pass.
