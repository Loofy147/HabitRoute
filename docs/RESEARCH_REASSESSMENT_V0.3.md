# HabitRoute research reassessment v0.3

**Date:** 2026-11-08  
**Status:** Evidence review supporting the proposed Machine Habit Model v0.3  
**Scope:** machine behaviour, human habit mechanisms as a limited analogy, persistent agent systems, procedural memory, decision policies, capabilities and durable execution.

## 1. Research question

Can HabitRoute define and build a durable Machine Habit as one operational unit that owns its purpose, situational judgement, capability repertoire, compositional behaviour, persistent episodes, experience and evidence-governed evolution?

This is a more demanding question than whether habits, skills, memory, decision policies, workflow persistence or tools already exist. Those components are established areas. The question concerns their ownership and behaviour as one versioned, portable and continuously maintained operating unit.

## 2. Human habit research: useful principle, not literal implementation

Human habit research commonly describes learned cue/context-response associations that can make recurring actions more automatic and less deliberative. The useful engineering analogy is that a machine should not repeatedly solve a stable, proven operating problem from scratch. It should recognize a suitable context and activate a reliable default.

The analogy has limits. Human habits are context-dependent, can become maladaptive when goals or circumstances change, and are not simply immutable procedures. HabitRoute should therefore preserve useful defaults while checking context, freshness, outcome and risk. Machine behaviour must be specified through machine-observable contracts and evidence, not inferred from human biology.

Background sources:
- Wood and Rünger, Psychology of Habit, Annual Review of Psychology (2016): https://doi.org/10.1146/annurev-psych-122414-033417
- Lally et al., How are habits formed: Modelling habit formation in the real world, European Journal of Social Psychology (2010): https://doi.org/10.1002/ejsp.674

## 3. Existing technical prior art

The field already contains important pieces of the proposed system. These are close comparisons, not strawmen.

| System / research | Established capability | What it does not establish by itself |
|---|---|---|
| Agent Skills specification | A standard package shape for reusable instructions, scripts, references and assets, with progressive disclosure and metadata. https://agentskills.io/specification | A complete durable operating identity, episode runtime and whole-system evolution. |
| Letta stateful agents | Persistent agent identity, shared memory, model/tool configuration and message history across sessions and computers. https://docs.letta.com/concepts/stateful-agents | A universal, provider-independent Machine Habit package with independently verified whole-behaviour portability. |
| Letta skills | Agent-scoped skills can live in the agent's persistent memory and become part of that agent's identity. https://docs.letta.com/configuration/skills | This is a strong counterexample to the claim that no one embeds capabilities in a persistent agent. It does not, on its own, prove the exact HabitRoute operating contract. |
| Microsoft agent-learning | A persistent TaskPolicy over executable alternatives, outcome episodes, evidence-based resolution, and inspectable policy updates. https://github.com/microsoft/agent-learning | The complete repertoire, situational system, execution lifecycle and portability of a whole operating habit. |
| Memp (Findings of ACL 2026) | Procedural memory distilled from trajectories into reusable instructions and scripts, with ongoing update, correction and deprecation; experiments on TravelPlanner and ALFWorld report improved analogous-task success/efficiency and cross-model transfer. https://aclanthology.org/2026.findings-acl.866/ | General-purpose operational portability, provider-side side-effect guarantees or all-domain evidence; results are benchmark-scoped. |
| Temporal and durable workflow engines | Durable workflow state, event history, retries, replay and recovery mechanisms. https://docs.temporal.io/ | The meaning, capability repertoire, judgement and learning policy of a habit. Durable orchestration does not itself prove correct external side effects. |

These systems invalidate simple novelty claims such as:
- nobody builds persistent agents;
- nobody stores skills inside an agent identity;
- nobody learns procedures from execution traces;
- nobody records reusable decision policies and outcomes;
- nobody provides durable workflow recovery.

HabitRoute must compare against these systems directly. It should reuse compatible mechanisms where that is more reliable than rebuilding them.

## 4. Proposed research gap — still a hypothesis

**HYPOTHESIS:** A useful remaining design target is a first-class Machine Habit whose immutable release owns or governs the complete operating repertoire and whose runtime owns the relationship between:

1. purpose and outcome contract;
2. context/situation awareness;
3. internal knowledge and capability repertoire;
4. capability applicability, selection and minimal-sufficient composition;
5. planning, durable execution and recovery;
6. episodic, procedural, declarative and semantic memory;
7. independent verification and cost accounting;
8. evidence-based learning, versioned evolution and rollback;
9. authority and compatibility contracts across execution environments.

The differentiator, if validated, is not that every mechanism is new. It is that the habit is the durable behavioural unit that owns and coordinates these mechanisms, can survive changes of model/tool/harness/backend through explicit adapters, and can demonstrate that its whole behaviour improves over time.

This is not yet a claim that no competitor implements the same integrated model. A broader implementation-level market and code audit is required before any exclusivity or novelty statement.

## 5. What existing HabitRoute evidence supports

The repository's step-savings experiment provides early, limited evidence about machine-memory economics:

- In synthetic 12-state and 24-state environments, step-savings retention improved some capacity-limited route outcomes relative to usage utility.
- The effect was not universal across capacity settings and policy weights.
- Repeated transition rewiring exposed late-cycle trade-offs; in the 24-state world, the selected weight reduced planner calls and measured staleness but did not improve every route-quality outcome.
- The report uses eight paired seeds and descriptive directional comparisons, not formal significance tests.
- The experiment does not test real APIs, model/tool use, provider failures, full habit portability, or durable recovery.

Primary artifacts:
- https://github.com/Loofy147/HabitRoute/blob/main/experiments/step_savings_v1/RESULTS_REPORT.md
- https://github.com/Loofy147/HabitRoute/blob/main/experiments/step_savings_v1/REPEATED_CHANGE_ANALYSIS.md
- https://github.com/Loofy147/HabitRoute/blob/main/experiments/step_savings_v1/SENSITIVITY_ANALYSIS.md

**Conclusion:** preserve this as an initial controlled experiment on retention and route reuse. Do not generalize it to the complete Machine Habit Model.

## 6. Required comparative experiment

A first reference habit should be evaluated against at least these conditions:

1. baseline host agent with no reusable habit;
2. host agent with a static instruction/skill package;
3. host agent with ordinary tools and framework integrations but no habit-owned experience;
4. prior HabitRoute operation-pattern implementation;
5. proposed integrated habit with its repertoire, situation model, composition, episodes and evidence-based learning.

Use matched tasks and environments, repeated seeds where stochasticity exists, held-out cases and exact source/configuration provenance.

Measure separately:
- outcome correctness and quality;
- required postcondition and safety-constraint violations;
- task completion and recovery outcome;
- capability-selection precision and recall (whether required capabilities were selected and unnecessary ones avoided);
- composition size and avoidable operations;
- latency, model calls, tool/API calls, tokens, context/retrieval work, compute, external spend and memory/storage;
- retries, failed operations, recovery time and human intervention;
- adaptation after context, tool, model, schema or environment change;
- stale-memory reuse, false reuse, unnecessary rediscovery and capability-unavailability handling;
- crash/restart recovery, replay safety and cross-harness compatibility.

Do not collapse these measures into one score unless the weights and hard constraints are declared.

### Ablations

Remove one subsystem at a time: situation awareness, governed repertoire, selector, composition, memory, durable episode state, verification or controlled evolution. This tests whether each subsystem contributes to the claimed performance rather than merely increasing architecture size.

### Durability tests

- restart the process between operation intent and result;
- make an external side effect succeed while its acknowledgement is lost;
- duplicate a delivery;
- remove or change a capability version;
- change the model provider or harness;
- expire context and cached evidence;
- invalidate a schema or dependency;
- present a situation outside the habit's scope;
- inject contradictory historical evidence;
- roll back a candidate that regresses on a held-out case.

The correct result may be recovery, fallback, abstention or human intervention—not always autonomous success.

## 7. Evidence labels for product claims

- **ESTABLISHED:** directly supported by a cited paper, implementation, test or measured artifact.
- **EXPERIMENTALLY_SUPPORTED:** observed under a declared experiment with its limits.
- **INFERENCE:** follows from multiple findings but is not directly demonstrated.
- **HYPOTHESIS:** a proposed differentiator or causal explanation requiring a test.
- **UNKNOWN:** not established by the inspected evidence.
- **CONTRADICTED:** inconsistent with inspected evidence.

Do not describe an architectural diagram as an implemented capability. Do not describe an open PR as merged or a synthetic result as production performance.

## 8. Research decision

Proceed with the integrated Machine Habit as the product hypothesis. First validate the model with one reference habit and a comparative benchmark. Do not expand the runtime or claim novelty until the end-to-end behaviour has been demonstrated and compared with the systems above.
