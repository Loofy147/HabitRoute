# HabitRoute

**Evidence-backed adaptive skills and route memory.**

HabitRoute is a research-to-engineering project for learning, verifying, composing and retaining reusable temporally extended behaviors in changing environments.

> Current status: research prototype plus a proposed habit/option specification. The experimental simulator remains the executable baseline; the reusable core is under development and is not yet a stable release.

## The central design

A habit is not just an action list. HabitRoute is moving toward a **versioned adaptive option** with an explicit safe initiation contract, an internal controller, semantic goal/termination conditions, safety and interruption guards, an outcome/cost model, and evidence scoped to its exact version and context.

Fixed action macros remain supported for predictable, invariant sequences. Guarded and reactive controllers are needed when the correct next action depends on the current state. A goal-directed planner remains responsible for selecting skills and falling back when initiation or applicability checks fail.

## Research and design

- [Habit-model research review](docs/HABIT_MODEL_RESEARCH.md) — options, action-sequence formation, composability, predictive state abstraction, successor representations and non-stationarity.
- [Habit specification v0.1](docs/HABIT_SPEC_v0.1.md) — proposed object contract, lifecycle, evidence, composition and invariants.
- [Contradictions and gaps](docs/CONTRADICTIONS_AND_GAPS.md) — code-backed defects, severity, repairs and falsifiable tests.
- [Core implementation status](docs/CORE_STATUS.md) — what the first dependency-free core enforces and what it does not.
- [Architecture](docs/ARCHITECTURE.md) — target component boundaries.
- [Roadmap](docs/ROADMAP.md) — implementation order and promotion gates.
- [Decisions](docs/DECISIONS.md) — accepted design choices and open questions.

## Current experimental evidence

The initial step-savings study compared usage-based retention with counterfactual action-step-savings retention.

- 12-state and 24-state synthetic worlds;
- eight paired seeds (0–7) per world;
- observation noise parameter σ = 2;
- capacity tests at 12, 20, 28 and uncapped;
- repeated-change tests with five consecutive 30% transition-rewiring events;
- focused tests: 10/10 passing; built-in assertions: 22/22 passing.

The strongest observed capacity-28 results favored step-savings weight 0.5 in the tested worlds. These are experiment-specific results, not statistical proof or a universal policy win. Repeated regime changes remain unresolved. The existing usage-based utility policy remains the overall default; savings is opt-in.

See [the experiment report](experiments/step_savings_v1/RESULTS_REPORT.md).

## Repository layout

- experiments/step_savings_v1/ — preserved simulator, baseline behavior, tests and reports.
- docs/ — research, habit contract, contradictions, architecture and roadmap.
- src/habitroute/ — target dependency-free habit contract and core, being built incrementally.

## Project principles

- A planner prediction is not empirical verification.
- Unknown or out-of-distribution observations must not launch a habit by nearest-neighbor fallback.
- A certificate is scoped empirical evidence, not a permanent guarantee or formal safety proof.
- Transition correctness, task value and safety are separate dimensions.
- Coverage, reliability, duration, risk, resource cost and lookup overhead remain separately measurable.
- Failed tests, negative results, uncertainty and computational cost are part of the evidence record.

## License

No license has been selected. Default copyright applies; do not assume unrestricted reuse.