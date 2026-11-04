# Verification record

- \`python -m py_compile habit_system.py habit_library.py habit_refine.py test_habit_utility.py\`: PASS
- \`python -m unittest -v test_habit_utility.py\`: 10/10 PASS
- \`habit_system.selftest()\`: 22/22 PASS, with the real \`habit_refine.py\` import available
- Structural invariant checks in the successful baseline, sensitivity and selected-weight repeated-change batches: 992 checks, no failures
- Seed-0 repeat determinism: all non-timing metrics and operation counters reproduced exactly in 16/16 result groups in each world size; wall-clock fields are intentionally excluded
- Worlds: 12 and 24 states; 8 paired seeds (0–7); sigma=2; 16 train task pairs
- Sensitivity: ST4 at coverage weights 0.5, 2.0, and 4.0; ST5 at 0.5 and 2.0
- Formal significance tests: NOT RUN. Reports give means, sample SDs, paired differences and directional seed counts.
