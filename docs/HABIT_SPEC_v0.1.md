**Historical design notice (2026-11-08):** This document records the earlier v0.2 operation-pattern model. It is retained for provenance and reusable engineering details, but it is no longer the canonical product definition. The proposed integrated model is [Machine Habit Model v0.3](MACHINE_HABIT_MODEL_V0.3.md), with topology in [Architecture](ARCHITECTURE.md) and prior-art analysis in [Research Reassessment v0.3](RESEARCH_REASSESSMENT_V0.3.md). Do not interpret the older separation of habit, harness and flow as the v0.3 ownership model.

# Machine Habit Specification v0.2

**Status:** corrected canonical target model.  
**Supersedes:** the earlier option/skill framing of this specification.  
**Scope:** efficient recurring machine operations, not human habit psychology or reinforcement-learning skills.

## 1. Definition

A machine habit is a reusable, versioned operation pattern that performs a recurring machine task more efficiently than its baseline while preserving the required outputs, side effects, postconditions and operational constraints.

A habit is an **execution optimization artifact**. It does not own long-lived workflow progress. Persistent flows own progress; execution harnesses own operation control and verification.

## 2. Minimum MachineHabit record

| Field | Required | Meaning |
|---|---|---|
| `habit_id`, `version` | yes | Stable identity and immutable version |
| `harness_id`, `harness_version` | yes | Execution environment/contract where validated |
| `environment_scope` | yes | Environment, machine, tenant, project or context constraints |
| `trigger_contract` | yes | Recurring operation/task signature that makes the habit a candidate |
| `input_contract` | yes | Required inputs, parameter types and binding rules |
| `preconditions` | yes | Required state before execution |
| `operation_pattern` | yes | Ordered operations, parameter bindings, and permitted branches |
| `postconditions` | yes | Required output and side-effect conditions |
| `idempotency_contract` | yes | Read-only/idempotent/deduplicated/compensatable/non-repeatable semantics |
| `resource_limits` | yes | Time, calls, compute, money and safety limits |
| `fallback_ref` | yes | Baseline procedure or safe escalation |
| `efficiency_evidence` | yes | Matched baseline/candidate outcomes and cost distributions |
| `provenance` | yes | Source traces, run IDs, code, data, dependency and harness revisions |
| `lifecycle` | yes | candidate, verified, active, at_risk, quarantined, revoked or superseded |

Published habit versions are immutable. A change in operation sequence, parameters, preconditions, postconditions, harness contract or dependency assumptions creates a new version.

## 3. Applicability

Candidate retrieval is not authorization. A habit is applicable only if the exact required environment/harness version, trigger signature, input schema and preconditions match.

Unknown context, missing preconditions, incompatible harness, changed operation contracts or missing evidence must fail closed to the baseline flow or a declared escalation path.

## 4. Efficiency proof

Each candidate is compared with the baseline on a matched cohort and identical harness policy.

Promotion requires:

- minimum sample size;
- required output/side-effect contract pass rate;
- success-rate regression within an explicit tolerance;
- improvement in at least one predeclared cost metric;
- separate reporting of latency, operation calls, compute, tokens, external spend, retries, recovery and human intervention;
- reproducible environment, code, input cohort and harness provenance.

A habit is not better solely because it uses fewer steps. If it saves API calls but increases failure recovery or external cost, the complete result must expose that trade-off.

## 5. Operation pattern

Initial controller forms:

- **Sequence:** fixed, parameterized sequence of operation calls.
- **Guarded sequence:** conditional branches selected by recorded/validated state.
- **Reusable subflow:** an invocation of another immutable flow fragment.
- **Execution shortcut:** a validated reuse of an intermediate result or cached computation, with freshness and invalidation conditions.

These are machine procedure forms, not learned human-like behaviors. No general-purpose policy-learning framework is required to represent them.

## 6. Safety and side effects

Every operation is classified as read-only, idempotent, deduplicated by idempotency key, compensatable, or non-repeatable. A harness may not automatically retry non-repeatable side effects unless a verified deduplication/compensation mechanism exists.

Execution always checks the harness operation allowlist, approvals, time/resource limits, preconditions and postconditions. A habit cannot weaken the harness's controls.

## 7. Persistent flow boundary

A machine habit is a reusable component that a persistent flow may invoke. The flow owns:

- immutable flow definition version;
- run ID and cursor;
- durable input/context and completed outputs;
- event sequence and checkpoint history;
- waiting, approval, retry, pause, resume and cancellation state;
- exact habit versions used by each node.

Resumption must not silently switch a running flow to a new habit or flow-definition version. Such changes require an explicit migration or new run.

## 8. Certificate

A machine-habit certificate identifies the exact habit version, harness/environment scope, input cohort, correctness gate, efficiency evidence, dependencies, issue time and revocation reason. It is empirical evidence of measured applicability and efficiency, not a formal correctness proof unless a separate formal verification method is supplied.

## 9. Invariants

1. A habit cannot execute outside its declared harness/environment/input scope.
2. A habit cannot weaken harness approvals, allowlists, safety or resource limits.
3. A habit is promoted only after correctness/quality and efficiency gates pass.
4. The baseline remains available for fallback and paired evaluation.
5. Habit versions and their evidence are immutable; revocation is a new lifecycle event.
6. A persistent flow pins its own definition and exact habit versions used.
7. A checkpoint is committed before the flow advances beyond a side-effecting operation.
8. Retries obey operation idempotency/deduplication/compensation semantics.
9. Replaying flow history does not repeat already-committed external side effects.
10. Efficiency dimensions remain individually observable.
11. All traces and evidence carry enough provenance to reproduce the comparison.

## 10. Promotion gates

- [ ] A habit passes on matched baseline/candidate inputs.
- [ ] Required output and postcondition equivalence passes.
- [ ] At least one target cost improves beyond the declared margin.
- [ ] Reliability is not degraded beyond the declared tolerance.
- [ ] Non-idempotent operations cannot be blindly retried.
- [ ] Context/harness/version mismatches force fallback.
- [ ] A flow run can recover from a persisted checkpoint without repeating committed operations.
- [ ] Replaying the same event history yields identical control state.
- [ ] Harness fault injection covers timeout, duplicate delivery, partial completion and dependency outage.