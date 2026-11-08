# Machine Habit Model v0.3

**Date:** 2026-11-08  
**Status:** Proposed canonical architecture; documentation-only draft pending review  
**Supersedes:** the narrow operation-pattern definition in Machine Habit Specification v0.2 and the former three-entity product model  
**Implementation status:** not implemented by the current core

## 1. Product thesis

HabitRoute treats a Machine Habit as the durable unit of machine behaviour.

A Machine Habit is not merely a prompt, skill file, fixed procedure, tool router, workflow definition, memory store, or execution wrapper. It is an integrated operational system that knows how to respond to a recurring class of situations. It contains or owns a governed repertoire of capabilities and knowledge, recognizes when and where they apply, selects and combines the relevant parts, executes through an authorized environment, verifies what happened, preserves experience, and improves its future behaviour through evidence.

Skills, tools, scripts, models, frameworks, APIs, datasets, services, procedures, sub-habits, context packages and other resources are components of the habit's repertoire. They are not conceptually outside the habit merely because some are implemented or hosted elsewhere.

A habit does not have to copy or vendor every dependency. It must own the manifest, purpose, compatibility rules, selection knowledge, configuration, provenance, lifecycle and use policy for each component it relies on. A component can be embedded, referenced, locally installed, remotely provided or dynamically discovered; each form must be represented and governed.

## 2. Definition

A **Machine Habit** is an independently identifiable, versioned and durable operational system that:

1. pursues a declared purpose and measurable outcome contract;
2. perceives and models the situation in which it is expected to operate;
3. maintains a governed repertoire of knowledge, procedures and executable capabilities;
4. knows when, where, why and how those capabilities may be used;
5. selects and composes the smallest sufficient set of capabilities for the present situation;
6. plans, executes and coordinates the resulting behaviour;
7. persists its identity, working state, decisions, execution progress and experience;
8. verifies results against independent outcome and constraint checks;
9. learns from successful, failed, incomplete and changed situations;
10. revises its behaviour through controlled, versioned and reversible evolution.

A habit is therefore the unit that owns the **operating behaviour**. Its model, scripts, tools, skills, procedures, flows, memory, evaluators and adapters are parts of that behaviour system.

## 3. What a habit is not

- Not a static prompt or a set of instructions placed into model context.
- Not merely a skill directory, script, workflow macro or ordered operation list.
- Not only a memory database, vector store, trace archive or decision policy.
- Not a model, model router, tool registry, plugin catalogue or general-purpose agent harness.
- Not a claim that all resources must be copied into one repository or process.
- Not an unrestricted autonomous agent that can expand its own permissions.
- Not a human habit reproduced biologically in software.

A fixed sequence, tool call or reusable skill can be a component or one strategy of a habit. It is not, by itself, the complete concept.

## 4. Habit as an integrated operational system

The following are internal responsibilities of one habit. They may be separate modules and may use replaceable infrastructure, but they belong to the habit's logical identity and lifecycle.

### 4.1 Purpose and outcome contract

Owns the task family, intended outcome, quality floor, required invariants, unacceptable outcomes, resource objectives and abstention/escalation conditions. It distinguishes the user's requested result from a convenient proxy such as fewer steps.

### 4.2 Situation awareness

Collects observations and builds a bounded situation frame: current task, relevant context, environment, state, constraints, available resources, changes, uncertainty and risk. It determines what information is missing and whether further inspection is worthwhile.

A situation frame records its provenance and freshness. A missing observation is not silently treated as a negative observation or as zero cost.

### 4.3 Governed repertoire

Maintains the capabilities and knowledge that the habit can use. Examples include:

- procedural assets: skills, playbooks, scripts, recipes and verified patterns;
- tools: APIs, CLIs, repository operations, file systems, browsers and device interfaces;
- computational assets: libraries, frameworks, runtimes, models and local programs;
- information assets: schemas, datasets, indexes, context packages, reference material and cached results;
- service capabilities: hosted model APIs, cloud services and specialized external providers;
- other habits or bounded sub-habits.

Each repertoire entry declares, as appropriate: stable identity, type, version or digest, source and provenance, owner, license/terms, input/output contract, compatibility, availability/health, required authority, data exposure, cost profile, failure modes, validation status and fallback.

A referenced resource is still part of the habit's governed repertoire. A remote API remains remote in execution and authority; the habit does not claim to own the provider or its infrastructure.

### 4.4 Operational judgement

Owns the logic for deciding:

- whether this habit is applicable at all;
- which observations are necessary;
- which repertoire entries are eligible in this context;
- which strategy or combination is appropriate;
- when to reuse verified knowledge and when to recompute;
- when to inspect more deeply, choose another route, wait, ask for approval, escalate or abstain;
- when previous knowledge is stale, contradictory or unsafe.

Selection may initially use deterministic rules, evidence ranking, bounded heuristics or an explicitly defined decision policy. Learned preference is optional, not a default requirement. A model recommendation is not execution evidence.

### 4.5 Minimal-sufficient composition

Composes only the capabilities needed to meet the outcome contract. It should reuse a validated component where its scope and freshness are valid, and avoid invoking an entire framework, toolchain, model or workflow when a smaller component is sufficient.

Minimality is subordinate to correctness, safety and required coverage. The shortest plan is not automatically the best plan. The objective is to minimize declared total cost subject to quality, reliability, safety and completion constraints.

### 4.6 Planning, flow and execution

Owns the habit's reusable operating strategies and the execution plan for each run. A strategy may be a sequence, guarded procedure, dynamic plan, reusable subflow, parallel composition, cached-result reuse or a combination.

Each execution creates a durable **Habit Episode**. The episode belongs to the habit and records its own progress, decisions, operation intents/results, checkpoints, waits, retries, external callbacks, approvals, pauses, recovery and terminal outcome.

A generic workflow engine, queue, scheduler or event store may implement these mechanics. It is an implementation dependency, not the owner of the habit's meaning, strategy, identity or episode lineage. The habit pins exact versions of its strategy, capabilities and dependencies for an active episode.

### 4.7 Memory and experience

Owns or governs memory required for future behaviour. At minimum, distinguish:

- **Declarative memory:** facts, schemas, environment models and constraints.
- **Procedural memory:** how to perform a task or use a capability.
- **Episodic memory:** what happened in a particular execution, including context, choices, outcomes and evidence.
- **Semantic/relational memory:** learned relationships between contexts, resources, actions, failure modes and outcomes.

Memory must carry provenance, timestamps, scope, confidence/quality metadata, freshness and invalidation rules. Repeated mention or retrieval does not make a memory correct. The system must support correction, consolidation, deduplication, decay or retirement, and explicit preservation of unresolved contradictions.

### 4.8 Verification and evaluation

Owns the outcome contract and declares what evidence can establish that the task succeeded. Execution success responses, model self-assessment, selected-option probabilities and repeated usage are not substitutes for independent verification.

Evaluation covers outcome correctness, required postconditions, safety and policy compliance, reliability, recovery, resource use and user-visible completion. A habit can optimize one cost dimension only while reporting important regressions in the others.

### 4.9 Learning, maintenance and evolution

Uses completed episodes and verified evidence to identify useful patterns, capability gaps, stale assumptions, repeated failures, unnecessary work and opportunities for improvement.

Changes are proposed as candidate revisions. They are tested against matched and held-out cases, checked for regressions, staged in shadow/canary mode when appropriate, then promoted as a new immutable version or rejected. Active versions are never silently mutated. Rollback, quarantine, revocation and retirement are explicit lifecycle operations.

Learning must not reward the habit for its own unverified claims. A proposed improvement requires independent outcome evidence or an explicitly labeled weaker evidence class.

### 4.10 Governance and portability

The habit carries its declared trust, dependency, license, data-handling and permission requirements. The host execution environment remains authoritative for actual credentials, sandboxing, approvals, egress and side-effect permissions. A habit can request and use capabilities only within authority granted by the host; it cannot widen its own authority.

The package must declare compatibility with model providers, tool adapters, host harnesses, operating systems, storage backends and versions. Portability is verified per adapter and contract; it is not inferred from a provider-neutral interface alone.

## 5. Operating loop

~~~text
Purpose and outcome contract
        |
        v
Observe situation -> build provenance-bound situation frame
        |
        v
Check applicability, freshness, risk and missing information
        |
        v
Filter governed repertoire by hard constraints and compatibility
        |
        v
Choose strategy and compose minimum sufficient capabilities
        |
        v
Request/verify host authorization
        |
        v
Execute durable Habit Episode
        |
        v
Observe effects -> independently verify outcome and constraints
        |
        v
Persist episode, evidence, cost and unresolved uncertainty
        |
        v
Consolidate memory -> propose, test and govern improvements
        |
        +----> future situations use the verified active version
~~~

The habit has multiple operating modes:

- **Routine:** use a proven strategy when context and dependencies still match.
- **Deliberative:** inspect, compare alternatives or collect information when novelty, uncertainty or risk is material.
- **Recovery:** resume, reconcile, compensate, switch strategy, escalate or stop according to side-effect semantics.
- **Maintenance:** validate dependencies, prune stale knowledge, evaluate candidate improvements and roll back regressions.

## 6. Logical data model

The names are proposed conceptual contracts, not implemented Python classes.

| Record | Responsibility |
|---|---|
| HabitIdentity | Stable identity, owner, purpose and lineage across versions |
| HabitRelease | Immutable version and complete content/dependency manifest |
| OutcomeContract | Success criteria, invariants, quality floor and abstention rules |
| SituationFrame | Context observations, source, time, freshness, uncertainty and environment identity |
| CapabilityEntry | Repertoire item, adapter, contract, version, trust, constraints and cost |
| KnowledgeAsset | Procedural, declarative, semantic or other versioned knowledge |
| Strategy | Reusable plan or composition of capability references |
| HabitPolicy | Applicability, selection, composition, reuse, fallback and escalation rules |
| HabitEpisode | Durable execution instance tied to exact habit and dependency versions |
| EpisodeEvent | Append-only observation, decision, operation intent/result, checkpoint or lifecycle event |
| MemoryRecord | Consolidated experience with scope, provenance, freshness and evidence links |
| EvidenceBundle | Independent verification, matched trials, measurements and provenance |
| EvaluationReport | Quality, reliability, safety, efficiency and uncertainty assessment |
| EvolutionProposal | Candidate change, rationale, expected effect, affected contexts and rollback plan |
| PromotionDecision | Evidence-gated activation, rejection, quarantine, revocation or retirement |

A HabitRelease is immutable. An Episode is mutable only through append-only events and explicit state reduction. Episode references pin the exact HabitRelease, capability versions, strategy revision, policy revision, context digests and host/harness identity used.

## 7. Durability requirements

Durability means more than saving a chat history or workflow cursor.

1. **Identity continuity:** stable habit identity and release lineage survive process, session and host restarts.
2. **Repertoire continuity:** capability manifests, versions, contracts, provenance and compatibility state are recoverable.
3. **Knowledge continuity:** verified procedural and contextual knowledge is preserved with freshness and scope.
4. **Episode continuity:** in-progress work resumes or reaches a safe reconciliation state after interruption.
5. **Decision continuity:** the system can explain which situation, options, constraints and evidence led to its behaviour.
6. **Evolution continuity:** candidate, active and prior releases remain inspectable and rollback-capable.
7. **Portability:** a habit can be exported and re-bound to another compatible runtime without silently losing meaning, evidence or policy.

The habit must not pretend every dependency is portable. Missing or changed dependencies produce an explicit compatibility failure and a safe fallback or escalation.

## 8. Core invariants

1. A Machine Habit owns its operating behaviour and governed repertoire; no individual skill, tool, model or workflow is the whole habit.
2. Every action is traceable to a purpose, situation frame, applicable policy and capability contract.
3. Hard constraints and host permissions filter capabilities before selection or optimization.
4. Composition uses the smallest sufficient set of eligible capabilities, never at the expense of correctness, quality or safety.
5. Active episodes pin exact habit, strategy, policy and dependency versions.
6. Durable recovery never blindly repeats an external effect whose outcome is unknown and whose semantics do not permit safe replay.
7. Memory and learning retain provenance, scope, freshness and contradictory evidence.
8. Execution success is independently checked against the outcome contract.
9. Candidate improvements cannot mutate an active release; promotion and rollback are explicit.
10. Cost dimensions remain separately inspectable; no opaque score hides quality or safety regressions.
11. A habit cannot expand its own authority or claim provider guarantees that have not been verified.
12. Missing context, unavailable capabilities, stale evidence or uncertainty can lead to inspect-more, fallback, human approval or abstention.

## 9. Reference example: repository change verification

A repository-verification habit owns a purpose (determine whether a specific change satisfies its verification contract), a situation model (repository, branch, base/head commit, changed paths, risk, language, CI state and prior evidence), and a repertoire that may include Git operations, file readers, test runners, linters, type checkers, dependency/license scanners, CI APIs, cached verification evidence and specialist review procedures.

It does not run every tool on every change. It composes a minimal sufficient verification plan:

- documentation-only change: relevant link, formatting and documentation checks;
- isolated source change: inspect affected code and run the most relevant tests, escalating to broader checks based on impact and risk;
- dependency or security-sensitive change: add the applicable dependency, license or security checks;
- exact, fresh CI evidence for the same commit and configuration may be reused; stale or mismatched evidence is rejected;
- ambiguous impact, missing capability or failed verification triggers deeper inspection, broader tests or escalation.

The episode stores the exact commit/context, selected checks, capability versions, commands/API requests, outputs, checkpoints and independent verdict. Across episodes, the habit can learn which checks are predictive and which are wasteful, but only promotes changes after testing on matched and held-out repository cases. This is a design specimen, not an implemented or runtime-enforced habit.

## 10. Relation to existing HabitRoute work

The existing core is an operation-pattern prototype with a harness contract, executor and persistent-flow journal. The synthetic step-savings experiment is an early study of route memory, retention, capacity and adaptation. Both remain valuable evidence and implementation material.

They do not yet implement this complete model. In particular, the current repository does not yet provide the complete governed repertoire, situation intelligence, capability composition, habit-owned durable episode lifecycle, cross-harness migration, full memory model, trace discovery, independent raw-trial evaluation or staged whole-habit evolution described here.

The open per-operation checkpoint work in PR #8 addresses an important execution-durability mechanism. It should be mapped to the Habit Episode model before it is treated as the complete persistence architecture. No PR or implementation status is changed by this document.

## 11. Deliberate non-decisions

This model does not yet choose a universal plugin format, capability marketplace, vector database, workflow engine, policy-learning algorithm, model router, packaging format or cloud provider. Those are replaceable implementation choices. The first implementation should prove the operating model with a narrow reference habit before generalizing the runtime.
