# HabitRoute Core (experimental)

Dependency-free domain contracts for versioned reusable habits.

## Current scope

This first core slice defines immutable habit versions, context and representation scope, a belief-aware initiation gate, fixed macros, a finite state-conditioned reactive policy, references for future controller kinds, termination and safety contracts, and version-scoped empirical certificates.

It does not yet run a full environment execution loop, learn reactive policies, estimate beliefs, prove safety, compose options, persist evidence, or integrate with the legacy simulator. Guarded-sequence and goal-conditioned policies are currently artifact references only. Those are explicit follow-up tasks.

## Install from a checkout

~~~bash
python -m pip install -e .
~~~

## Run tests

~~~bash
python -m unittest discover -s tests -v
~~~

## Fail-closed authorization

Call authorize_habit before executing a candidate. Candidate retrieval (including nearest-neighbor retrieval) is not authorization. The authorization gate checks:

1. habit lifecycle is ACTIVE;
2. exact environment/context scope;
3. exact representation identity/version for both scope and belief;
4. certificate identity and exact habit version;
5. certificate status, evidence count and Wilson lower confidence bound;
6. belief mass inside the declared initiation region and maximum unknown mass.

The Wilson lower bound is a statistical evidence gate, not a guarantee of future success or formal safety. Thresholds are policy parameters and must be calibrated for the task's risk.

See docs/HABIT_SPEC_v0.1.md for the proposed full habit contract and docs/CONTRADICTIONS_AND_GAPS.md for limitations still open.