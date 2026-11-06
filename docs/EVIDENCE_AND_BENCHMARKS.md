# Evidence and Benchmark Protocol

## Evidence labels

Use the following labels consistently:

- **FACT:** directly verified in a source artifact or authoritative repository record.
- **EXPERIMENTALLY_SUPPORTED:** reproduced by a controlled experiment with recorded method and data.
- **USER_REPORTED:** supplied by the repository owner but not independently reproduced.
- **INFERENCE:** reasoned interpretation from identified facts.
- **HYPOTHESIS:** proposition requiring an experiment.
- **CONTRADICTED:** current evidence directly conflicts with the claim.
- **OPEN:** evidence is insufficient or absent.

A repeated conversation statement does not upgrade evidence status.

## HabitRoute baseline

The canonical synthetic step-savings experiment remains scoped to the simulated transition-routing environment. Its reported capacity-28 results are useful and worth preserving, but the fifth repeated-change cycle shows that gains are not uniform. Do not generalize them to real tool calls, APIs or agents.

## CPM baseline

The CPM v0.5.0 preparation run passed 183 tests. Its footprint benchmark uses the project's accounting method and must not be described as provider-reported token reduction. Fixture scoring is not live semantic quality parity. Container isolation was marked NOT_RUN in the release verification material.

## Combined-system hypotheses

H1. Resolving a machine habit's declared context references through CPM improves readiness or success without exceeding the context budget.

H2. Reusing a verified habit reduces total execution cost while preserving postconditions.

H3. Joint context/habit selection outperforms independent context selection plus independent habit selection on matched tasks.

All three remain **HYPOTHESES** until tested.

## Experimental design

- Pre-register objective, workload, inclusion/exclusion rules, primary outcomes, safety constraints and analysis plan.
- Use paired baseline/candidate runs over the same case IDs and exact input digests.
- Pin model/provider, CPM version, tokenizer/accounting method, HabitRoute version, flow/habit version, harness and environment.
- Randomize or counterbalance order where order effects are possible.
- Include warm/cold cache conditions and cache-management overhead.
- Independently verify outputs and side effects.
- Capture failed runs, retries, human interventions and censored/unknown results.
- Report per-dimension costs with units; do not collapse latency, tokens, calls, memory and money into one unlabeled score.
- Publish raw trial-level data, summary statistics, uncertainty and reproducibility scripts.
- Use suitable paired statistical methods and correct for repeated comparisons when applicable.

## Minimum benchmark matrix

1. Context only: CPM enabled/disabled; measure context size, retrieval work and task quality.
2. Habit only: baseline operation vs habit; measure output correctness, calls, latency, recovery and resource cost.
3. Joint: factorial context-selection × habit-selection design; estimate interaction effect.
4. Drift: change tool schema, provider, harness version and context source; test invalidation/quarantine.
5. Recovery: interrupt before/after operation, after effect/before acknowledgement, after journal append and during restart.

A benchmark is invalid for a quality claim if the quality metric is a fixture constant or if candidate and baseline do not share matched case identities.
