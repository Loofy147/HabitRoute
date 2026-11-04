# Sensitivity analysis: coverage weight

Eight paired seeds (0–7), sigma=2, 16 training task pairs. Each value is mean ± sample SD across seeds. Paired deltas are savings minus utility; lower is better for execution steps and planner calls. No p-values or formal significance tests were run.

## 12-state world

| Capacity | Policy | D+1 success | Steps | Planner calls |
|---:|---|---:|---:|---:|
| 12 | utility | 0.933 ± 0.087 | 2.871 ± 0.377 | 10.43 ± 1.94 |
| 12 | savings, weight=0.5 | 0.938 ± 0.045 | 2.746 ± 0.158 | 9.76 ± 1.89 |
| 12 | savings, weight=2 | 0.963 ± 0.038 | 2.675 ± 0.164 | 9.82 ± 1.57 |
| 12 | savings, weight=4 | 0.900 ± 0.108 | 2.879 ± 0.327 | 9.35 ± 2.56 |
| 20 | utility | 0.571 ± 0.160 | 4.100 ± 0.681 | 3.57 ± 2.04 |
| 20 | savings, weight=0.5 | 0.883 ± 0.101 | 2.958 ± 0.305 | 4.25 ± 2.59 |
| 20 | savings, weight=2 | 0.804 ± 0.100 | 3.271 ± 0.357 | 2.17 ± 2.30 |
| 20 | savings, weight=4 | 0.650 ± 0.094 | 3.650 ± 0.325 | 0.38 ± 0.74 |
| 28 | utility | 0.512 ± 0.137 | 4.271 ± 0.486 | 0.47 ± 0.89 |
| 28 | savings, weight=0.5 | 0.904 ± 0.065 | 2.908 ± 0.183 | 0.36 ± 0.68 |
| 28 | savings, weight=2 | 0.887 ± 0.067 | 2.971 ± 0.197 | 0.00 ± 0.00 |
| 28 | savings, weight=4 | 0.900 ± 0.078 | 2.938 ± 0.159 | 0.00 ± 0.00 |
| uncapped | utility | 0.929 ± 0.068 | 2.842 ± 0.311 | 0.00 ± 0.00 |
| uncapped | savings, weight=0.5 | 0.929 ± 0.068 | 2.842 ± 0.311 | 0.00 ± 0.00 |
| uncapped | savings, weight=2 | 0.929 ± 0.068 | 2.842 ± 0.311 | 0.00 ± 0.00 |
| uncapped | savings, weight=4 | 0.929 ± 0.068 | 2.842 ± 0.311 | 0.00 ± 0.00 |

## 24-state world

| Capacity | Policy | D+1 success | Steps | Planner calls |
|---:|---|---:|---:|---:|
| 12 | utility | 0.996 ± 0.012 | 3.146 ± 0.294 | 25.06 ± 3.65 |
| 12 | savings, weight=0.5 | 0.992 ± 0.024 | 3.163 ± 0.268 | 25.38 ± 3.45 |
| 12 | savings, weight=2 | 0.988 ± 0.025 | 3.171 ± 0.278 | 25.34 ± 3.42 |
| 12 | savings, weight=4 | 0.992 ± 0.024 | 3.163 ± 0.268 | 25.33 ± 3.51 |
| 20 | utility | 0.979 ± 0.025 | 3.200 ± 0.314 | 24.27 ± 3.69 |
| 20 | savings, weight=0.5 | 0.988 ± 0.017 | 3.171 ± 0.271 | 24.50 ± 3.81 |
| 20 | savings, weight=2 | 0.979 ± 0.047 | 3.212 ± 0.358 | 24.12 ± 4.48 |
| 20 | savings, weight=4 | 0.971 ± 0.033 | 3.221 ± 0.218 | 23.76 ± 4.55 |
| 28 | utility | 0.883 ± 0.078 | 3.746 ± 0.390 | 21.92 ± 4.72 |
| 28 | savings, weight=0.5 | 0.963 ± 0.058 | 3.254 ± 0.366 | 21.54 ± 4.57 |
| 28 | savings, weight=2 | 0.925 ± 0.081 | 3.408 ± 0.291 | 22.02 ± 5.27 |
| 28 | savings, weight=4 | 0.808 ± 0.127 | 3.917 ± 0.803 | 15.77 ± 5.63 |
| uncapped | utility | 0.829 ± 0.082 | 3.729 ± 0.279 | 0.38 ± 1.08 |
| uncapped | savings, weight=0.5 | 0.829 ± 0.082 | 3.729 ± 0.279 | 0.38 ± 1.08 |
| uncapped | savings, weight=2 | 0.829 ± 0.082 | 3.729 ± 0.279 | 0.38 ± 1.08 |
| uncapped | savings, weight=4 | 0.829 ± 0.082 | 3.729 ± 0.279 | 0.38 ± 1.08 |

## Paired direction counts at capacity 28

| World | Weight | D+1 success improved | Steps reduced | Calls reduced |
|---:|---:|---:|---:|---:|
| 12 | 0.5 | 8/8 | 8/8 | 1/8 |
| 12 | 2 | 8/8 | 8/8 | 2/8 |
| 12 | 4 | 8/8 | 8/8 | 2/8 |
| 24 | 0.5 | 7/8 | 7/8 | 4/8 |
| 24 | 2 | 5/8 | 6/8 | 3/8 |
| 24 | 4 | 1/8 | 4/8 | 7/8 |

## Sensitivity conclusion

- Weight 0.5 gives the best observed capacity-28 route quality in both worlds: D+1 success 0.904 and 0.963 in the 12- and 24-state worlds, respectively.
- Weight 4.0 overweights coverage in the 24-state, capacity-28 case: D+1 success falls to 0.808 and mean steps rise to 3.917, below the utility control on both measures.
- At capacity 12 in the 24-state world, none of the tested weights improves the already high D+1 success; this is not a useful regime for the more expensive savings calculation.
- Weight 0.5 is selected as the default parameter for the opt-in savings policy, not as proof of a global optimum. The agent default remains \`utility\`.
