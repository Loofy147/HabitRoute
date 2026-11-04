# Step-savings experiment v1

This directory preserves the current experimental implementation and evidence. It is intentionally not the public `habitroute` package.

## Contents

- `habit_system.py` — experiment harness, library implementation, policies, and scenario runners.
- `habit_library.py` — simulator/world and latent model implementation used by the experiment.
- `habit_refine.py` — planner, rewiring, setup, and practice helpers restored as the previously missing dependency.
- `test_habit_utility.py` — focused regression tests.
- The usage-based `utility` policy remains in `habit_system.py` as the executable control; a separate baseline source snapshot is not yet committed.
- `RESULTS_REPORT.md` — main capacity and repeated-change findings.
- `SENSITIVITY_ANALYSIS.md` — coverage-weight sweep.
- `REPEATED_CHANGE_ANALYSIS.md` — per-cycle comparisons.
- `VERIFICATION.md` — reported verification protocol and results.
- The Markdown reports contain the checked-in aggregate results; raw per-seed JSON and CSV artifacts from the local experiment package are not yet committed.

## Install and test

Python 3.10+ and NumPy are required.

```bash
python -m pip install -r requirements.txt
python -m py_compile habit_system.py habit_library.py habit_refine.py test_habit_utility.py
python -m unittest -v test_habit_utility.py
```

## Reproduce

The harness accepts scenario groups, world-size, seed offsets, and result-path environment variables. Example matched capacity and repeated-change run:

```bash
HL_S=12 HL_COVERAGE_WEIGHT=0.5 HL_SEED_START=0 \
HL_RESULTS_PATH=results-12-seed0.json python habit_system.py 4 ST4,ST5

HL_S=24 HL_COVERAGE_WEIGHT=0.5 HL_SEED_START=4 \
HL_RESULTS_PATH=results-24-seed4.json python habit_system.py 4 ST4,ST5
```

Run batches with seed ranges 0–3 and 4–7 to reproduce the eight-seed studies. Timing diagnostics are expected to vary; deterministic operation counters and non-timing result fields should be compared separately.

For full scenario names, settings, and limitations, see `EXPERIMENT_NOTES.md` and `RESULTS_REPORT.md`.
