# Architecture: integrated Machine Habit v0.3

**Status:** proposed architecture; implementation not yet aligned  
**Canonical product model:** [Machine Habit Model v0.3](MACHINE_HABIT_MODEL_V0.3.md)

## 1. Architectural premise

The Machine Habit is the primary behavioural unit. It owns the operating logic and governed repertoire required to respond to a class of situations: purpose, context awareness, knowledge, skills, tools, frameworks, models, procedures, strategy, execution, memory, verification and controlled evolution.

These responsibilities may be implemented as modules and may use external providers. They are nevertheless part of one logical habit identity and release. A tool registry, skill directory, workflow engine, context manager or memory database is not the habit by itself.

## 2. Logical topology

~~~text
Host Application / Agent Runtime
    |  request, lifecycle supervision, available host context
    v
Machine Habit (versioned behavioural unit)
    |
    +-- Purpose and outcome contract
    +-- Situation awareness and context needs
    +-- Governed capability and knowledge repertoire
    |     +-- skills / scripts / procedures
    |     +-- tools / APIs / CLIs / device interfaces
    |     +-- models / frameworks / libraries / runtimes
    |     +-- datasets / context packages / indexes / services
    |     +-- bounded sub-habits
    |
    +-- Applicability, judgement and composition
    +-- Strategies and durable Habit Episodes
    +-- Memory, experience and evidence
    +-- Independent verification contract
    +-- Learning, release management and rollback
    |
    v
Capability adapters and persistence backends
    |
    v
Host execution boundary (credentials, sandbox, approval, egress)
    |
    v
External operations and observed effects
    |
    v
Evidence capture and verification -> habit memory/evaluation
~~~

The drawing shows logical ownership, not a requirement to place all components in one process. Capability implementations, persistence stores and execution providers remain replaceable dependencies.

## 3. Primary entities

### Machine Habit package

The immutable release manifest identifies the habit purpose, outcome contract, applicable contexts, repertoire entries, knowledge assets, policies, strategies, memory schema, evaluation requirements, authority requirements, compatibility and provenance. The habit may embed assets or pin external resources by version/digest.

### Habit runtime

The runtime interprets the package. It observes the situation, checks applicability, resolves capability and knowledge needs, selects a strategy, composes a minimal sufficient plan, requests authorized execution, observes outcomes, verifies and records experience.

Routine execution may use a proven default. Novel, uncertain, degraded or high-risk situations trigger deeper inspection, alternatives, approval or abstention.

### Habit Episode

An episode is the durable instance of one habit operating on one situation. It pins the exact habit release and capability versions, records the situation frame and decisions, and owns progress through operation intent/result records, checkpoints, waits, retries, recovery and terminal outcome.

A generic flow/workflow engine may provide execution mechanics. The episode and its semantic lineage still belong to the habit. An external flow can coordinate multiple habits, but it must not own or erase the internal behaviour and episode history of each habit.

### Capability adapter

A capability adapter binds a repertoire entry to its actual implementation: skill runtime, CLI, API, framework, local program, model service or other resource. It declares input/output contracts, versions, availability, cost, required authority, side effects, failure semantics and verification expectations.

### Host execution boundary

The host harness or execution environment enforces actual credentials, permissions, sandbox, approvals, egress, quotas and side-effect controls. HabitRoute can declare and request the narrowest necessary capabilities; it cannot create authority by declaring it in a habit manifest.

### Evidence and verifier

Evidence links the situation, decision, exact capability versions, operation outcomes, output checks, cost and user-visible completion. Verification must not rely only on the executor or model's own success assertion.

## 4. Operating sequence

1. Receive a task and determine whether the habit is in scope.
2. Gather only the observations needed to characterize the current situation.
3. Check context freshness, dependency health, constraints and uncertainty.
4. Filter repertoire entries by capability contract, compatibility, trust, budget and host authority.
5. Select a proven strategy or deliberate over alternatives.
6. Compose the smallest sufficient set of capabilities for the outcome contract.
7. Create a version-pinned durable Habit Episode.
8. Execute through authorized adapters; commit intent and result/checkpoint records according to side-effect semantics.
9. Verify outputs, effects, quality and constraints independently.
10. Record cost, outcome, uncertainty and provenance.
11. Consolidate experience and propose improvements separately from active execution.
12. Evaluate, stage, promote or reject a new immutable release; monitor and roll back when required.

## 5. Capability repertoire and composition

Every capability entry should define, where applicable:

- stable ID and type;
- source, owner, license and provenance;
- pinned version, digest or provider revision;
- purpose and applicability conditions;
- input/output schema and expected semantics;
- required permissions and data exposure;
- dependencies, compatibility and runtime requirements;
- availability, health, timeout and failure modes;
- latency, calls, compute, token/context and external cost;
- retry, idempotency, deduplication and compensation semantics;
- test and verification evidence;
- fallback or replacement capability.

A remote resource can be included in the repertoire by a pinned contract and adapter. The habit does not claim to own the remote provider, and a generic interface does not prove cross-provider equivalence.

Composition follows hard constraints first. The system then seeks minimum sufficient capability coverage under the declared outcome contract. Fewer operations, tools or tokens are not acceptable when they reduce quality, omit a required check or increase risk.

## 6. Memory and learning

Memory is structured by purpose, not a single undifferentiated transcript:

- declarative: facts, schemas, environment models and constraints;
- procedural: verified methods and capability-use patterns;
- episodic: specific situations, decisions, operations and outcomes;
- semantic/relational: relationships among context, capabilities, failures and outcomes.

Every memory has provenance, scope, freshness, validity conditions and correction/retirement semantics. Episodes remain append-only evidence; consolidation creates separately versioned memory assets.

Candidate learning must be separated from active behaviour. Use matched cases, held-out tests, independent verification, shadow/canary rollout where appropriate, and explicit promotion/rollback decisions. Never silently mutate an active release.

## 7. Durability and recovery

Habit identity, repertoire manifests, knowledge, decision policies, episodes, evidence and evolution lineage must survive process/session restart. An active episode pins exact versions so that a deployment cannot silently substitute a changed tool or strategy during recovery.

For external effects, journal durability is not an exactly-once guarantee. Operations require read-only/idempotent/deduplicated/compensatable/non-repeatable classification. Unknown outcomes require provider reconciliation, safe deduplication, compensation where proven, or human intervention. Do not retry a non-repeatable effect blindly.

## 8. Integration boundaries

- **CPM:** optional capability for context-package resolution, retrieval, budgeting, progressive disclosure and caching. The habit owns its context needs and decides when/how CPM is used.
- **Agent Skills:** an interoperable format for procedural assets; skills may be embedded or referenced in the habit repertoire. A skill alone is not the whole habit.
- **Models:** capabilities selected by the habit according to task needs, policy, provider availability, evaluation and budget; the model does not define habit identity.
- **Workflow engines:** optional persistence/orchestration backends for episode execution. They do not own habit meaning or learning.
- **Claude Code, Codex or other agent hosts:** execution environments or supervisors that provide tools and enforce their own security boundaries. HabitRoute should integrate through adapters rather than recreate each product.
- **External verifiers:** may evaluate outputs, invariants or policy compliance; their identity and evidence must be recorded.

## 9. Mapping to current repository code

| Current component | Role under the proposed model | Status |
|---|---|---|
| MachineHabit in machine.py | One narrow operation strategy and scope contract | Implemented prototype; incomplete |
| HarnessProfile / HarnessAdapter | Capability/host binding and execution contract | Partial; no production enforcement adapter proven |
| flows.py / FlowWorker | Durable episode execution primitives | Partial; must be mapped to HabitEpisode semantics |
| HabitRegistry | Versioned habit package/release registry | Current registry is in-memory; durable package registry absent |
| step_savings_v1 | Early experiment in memory retention and route efficiency | Synthetic evidence only |
| contracts.py / execution.py | Earlier option/route research prototype | Historical, non-canonical |

The current core is not an implementation of the complete v0.3 model. The open PR #8 operation-checkpoint work is still a draft and should be evaluated as an episode-durability component, not treated as the entire durability solution.

## 10. Core invariants

1. The habit owns its operating behaviour and governed repertoire.
2. Every selected capability is traceable to a situation, purpose, policy and pinned contract.
3. Hard compatibility, trust, safety and authority constraints precede optimization.
4. Capability composition is minimum-sufficient under correctness and quality constraints.
5. Every episode pins exact habit, strategy, policy and capability versions.
6. Replaying committed history does not repeat completed side effects.
7. Unknown non-repeatable effects require reconciliation or escalation.
8. Memory retains source, scope, freshness, uncertainty and contradictory evidence.
9. Independent verification gates promotion.
10. Active releases are immutable; candidate evolution is staged and reversible.
11. Cost and quality dimensions remain inspectable separately.
12. Missing context or capability can produce fallback, approval, or abstention—not fabricated success.
