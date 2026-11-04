# HabitRoute Habit Specification v0.1

**Status:** proposed target contract; not yet implemented.
**Purpose:** define what a reusable habit is before changing the execution engine.

## 1. Definition

A HabitRoute habit is a versioned, temporally extended controller that may start only when declared conditions hold, acts toward a declared subgoal, and terminates by success, failure, interruption, timeout, or resource exhaustion. Its applicability is supported by evidence scoped to an environment/context and state-representation version.

The theoretical foundation is the Options abstraction:

~~~text
option = (initiation_set, intra_option_policy, termination_condition)
~~~

HabitRoute extends that abstraction:

~~~text
habit = (identity, scope, initiation, controller, goal, termination, safety, effects, costs, evidence, recovery)
~~~

A habit is not an episode, a route, a planner result, or a certificate. Those are separate entities.

## 2. Controller types

The schema must support multiple controllers. The first implementation can run only fixed macros, but the schema must not force every habit to be an action tuple.

| Type | Behavior | Appropriate when |
|---|---|---|
| fixed_macro | Fixed action sequence with observation checkpoints | The same next action remains appropriate across the plausible states inside the initiation region |
| guarded_sequence | Sequence with condition-based branches and interrupts | A small number of observed branches recur |
| reactive_policy | Chooses each action from current observation/belief and context | The correct next action depends on current state |
| goal_conditioned_policy | Policy receives a target/subgoal parameter | One controller can reach a family of compatible targets |

A macro is valid only where its internal action choices are sufficiently invariant. If plausible successor states require different actions, a fixed sequence is the wrong controller; use a branch or feedback policy.

## 3. Minimum immutable habit version

Each published habit version is immutable. A changed controller, initiation boundary, termination rule, representation, or safety contract creates a new version.

| Field | Required | Meaning |
|---|---|---|
| habit_id / version | yes | Stable identity and immutable version |
| controller_kind | yes | fixed_macro, guarded_sequence, reactive_policy, or goal_conditioned_policy |
| controller_ref | yes | Serialized controller or content-addressed artifact |
| environment_scope | yes | Environment, task mode and context predicates where evidence applies |
| representation_id/version | yes | Exact observation/state abstraction required by this version |
| initiation_contract | yes | Safe start region, preconditions and uncertainty threshold |
| goal_contract | yes | Semantic goal or terminal region, not merely a prototype ID |
| termination_contract | yes | Success, failure, interrupt, timeout and resource conditions |
| safety_contract | yes | State/action constraints and allowed risk envelope |
| effect_model | yes | Distribution over terminal outcomes and duration |
| cost_model | yes | Action, time, resource, lookup, audit and recovery cost estimates |
| evidence_refs | yes | Immutable execution/test evidence references |
| provenance | yes | Parent trajectories/skills, algorithm, code, model and dataset revisions |
| lifecycle_status | yes | candidate, probation, active, at_risk, quarantined, revoked or superseded |

Do not replace these dimensions with one uninspectable confidence score.

## 4. Initiation and representation

### 4.1 Fail closed

A habit is executable only if the observed state or state belief satisfies its safe initiation contract. For probabilistic state inference:

~~~text
P(current_belief in safe_initiation_region | observation, context) >= initiation_threshold
~~~

Nearest-neighbor lookup may suggest candidate habits, but it must not authorize execution. If the representation says unknown, out-of-distribution, ambiguous, or below threshold, the selector must fall back to planning or a separately validated recovery controller.

### 4.2 Predictive sufficiency

A state abstraction must preserve information needed to predict the outcomes that the habit and its safety monitor rely on. If the same abstract cue and action lead to different outcomes due to hidden state, history, context, or stochasticity, one deterministic successor is not a valid invariant.

The engine should support:
- deterministic transitions when justified by evidence and environment contract;
- stochastic outcome distributions when transitions vary;
- belief/context-augmented state when the current abstraction aliases decision-relevant situations;
- explicit unknown/OOD results.

Encoder or prototype changes require a new representation version. Existing habit versions must be suspended until a validated migration or revalidation is available.

## 5. Execution and termination

Each controller step receives a fresh observation unless the controller's observation schedule has itself been justified and certified. Fixed macros still require runtime guards and interruption points.

Termination causes are distinct:

- SUCCESS: semantic goal contract satisfied;
- FAILURE: expected behavior contradicted or continuation is no longer valid;
- INTERRUPTED: safety monitor, context change, higher-level policy or user interrupts;
- TIMEOUT: time or primitive-step budget exhausted;
- RESOURCE_LIMIT: energy, memory or other declared budget exhausted;
- UNKNOWN: current state cannot be classified within the accepted representation envelope.

A mismatch is evidence of a discrepancy, not automatically proof of a regime change. It may be caused by a slip, observation noise, state aliasing, model error, or persistent transition change.

## 6. Composition

A route is an ordered or graph-structured composition of habit versions. Exact endpoint-prototype equality is too brittle as the long-term composition contract.

Link habit A to habit B only when A's terminal-outcome distribution is compatible with B's safe initiation region:

~~~text
P(terminal_outcome_of_A is inside safe_initiation_of_B | context) >= composition_threshold
~~~

Use a conservative confidence bound for this gate, not only a point estimate. Every link records the A and B versions, scope, compatibility evidence, uncertainty, and fallback.

High-level route planning must account for the duration and outcome distribution of each option. A route is not optimal merely because it uses fewer options.

## 7. Evidence and certificate

A certificate is an empirical applicability attestation, not a formal safety proof unless a separate formal-verification process establishes that claim.

It applies to one exact habit version and declares:
- habit_id and habit_version;
- controller and safety-contract hashes;
- environment/context scope and revision;
- state-representation ID/version;
- initiation region and tested operating envelope;
- goal/termination contract;
- run/evidence references and provenance;
- success, failure, interruption and timeout outcomes;
- duration/cost distribution;
- calibrated reliability/risk estimate and uncertainty;
- issue, expiry, suspension and revocation conditions.

A context-local change must not erase valid historical evidence for an unrelated context. A new certificate is required for a new habit version or scope.

## 8. Evidence ledger

Keep an append-only execution/event ledger separate from mutable indexes and derived summaries. At minimum, each event records:

- run/event ID and logical time;
- habit ID/version and controller step;
- context and representation version;
- initiation confidence and relevant state features;
- action selected and predicted outcome distribution;
- observed outcome and observation confidence;
- termination cause and safety-monitor result;
- task reward, duration, resource and recovery cost;
- change-detector evidence and decision;
- code, model, dataset and task-schedule provenance.

Summary counts and posterior estimates must be reproducible from this ledger.

## 9. Lifecycle and admission

Recommended lifecycle:

~~~text
CANDIDATE -> PROBATION -> ACTIVE -> AT_RISK -> QUARANTINED -> REVALIDATING -> ACTIVE
                                  |                                  |
                                  +----------> REVOKED <-------------+
~~~

Admission rules:

1. A candidate comes from observed experience or an explicit discovery process.
2. A planner prediction alone does not make a candidate trusted.
3. Probation requires executed evidence that satisfies initiation and goal contracts.
4. Promotion requires sufficient context coverage and a calibrated lower confidence bound appropriate to task criticality.
5. A single successful start/end pair does not certify a whole region.

Quarantine on a strong change signal, repeated predictive contradictions, context/representation mismatch, goal-contract failure, or safety/resource violation. Preserve all old evidence. Reactivation requires a new scoped validation result.

## 10. Discovery and segmentation

Do not turn every contiguous subsequence of every successful path into an equally selectable habit. A length-L path can generate L(L+1)/2 overlapping records, increasing memory and lookup load without guaranteeing additional reusable behavior.

Discover candidate skill boundaries at:
- stable subgoal/landmark regions;
- points where action choice changes or branches;
- points where prediction uncertainty rises;
- regions from which the same continuation works across varied successor states;
- reusable behavior boundaries with repeated evidence.

Track episode memory, transition evidence, habit definitions and certificates separately. They have different lookup, retention and provenance needs.

## 11. Cost and value

Keep these measures separate before any weighted score is used:
- primitive action count;
- elapsed-time and option-duration distribution;
- resource/energy usage;
- task reward/goal value;
- probability and severity of failure;
- expected interruption and recovery cost;
- safety/constraint risk;
- planning, lookup and audit computation;
- memory and maintenance cost.

The current cost len(actions) + lambda_per_habit remains a control. The long-term route objective should expose task-dependent weights and report each cost component instead of silently equating shorter action count with lower total cost.

## 12. Non-negotiable invariants

1. No habit executes unless the initiation contract passes.
2. Unknown/OOD observations do not authorize habits by nearest-neighbor fallback.
3. Every running habit is interruptible under its declared safety, context, failure and budget guards.
4. Planner predictions are not empirical verification.
5. Certificates refer to exact immutable habit versions and explicit scopes.
6. Old evidence is retained; context-local invalidation does not erase unrelated evidence.
7. Deterministic single-successor invariants are used only when the environment and abstraction justify them.
8. Composition requires measured terminal-to-initiation compatibility.
9. Dominance proofs use only currently admissible, sufficiently reliable replacement behavior.
10. Experiments record code, representation, environment, seed, context and task/policy versions.

## 13. Promotion gates

- [ ] OOD initiation tests fail closed.
- [ ] Hidden-state aliasing cannot create false deterministic certificates.
- [ ] At least one stochastic transition benchmark is supported.
- [ ] Fixed macro and reactive option are compared on branch and non-branch tasks.
- [ ] Composition uses terminal-region compatibility and uncertainty bounds.
- [ ] Certificates are immutable, per-habit-version and scope-aware.
- [ ] Pruning cannot use invalid habits as dominance witnesses.
- [ ] Slip, burst noise, regime change and representation drift are evaluated separately.
- [ ] Existing experiment suite remains reproducible as a legacy baseline.