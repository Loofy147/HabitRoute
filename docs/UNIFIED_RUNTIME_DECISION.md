# Unified Agent Runtime — Architecture Decision

**Decision date:** 2026-11-06  
**Status:** Accepted direction; implementation not yet integrated  
**Host repository:** `Loofy147/HabitRoute`  
**Base snapshot:** `43d714c8760a15026e0acb966919f483d893e7d0`

## Decision

Evolve the existing HabitRoute repository into the modular monorepo for HabitRoute and Context Package Manager (CPM). Do not create a second repository as the first integration step. HabitRoute remains the canonical execution-memory project and its existing history remains intact.

Combine capabilities at the runtime/orchestration level. Do not merge package identities, data models, storage systems or safety ownership.

## Product responsibilities

| Component | Owns | Must not own |
|---|---|---|
| Context Package Manager (CPM) | Skill/package registry, progressive disclosure, context planning, context manifests, budgeting, retrieval and context cache | Machine-habit definitions, flow progress, operation authorization |
| HabitRoute | Machine habits, operation-effect semantics, harness contracts, persistent flow definitions/runs, execution evidence | Context selection policy, skill-body loading, agent prompt assembly |
| Unified Agent Runtime | Task coordination, context-to-habit composition, adapter selection, run manifests, explainable plans | Replacing package-local safety gates or silently rewriting package state |
| Shared contracts | Versioned task, context, habit-selection, event-reference and evidence envelopes | Shared mutable memory or a universal opaque score |
| Independent verifier | Checks outcomes, postconditions, experiment evidence and release gates | Trusting the executor's success claim without evidence |

## Five invariants

1. **Independent installability:** CPM and HabitRoute remain independently importable, testable and distributable.
2. **Acyclic dependencies:** neither package imports the other. The runtime is the composition point.
3. **Separate stores:** CPM context cache, HabitRoute habit registry and flow journal remain different stores with different retention and consistency rules.
4. **Shared provenance, not shared authority:** events may reference task IDs, context manifest digests, habit versions and evidence IDs; those references do not grant permission.
5. **Independent verification:** context or operation optimization cannot waive harness authorization, contract checks, postconditions or recovery constraints.

## Repository layout

The first migration should minimize disruption to the working HabitRoute package. Preserve the current root-level HabitRoute project initially; add CPM as an independently installable package under `packages/contextpm/`. Add the runtime under `runtime/` and language-neutral schemas under `shared/contracts/`.

Target logical layout:

```text
HabitRoute/
├── src/habitroute/                 # preserve initially; move only in a tested migration
├── tests/                          # HabitRoute core tests
├── experiments/step_savings_v1/    # preserve unchanged
├── packages/
│   └── contextpm/                  # CPM v0.5.0: contextpm + cheg
├── runtime/
│   └── unified_agent_runtime/      # thin composition layer
├── shared/
│   ├── contracts/                  # versioned JSON Schemas
│   └── evidence/                   # evidence format and validation
├── benchmarks/
│   ├── context_efficiency/
│   ├── habit_execution/
│   └── combined_runtime/
├── docs/
└── pyproject.toml                  # HabitRoute distribution until migration is proven
```

A later symmetrical `packages/habitroute/` layout is acceptable only as a separate behavior-preserving move with tests, import checks and rollback evidence. Do not move files merely to make the directory tree look uniform.

## Context-to-habit feedback loop

A machine habit may declare references to skills or context packages it requires. The runtime asks CPM to resolve those references and records the returned manifest ID/digest. HabitRoute then executes only through its own authorized harness and flow worker. The independent verifier checks the required outcome. Experiment records can test whether the selected context actually improved correctness or total cost.

This is a research hypothesis, not an established capability. A context item being loaded does not prove it contributed to success. Fewer operations do not prove lower total cost or preserved quality.

## Execution policy for the first integrated release

Start with **read-only composition and dry-run planning**. Do not allow a composed multi-step side-effecting habit until HabitRoute's per-operation checkpoint and external-effect recovery gaps are closed with crash-injection evidence.

## Explicit non-goals

- Rewriting CPM or HabitRoute.
- A shared mutable memory database.
- Direct CPM-to-HabitRoute imports.
- General autonomous execution or broad provider integrations in the first milestone.
- Claiming distributed workflow guarantees from a local JSONL journal.
- Claiming quality parity, token savings or joint optimization without suitable measurements.

## Decision consequences

- HabitRoute is the host repository.
- CPM v0.5.0 is the initial CPM source pin; preserve both `contextpm` and `cheg` packages and their CLI entry points.
- The repository license is MIT as of this decision. The CPM distribution also declares MIT in its package metadata; keep component provenance and attribution visible.
- The existing synthetic route experiment remains a legacy benchmark and is not silently converted into a machine-tool benchmark.
- Every migration stage gets a source pin, diff, test report and rollback path.
