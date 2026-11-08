# Unified Agent Runtime — integration decision under Machine Habit v0.3

**Decision date:** 2026-11-08  
**Status:** proposed boundary revision; CPM import remains unimplemented  
**Host repository:** Loofy147/HabitRoute  
**Canonical product model:** [Machine Habit Model v0.3](MACHINE_HABIT_MODEL_V0.3.md)

## 1. Decision

Evolve HabitRoute into a modular repository that can host the Machine Habit system, Context Package Manager (CPM) and a thin host/runtime integration. The Machine Habit remains the primary behavioural unit.

Under v0.3, CPM is one possible context-management capability in a habit's governed repertoire. The habit owns its purpose, situation model, context requirements and decision about when/how to use CPM. CPM can implement package resolution, retrieval, progressive disclosure, budgeting, manifests and caching. It does not own the habit's operational judgement or identity.

Packages may remain separately installable and stores may remain separate. These are replaceable implementation boundaries, not a semantic rule that skills, context or other capabilities are outside the habit.

## 2. Product and infrastructure responsibilities

| Element | Role in the system | Boundary |
|---|---|---|
| Machine Habit | Owns purpose, situation awareness, governed repertoire, capability-use behaviour, composition, strategies, episodes, memory, verification and evolution | Cannot grant itself host permissions or claim ownership of remote provider infrastructure |
| CPM | Provides context/package registry, retrieval, progressive disclosure, budgeting, manifests and cache as a capability | Does not decide the habit's overall strategy or own habit identity/episodes |
| Host Agent / Runtime | Submits tasks, supervises execution, provides runtime services and can coordinate multiple habits | Must not silently rewrite a habit release or bypass its own security controls |
| Host Harness / Environment | Enforces credentials, sandbox, egress, approvals, quotas and actual tool execution constraints | Its permissions are authoritative; the habit's declared policy is not a security boundary |
| Capability adapters | Bind repertoire entries to models, APIs, CLIs, scripts, frameworks, context services and other implementations | Must expose versioned contracts and explicit effect/failure semantics |
| Evidence verifier | Independently checks outcomes, invariants, experiments and release gates | Must not accept the executor's success claim as sufficient evidence |

## 3. Five integration invariants

1. **Habit ownership:** the habit owns the logical repertoire, context needs, capability-use policy, strategies and episode lineage.
2. **Replaceable implementation:** CPM, model providers, tools, workflow engines, storage and host harnesses can be replaced through versioned contracts when compatibility is demonstrated.
3. **Acyclic packages:** CPM and the HabitRoute package may remain independently importable; neither needs a private import from the other. The habit can call CPM through a public adapter.
4. **Provenance and authority separation:** manifests may record context digests, capability IDs, habit releases, evidence IDs and host identities. These references do not grant authority.
5. **Independent verification:** context optimization or capability reuse cannot waive host authorization, output contracts, postconditions or recovery constraints.

## 4. Logical repository layout

The current root-level HabitRoute package should be preserved until a behavior-preserving move is proven. The target may add:

~~~text
HabitRoute/
├── src/habitroute/                  # existing core; migrate only with tests
├── tests/
├── experiments/step_savings_v1/     # preserved legacy experiment
├── packages/
│   └── contextpm/                   # independently installable CPM source
├── runtime/
│   └── unified_agent_runtime/       # optional host composition and scheduling
├── shared/
│   ├── contracts/                   # versioned, language-neutral schemas
│   └── evidence/                    # evidence formats and validators
├── benchmarks/
│   ├── habit_repertoire/
│   ├── habit_execution/
│   └── cross_runtime/
└── docs/
~~~

This is a logical target, not a mandate to import CPM before the Machine Habit package and episode contracts are settled.

## 5. Context-to-habit flow

1. The host submits a task and its available context references.
2. The habit decides whether it applies and what observations/context it needs.
3. The habit may use CPM or another context capability to resolve those needs.
4. It records the returned context manifest ID/digest, source, accounting method and freshness.
5. The habit selects and composes capabilities under its own outcome contract and policy.
6. The host harness enforces actual authority for the episode.
7. Independent verification checks the result; the episode records outcomes and cost.
8. The habit may later use verified experience to propose an update.

A context item being loaded does not prove it contributed to success. A smaller context footprint does not prove lower provider-reported token use or preserved quality.

## 6. CPM import constraints

Retain the existing CPM v0.5.0 source pin, package names, CLI entry points, upstream tests and provenance review from CPM_INTEGRATION_PLAN.md. Exclude machine-specific runtime state and caches. Check every imported skill, dependency and artifact license/notice. Treat the declared MIT metadata as an assertion to verify, not a substitute for source provenance.

The original CPM verification findings remain relevant: container isolation was not proven, fixture quality was not a live semantic evaluation, and byte-count savings were not provider-reported token savings.

## 7. First integration mode

Begin with read-only context resolution and explainable dry-run composition. The first reference habit must demonstrate complete repertoire and episode contracts before a general side-effecting unified runtime is built.

No integration is considered complete without:
- independent operation when CPM is absent;
- independent operation of CPM when HabitRoute is absent;
- public-contract-only integration tests;
- pinned source and dependency manifests;
- exact context/capability provenance per episode;
- host permission-denial tests;
- evidence that context and capability choices improve outcomes on matched cases.

## 8. Decision consequences

- HabitRoute remains the host repository.
- CPM is a capability provider, not the owner of habit context judgement.
- The habit decides what context it needs and when/how to request it.
- Package and store separation remains a deployment choice.
- The existing synthetic route experiment remains unchanged and limited to its tested conditions.
- No automatic side-effecting composition is permitted before episode recovery, adapter authorization and independent verification gates pass.
