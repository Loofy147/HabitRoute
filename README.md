# HabitRoute

**Evidence-backed route memory for adaptive agents.**

HabitRoute is a research-to-engineering project for learning reusable action sequences ("habits"), verifying them against observed transitions, detecting when they become unreliable, and retaining useful routes under a bounded memory budget.

> Current status: research prototype. The initial simulator, retention-policy experiments, tests, and evidence reports are committed. The extracted reusable Python library is not yet implemented.

## Why it exists

A planner can find routes in a model of the world, while a habit library can reuse routes that have already worked in the world. Reuse is valuable only while the evidence remains applicable. HabitRoute studies the lifecycle around that reuse:

1. discover a route through execution;
2. store the route with evidence and context;
3. audit it adaptively;
4. detect slips and real environmental change;
5. revoke or quarantine invalid routes;
6. retain routes that balance reliability, coverage, and action-step savings;
7. fall back to planning when trusted reuse is unavailable.

## Current experimental evidence

The initial step-savings study compares the existing usage-based retention policy with a counterfactual action-step-savings policy.

- 12-state and 24-state simulated worlds;
- eight paired seeds (0–7) per world;
- noise parameter σ = 2;
- capacity tests at 12, 20, 28, and uncapped;
- repeated-change tests with five consecutive 30% transition-rewiring events;
- focused tests: 10/10 passing; built-in assertions: 22/22 passing.

The most consistent benefit appears at capacity 28. In the 12-state world, the step-savings policy at coverage weight 0.5 reached mean D+1 success 0.904 versus 0.513 for usage utility, with mean steps 2.908 versus 4.271. In the 24-state world, the corresponding results were 0.963 versus 0.883 and 3.254 versus 3.746.

These are experiment-specific results, not statistical proof or a universal policy win. Repeated regime changes still expose a route-quality/adaptation trade-off. The usage-based `utility` policy remains the overall default; `savings` is opt-in.

See [the experiment report](experiments/step_savings_v1/RESULTS_REPORT.md) and [the roadmap](docs/ROADMAP.md).

## Repository map

- `experiments/step_savings_v1/` — preserved simulator, usage-utility control, step-savings policy, tests, protocol, and analysis reports.
- `docs/ARCHITECTURE.md` — target system boundaries and invariants.
- `docs/ROADMAP.md` — sequenced engineering work and promotion gates.
- `docs/DECISIONS.md` — explicit decisions and unresolved assumptions.

The experiment code is intentionally kept separate from the future library implementation. The first engineering milestone is to extract stable interfaces without changing the experiment's behavior.

## Reproduce the focused checks

Requirements: Python 3.10+ and NumPy.

From `experiments/step_savings_v1/`:

```bash
python -m pip install -r requirements.txt
python -m py_compile habit_system.py habit_library.py habit_refine.py test_habit_utility.py
python -m unittest -v test_habit_utility.py
```

Full experiment commands and environment variables are documented in the experiment README.

## Project principles

- A route is not trusted merely because a planner predicted it.
- A certificate is scoped evidence, not a permanent guarantee.
- A change in world revision invalidates assumptions that depend on the old revision.
- Slips must not be confused with persistent transition changes.
- Library coverage and route quality are separate objectives.
- Every optimization must be compared against retained baselines on matched seeds.
- Failed tests, negative results, and computational costs are part of the evidence record.

## License

No license has been selected yet. Until one is added, default copyright applies; do not assume the code is available for unrestricted reuse.
