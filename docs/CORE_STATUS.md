# HabitRoute Core — implementation status

**Status date:** 2026-11-04
**Version:** 0.1.0.dev0 (experimental; not a stable API)

## Implemented

Location: src/habitroute/

- Immutable, typed records for context scope and representation version.
- State belief with explicit unknown mass and normalized probability validation.
- Initiation region gate with minimum in-region mass and maximum unknown mass.
- Fixed macro schema with action sequence, expected state checkpoints and an independent checkpoint-confidence threshold.
- Finite state-conditioned reactive policy that chooses an action only when one action covers enough current belief mass; refuses ambiguous, unsupported or representation-mismatched beliefs.
- Typed artifact references for guarded-sequence and goal-conditioned controller kinds (not yet executable).
- Goal/termination metadata with success states and maximum step budget.
- Safety metadata with forbidden states and optional allowed-action set.
- Per-habit-version, per-scope empirical certificate record.
- Authorization policy with minimum evidence count and Wilson lower confidence bound.
- Fail-closed authorization reasons for lifecycle, environment/context, representation, habit identity/version, certificate scope/status, insufficient evidence, reliability and initiation failures.
- Structural checks that a fixed macro starts inside its initiation region, ends in a declared success state, fits its step budget, uses allowed actions and avoids declared forbidden states.
- Structural checks that a reactive policy's representation matches the habit scope, avoids forbidden states and uses only allowed actions.

## What authorization means

authorize_habit returns permission to attempt a habit only when the supplied belief, context, habit version, and empirical certificate satisfy the configured contract. Candidate retrieval is separate and must not itself trigger execution.

The Wilson lower bound is an empirical statistical gate over a caller-supplied success count. Its interpretation assumes reasonably comparable Bernoulli trials within the declared scope; correlated, adaptive or regime-mixed executions can invalidate that interpretation. The current defaults (20 trials and an 0.80 lower bound) are engineering placeholders, not calibrated safety thresholds. The bound is not a guarantee of future behavior or a formal safety proof.

## Not implemented yet

- No environment-owning executor: `ExecutionSession` is only an adapter-facing controller state machine and does not call `step()` on an environment.
- No learned reactive policy discovery/update; the current reactive controller is a finite state/action table. Guarded-sequence and goal-conditioned controllers are references only.
- No independent evidence ledger, signed evidence refs, or verification that caller-supplied trial counts came from genuine runs.
- No automatic candidate/probation/active promotion workflow.
- No certificate expiry scheduler, change detector, revalidation engine or revocation propagation.
- No online belief estimator; adapters must supply a valid normalized belief.
- No probabilistic transition model or Markov-abstraction test.
- No terminal-outcome to successor-initiation composition calculation.
- No independent safety monitor or tested fallback controller. `ExecutionSession` checks declared forbidden states and action allowlists, but does not establish formal safety, evaluate the optional numeric risk budget, or enforce every custom failure/interruption condition.
- No adapter to the old simulator yet.
- The caller must interrupt the session when a live certificate is revoked or a non-step resource budget is exhausted; the session does not poll a certificate registry.

## Verification

- Local focused core tests: 39/39 passing.
- Local compileall: passing.
- Local editable install using the pyproject metadata: passing.
- GitHub Actions: tests run on Python 3.11, 3.12 and 3.13; the latest run is linked from the repository Actions tab. This status record must be updated if the newest commit changes the test result.

## Immediate next build

Add an append-only execution evidence event interface, then compose terminal-outcome distributions with successor initiation regions. After that, build a simulator adapter and test it against the legacy harness while ensuring nearest-prototype lookup cannot bypass the initiation gate.