# Reference Habit v0.3 mapping — repository change verification

**Date:** 2026-11-08  
**Status:** design assessment; no runtime changes  
**Existing specimen:** PR #4, Repo Change Verification v1, hand-designed / not runtime-enforced  
**Target model:** [Machine Habit Model v0.3](MACHINE_HABIT_MODEL_V0.3.md)

## 1. Why this specimen

The existing Repo Change Verification v1 is a useful first habit because it already defines intent, strict read-only scope, invariants, preconditions, inspection order, validation selection, safe-skip rules, immutable decisions, evidence, budget requirements, intervention classification and later independent revalidation.

It is not merely a short workflow. It already contains meaningful judgement and evidence requirements. The correct next step is to preserve that work and extend it into the integrated Machine Habit model.

PR #4 remains an open draft based on the earlier documentation branch. Its own specification states HAND_DESIGNED / NOT YET RUNTIME-ENFORCED. The PR's CI record reports 97 tests passing per Python matrix job; schema/contract tests establish design-shape checks, not runtime enforcement. See [PR #4](https://github.com/Loofy147/HabitRoute/pull/4), its [Core Status snapshot](https://github.com/Loofy147/HabitRoute/blob/feat/hand-designed-repo-verification-v1/docs/CORE_STATUS.md), and [CI run 42231017168](https://github.com/Loofy147/HabitRoute/actions/runs/42231017168).

## 2. Existing v1 coverage against v0.3

| v0.3 responsibility | Existing v1 evidence | Assessment |
|---|---|---|
| Purpose and outcome contract | Intent, exclusions, invariants and SUCCESS_HELD contract | Strong design coverage |
| Situation awareness | Repository identity, refs, worktree state, changed paths, environment and policy preconditions | Present, but not yet a single typed SituationFrame contract |
| Governed repertoire | Read-only capability profile, allowed commands, tools and validation classes | Partial; no complete capability manifest/registry |
| Operational judgement | Decision points for baseline, inspection, validation, safe skip, retry and verdict | Strong hand-authored decisions; selection policy is not yet general |
| Minimal-sufficient composition | Path-to-validation matrix and per-target safe-skip decisions | Partial; no explicit capability composition objective, coverage solver or unnecessary-capability measurement |
| Planning and execution | Declarative flow graph and defined ordered stages | Present as hand-designed flow; not connected to the runtime |
| Habit-owned durable episode | Trace-event, decision, outcome and verdict contracts are proposed | Partial; not yet explicitly packaged/pinned as a HabitEpisode with complete capability lineage |
| Memory and experience | Prior validation evidence, source fingerprints and mining boundary | Partial; no typed memory lifecycle, consolidation, correction and freshness model |
| Independent verification | Evidence validation, exact source digest, later same-digest revalidation | Strong design coverage |
| Learning and evolution | Mining eligibility rules, candidate proposal and human-authored redesign | Design boundary present; no implemented discovery/evaluation/promotion pipeline |
| Governance and portability | Immutable constraint policy, read-only profile, intervention and authority limits | Strong local scope definition; cross-host and capability compatibility are not established |

## 3. Missing pieces to specify

### 3.1 Capability manifest

The current read-only capability profile identifies a policy boundary, but the habit needs an explicit repertoire entry for each capability it may use.

A proposed entry should include:

- stable capability ID and kind (skill, script, CLI, API, library, framework, model, service, dataset, sub-habit);
- pinned implementation version or digest and source/provenance;
- purpose, applicability conditions and input/output contract;
- supported repository languages, file types, test runners or build systems;
- required permissions, data exposure and whether the adapter can mutate state;
- dependency and host/harness compatibility;
- availability/health, timeout, retry and failure semantics;
- cost dimensions and measurement source;
- validation status, evidence references, fallback and replacement rules.

This lets the habit know what it has, what each component can do, what it cannot do, and when it is appropriate. A tool being installed or callable is not proof that it is suitable for a particular change.

### 3.2 Typed situation frame

The current preconditions should be consolidated into a typed SituationFrame with:

- repository identity, base/target commit or immutable working-tree snapshot;
- change inventory and affected-surface map;
- language, file classifications, interfaces and dependency closure;
- CI state and exact evidence fingerprints;
- environment, toolchain, package-lock and policy identities;
- risk class, required quality level and user acceptance criteria;
- available repertoire entries and their current health/compatibility;
- missing observations, confidence/uncertainty and observation timestamps.

Each field needs source, freshness and invalidation semantics. A missing field remains unknown.

### 3.3 Capability-selection and composition policy

The existing validation matrix tells the habit which checks are required, but v0.3 needs a general policy for selecting and composing the actual capability set.

For example:
- use Git metadata and a diff parser to establish change scope;
- use targeted tests when impact is narrow and the mapping is validated;
- add full regression tests when dependency closure, risk or uncertainty requires them;
- invoke a type checker only for affected typed surfaces and compatible configurations;
- use a license scanner when dependency metadata changes;
- reuse previous CI evidence only when the entire validation fingerprint matches;
- use a model-assisted review only when it adds coverage that deterministic tools cannot provide and the task's data policy permits it;
- abstain or ask for a missing capability when no eligible combination can meet the outcome contract.

Selection must account for coverage, quality, cost, safety, uncertainty and redundancy. Minimizing the number of tools is not the goal by itself; choose the smallest sufficient set that satisfies the verification contract.

### 3.4 Habit-owned episode

The existing event and decision contracts are useful starting points. A v0.3 HabitEpisode should additionally pin:

- HabitRelease identity and digest;
- situation-frame digest and source timestamps;
- policy and strategy versions;
- exact selected and rejected repertoire entries with reasons;
- adapter/provider versions and effective host capability profile;
- execution plan and per-operation intents/results/checkpoints;
- evidence artifacts and independent verifier identities;
- final verdict, unresolved uncertainty and cost vector;
- memory records proposed or updated after the episode.

A workflow engine may store and replay these events, but the episode belongs to the habit.

### 3.5 Memory and adaptation

The habit should accumulate more than a list of successful commands. Useful memory includes:

- which change patterns tend to affect which interfaces or tests;
- which capabilities are reliable for each language/build/test environment;
- which validation shortcuts were safe under exact fingerprints;
- which tests failed to detect injected defects;
- which historical evidence is still fresh and valid;
- where the habit previously misclassified risk or skipped a required check.

A candidate memory or policy update must preserve counterexamples and scope. A pattern that works for one repository or stack must not be generalized to another without evidence.

## 4. Design example: composing the repertoire

| Observed situation | Candidate repertoire | Habit's selection behaviour |
|---|---|---|
| Documentation-only change | Git diff, Markdown/link checker, docs schema checker | Inspect every changed document and run applicable documentation checks; no unsupported claim that code runtime was tested |
| Source change in one module | Git diff, language parser, affected tests, type/lint tools | Establish imports/callers and affected tests; run targeted checks, then broaden when impact/risk is unclear |
| Dependency/lockfile change | Package metadata parser, lockfile verifier, license scanner, clean build/test environment | Inspect transitive delta and provenance; require dependency/build checks; install only under separately authorized policy |
| CI or permission change | Workflow parser, action metadata, policy scanner, test workflow or CI API | Check syntax, permissions, triggers and intended job effects; don't equate YAML parsing with workflow correctness |
| Test-only change | Test runner, fixture inspector, mutation/negative test | Verify the test exercises the intended behavior and fails under the target defect where practical |
| Prior CI evidence exists | Evidence index, digest verifier, CI adapter | Reuse only if source, tests, config, dependencies, environment and policy fingerprints are all compatible and unexpired |
| Tool unavailable or version drift | Capability health checker, compatible substitute, human escalation | Recompute eligible choices; do not silently substitute an unvalidated tool or claim equivalent coverage |

This composition table is illustrative. Each strategy must be validated by cases and by the actual contracts of its capabilities.

## 5. Versioning and PR relationship

Do not silently rewrite the existing v1 design or assume that its open PR is already part of main.

Recommended sequence:

1. Review and settle the v0.3 model in PR #9.
2. Rebase the existing hand-designed v1 artifacts onto the accepted architecture without changing their intent or evidence semantics.
3. Map the current flow and trace contracts to HabitEpisode, SituationFrame and CapabilityEntry.
4. Decide whether the additional repertoire/composition semantics can be added compatibly or require a new major habit release. Do not choose a version number before reviewing schema compatibility.
5. Keep v1 read-only. The first implementation remains dry-run/read-only until operation durability, host denial, evidence and independent-verification gates are executable.
6. Use the same v1 task set as a baseline for the integrated habit, then add held-out and changed-environment cases.

PR #4 is a design and schema artifact. Its runtime gaps remain open. PR #8 is a separate draft for per-operation checkpoint/recovery mechanics and must be mapped to the HabitEpisode contract rather than assumed to complete it.

## 6. Minimum proving experiment

Compare the current hand-designed v1 path against an integrated v0.3 implementation using the same repository-change cases.

Include:
- ordinary source changes, tests, docs, config, dependencies, CI and renames/deletions;
- low-risk and high-risk changes;
- stale/missing/contradictory prior evidence;
- capability unavailable, wrong version and incompatible host;
- safe and unsafe skip counterexamples;
- injected defects that targeted checks should detect;
- interrupted operations, lost acknowledgements and duplicate delivery;
- changed toolchain, dependency lock and host runtime.

Measure:
- change coverage and independent verdict accuracy;
- missed defects and false success/skip rates;
- selected capability precision/recall and unnecessary operations;
- time, model/tool calls, tokens, context/retrieval, compute and external cost;
- retries, recovery, human interventions and incomplete outcomes;
- portability and degradation when optional capabilities are removed.

Use matched cases and held-out repositories. Publish failures and negative results. The habit should be considered useful only if its complete behaviour improves over the existing design without weakening its verification contract.

## 7. Current conclusion

The existing repository-verification design is a strong initial behaviour contract. It already answers many questions about what the habit must protect. The v0.3 work should add a governed capability repertoire, explicit situation representation, capability composition, habit-owned episode lineage and whole-habit memory/evolution.

Do not discard the v1 work. Do not mistake its detailed flow for the completed Machine Habit system.
