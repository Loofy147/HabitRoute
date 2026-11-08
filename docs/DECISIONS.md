# Decisions and open questions

New evidence may supersede a decision. Superseded decisions remain visible with their original rationale and affected implementation history.

## D-001 — Preserve the experiment as a separate baseline

**Status: accepted**

Keep the executable synthetic research harness under experiments/step_savings_v1/. Do not rewrite its behavior while building the broader machine-habit system.

## D-002 — Preserve usage utility as the legacy default

**Status: accepted for the legacy experiment**

The existing experiment keeps usage utility as its default. Step-savings remains an opt-in capacity policy because gains are not uniform across capacity and repeated-change conditions. Do not extrapolate that policy into a universal habit selector.

## D-003 — Machine habits are execution optimizations, not skills

**Status: superseded by proposed D-012**

The prior decision defined a habit as a reusable operation pattern. That model was too narrow: it explicitly excluded skills, knowledge, situation awareness, composition and the broader operating system. Preserve the original implementation and experiment as a historical foundation, not as the complete product definition.

## D-004 — Separate habits, harnesses and persistent flows

**Status: superseded by proposed D-012 and D-014**

The prior separation incorrectly made the habit only a reusable pattern while placing execution progress and supporting capabilities outside it. The useful technical boundaries remain: host permissions, adapters, workflow mechanics and storage can be replaceable. Their implementation boundaries must not fragment the habit's logical ownership of behaviour and episodes.

## D-005 — Efficiency is a gated claim

**Status: accepted; extended by proposed D-012**

Fewer steps or calls alone do not prove improvement. Promotion requires the outcome contract and safety constraints to pass, independent verification, reliability within declared tolerances and improvement in a predeclared cost objective on comparable cases. Report quality and cost dimensions separately.

## D-006 — Persistent progress is separate from reusable procedures

**Status: superseded by proposed D-014**

Definitions and releases must remain immutable and separate from mutable execution episodes. However, the episode is logically owned by the habit whose behaviour it records. A generic flow engine may implement event storage and recovery; it does not own the habit's semantic identity, policy or episode lineage.

## D-007 — Side-effect retries require idempotency or compensation

**Status: accepted**

A durable journal cannot by itself guarantee exactly-once effects in an external system. Operations must be classified and retried only under a documented and verified idempotency, deduplication or compensation contract. Unknown non-repeatable outcomes require reconciliation or escalation.

## D-008 — Preserve the option-oriented prototype as historical research

**Status: accepted**

The prior contracts.py and execution.py files and their tests remain available for research comparison. They are not the full definition of a Machine Habit. Their useful concepts may be re-evaluated when supported by evidence.

## D-009 — HabitRoute is the host repository for CPM integration

**Status: accepted as repository direction; product boundaries superseded by proposed D-013**

Evolve the existing Loofy147/HabitRoute repository into the modular monorepo. Preserve CPM as independently installable where practical. CPM can provide context and package-management capabilities to a habit; it does not own the habit's purpose, context judgement, operating strategy or identity.

## D-010 — Keep CPM and HabitRoute responsibilities and stores independent

**Status: superseded by proposed D-013**

Independent package boundaries and stores remain valid implementation choices. The prior semantic boundary was too restrictive: HabitRoute must own its context needs and decide when/how to use a context capability such as CPM. CPM may provide retrieval, packaging, budgeting and cache mechanisms. Package separation does not mean the capability is external to the habit's governed repertoire.

## D-011 — MIT license for HabitRoute repository

**Status: accepted**

The repository-level MIT license remains in effect. Imported components and dependencies require their own provenance, license and notice review; the repository license does not override third-party terms.

## D-012 — The Machine Habit is the integrated unit of operating behaviour

**Status: proposed; pending review**

A Machine Habit is a durable, versioned operational system that owns its purpose, outcome contract, situation awareness, governed capability and knowledge repertoire, operational judgement, minimal-sufficient composition, strategies, execution episodes, memory, verification, learning, governance and portability. Skills, tools, models, frameworks, scripts, APIs, data, services and sub-habits are components of its repertoire, whether embedded or referenced. No individual component is the whole habit.

## D-013 — Capability ownership is logical, not necessarily physical

**Status: proposed; pending review**

A habit owns the manifest, purpose, applicability, compatibility, use policy, provenance, configuration and lifecycle of each capability it relies on. Assets can be bundled, referenced, installed or remotely provided. The habit decides what it needs and when/how to use it. Shared infrastructure such as CPM can implement a capability without becoming the owner of the habit's behaviour.

## D-014 — Habit Episodes own durable progress

**Status: proposed; pending review**

Each execution creates a Habit Episode tied to an exact immutable habit release and pinned strategy/capability versions. The episode owns situation, decisions, operation intent/results, checkpoints, retries, waits, recovery, evidence and terminal outcome. A generic workflow engine or event store may implement episode mechanics, but the habit owns their semantic lineage. Cross-habit workflows may coordinate episodes without replacing them.

## D-015 — Compose the smallest sufficient capability set

**Status: proposed; pending review**

A habit should use the smallest eligible and validated set of repertoire components that can satisfy the outcome contract. Hard quality, safety, reliability and coverage constraints precede cost minimization. Neither step count nor tool count is a sufficient optimization objective.

## D-016 — Host authority remains authoritative

**Status: proposed; pending review**

A habit may declare and request the narrow capabilities needed for an episode, but actual credentials, sandboxing, approvals, egress, quotas and side-effect authority remain enforced by the host execution boundary. A habit cannot widen its own permissions or treat its internal policy as a security boundary.

## D-017 — Whole-habit learning is controlled and reversible

**Status: proposed; pending review**

Episodes provide experience, not automatic proof. Candidate changes to repertoire, procedures, policies, memory and composition must be evaluated against independent outcome evidence, matched and held-out cases, and explicit safety/quality gates. Active releases remain immutable. Promotion, rollback, quarantine, revocation and retirement are explicit.

## Open questions

- What minimum package manifest is sufficient to reproduce a habit's identity and behaviour across runtimes?
- Which capability classes need executable adapters versus declarative assets?
- What is the smallest useful common input/output and authority contract for heterogeneous capabilities?
- How should a habit decide whether to inspect more, reuse evidence, invoke a model or abstain?
- Which parts of declarative, procedural, semantic and episodic memory should be stored together, and which should use separate backends?
- What evidence links a context/capability choice causally to a successful outcome?
- How should the system detect context drift, capability degradation and stale memory before a failure?
- What are the episode and event consistency guarantees required for local, transactional and distributed execution?
- Which existing workflow, memory and decision systems should be integrated rather than reimplemented?
- What benchmark can establish improvement over a strong skill-equipped host agent and persistent-agent baseline?
- What degree of cross-harness portability can be proven, and which bindings must be revalidated?
