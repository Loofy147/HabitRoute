# Decisions and open questions

This file records explicit choices. New evidence may supersede a decision, but the reason and affected experiments must remain visible.

## D-001 — Preserve the experiment as a separate baseline

**Status:** accepted

Keep the current executable research harness under `experiments/step_savings_v1/`. Do not move it directly into the public library package or refactor it in place. The harness is evidence provenance and the comparison baseline for extraction.

## D-002 — Usage utility remains the overall default

**Status:** accepted

The agent default remains `policy="utility"`. The step-savings policy is opt-in (`policy="savings"`) with a default coverage weight of 0.5. The tested improvement is strongest around capacity 28; it is not uniform across capacities and worlds.

## D-003 — Treat certificates as scoped, revocable evidence

**Status:** target design

A verified route is valid only within the context and representation under which it was tested. World changes, representation changes, or contradictory observations can make its evidence inapplicable. A certificate must support explicit invalidation and revalidation.

## D-004 — Separate objectives and diagnostics

**Status:** accepted

Do not hide coverage, reliability, freshness, action steps saved, lookup cost, and memory cost in a single uninspectable scalar. A policy may use a weighted score, but each component and trade-off must remain measurable.

## Open questions

- What is the minimum evidence needed to activate a route certificate?
- How should context identity be defined for partially observed or stochastic worlds?
- How can a detector separate a transient slip from a true transition change under correlated noise?
- Should freshness be time-based, evidence-based, revision-based, or a combination?
- How should the engine handle representation drift when state keys themselves move?
- Can certificates compose safely across multiple route segments?
- What is the right query-cost model when library lookup dominates planner cost?
- Which persistence contract is required before the library becomes a general dependency?
