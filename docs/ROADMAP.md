# Roadmap

## P0 — Preserve and verify the experimental baseline

**Status: preserved; clean-clone artifact completeness still needs final verification.**

- [x] Create the public repository.
- [x] Preserve the simulator and step-savings experiment.
- [x] Preserve the planner/world dependency and focused tests.
- [x] Record capacity, sensitivity and repeated-change findings.
- [ ] Add all raw per-seed artifacts and a reproducibility manifest.
- [ ] Verify experiment reproduction from a clean clone and pin dependency versions.

**Gate:** the legacy experiment is independently reproducible and remains unchanged by core extraction.

## P1 — Define and enforce the habit contract

**Current priority.** See HABIT_SPEC_v0.1.md and CONTRADICTIONS_AND_GAPS.md.

- [x] Add dependency-free typed records for immutable habit versions, scopes, initiation, controllers, goals and termination metadata.
- [x] Add fail-closed initiation evaluation: candidate retrieval cannot authorize execution.
- [x] Add version/scope-bound empirical certificate validation with a Wilson lower confidence bound.
- [ ] Add typed termination outcomes: success, failure, interrupted, timeout, resource limit and unknown.
- [x] Add invariant tests for version mismatch, context mismatch, OOD belief, low evidence and macro-contract coherence.
- [ ] Keep fixed macros as the first supported controller without limiting the schema to fixed macros.

**Gate:** unknown/OOD state, mismatched context, mismatched representation, or invalid certificate cannot authorize a habit. All decisions have explicit reasons.

## P2 — Repair representation and composition assumptions

- [ ] Measure Markov/predictive sufficiency of the abstract representation.
- [ ] Add belief/context-aware states or probabilistic transitions for aliasing and stochastic outcomes.
- [ ] Fix staleness metrics for many-to-one prototype mappings.
- [ ] Add terminal-outcome to next-initiation compatibility with uncertainty bounds.
- [ ] Version encoders/prototypes and suspend unaligned habits.

**Gate:** aliasing and stochastic-transition tests do not trigger false edge contradictions or false certificates.

## P3 — Discover better habits, not more chunks

- [ ] Separate episode memory, primitive transition evidence and option definitions.
- [ ] Compare all-contiguous-subsequence enumeration with segmentation at stable subgoals and decision points.
- [ ] Build a guarded finite-state controller for branching continuations.
- [ ] Compare fixed macro and reactive option on the same branching/non-branching tasks.
- [ ] Measure independent coverage, lookup load, memory, duration and execution quality.

**Gate:** segmentation reduces redundant records/lookup work without unacceptable loss of coverage or route quality.

## P4 — Correct adaptation and trust economics

- [ ] Make certificates per habit version and context, not a start/goal cache.
- [ ] Ensure every behavior-affecting mutation invalidates dependent lookup/audit caches.
- [ ] Separate transient slips, burst noise, observation/representation failures and persistent regime changes.
- [ ] Compare sequential change-detection approaches on false alarms, delay and misses.
- [ ] Make adaptive audit risk/value-of-information based and include audit cost.
- [ ] Ensure dominated pruning proves replacement using only currently admissible habits and that replacement survives.

**Gate:** no invalid route can dominate/delete a valid route; false-demotion and detection-delay trade-offs are quantified.

## P5 — Optimize selection and retention

- [ ] Keep the current action-step cost as a baseline.
- [ ] Add task-dependent duration, resource, failure, safety, recovery, lookup and planning cost components.
- [ ] Evaluate goal/reward revaluation when transitions remain unchanged.
- [ ] Compare retention policies with paired uncertainty and multi-objective results.

**Gate:** no new scalar policy is promoted without showing each component and its trade-offs.

## P6 — Release a reusable Python library

- [ ] Extract the validated core behind simulator-independent adapters.
- [ ] Add type checking, linting, CI, documentation and an example adapter.
- [ ] Define persistence and schema migration after the contract stabilizes.
- [ ] Select a license before encouraging reuse.
- [ ] Publish a versioned release only after clean-install and integration tests.

## Immediate next task

Implement P1 as a pure-Python, dependency-free domain contract and test it before connecting it to the old simulator. Do not replace the current experiment implementation yet.