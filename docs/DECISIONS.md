# Decisions and open questions

New evidence may supersede a decision, but the reason and affected experiments must remain visible.

## D-001 — Preserve the experiment as a separate baseline

**Status: accepted**

Keep the executable synthetic research harness under `experiments/step_savings_v1/`. Do not rewrite its behavior while building the machine-habit core.

## D-002 — Preserve usage utility as the legacy default

**Status: accepted**

The existing experiment keeps `policy="utility"` as its default. Step-savings remains opt-in because gains are not uniform across capacity and repeated-change conditions.

## D-003 — Machine habits are execution optimizations, not skills

**Status: accepted; canonical**

A machine habit is a reusable, verified operation pattern that improves efficiency while preserving required outputs, postconditions and operational constraints. Human habit psychology and RL option/skill terminology are not the product foundation.

## D-004 — Separate habits, harnesses and persistent flows

**Status: accepted; canonical**

Habit = reusable optimized pattern. Harness = controlled execution and verification boundary. Persistent flow = durable orchestration definition and run state. A flow invokes habits through a harness; none of the three substitutes for the others.

## D-005 — Efficiency is a gated claim

**Status: accepted; canonical**

Fewer steps alone does not prove efficiency. Promotion requires comparable baseline/candidate work, passing output/postcondition checks, bounded quality regression and improvement in a declared cost dimension. Other costs remain separately visible.

## D-006 — Persistent progress is separate from reusable procedures

**Status: accepted; canonical**

Persistent flow definitions are immutable/versioned; run instances pin a definition version and record exact habit versions. Habits do not own long-lived progress.

## D-007 — Side-effect retries require idempotency or compensation

**Status: accepted; canonical**

A durable journal cannot by itself guarantee exactly-once effects in an external system. Operations must be classified and retried only under a documented idempotency, deduplication or compensation contract.

## D-008 — Existing option-oriented prototype is non-canonical

**Status: accepted**

The prior `contracts.py` / `execution.py` files and their tests are preserved as a research prototype. They are not the definition of a HabitRoute machine habit. New development uses machine-operation and persistent-flow abstractions.

## D-009 — HabitRoute is the host repository for CPM integration

**Status: accepted; preparation branch**

Evolve the existing `Loofy147/HabitRoute` repository into the modular monorepo. Do not create a new repository as the first integration step. Preserve current HabitRoute package behavior and import CPM as a separate, independently installable distribution. See [UNIFIED_RUNTIME_DECISION.md](UNIFIED_RUNTIME_DECISION.md).

## D-010 — Keep CPM and HabitRoute responsibilities and stores independent

**Status: accepted; canonical integration constraint**

CPM owns context selection, progressive disclosure, budgeting, retrieval and context cache. HabitRoute owns machine habits, harness policy and persistent flows. The runtime coordinates them through versioned contracts. No circular imports; no shared mutable memory store.

## D-011 — MIT license for HabitRoute repository

**Status: accepted; preparation branch**

Select MIT for the repository, effective in this preparation branch. The package metadata and root `LICENSE` must agree. Imported components and dependencies still require provenance and compatibility review; a repository-level license does not override third-party terms.

## Open questions

- Which trace normalization and similarity features best identify reusable machine-operation patterns?
- How much paired evidence is needed to promote an optimization for each cost/risk class?
- Which harness contracts are common across APIs, CLIs, repositories, agents and local scripts?
- Which flow journal/store guarantees are required: local single-writer, transactional SQL, event store, or external durable workflow engine?
- What is the correct recovery protocol when an external side effect may have succeeded but its acknowledgement was lost?
- How should habits be invalidated when an API, schema, tool, credential scope, dependency or environment changes?
- Which costs should be hard constraints and which can be traded off?
- Should HabitRoute own the durable flow runtime or integrate with Temporal, Step Functions, Camunda or another provider through adapters?
- What exact task/context/habit evidence relationship is sufficient to establish that a context selection contributed to a successful execution?
