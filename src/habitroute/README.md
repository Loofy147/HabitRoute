# HabitRoute Core (experimental)

Dependency-free domain contracts for versioned reusable habits.

## Current scope

This core slice defines immutable habit versions, context and representation scope, a belief-aware initiation gate, fixed macros, a finite state-conditioned reactive policy, a closed-loop execution session, termination and safety metadata, and version-scoped empirical certificates.

`ExecutionSession` is an adapter-facing action/observation state machine: it authorizes before the first action, emits one action, requires a fresh observation, checks macro checkpoints or reselects a reactive action, and stops on goal, mismatch, unknown state, forbidden state, context change, interruption, or step budget. The caller still executes actions and supplies beliefs/context.

It does not yet execute an environment, learn policies, estimate beliefs, enforce every declared failure/interruption condition, prove safety, compose options, persist evidence, or integrate with the legacy simulator. Guarded-sequence and goal-conditioned policies are artifact references only. A caller must explicitly interrupt the session when a certificate is revoked or a resource budget is exhausted.

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

Run `python -m unittest discover -s tests -v` for the core tests. See docs/HABIT_SPEC_v0.1.md for the target contract and docs/CORE_STATUS.md for exact implemented/non-implemented boundaries.