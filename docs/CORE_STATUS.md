# HabitRoute Core — implementation status

**Status date:** 2026-11-04
**Version:** 0.1.0.dev0 (experimental; not a stable API)

## Implemented

Location: src/habitroute/

- Immutable, typed records for context scope and representation version.
- State belief with explicit unknown mass and normalized probability validation.
- Initiation region gate with minimum in-region mass and maximum unknown mass.
- Fixed macro schema with action sequence and expected state checkpoints.
- Typed artifact references for guarded sequence, reactive policy and goal-conditioned policy kinds (these controllers are not yet executable).
- Goal/termination metadata with success states and maximum step budget.
- Safety metadata with forbidden states and optional allowed-action set.
- Per-habit-version, per-scope empirical certificate record.
- Authorization policy with minimum evidence count and Wilson lower confidence bound.
- Fail-closed authorization reasons for lifecycle, environment/context, representation, habit identity/version, certificate scope/status, insufficient evidence, reliability and initiation failures.
- Structural checks that a fixed macro starts inside its initiation region, ends in a declared success state, fits its step budget, uses allowed actions and avoids declared forbidden states.

## What authorization means

authorize_habit returns permission to attempt a habit only when the supplied belief, context, habit version, and empirical certificate satisfy the configured contract. Candidate retrieval is separate and must not itself trigger execution.

The Wilson lower bound is an empirical statistical gate over a caller-supplied success count. Its interpretation assumes reasonably comparable Bernoulli trials within the declared scope; correlated, adaptive or regime-mixed executions can invalidate that interpretation. The current defaults (20 trials and an 0.80 lower bound) are engineering placeholders, not calibrated safety thresholds. The bound is not a guarantee of future behavior or a formal safety proof.

## Not implemented yet

- No executor or runtime step loop.
- No actual guarded or reactive policy implementation; non-macro controller kinds are references only.
- No independent evidence ledger, signed evidence refs, or verification that caller-supplied trial counts came from genuine runs.
- No automatic candidate/probation/active promotion workflow.
- No certificate expiry scheduler, change detector, revalidation engine or revocation propagation.
- No online belief estimator; adapters must supply a valid normalized belief.
- No probabilistic transition model or Markov-abstraction test.
- No terminal-outcome to successor-initiation composition calculation.
- No runtime safety monitor, interrupt handler or tested fallback controller. Static macro/action checks do not make execution safe.
- No adapter to the old simulator yet.

## Verification

- Local focused core tests: 21/21 passing.
- Local compileall: passing.
- Local editable install using the pyproject metadata: passing.
- GitHub Actions: tests run on Python 3.11, 3.12 and 3.13; the latest run is linked from the repository Actions tab. This status record must be updated if the newest commit changes the test result.

## Immediate next build

Implement the execution result types, a guarded fixed-macro executor, step-by-step observation validation, interruption/timeout handling and an append-only evidence event interface. Wire the executor to authorize_habit without allowing the legacy nearest-prototype lookup to bypass the initiation gate.