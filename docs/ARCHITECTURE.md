# Architecture

## Scope

HabitRoute turns successful action sequences into reusable route-memory records. It is not a world simulator, a general planner, or an encoder. Those are dependencies supplied through interfaces.

The architecture below is the target design. The current executable implementation remains in `experiments/step_savings_v1/`.

## Runtime flow

1. **Observe** — obtain an observation and a stable environment/context fingerprint.
2. **Resolve state** — map the observation into the current state representation. An unresolved or ambiguous state is not silently treated as a known state.
3. **Select route** — search the trusted library for a compatible route; compare it with the planner when audit policy requires.
4. **Execute** — execute the next action while observing the resulting state.
5. **Verify** — compare the observed transition with the route's predicted next state.
6. **Update evidence** — record success, slip, contradiction, and context; preserve provenance.
7. **Adapt** — quarantine, revoke, or revalidate affected habits when evidence indicates a change.
8. **Retain** — prune under capacity constraints using explicit, measurable objectives.

## Components

### Environment adapter

Owns reset/observe/step semantics and exposes context identity. HabitRoute must not assume a discrete grid, a particular simulator, or a particular action type.

### State and representation adapter

Maps observations to comparable state identities. The initial experiments use latent prototypes; the engine boundary must permit symbolic, learned, or externally supplied state keys.

### Planner adapter

Produces a candidate route and its cost. Planner output is a proposal, not proof that the route is executable in the live world.

### Habit library

Stores route records and indexes them for lookup. The initial experiment stores contiguous subsequences. A future implementation must define route identity, deduplication, indexing, persistence, and migration behavior.

### Certificate and evidence layer

Associates each route with scoped evidence: context fingerprint/revision, representation version, tested preconditions, execution counts, observed outcomes, and provenance. A certificate is a revocable claim with an applicability boundary—not a permanent guarantee.

### Adaptive audit

Chooses when to compare a stored route with a fresh planner proposal or perform a verification execution. Audit decisions must account for expected risk and the cost of lookups/planner calls.

### Change and slip monitor

Distinguishes isolated execution slips from persistent transition contradictions. It must avoid automatic permanent demotion from one noisy observation.

### Retention and pruning

Treats coverage, reliability, action steps saved, freshness, and computational cost as distinct dimensions. Keep the utility baseline and candidate policies independently selectable until comparative evidence supports promotion.

### Executor and recovery

Executes only routes that pass applicability and trust gates. On mismatch, stops the route, records evidence, and falls back to a planner/recovery path.

## Core invariants

- Unverified planner predictions never enter the trusted library as verified habits.
- Every trusted habit is scoped to an environment/context fingerprint and representation version.
- Contradicted transitions invalidate or quarantine all dependent habits before reuse.
- A single slip is not equivalent to a confirmed regime change.
- A certificate can expire, be suspended, be revoked, and be renewed.
- A route lookup must not return a habit whose applicability gate fails.
- Capacity pruning must respect configured structural invariants and report any coverage loss.
- Deterministic test runs record seed, configuration, code revision, and data revision.
- Unknown state mappings remain unknown; they are not coerced into false certainty.

## Certificate lifecycle

Proposed states:

`PROPOSED → VERIFIED → ACTIVE → AT_RISK → QUARANTINED → REVOKED`

A quarantined route may return to `ACTIVE` only after revalidation against the current context. Expiry and explicit invalidation are separate events and must be recorded.

## Policy objective

Do not collapse all value into one opaque score. Retention should expose interpretable terms and diagnostics:

- expected action steps saved;
- reliability estimate and evidence volume;
- marginal coverage contribution;
- freshness / change risk;
- lookup and verification cost;
- memory cost.

The first optimization study showed that usage-frequency utility can preserve detours under tight capacity, while step-savings can improve route quality. It also showed that the latter does not consistently solve repeated regime changes. Any combined score must preserve this distinction in its evaluation.

## Current implementation boundary

The experiment code currently couples simulation, model setup, route storage, audit logic, and benchmark execution. It is retained unchanged as a research baseline. Extraction into `src/habitroute/` is a separate milestone with behavior-parity tests.
