# HabitRoute Core — Implementation Status

**Status date:** 2026-11-07  
**Observed runtime-code baseline:** `43d714c8760a15026e0acb966919f483d893e7d0`  
**Integration-documentation base:** `e81d8f1ec07d53023e77063c1d1964f976549a66`  
**PR #4 hand-design branch head:** `8facb898fa7734978dd6b9e0bd2ee934688c7d9e` (draft)  
**Research implementation/test head:** `0409487664a599884a6677cb84ed02460dc87cac` (PR #6 draft; based on PR #4; the following status-record update is documentation-only)  
**Package:** `habitroute` 0.1.0.dev0 (experimental; not a stable production runtime)

## Canonical machine-habit core

### `src/habitroute/machine.py`

- Immutable machine-habit identity/version and harness/environment/context scope.
- Trigger and precondition predicates, input bindings and postconditions.
- Operation steps classified as read-only, idempotent, deduplicated, compensatable or non-repeatable.
- Harness profile with operation allowlist, approval-required operations, attempt ceiling and compensation capability declaration.
- Provider-neutral `HarnessAdapter` protocol and typed operation outcomes/results.
- Baseline/candidate aggregate performance profiles tied to a cohort label and sample count.
- Efficiency gate using Wilson lower bounds for success and postcondition reliability, plus improvement in a declared latency/call/resource/recovery metric.
- Fail-closed machine-habit authorization.
- Adapter-driven machine-habit executor with input binding, stable logical-step idempotency key across retries, execution records, postcondition checks and unknown-outcome handoff.
- Compensatable steps remain unavailable until a real compensation adapter/API exists.

### `src/habitroute/flows.py`

- Immutable versioned flow definitions and typed operation, habit, branch, wait and terminal nodes.
- Habit nodes pin an exact machine-habit version.
- Deterministic event reducer with contiguous sequence validation and duplicate-event idempotency.
- Persistent run controller for start, step success/failure, unknown outcome, branch resolution, wait release, pause/resume, cancellation and needs-attention escalation.
- Stable per-run/per-flow-version/per-node/per-attempt idempotency keys.
- Local append-only JSONL journal with sequence validation and fsync.
- Recovery by replaying the journal into the flow reducer.
- Single-writer-per-run contract.

### `src/habitroute/worker.py`

- `FlowWorker.dispatch()` dispatches one current flow node per call.
- Handles ordinary operation nodes and exact-version machine-habit nodes.
- Checks operation allowlist, approval and attempt ceiling before ordinary operation invocation.
- Records operation outcome/cost metadata and checks postconditions for ordinary operation nodes.
- Uses `HabitRegistry` for exact-version lookup; the registry is in memory, not durable.
- Routes ambiguous adapter outcomes to `NEEDS_ATTENTION`.
- Tests use a `StubHarness`; no production provider adapter was found.

## Hand-designed reference habit — design complete, runtime open

PR #4 adds the first manually authored habit, `repo-change-verification/v1`:

- `habits/repo-change-verification/v1/HABIT_SPEC.md`: intent, invariants, constraints, decision points, inspection/validation matrix, complete safe-skip fingerprint, retry/failure rules, evidence contract, intervention classification and later-held success definition.
- `habits/repo-change-verification/v1/flow.json` and `flow.schema.json`: explicit ordered flow and transition schema.
- `shared/contracts/v0.1/`: structured trace-event, decision-record, later decision-outcome and strict flow-verdict schemas.
- `tests/test_hand_designed_contracts.py`: schema validity, graph closure, separation of decision/outcome records, mining boundary and negative tests against false `SUCCESS_HELD` claims.

**Status:** the hand design and schema-level tests are present on the PR branch. The runtime does not yet emit or enforce these contracts. The habit is not ACTIVE and its traces are not a mining dataset. A local pass is `VERIFIED_AT_END`; only independent later revalidation on the exact same source digest can produce `SUCCESS_HELD`.

## Retrospective adaptation research extension — design only

PR #6 adds a research-grounded proposal and transfer-evaluation protocol plus draft schemas for proposals, paired trials and derived evaluations. It also updates the hand-designed lifecycle and roadmap.

The extension is **not runtime functionality**. HabitRoute still has no trace-backed retrospective discovery, raw paired-trial store, deterministic statistical evaluator, shadow adaptation engine, promotion service, drift quarantine or automatic harness modification. The new schemas are not emitted by the runtime and do not authorize candidate execution or activation.

The protocol requires held-success, independently revalidated traces before experience-driven proposal mining; fresh matched baseline/adapted trials; separate opportunity, action, adaptation-loading and task-outcome observations; per-dimension cost and unrelated-work accounting; and human review plus rollback before activation.

PR #6's first CI run identified a stale hand-designed trace fixture after the v0.1 trace schema made canonicalization mandatory; the fixture was corrected in the follow-on branch. The corrected run [42313250815](https://github.com/Loofy147/HabitRoute/actions/runs/42313250815) passed 104 tests per Python version. After adding explicit negative tests and schema constraints for NET_BENEFIT, final run [42313443509](https://github.com/Loofy147/HabitRoute/actions/runs/42313443509) passed **106 tests on each of Python 3.11, 3.12 and 3.13**.


## Research synthesis and executable probe extension

The branch `research/adaptation-evaluation-and-durability-v1` adds:

- `docs/RESEARCH_SYNTHESIS_AND_EXPERIMENT_PROGRAM.md`: evidence-linked research synthesis covering retrospective harness adaptation, contrastive trajectory diagnosis, event-log granularity, causal/paired evaluation, durable execution, runtime enforcement, modular evolution, CPM factorial testing, canarying and drift.
- `experiments/adaptation_eval_v1/`: dependency-free paired-trial analysis probe. It validates pair identity, opportunity/action observability, trace completeness, adaptation digest consistency and explicit loading/fingerprint consistency. It retains assigned treatment trials in the intention-to-treat denominator, keeps cost metrics in separate units, and reports missingness instead of converting it to zero.
- `tests/test_crash_window_characterization.py`: deterministic fault-injection characterization against the current `FlowWorker`. It simulates abrupt process termination after an external provider effect but before a journal acknowledgement, then restores from the JSONL journal.

**Observed implication:** the characterization tests are expected to reproduce duplicate external effects for a non-repeatable ordinary operation and a multi-operation habit after replay. The journal records only the initial flow start before the replay, while the restored flow remains at the same node. These tests document an existing failure mode; they do not fix it and must not be counted as a successful reliability result.

The paired evaluator is a research helper, not a statistical promotion gate. It does not calculate sample-size power or quality non-inferiority confidence intervals, validate real provider telemetry, establish raw trace provenance, or issue an activation verdict. Fixtures are synthetic and are not an eligible mining dataset.

The GitHub Actions workflow includes the new probe tests in the existing Python 3.11/3.12/3.13 matrix. PR #7 run [42315856101](https://github.com/Loofy147/HabitRoute/actions/runs/42315856101) passed all three matrix jobs: 10 legacy experiment tests, 108 core/contract tests (including the two crash-window characterizations), and 13 paired-evaluator tests per Python version. The first run exposed a fixture inconsistency in the explicit-unloaded case; the test fixture was corrected and the final run passed. The failure reproduction remains a finding, not a recovery fix.

## Important execution boundary

The worker exists; older status text and issue bodies that say it is missing are stale. However, the ordinary operation-node path and multi-operation habit path have different checkpoint granularity.

For a multi-operation habit, the worker calls the sequence executor and commits the flow event after that sequence returns. It does not currently commit an independent flow event/checkpoint after each individual operation. A crash after one external side effect but before the sequence result is committed can therefore leave partial effects without per-operation flow progress. This is the highest-priority durability gap.

## Verification

- GitHub Actions workflow: `.github/workflows/tests.yml`.
- Runtime-code baseline main run: [41841168040](https://github.com/Loofy147/HabitRoute/actions/runs/41841168040) succeeded on Python 3.11, 3.12 and 3.13.
- PR #4 earlier contract run [42231017168](https://github.com/Loofy147/HabitRoute/actions/runs/42231017168) passed 97 tests per Python matrix before the latest canonicalization requirement was added to the trace schema; the dependent fixture correction is included in PR #6.
- PR #6 run [42313250815](https://github.com/Loofy147/HabitRoute/actions/runs/42313250815) passed **104 tests on each of Python 3.11, 3.12 and 3.13**.
- CI installs `jsonschema>=4.23,<5` for schema/contract tests; HabitRoute's runtime dependency list remains empty.
- PR #7 run [42315856101](https://github.com/Loofy147/HabitRoute/actions/runs/42315856101) passed 10 legacy experiment tests + 108 core/contract tests + 13 paired-evaluation tests on each of Python 3.11, 3.12 and 3.13 (131 per version). The CodeRabbit review check was skipped because the PR is draft.
- PR #4 remains a draft against `docs/unified-runtime-foundation`; PR #6 remains a draft against the PR #4 branch; PR #7 remains a draft against PR #6's branch. None is merged into main.
- Historical 77/77 count applies to commit `090fc7c3fddbc95c7b128045fa7a20ab3dd63400`, not the current tested branch.
- Legacy simulator tests remain under `experiments/step_savings_v1/`.

## Not implemented or not proven

- No production adapter invokes external APIs, CLIs, repositories, scripts or agent runtimes.
- No production-grade provider enforcement for credentials, egress, hard resource/time budgets, cancellation or output limits.
- No per-operation durable checkpoints inside a multi-operation habit invocation.
- No transactional coordination between external operations and the local flow journal.
- No guarantee of exactly-once external side effects.
- No durable habit registry; current registry is in-memory exact-version lookup.
- No production trace-ingestion pipeline, automatic candidate discovery, durable paired-trial evidence store or automated promotion/quarantine. The new paired evaluator is research-only.
- Efficiency profiles are caller-supplied aggregates; cohort label equality does not prove matching raw case identities or independent verification.
- Cost propagation is incomplete across multi-operation habit records and flow metadata; token, context, compute and memory measurements are not comprehensive.
- No external SQL/event store, distributed lock/lease or multi-worker-per-run support.
- No snapshot compaction; replay reads the full local event journal.
- No timer scheduler, callback receiver or approval service.
- No automatic migration of a running flow to a new definition or habit version.
- The earlier `contracts.py` and `execution.py` remain an RL-style route/option prototype and are not canonical.

## Immediate engineering priorities

1. Review and merge the architecture preparation and hand-design PRs in dependency order; keep the habit in design-only state until runtime gates exist.
2. Implement structured append-only trace events and a separate immutable decision/outcome ledger; add semantic validation and replay/integrity tests.
3. Add operation-level durable intent/result/checkpoint records for multi-operation habits.
4. Define idempotency/reconciliation semantics and inject crashes around provider side effects. The new characterization test proves the current replay hazard is reproducible; a fix remains open.
5. Enforce complete budget, evidence, constraint, intervention and later-revalidation gates in a verdict evaluator.
6. Replace caller-supplied aggregate profiles as the sole efficiency evidence with raw paired trial records and independent verification.
7. Add a concrete read-only harness adapter and prove actual policy enforcement; only then stage discovery/promotion.
