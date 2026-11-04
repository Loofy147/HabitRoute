# Roadmap

## P0 — Preserve the evidence baseline

**Status: initializing**

- [x] Create the public repository.
- [x] Preserve the current simulator and step-savings implementation.
- [x] Preserve the baseline implementation and focused tests.
- [x] Record the capacity, sensitivity, and repeated-change results.
- [ ] Verify every committed artifact from a clean clone.
- [ ] Pin the experiment environment and record the Python/NumPy versions used.

**Gate:** a clean checkout reproduces the focused test suite and the published deterministic result files.

## P1 — Extract a behavior-preserving engine

- [ ] Define typed interfaces for environment, state representation, planner, route store, and executor.
- [ ] Extract pure route/library logic from the simulation harness.
- [ ] Preserve the existing usage-utility and step-savings policies as named baselines.
- [ ] Add parity tests that run identical fixtures through old and extracted code.
- [ ] Keep the experiment harness in place until parity is demonstrated.

**Gate:** no unexplained metric or behavior drift on the fixed fixtures and selected seeds.

## P2 — Make trust explicit

- [ ] Define a habit identity and immutable evidence record.
- [ ] Define certificate scope: environment fingerprint/revision, representation version, preconditions, and validity window.
- [ ] Implement certificate states, expiry, quarantine, revocation, and renewal.
- [ ] Prevent lookup/execution when applicability checks fail.
- [ ] Test contradictory transitions and invalidation propagation.

**Gate:** no stale or out-of-scope certificate is accepted by the route selector.

## P3 — Improve adaptation and audit economics

- [ ] Separate slip detection from persistent change detection.
- [ ] Compare adaptive audit with fixed audit at matched quality and compute paired uncertainty.
- [ ] Add freshness/change-risk to retention as a separate experimental term.
- [ ] Measure lookup count, lookup latency, planner calls, audit calls, execution steps, aborts, and recovery cost.
- [ ] Test single changes, repeated changes, change-plus-slip, and noisy representations.

**Gate:** no false permanent demotion in unchanged-world slip tests; repeated-change regressions are quantified and compared with the planner ceiling.

## P4 — Validate retention and scalability

- [ ] Retain coverage and action-step quality as separate outcomes.
- [ ] Compare utility, step-savings, random, FIFO, and any new policy on paired seeds.
- [ ] Add capacities across a wider range, not only 12/20/28.
- [ ] Profile library lookup and pruning in larger worlds.
- [ ] Test alternate change mechanisms and encoder drift.
- [ ] Add formal paired statistical analysis with effect sizes and confidence intervals.

**Gate:** a policy is promoted only for the region where it beats the control without violating safety/coverage constraints.

## P5 — Release a reusable Python library

- [ ] Create the `src/habitroute/` package and public API.
- [ ] Add type checking, linting, docs, and CI.
- [ ] Add at least one simulator-independent example adapter.
- [ ] Define persistence and schema versioning only after core interfaces stabilize.
- [ ] Select a license explicitly before inviting reuse.
- [ ] Publish a versioned release only after clean-install verification.

## Immediate next task

Start P1 with a characterization suite around the current library's externally observable behavior. Extract the library behind interfaces without changing scoring, pruning, or audit decisions. Do not add freshness/change-risk to the production path yet; first make it a separately switchable experimental policy.
