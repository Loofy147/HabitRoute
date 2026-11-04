# HabitRoute contradictions and gaps

**Date:** 2026-11-04
**Basis:** current main-branch experiment implementation and external research.
**Purpose:** preserve what the code actually does, distinguish it from assumptions, and define falsifiable repairs.

Severity: Critical = can authorize out-of-scope execution or false trust; High = can break correctness, composition or adaptation; Medium = weakens generality or economics; Open = requires measurement.

## Critical contradictions

### C-01 — OOD observations can still launch a habit

**Observed code:** epS computes cur = m.snap(z), then if cur is negative it chooses m.nearest(z) as the cue and searches the habit library. The snap rejection therefore does not fail closed.

**Why it matters:** nearest-prototype similarity is a retrieval heuristic, not evidence that the current observation is inside a habit's safe initiation region. A habit can issue an action from an unknown or out-of-domain state.

**Repair:** separate candidate retrieval from execution authorization. Require an explicit initiation predicate and confidence threshold. Unknown/OOD must fall back to planning or a validated recovery behavior.

**Discriminating test:** create an observation outside the snap radius but nearest to a known habit cue; assert zero habit actions execute.

### C-02 — deterministic abstract edges are assumed without proving the abstraction is Markov

**Observed code:** records store one successor prototype per (prototype, action). check() reports multiple successors as an edge contradiction; _purge removes habits that disagree with a newly observed successor.

**Why it matters:** if multiple real situations map to the same prototype, or transitions are stochastic, multiple successors can be legitimate. The current rule can erase valid behavior or preserve whichever successor was observed most recently.

**Measurement defect:** stale_frac builds inv = {prototype: true_state}; duplicate assignments overwrite earlier states. The metric is not valid for many-to-one prototype mappings.

**Repair:** retain belief/context-conditioned or probabilistic transitions; test predictive sufficiency before treating abstract states as Markov. Correct staleness measurement for many-to-one mappings.

**Discriminating tests:** aliased hidden states with different outcomes; stochastic transition with two valid outcomes; split observations from the same underlying state; duplicate-prototype staleness calculation.

### C-03 — the stored habit is an action macro, not a complete adaptive skill

**Observed code:** each record contains an action tuple and expected prototype path. Execution checks intermediate prototypes and aborts when one differs, but the internal action sequence itself does not branch on the new observation.

**Why it matters:** this can work on invariant paths, but cannot represent a skill whose next action depends on which legitimate state was reached. It also lacks a semantic success region, explicit timeout/interruption classes, and a controller-specific safety contract.

**Repair:** use the option contract: initiation region, intra-option controller and termination condition. Preserve fixed macros as one controller kind; add guarded/reactive controllers where branching is required.

**Discriminating tests:** branch environment where a reactive option succeeds and fixed macro fails; perturbations inside initiation region; early goal achievement; timeout and external interruption.

### C-04 — the variable named cert is a coarse audit cache, not a habit certificate

**Observed code:** cert is keyed by (start_prototype, goal_prototype) and stores a library-wide revision number. It is updated by an audit decision. It has no habit ID/version, run evidence, environment scope, representation version, confidence interval or tested operating envelope.

**Revision gap:** _purge and some edge-bad transitions increment rev, but _drop, capacity pruning and dominated pruning do not. The audit cache can remain apparently current after relevant library content changes.

**Repair:** rename this structure to audit_cache. Implement a separate immutable empirical certificate for an exact habit version and scope. Invalidate local caches on every behavior-affecting change.

**Discriminating tests:** prune/replace a habit and verify relevant audit evidence invalidates; context and encoder mismatch fail closed; unrelated context certificate remains valid.

## High-severity correctness and adaptation gaps

### H-01 — dominated pruning uses invalid routes as proof of replacement

**Observed code:** prune_dominated builds an all-pairs graph from every stored habit. It does not apply _eligible, bad-edge, reliability, context or safety filters. By contrast, step_savings shortest-path lookup filters _eligible.

**Why it matters:** an unreliable/stale short alternative can cause a valid longer habit to be deleted, after which runtime chain selection rejects the purported replacement.

**Repair:** only prove dominance via an admissible replacement chain under the same context, goal, safety constraints and uncertainty threshold. Preserve the old habit until the replacement is retained and independently available.

**Test:** a short invalid habit must not dominate a longer valid route; after removal of the invalid habit, reachability must still hold.

### H-02 — all contiguous subsequences create a combinatorial habit set

**Observed code:** add_path creates every contiguous subpath. A path of length L yields up to L(L+1)/2 records before deduplication.

**Why it matters:** overlapping records compete for capacity and make lookup expensive. User-reported experiments measured approximately 39 library lookups per task against 12 planner calls. This may be a representation/granularity problem, not only a pruning-score problem.

**Repair:** retain primitive transition/evidence memory separately. Discover skill boundaries at stable subgoals, action-branch points and predictable continuation regions. Compare segmentation against all-subpath enumeration.

**Tests:** measure records, unique coverage, lookup operations and route quality as trajectory length grows; test whether segment boundaries preserve composition.

### H-03 — habit reliability is not context-conditioned and hides uncertainty

**Observed code:** chain eligibility begins after two executions and rejects a segment below a 0.5 success ratio. Step-savings uses a Beta-smoothed point estimate (n_ok+1)/(n_exec+2). Counts aggregate across contexts and regimes.

**Why it matters:** the same point estimate may arise from very different sample sizes. One regime's successes can hide another regime's failures. Whole-option success is also not the same as per-transition correctness.

**Repair:** store evidence by context/representation version; expose posterior or calibrated lower confidence bounds; distinguish option success, transition prediction and safety outcomes.

**Tests:** same route succeeds in regime A and fails in B; equal mean but low/high sample counts; Brier score, log loss and reliability curves.

### H-04 — change detection is a fixed threshold rather than a calibrated sequential detector

**Observed code:** bad() flags an edge after at least two observations and more than 50% mismatches.

**Why it matters:** independent slips, bursts of slips, observation noise, state aliasing and actual regime changes can all cause mismatches. A single threshold does not estimate their different likelihoods or detect delay/false alarm trade-offs.

**Repair:** model the observation/slip process separately from persistent transition change. Introduce a sequential change posterior or change-point detector only after collecting calibrated residual data; quarantine locally and revalidate.

**Tests:** independent slips, correlated/bursty slips, a single persistent transition change, repeated changes, encoder drift with unchanged world.

### H-05 — chain cost is not total execution cost

**Observed code:** the route search charges len(actions) + lambda per stored habit.

**Why it matters:** it ignores option-specific duration, failure probability, risk severity, resource consumption, goal value, lookup/audit overhead and recovery cost. The old cost-weight experiment only tests one component of chain preference; it does not validate total cost.

**Repair:** keep the current cost as a baseline. Add separate measured cost distributions and task-dependent selection constraints/weights.

**Tests:** route ranking under different duration, reliability, resource budgets, safety risk and recovery penalties.

### H-06 — adaptive audit is fixed-probability and cached at start/goal scope

**Observed code:** the adaptive audit mode uses pu when the (start, goal) revision cache is not current. It does not prioritize by per-habit risk, uncertainty, context hazard, task criticality or audit cost.

**Why it matters:** audit effort may be spent on low-risk routes while critical uncertain skills remain unchecked; a global revision invalidates too broadly, while missing revision increments fail to invalidate when needed.

**Repair:** make audit a value-of-information decision over expected failure impact, epistemic uncertainty, change hazard, novelty and audit cost. Use local habit-version scope.

**Tests:** vary risk at fixed uncertainty; vary audit cost at fixed risk; local route change invalidates only dependent attestations.

### H-07 — transition verification is not a safety contract

**Observed code:** execution aborts on expected-prototype mismatch. No independent action admissibility, task invariant, risk budget, hazard monitor or validated fallback is defined.

**Why it matters:** an expected transition can still violate safety or task constraints. Successful route execution is not proof of safety.

**Repair:** add safety preconditions, runtime guard interface, interruption protocol and declared recovery controller. Do not label the result formally safe without a formal proof.

**Test:** a predicted transition violates a hard constraint; trigger mid-option hazard; measure interrupt latency and fallback success.

## Medium-severity gaps

### M-01 — no data-driven segmentation or intra-habit branching

Planner paths generate all contiguous chunks; existing habit execution updates counters but does not learn a feedback controller. Add a segmentation baseline and a small finite-state reactive controller before deep option learning.

### M-02 — representation and policy versions are not part of habit identity

Prototype integers can change meaning after encoder/prototype changes. Add immutable representation versions. Suspend old habits on incompatible versions unless a measured mapping migration is proven.

### M-03 — composition is exact prototype equality

A route links a habit endpoint to the next habit cue by exact ID. Replace this with a terminal-outcome distribution versus successor initiation region compatibility estimate with a conservative confidence bound.

### M-04 — task/reward revaluation is untested

The benchmark is mainly shortest-path goal reaching. A transition-valid habit may become useless when goals, rewards, costs or constraints change. Test objective changes without rewiring the world.

### M-05 — error attribution is too coarse

Failures can come from representation aliasing, initiation, controller, composition, transition shift, audit or pruning. Instrument these causes separately and include module-level ablations.

## Experiments required

| ID | Experiment | Falsifiable question | Measures |
|---|---|---|---|
| X01 | OOD initiation | Can an unknown observation launch a habit? | false accepts/rejects, fallback rate |
| X02 | State aliasing | Can one abstract cue/action have multiple valid outcomes? | calibration, false invalidations, success |
| X03 | Stochastic transitions | Can a habit represent a transition distribution? | likelihood/calibration, success |
| X04 | Branching continuation | Does a reactive option beat a fixed macro when actions depend on state? | success, aborts, steps, replans |
| X05 | Composition | Does terminal-region overlap predict chain success? | chain success, lower confidence bound |
| X06 | Certificate scope | Does a certificate fail closed under context/version mismatch? | false acceptance |
| X07 | Dominance | Can invalid routes delete valid alternatives? | post-prune reachability |
| X08 | Slips vs changes | Can detector separate independent/bursty slips from change? | false alarms, delay, misses |
| X09 | Goal revaluation | Does selector abandon transition-valid but now-suboptimal skills? | regret and objective cost |
| X10 | Segmentation | Does segmentation reduce memory/lookup without harming coverage? | records, lookups, route quality |
| X11 | Representation drift | Are old habits safely suspended/migrated after encoder change? | false reuse, revalidation cost |
| X12 | Runtime interruption | Can safety/context interruption stop a running option? | interrupt latency, violations, recovery |

## What is not contradicted

- Current habit admission is based on successful observed execution of a planner-derived route whose states are snapped; this is a valuable empirical foundation under the benchmark assumptions.
- The current executor checks intermediate prototype outcomes and aborts on mismatch. It is not an unchecked open-loop macro.
- Step-savings has demonstrated a specific capacity benefit in the tested synthetic worlds; that result does not establish that the habit representation is adequate.
- Deterministic edge invariants are appropriate for a deterministic world with a sufficiently Markov, unaliased abstraction. The problem is applying them beyond those assumptions.

## Decision priority

1. P0: fail-closed initiation; explicit habit/option contract; certificate identity/scope; admissible dominance proof.
2. P1: state-belief/representation validity; immutable versioning; evidence ledger.
3. P2: segmentation and a guarded/reactive controller; terminal-to-initiation composability.
4. P3: context-conditioned reliability; calibrated slip/change detection and adaptive audit.
5. P4: task/risk/resource cost model and scalable retention.
6. P5: goal-conditioned skills, successor-feature/SR discovery, continuous-control adapters and deep skill learning.