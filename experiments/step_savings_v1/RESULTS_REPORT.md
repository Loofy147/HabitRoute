# Habit retention: step-savings experiment

## Executive result

The step-savings retention score fixes the specific capacity-pruning failure in the 12-state experiment and improves route quality at capacity 28 in both the 12-state and 24-state experiments. The best tested coverage bonus was \`0.5\`, not the original \`2.0\`.

This is not a universal replacement for usage utility. The overall agent default remains \`policy="utility"\`; \`policy="savings"\` is an opt-in capacity policy. Repeated regime changes still expose a route-quality/adaptation trade-off, especially in the 24-state world.

## Experimental scope

- World sizes: 12 and 24 states.
- Seeds: 0–7 in each world; comparisons are paired by seed.
- Noise: \`sigma=2\`.
- Training: 16 task pairs, each repeated twice during practice.
- ST4 capacity test: caps 12, 20, 28 and uncapped; matched practice order and test tasks; adaptive audit and dominated-route pruning enabled; then 30 novel tasks.
- ST5 repeated-change test: capacity 28; five consecutive 30% transition-rewiring events; 60 adaptation tasks per cycle; adaptive audit and planner-model adaptation enabled.
- Policies: existing usage utility control versus step-savings. ST4 also includes random and FIFO controls. The savings coverage weight was swept at 0.5, 2.0 and 4.0. ST5 was run at 0.5 and 2.0.

## Capacity results

### 12-state world

| Capacity | Policy | D+1 success | Steps | Planner calls |
|---:|---|---:|---:|---:|
| 20 | Utility | 0.571 | 4.100 | 3.58 |
| 20 | Savings, weight 0.5 | **0.883** | **2.958** | 4.25 |
| 20 | Savings, weight 2.0 | 0.804 | 3.271 | **2.17** |
| 20 | Savings, weight 4.0 | 0.650 | 3.650 | 0.38 |
| 28 | Utility | 0.513 | 4.271 | 0.48 |
| 28 | Savings, weight 0.5 | **0.904** | **2.908** | 0.36 |
| 28 | Savings, weight 2.0 | 0.887 | 2.971 | **0.00** |
| 28 | Savings, weight 4.0 | 0.900 | 2.938 | **0.00** |

At capacity 28, weight 0.5 improved D+1 success and reduced steps in all eight paired seeds. At capacity 20, the same setting improved both metrics in all eight seeds, while planner calls were modestly higher than the utility control.

### 24-state world

| Capacity | Policy | D+1 success | Steps | Planner calls |
|---:|---|---:|---:|---:|
| 12 | Utility | 0.996 | 3.146 | 25.06 |
| 12 | Savings, weight 0.5 | 0.992 | 3.163 | 25.38 |
| 20 | Utility | 0.979 | 3.200 | 24.28 |
| 20 | Savings, weight 0.5 | 0.988 | 3.171 | 24.50 |
| 28 | Utility | 0.883 | 3.746 | 21.93 |
| 28 | Savings, weight 0.5 | **0.963** | **3.254** | 21.54 |
| 28 | Savings, weight 2.0 | 0.925 | 3.408 | 22.02 |
| 28 | Savings, weight 4.0 | 0.808 | 3.917 | 15.77 |

At capacity 28, weight 0.5 improved D+1 success in seven of eight seeds and reduced execution steps in seven of eight. At capacity 12, the savings calculations provide no useful gain in the 24-state world. Capacity 20 changes are small.

## Repeated-change results

The table below uses the selected weight 0.5. Cycle five is shown against the utility control; all metrics are means across eight paired seeds.

| World | Policy | Success | Steps | Planner calls | Aborts | Stale fraction |
|---:|---|---:|---:|---:|---:|---:|
| 12 | Utility | 0.917 | 4.294 | 5.48 | 0.775 | 0.144 |
| 12 | Savings, weight 0.5 | 0.915 | **3.552** | 5.23 | **0.658** | **0.095** |
| 24 | Utility | 0.829 | 4.508 | 46.81 | 1.127 | 0.045 |
| 24 | Savings, weight 0.5 | 0.817 | 4.577 | **40.40** | **1.096** | **0.011** |

The selected weight improves or preserves several adaptation indicators, but not all. In the 12-state world, step-savings has a clear cycle-five step and abort advantage after an uneven cycle three. In the 24-state world, cycle-five planner calls, aborts and measured staleness improve, while success and steps are slightly worse. Across both worlds, later-cycle behavior is not uniformly superior.

## Interpretation by evidence level

**ESTABLISHED**

- The new score computes the marginal action-step saving from retaining a habit, discounts it by observed route success, and awards a configurable coverage credit when the habit is the only available route.
- The old utility metric remains available and is still the default agent policy.
- The selected default coverage weight for the opt-in savings policy is now 0.5.
- The current test suite passes 10/10; the built-in self-test passes 22/22.
- Across the successful capacity and repeated-change experiment batches, 992 structural library checks ran without an invariant failure.
- Repeated seed-0 runs reproduced all non-timing metrics and operation counters in 16/16 result groups for each world size. Wall-clock measurements are not deterministic and were excluded.

**EXPERIMENTALLY_SUPPORTED**

- Step-savings materially improves capacity-28 route quality in the 12-state world, and weight 0.5 improves it in the 24-state world.
- Weight 4.0 can preserve more chains while producing worse short-horizon route quality. In the 24-state capacity-28 test it underperformed the utility control in both D+1 success and steps.
- The savings policy often reduces planner calls and measured library staleness during repeated changes, but this does not guarantee fewer steps or higher success.

**INFERENCE**

- The original frequency-based utility was retaining familiar detours instead of shorter routes. The capacity-28 results support this diagnosis; the effect is not uniform at every capacity or world size.
- A high coverage bonus can protect long, unique routes at the expense of execution efficiency. The weight-4 results support this mechanism, but do not prove it is the only cause.

**OPEN**

- Whether a freshness-aware or change-risk term can prevent late-cycle route-quality regressions.
- Whether the chosen weight generalizes beyond rewiring and \`sigma=2\`.
- Whether the result persists with a learned encoder rather than the current frozen encoder.
- Formal significance testing. This report provides seed-level sample standard deviations and paired directional counts, not p-values or claims of statistical significance.

## Decision

Keep \`utility\` as the overall agent default. Keep \`savings\` as an opt-in policy with \`coverage_weight=0.5\` by default. For the tested 12-state and 24-state worlds, capacity 28 is the clearest use case. Do not claim the savings policy has solved repeated-regime adaptation.

The next implementation target is a separate freshness/change-risk adjustment to habit retention, evaluated against the unchanged utility and savings controls. It should not be merged into the current score until it passes the same slip false-demotion, capacity and repeated-change checks.

## Reproduction

The bundle includes \`habit_system.py\`, \`habit_library.py\`, and the restored \`habit_refine.py\` dependency. The tested parameter is supplied explicitly when running a batch; \`HL_SEED_START\` permits deterministic 4-seed batches and \`HL_RESULTS_PATH\` saves raw per-seed JSON.

\`\`\`bash
HL_S=12 HL_COVERAGE_WEIGHT=0.5 HL_SEED_START=0 \\
  HL_RESULTS_PATH=results_12.json python habit_system.py 4 ST4,ST5

HL_S=24 HL_COVERAGE_WEIGHT=0.5 HL_SEED_START=4 \\
  HL_RESULTS_PATH=results_24.json python habit_system.py 4 ST4,ST5
\`\`\`

For only capacity experiments use \`ST4\`; for only repeated changes use \`ST5\`. Run the standard checks with:

\`\`\`bash
python -m py_compile habit_system.py habit_library.py habit_refine.py test_habit_utility.py
python -m unittest -v test_habit_utility.py
\`\`\`
