# Repertoire and Composition Planner v0.3

**Status:** implemented planning primitive; dry-run only  
**Code:** `src/habitroute/repertoire.py`  
**Public API:** `habitroute` package exports  
**Tests:** `tests/test_repertoire.py`

## 1. What this adds

The Machine Habit now has an executable representation of a governed capability repertoire and a situation-aware composition planner.

A habit can declare capabilities such as skills, tools, scripts, APIs, libraries, frameworks, models, services, datasets, context providers and sub-habits. Each entry declares what it can provide, what inputs it needs, which permissions it requires, which harness/environment versions it supports, which side-effect class it has, its lifecycle/evidence reference and estimated costs.

At planning time, the habit receives:
- a time-bound `SituationFrame`;
- a host-supplied `HostCapabilitySnapshot` containing exact available capability versions, permissions and allowed effects;
- its `OutcomeContract`;
- its `CompositionPolicy`.

The planner returns an inspectable `CompositionPlan`: selected capabilities in execution order, achieved outcomes, missing outcomes/inputs, rejected alternatives, estimated cost and reason.

**It plans; it does not execute.** No adapter is invoked and no network, process, filesystem or provider call is made by `compose_habit`.

## 2. Core contracts

### CapabilityEntry

Important fields:

- `capability_id`, `kind`, `version`: stable identity and version for the resource.
- `provides`: facts or outcomes the capability can produce.
- `requires_inputs`: facts that must exist before it can be used. They may come from the initial situation or the outputs of earlier selected capabilities.
- `context_requirements`: exact situation facts that must match before the capability is eligible.
- `required_permissions`: permissions that the host must already grant.
- `compatible_harnesses`, `compatible_environments`: exact `id@version` references.
- `effect`: side-effect class from the existing `OperationEffect` contract.
- `status`, `evidence_digest`: only ACTIVE entries are eligible; ACTIVE requires a non-empty evidence reference.
- `cost`: estimated calls, latency, tokens, resource units and external cost.

The evidence digest is an opaque reference. This planner does not retrieve or independently verify the evidence. A separate verifier and governed activation process must validate it before a capability is marked ACTIVE.

### SituationFrame

Records a situation ID, offset-aware observation time, exact harness/environment IDs and versions, available input facts, context digest and typed string facts for applicability rules.

The caller must supply the observation time and the planner's `now`; the planner does not read a clock implicitly. Context older than the habit's declared freshness window is rejected. A future-dated situation is blocked.

### HostCapabilitySnapshot

This is the host's input to planning. `available_capabilities` must contain exact references such as `git-reader@1.0.0`, not unversioned names. It also records the host's effective permissions and allowed operation effects.

This data structure does not itself authenticate the host or enforce permissions. The real host/harness must produce a trustworthy snapshot and enforce the same limits at execution time. A habit cannot grant itself permissions.

### OutcomeContract

Defines required outcomes, required initial situation inputs, maximum situation age and the effects this habit is allowed to consider. The default permitted effect is READ_ONLY. A host may allow more than the habit contract; the intersection still applies.

### CompositionPolicy

The planner minimizes one explicitly declared cost dimension (CALLS by default). Capability count and stable IDs break ties. Other cost dimensions are reported separately and are not blended into an opaque score.

The planner also has `max_capabilities` and `max_search_states` bounds. Exceeding a bound returns NEEDS_CAPABILITY; it never returns a partial READY plan.

## 3. Selection and composition algorithm

The selector performs these stages:

1. Validate host/situation identity, freshness and required initial inputs.
2. Filter capabilities by ACTIVE status, exact version availability, harness/environment compatibility, situation facts, granted permissions, habit-permitted effects and host-permitted effects.
3. Build a directed fact graph from capability input requirements and outputs.
4. Search reachable states using bounded Dijkstra-style planning. A capability becomes usable only when its required inputs are present; its outputs can unlock later capabilities.
5. Stop only when every required outcome has been produced by the selected capability chain.
6. Optimize the declared primary cost dimension; use capability count and stable identifiers as deterministic tie-breakers.
7. Return the executable order, cost estimates, missing outcomes/inputs and rejected alternatives.

A capability can be useful even when it does not directly satisfy a final outcome: it may produce an intermediate artifact required by another capability. Irrelevant capabilities are excluded. Eligible alternatives not selected are explained as not selected by the declared objective.

The model treats capabilities as monotonic fact producers for this first slice. It does not yet model arbitrary mutable state, loops, capability retries, resource contention, concurrent branches, compensation or side-effect execution.

## 4. Example: compose a read-only repository inspection chain

This example illustrates the API shape. The evidence strings must be replaced with verifier-issued references before capabilities are activated; the example does not assert that any external adapter has been verified or installed.

```python
from datetime import datetime, timezone

from habitroute import (
    CapabilityEntry,
    CapabilityKind,
    CapabilityStatus,
    CostEstimate,
    HabitDefinition,
    HostCapabilitySnapshot,
    OperationEffect,
    OutcomeContract,
    SituationFrame,
    compose_habit,
)

harness = "local-readonly@1"
environment = "git-worktree@1"

repertoire = (
    CapabilityEntry(
        capability_id="git-reader",
        kind=CapabilityKind.TOOL,
        version="1.0.0",
        provides=frozenset({"repository_snapshot"}),
        requires_inputs=frozenset({"repository"}),
        required_permissions=frozenset({"repository.read"}),
        compatible_harnesses=frozenset({harness}),
        compatible_environments=frozenset({environment}),
        effect=OperationEffect.READ_ONLY,
        status=CapabilityStatus.ACTIVE,
        evidence_digest="sha256:REPLACE_WITH_VERIFIER_ISSUED_DIGEST",
        cost=CostEstimate(calls=1, latency_ms=20),
    ),
    CapabilityEntry(
        capability_id="changed-path-inventory",
        kind=CapabilityKind.TOOL,
        version="1.0.0",
        provides=frozenset({"verified_inventory"}),
        requires_inputs=frozenset({"repository_snapshot"}),
        required_permissions=frozenset({"repository.read"}),
        compatible_harnesses=frozenset({harness}),
        compatible_environments=frozenset({environment}),
        effect=OperationEffect.READ_ONLY,
        status=CapabilityStatus.ACTIVE,
        evidence_digest="sha256:REPLACE_WITH_VERIFIER_ISSUED_DIGEST",
        cost=CostEstimate(calls=1, latency_ms=30),
    ),
)

habit = HabitDefinition(
    habit_id="repo-change-verification",
    version="0.3.0",
    purpose="Establish a verified repository change inventory.",
    capabilities=repertoire,
    outcome_contract=OutcomeContract(
        required_outcomes=frozenset({"verified_inventory"}),
        required_inputs=frozenset({"repository"}),
        max_situation_age_seconds=300,
    ),
)

situation = SituationFrame(
    situation_id="review-0001",
    observed_at=datetime.now(timezone.utc),
    harness_id="local-readonly",
    harness_version="1",
    environment_id="git-worktree",
    environment_version="1",
    available_inputs=frozenset({"repository"}),
    context_digest="sha256:REPLACE_WITH_CONTEXT_DIGEST",
)

host = HostCapabilitySnapshot(
    harness_id="local-readonly",
    harness_version="1",
    environment_id="git-worktree",
    environment_version="1",
    available_capabilities=frozenset({
        "git-reader@1.0.0",
        "changed-path-inventory@1.0.0",
    }),
    granted_permissions=frozenset({"repository.read"}),
    allowed_effects=frozenset({OperationEffect.READ_ONLY}),
    snapshot_digest="sha256:REPLACE_WITH_HOST_SNAPSHOT_DIGEST",
)

plan = compose_habit(
    habit,
    situation,
    host,
    now=datetime.now(timezone.utc),
)

assert plan.dry_run
if plan.status.value == "ready":
    print(plan.selected_ids)  # ('git-reader', 'changed-path-inventory')
else:
    print(plan.status, plan.reason, plan.missing_inputs, plan.missing_outcomes)
```

The returned order matters: `git-reader` produces `repository_snapshot`, which satisfies the input requirement of `changed-path-inventory`. The planner does not invoke either capability.

## 5. Fail-closed outcomes

- `BLOCKED_CONTEXT`: the host snapshot does not match the situation identity, or the situation timestamp is in the future.
- `STALE_SITUATION`: the observation exceeded the declared freshness window.
- `NEEDS_INFORMATION`: required initial inputs are missing from the situation.
- `NEEDS_CAPABILITY`: no eligible composition satisfies the outcome contract, an input dependency is unreachable, a capability limit is exceeded, or the search bound is exceeded.
- `READY`: a complete capability composition exists for planning. This is not proof that execution will succeed or that the task outcome is correct.

Rejected alternatives record reasons such as inactive status, unavailable exact version, incompatible harness/environment, missing context facts, missing host permissions, habit-forbidden effect, host-forbidden effect, missing input dependencies or not being selected by the primary objective.

## 6. Verification

The tests cover:
- minimum-cost sufficient selection and cheaper single-capability alternatives;
- deterministic tie breaking;
- context-conditioned choices;
- capability chains through intermediate outputs;
- exact host/harness/environment compatibility;
- freshness and future timestamps;
- missing situation inputs and capability prerequisites;
- inactive or evidence-less capabilities;
- missing host permissions and effects forbidden by either habit or host;
- explicit cost-dimension selection;
- maximum capability and search-state limits;
- dependency cycles and incomplete outcome coverage.

GitHub Actions run [42635404943](https://github.com/Loofy147/HabitRoute/actions/runs/42635404943) passed the full repository matrix on Python 3.11, 3.12 and 3.13. Each job reported 10 legacy experiment tests and 112 core tests passing at that commit. Later commits must be revalidated.

## 7. Explicit limits and next extensions

This is the first executable v0.3 slice, not the complete Machine Habit runtime.

Not implemented here:
- a durable HabitRelease registry or import/export package;
- authenticated host snapshot production;
- capability adapter invocation;
- HabitEpisode event persistence and crash recovery;
- memory consolidation, trace ingestion or whole-habit learning;
- independent validation of evidence digests;
- automatic capability discovery or promotion;
- a general-purpose non-monotonic planner, loops, parallelism or dynamic state mutation.

The next safe extension is to bind this planner to one read-only repository-verification habit and a real host-provided capability snapshot, then record a version-pinned episode through the durability layer. Do not enable side-effecting execution until provider authority, operation-level checkpoints, reconciliation and independent verification are proven.
