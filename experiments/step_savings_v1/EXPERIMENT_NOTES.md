# Habit library: step-savings pruning experiment

## Change

\`habit_system.py\` now supports a separate capacity policy, \`policy="savings"\` (alias: \`"step_savings"\`). The existing \`policy="utility"\` is unchanged and remains the control. Route-chain search is unchanged: it continues to price actual action steps plus the existing per-habit \`lam\` term.

For each habit, the new policy computes a counterfactual route value:

- \`d_with\`: shortest action-step count from the habit's cue to endpoint in the currently usable library.
- \`d_without\`: shortest action-step count between those endpoints after excluding that habit.
- \`coverage\`: 1 when excluding the habit disconnects those endpoints, otherwise 0.
- \`steps_saved\`: \`max(0, d_without - d_with)\` when an alternative route exists, otherwise 0.
- \`p_success\`: Beta-smoothed observed success rate, \`(n_ok + 1) / (n_exec + 2)\`.

The score retained by pruning is:

\`p_success * (HL_COVERAGE_WEIGHT * coverage + steps_saved)\`

The selected default \`HL_COVERAGE_WEIGHT\` is \`0.5\`; it is configurable through the environment. This setting had the best observed capacity-28 route quality in the 8-seed sensitivity sweep in both the 12-state and 24-state worlds. It is not a universal optimum: capacity-12 performance in the 24-state world was unchanged within small differences, and repeated-change adaptation still has trade-offs. The overall agent default remains \`policy="utility"\`; \`savings\` is opt-in.

The counterfactual search excludes known-bad edges and habits below the same 0.5 empirical success threshold used by chain search. Pruning also records its Dijkstra search count, expanded nodes, wall time, and capacity drops so the extra compute cost is visible.

## Tests added

- Legacy frequency utility still prefers a frequently used habit (control behavior).
- A newer shorter route outranks a much more frequently used detour under the new policy.
- Capacity pruning retains the shorter route in that counterexample.
- Unique routes receive coverage credit.
- Known-bad routes receive no value.
- Same-seed pruning is deterministic.
- Coverage weight is active and configurable; the opt-in savings policy defaults to 0.5.
- The overall agent default remains the legacy \`utility\` policy.
- Structural invariants remain valid after pruning.

## Full experiment branches added

- \`ST4\`: capacity comparison at caps 12, 20, 28 and uncapped. Adds \`savings\` alongside \`utility\`, \`random\`, and \`fifo\` where capacity applies. Each policy receives the same practice order and use-task sequence per seed. Output includes route quality, success, steps, planner calls, library size, and pruning overhead.
- \`ST5\`: matched \`utility\` versus \`savings\` comparison at cap 28 over five consecutive 30% rewiring changes, 60 tasks per cycle. Both policies receive the same initial library, transition-change schedule, task sequence, and random seed. Output includes success, steps, calls, aborts, staleness, library size, and pruning overhead.

Example full run (run in deterministic batches to preserve per-seed outputs):

\`\`\`bash
HL_S=12 HL_COVERAGE_WEIGHT=0.5 HL_SEED_START=0 HL_RESULTS_PATH=st4st5-seeds-0-3.json python habit_system.py 4 ST4,ST5
HL_S=12 HL_COVERAGE_WEIGHT=0.5 HL_SEED_START=4 HL_RESULTS_PATH=st4st5-seeds-4-7.json python habit_system.py 4 ST4,ST5
\`\`\`

Sensitivity was run at \`0.5\`, \`2.0\`, and \`4.0\` for ST4 in both world sizes, plus ST5 at \`0.5\` and \`2.0\`. Raw JSON and analysis reports are included in the results bundle. Keep seed IDs and task schedules fixed when reproducing the comparison.

## Full-run integration and execution

\`habit_refine.py\` is now included and provides \`bfs\`, \`rewire\`, \`plan2\`, and \`setup\`; the full ST4 and ST5 simulations were executed. Set \`HL_S=12\` or \`HL_S=24\` to choose the world size. \`HL_SEED_START\` permits deterministic seed batches; \`HL_RESULTS_PATH\` writes per-seed raw JSON. Wall-clock pruning time is expected to vary across reruns; all non-timing metrics and operation counters reproduced exactly in seed-0 repeat checks.
