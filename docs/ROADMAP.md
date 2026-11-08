# Roadmap — integrated Machine Habit v0.3

**Date:** 2026-11-08  
**Status:** proposed sequence; all future checkboxes require commit- and run-level evidence  
**Base reviewed:** main at e57e86afa12757223b9dada4ff191b496ece6c1f

This roadmap supersedes the previous operation-pattern-first plan. It preserves useful code and experiments but does not assume that the current narrow core is the finished product.

## P0 — Preserve evidence and establish the baseline

- [x] Preserve the synthetic step-savings experiment and reports.
- [x] Preserve usage-utility and step-savings policies as separate experimental controls.
- [ ] Commit complete raw per-seed outputs and a reproducibility manifest.
- [ ] Reproduce the experiment from a clean clone.
- [ ] Record current main, open PR heads, test runs and code-to-documentation drift in a baseline snapshot.

**Gate:** historical results stay attached to exact code, configuration, seeds and environment. Synthetic results are not described as production agent performance.

## P1 — Settle the Machine Habit product model

- [x] Inspect the existing canonical definition, code, experiments and unmerged durability work.
- [x] Reassess relevant prior art and the novelty boundary.
- [x] Draft the integrated Machine Habit Model v0.3.
- [x] Draft the research reassessment and comparative-test requirements.
- [x] Draft the revised architecture, decisions and roadmap on an isolated branch.
- [ ] Review and accept/revise the v0.3 model.
- [ ] Resolve the superseded definitions and all documentation contradictions.
- [ ] Define a compact glossary and stable vocabulary for habit, release, repertoire, capability, situation, strategy, episode, memory and evidence.

**Gate:** one unambiguous definition of what the habit owns, what it may reference, what the host enforces, and what constitutes durable behaviour.

## P2 — Specify one complete reference habit before generalizing

Use repository change verification as the first specimen.

- [ ] Define its purpose, outcome contract, in-scope and out-of-scope situations.
- [ ] Define situation inputs, context provenance, freshness and risk classification.
- [ ] Inventory its governed repertoire: Git, file readers, tests, linters, type checkers, CI, dependency/license/security checks, reusable skills and optional model services.
- [ ] Define capability manifests, adapters, versions, compatibility and permission requirements.
- [ ] Design routine, deliberative, fallback, recovery and maintenance behaviour.
- [ ] Define minimal-sufficient composition rules and abstention conditions.
- [ ] Define a complete Habit Episode and memory/evidence contract.
- [ ] Specify what can be reused and exactly when cached or prior verification evidence is invalid.
- [ ] Create adversarial and changed-context cases before implementing the habit.

**Gate:** a reviewer can determine the habit's behaviour from its contract without relying on an implicit general-purpose agent prompt.

## P3 — Define the package, repertoire and episode contracts

- [ ] Define immutable HabitRelease manifest and content/dependency digests.
- [ ] Define capability type, identity, contract, version, provenance, trust, licensing, compatibility, cost and side-effect metadata.
- [ ] Define embedded, referenced, locally installed and remotely provided capability semantics.
- [ ] Define SituationFrame and freshness/invalidation rules.
- [ ] Define strategy/composition and policy contracts.
- [ ] Define append-only HabitEpisode events, operation intent/result records and checkpoints.
- [ ] Define declarative, procedural, semantic and episodic memory records.
- [ ] Define independent EvidenceBundle and EvaluationReport.
- [ ] Define import/export and host-binding compatibility checks.

**Gate:** schema tests reject missing provenance, unpinned dependencies, unresolved authority, invalid episode lineage and ambiguous recovery state.

## P4 — Implement the durable habit runtime incrementally

- [ ] Keep existing operation-pattern and flow code as a compatibility layer until mapped or migrated.
- [ ] Map PR #8's per-operation checkpoint design to HabitEpisode events; preserve its crash/reconciliation tests where still applicable.
- [ ] Implement durable HabitRelease registry and capability manifest resolution.
- [ ] Implement a dry-run situation-to-composition path with explainable capability selection.
- [ ] Implement one read-only capability adapter and prove host-denial paths.
- [ ] Implement HabitEpisode persistence and crash/restart recovery.
- [ ] Add dependency/harness/environment drift refusal and safe fallback.
- [ ] Add bounded approval, needs-attention and abstention paths.
- [ ] Do not enable broad side effects before provider-specific idempotency/reconciliation is proven.

**Gate:** a habit can be exported, loaded, inspected, run in dry-run/read-only mode, interrupted, recovered and independently verified without changing its meaning or authority.

## P5 — Build memory and whole-habit learning

- [ ] Ingest real episode traces with provenance and outcome labels.
- [ ] Separate raw episodes from consolidated memories and active procedures.
- [ ] Discover repeated patterns, capability gaps, failures, unnecessary operations and stale assumptions.
- [ ] Create candidate updates to repertoire, policies, strategies and memory.
- [ ] Evaluate changes on matched and held-out cases, including context shifts.
- [ ] Add shadow/canary promotion, rollback, quarantine, revocation and retirement.
- [ ] Mutation-test learning and promotion gates against incomplete, mismatched or self-asserted evidence.
- [ ] Ensure an active release is never mutated in place.

**Gate:** the habit improves whole-task outcomes without silently broadening authority, retaining stale procedures or rewarding its own unsupported success claims.

## P6 — Comparative and longitudinal evaluation

- [ ] Compare a plain host agent, static skill package, tool-enabled agent, prior HabitRoute core and integrated habit.
- [ ] Use paired cases, controlled seeds, held-out environments and reproducible provenance.
- [ ] Measure accuracy, quality, safety, task completion and outcome reliability.
- [ ] Measure capability-selection precision/recall and unnecessary capability use.
- [ ] Measure latency, tool/model calls, tokens, context/retrieval, compute, external spend, memory and total recovery cost separately.
- [ ] Test long-running adaptation, stale memory, provider changes, schema changes, capability failures and cross-harness migration.
- [ ] Run component ablations to establish whether each subsystem adds measurable value.
- [ ] Publish negative results and conditions where the habit should fall back or abstain.

**Gate:** claims about efficiency, accuracy, durability, transfer or differentiation are limited to measured cases and uncertainty.

## P7 — Host, CPM and ecosystem integration

- [ ] Reconcile the CPM import plan with the v0.3 ownership model.
- [ ] Treat CPM as a selectable context-management capability; the habit owns context requirements and use policy.
- [ ] Keep CPM independently installable and preserve its source/license provenance.
- [ ] Integrate at least two distinct host/harness environments through adapters.
- [ ] Validate exact capability versions and permission boundaries in each host.
- [ ] Prove that missing or changed optional components cause safe degradation, not silent behaviour drift.
- [ ] Add a habit export/import test to a second compatible environment.

**Gate:** portability is demonstrated by measured compatibility and preserved behaviour, not by claiming a generic interface.

## P8 — Release and production readiness

- [ ] Dependency, license and provenance inventory (SBOM where appropriate).
- [ ] Security and threat-model review for repertoire loading and capability execution.
- [ ] Provider-specific credentials, egress, sandbox, budgets, cancellation and output limits.
- [ ] Crash/restart, duplicate delivery, reconciliation and rollback evidence.
- [ ] CI matrix, schema compatibility tests and migration tests.
- [ ] Operational monitoring for capability drift, stale memory, failure rates and cost regressions.
- [ ] Publish only the supported scope; do not label the entire system production-ready without deployment-specific evidence.

## Immediate next sequence

1. Review the proposed v0.3 model and accept or revise its ownership boundaries.
2. Specify the repository-verification habit as a full package with repertoire, situation model, composition, episode and evaluation contract.
3. Design the schemas from that specimen.
4. Map current operation/harness/flow code and PR #8 into the new model.
5. Only then implement the first end-to-end habit path.

Do not expand into a general autonomous runtime before one complete habit demonstrates reliable, durable behaviour.
