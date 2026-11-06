# Retrospective adaptation contracts — v0.1

**Status:** draft, schema-tested design artifacts. They are not emitted or enforced by the HabitRoute runtime.

These contracts extend the hand-designed flow evidence without changing the existing shared execution contracts.

| Schema | Purpose | Key rule |
|---|---|---|
| proposal.schema.json | Non-executable, evidence-attributed candidate | Provenance class and exact event/prior basis are mandatory |
| trial.schema.json | One baseline or adapted transfer-trial observation | Opportunity, action observation, loading, task quality and constraints are distinct |
| evaluation.schema.json | Derived report over raw paired trials | NET_BENEFIT only recommends human review; activation is not a schema state |

## Trust and semantics

- The trial ledger is authoritative; aggregate evaluation fields must be recomputed from referenced raw trial records.
- JSON Schema validates field shape. A runtime semantic validator must still verify exact one-baseline/one-adapted pairing, identical case/input/task/environment/agent/model/base-harness fingerprints, timestamps, pair counts, denominators, evidence digests and analysis arithmetic.
- For an eligible paired opportunity, unknown target-action observation is incomplete, not false. A missing opportunity is not a prevented action.
- adaptation_loaded is an exposure diagnostic, not a success signal. The primary comparison is intention-to-treat by assigned arm.
- Cost readings keep metric, unit and measurement source. Missing values remain unknown; estimates cannot be relabeled as observed.
- Hard constraints, permission violations and unobserved interventions block promotion.
- The evaluation schema allows NET_BENEFIT only when the directional effect is present, the quality and hard-constraint gates pass, and no material unrelated overhead is reported. Its only recommendation is human review; other verdicts cannot recommend human review.
- These shape-level constraints do not validate paired arithmetic, minimum-effect thresholds, or artifact truth; the semantic evaluator must recompute those from raw records.
- No schema field authorizes editing a live harness, publishing a change, or activating a habit.

The version is independent of the HabitRoute package version. Any semantic change to required fields, pairing rules or verdict meaning requires a new contract version and migration tests.
