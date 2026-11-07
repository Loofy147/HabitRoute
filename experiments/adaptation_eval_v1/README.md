# Retrospective evaluation probe v1

**Status:** research-only evaluator plus deterministic unit fixtures. It is not a HabitRoute runtime service, statistical promotion gate, or source of production performance claims.

## Purpose

Exercise the parts of the adaptation research that can be tested without mining unverified historical traces:

- opportunity-conditioned recurrence rather than raw action counts;
- exact matched pair identity and explicit exclusion reasons;
- intention-to-treat accounting even when an assigned adaptation was not loaded;
- separate exposure, task-quality, contract-quality and cost observations;
- exact two-sided McNemar calculation for the primary paired binary recurrence outcome;
- hard-constraint violations reported independently from cost savings.

## Run

From the repository root:

```bash
python -m unittest discover -s experiments/adaptation_eval_v1 -p 'test_*.py' -v
```

No third-party dependency is required.

## Interpretation boundary

The fixture tests validate analysis mechanics only. They do not provide task evidence, validate adaptation loading instrumentation, establish an appropriate sample size, calculate a quality non-inferiority confidence interval, prove statistical power, or recommend activation. The helper intentionally produces no promotion verdict.

Every real trial still requires a preregistered plan, immutable case and environment fingerprints, independently verified outcomes, complete trace provenance, and a separate human-reviewed decision.
