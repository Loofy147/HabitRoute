# Retrospective Adaptation Protocol

**Status:** design-only research protocol. No runtime discovery, candidate activation, or automatic harness rewriting is implemented by this document or its schemas.

## 1. Decision

HabitRoute should adopt the paper's retrospective proposal plus transfer-evaluation pattern, but not copy its small-sample procedure as a production promotion rule.

The system may analyse eligible execution evidence and propose a narrowly scoped change. It must then test that change on fresh, matched tasks against the unchanged baseline. A reduction in one repeated action is a mechanism-level result, not proof of better task outcomes or lower total cost. Promotion remains a separate, human-reviewed decision.

This extends the hand-design-first sequence. It does not authorize trace mining from the current prototype, chat history, unverified logs, or a design-only habit.

## 2. Research basis and limits

Treude and Baltes studied a retrospective skill that reviewed completed Claude Code sessions and proposed harness changes. Their study reports 30 SWE-bench Verified issues and 125 proposals. Of those proposals, 101 were experience-driven, 19 prior-driven and 5 weakly grounded. The proposed mechanisms included executable checks, navigation pointers, instructions, information access, tool/configuration changes and cases where no harness change was made.

The authors implemented 24 proposals and evaluated 12 changes on later issues from the same repositories. Each transfer comparison used five fresh sessions per arm. Seven evaluations were informative under their baseline-exposure rule: two eliminated the targeted action, one reduced it, and four did not reduce it. Some adaptations added work on unrelated tasks. The study did not show a consistent improvement in overall task success.

The study supports a disciplined evaluation loop, not the claim that retrospective changes generally improve agents. Its single-agent setting, selected transfer tasks, small per-arm samples and narrow recurrence outcome limit generalization. Five sessions per arm is not a universal adequate sample size.

Primary sources: [paper, arXiv:2610.34938](https://arxiv.org/abs/2610.34938); [replication package, Zenodo DOI 10.5281/zenodo.23653700](https://doi.org/10.5281/zenodo.23653700).

## 3. Boundary in HabitRoute

HabitRoute's canonical object remains a **Machine Habit**: a versioned, scoped operation pattern that preserves required postconditions while improving a declared execution cost.

A **Harness Adaptation Proposal** is a different object. It can propose an instruction, check, navigation pointer, information source, tool/configuration change, or operation pattern. It is not executable and is not automatically a Machine Habit. Only a change that satisfies the Machine Habit definition may later be represented as one.

Responsibilities remain separate:

- HabitRoute owns proposal provenance, trial pairing, raw observations, evaluation, lifecycle and evidence references.
- The execution harness owns actual operation authorization, instrumentation, provider boundaries and environment truth.
- CPM owns context packaging, retrieval and context accounting. It may supply pinned context references, but HabitRoute must not import CPM internals or treat context-size reduction as answer-quality or provider-token improvement.
- The unified runtime is the composition layer. It cannot rewrite evidence or bypass approval.

## 4. Eligibility before retrospective analysis

A run is eligible input only when all of the following hold:

1. It was produced by a pinned habit/flow/harness version and a known policy.
2. Its structured trace is complete, ordered and integrity-checked.
3. Required budget, intervention and side-effect observations are available.
4. Its immediate verdict passed and later independent same-target revalidation produced the required held-success state.
5. No later event invalidated, quarantined or revoked the evidence.
6. Referenced artifacts are immutable, readable and digest-verified.

For the reference repository-change habit, this means an independently revalidated SUCCESS_HELD record, not merely VERIFIED_AT_END. Existing runtime events and conversation summaries are not substitutes for the structured contract. Ineligible observations may be retained as context, but cannot support an experience-driven proposal.

## 5. Proposal generation and provenance

Every proposal is classified explicitly:

- **experience_driven** — one or more observed, eligible events support the proposed change;
- **prior_driven** — the proposal comes from an external rule, convention or prior belief, not from the observed session;
- **weak** — the connection between observation and proposed change is indirect;
- **mixed** — both observed events and prior knowledge contribute.

The proposal records exact run/event references, causal link, target scope, proposed mechanism, expected effect, plausible harms and rollback reference. A prior-driven proposal is never mislabeled as a lesson learned from a run.

Use a stable mechanism taxonomy: executable check, navigation pointer, instruction, information access, tool/configuration, operation pattern, or no change. This allows later analysis of which classes transfer and which add overhead.

The target behavior must be operationally defined: what action is measured, under what externally identifiable opportunity, in which harness/environment and for which task signature. Avoid vague targets such as 'be more careful' or 'work more efficiently'.

Keep each evaluated delta to one logical change unit. Multiple files may implement one atomic change, but the artifact digest and rollback reference must be pinned. Do not bundle unrelated instructions, tools and checks when attribution matters.

## 6. Transfer evaluation

### Matched fresh trials

For each proposal, preregister the task cohort, exclusions, target opportunity, primary outcome, non-inferiority margin, cost limits, sample-size rationale, statistical method and multiple-comparison family before inspecting treatment outcomes.

Each case produces a baseline trial and an adapted trial with the same case ID, input digest, task signature, agent/model identity, base harness version and environment fingerprint. The only intended experimental difference is the pinned adaptation artifact. Randomize or counterbalance execution order where order effects are possible. Use fresh sessions so an agent cannot carry hidden state from one arm to the other.

Set the required number of pairs from the minimum effect worth detecting, baseline event rate, uncertainty and risk of false promotion. If underpowered or inconclusive, report INSUFFICIENT_EVIDENCE and collect more data rather than lowering the gate after seeing results.

### Keep four observations separate

For every trial, record these as different facts:

1. **Target opportunity present:** the task/environment offered the preregistered opportunity. Establish this independently of whether the agent took the action.
2. **Target action observed:** the agent did or did not perform the exact action being targeted. Unknown trace coverage remains unknown, never 'did not happen'.
3. **Adaptation loaded:** the changed harness asset was actually consulted/loaded. Loading is exposure, not proof of compliance or benefit.
4. **Task and contract outcome:** whether the task succeeded and whether required outputs/postconditions passed.

The primary recurrence comparison is intention-to-treat: compare all eligible paired opportunity cases according to their assigned baseline/adapted arm. Report adaptation-loaded rate separately as a diagnostic. Do not discard treatment sessions where the adaptation was not loaded from the primary comparison; doing so can bias the estimate.

Do not count a case without the target opportunity as a successful prevention. Do not count an unobservable action as absent. If opportunity presence differs within a matched pair, mark the pair ineligible or confounded and retain the reason.

### Outcomes and costs

The primary outcome is the preregistered target-action recurrence rate among complete matched opportunity pairs. For binary recurrence, retain all four paired cells: both arms recur, neither recurs, baseline-only recurrence, and adapted-only recurrence. Report the paired risk difference and an appropriate paired uncertainty/test method.

Secondary gates are independent:

- Task success and required output/postcondition correctness, with a preregistered non-inferiority margin.
- Constraint violations, unsafe operations, permission/approval bypasses and unobserved interventions. These are hard blockers, not costs to trade away.
- Separate cost dimensions: provider-reported tokens, context accounting, tool/API calls, elapsed time, CPU/memory where measured, external spend, retries, recovery, checkpointing, verification and human intervention.
- Unrelated work caused by the adaptation, including extra checks, unnecessary reads, new branches or false alarms.
- Trace completeness, adaptation loading and environment/harness drift.

Use paired methods for paired observations. Adjust for multiple proposals when making claims across a family of evaluations. Report raw counts, denominators, uncertainty and exclusions; a p-value alone is not an optimization result. Never collapse unlike costs into an unlabeled scalar.

## 7. Evaluation verdicts and decision rule

The evaluator derives its report from the raw trial ledger and a pinned evaluator version. It does not accept agent-authored aggregate counts as authoritative.

- **INSUFFICIENT_EVIDENCE:** too few complete pairs/opportunities, excessive unknowns, or inadequate precision.
- **NOT_APPLICABLE:** the target opportunity did not occur often enough to evaluate the hypothesis.
- **NO_EFFECT:** the preregistered target reduction was not demonstrated and no material harm was established.
- **TARGET_REDUCTION_ONLY:** recurrence fell, but net efficiency or quality gates did not pass.
- **NET_BENEFIT:** the target effect met its preregistered threshold, task quality was non-inferior, constraints held, and no material unrelated overhead erased the benefit.
- **MIXED_EFFECT:** benefit and regression appeared in different outcome dimensions or subgroups.
- **HARMFUL:** a hard invariant failed or a material quality/safety/cost regression occurred.
- **INVALIDATED:** provenance, trace integrity, pairing, policy or source identity failed.
- **CONFOUNDED:** the arms differed in another material variable or treatment contamination occurred.

Only NET_BENEFIT may be recommended for human review. It is not self-activation. Human approval, immutable version creation, rollback readiness and post-activation monitoring are still required. An adaptation is quarantined or revoked when scope drift, recurrence regression, new side effects or evidence invalidation appears.

A reduction in the targeted action is never sufficient by itself. The paper's examples show why unrelated extra work and elapsed-time regressions must remain visible.

## 8. Lifecycle

PROPOSED → REVIEWED → EVALUATION_READY → SHADOW_EVALUATED → VERIFIED → HUMAN_APPROVED → ACTIVE → AT_RISK → QUARANTINED / REVOKED / SUPERSEDED.

Rejected, inconclusive and harmful candidates remain in the ledger with reasons. They are not silently deleted or regenerated as if no attempt occurred. Every version is immutable and retains its raw evidence, analysis code/version, scope and rollback path.

A proposal-only retrospective is read-only with respect to production harnesses. Evaluation changes run only in isolated test/shadow harnesses. Activation is an explicit approval event outside the retrospective agent's authority.

## 9. Runtime gates before this becomes operational

This protocol is design-only until each prerequisite has executable proof:

1. The v0.1 trace/decision/outcome schemas are emitted by the runtime, not only validated in tests.
2. Structured records are append-only, integrity-checked and replayable; semantic validators check cross-record references and chronology.
3. A durable per-operation intent/result/checkpoint boundary exists inside multi-operation habits.
4. Unknown side-effect outcomes are reconciled before retry; the journal is not described as exactly-once.
5. The read-only reference habit is enforced by a real harness adapter and independently revalidated.
6. Raw paired trials preserve case identity, assignment, opportunity annotation, complete event observations and per-dimension costs.
7. A deterministic evaluator recomputes results from raw trials, checks pairing, applies the preregistered analysis and rejects incomplete/mismatched evidence.
8. Promotion, monitoring, drift detection and quarantine are enforced by a durable exact-version registry.

The existing aggregate PerformanceProfile/EfficiencyGate is useful for a prototype but does not replace case-level paired trials. Cohort-label equality does not prove that the arms used identical cases.

## 10. CPM and combined optimization

Do not combine a context change and a habit/harness change into one treatment and then attribute the result to either. Pin CPM version and ContextManifest digest for each trial. First compare context-only and habit-only changes separately; then use a preregistered factorial design to estimate interaction effects.

CPM's reported footprint reductions are not proof of provider-token savings or semantic quality parity. Measure provider-reported token usage and task quality independently. The joint CPM × HabitRoute optimization remains a hypothesis until its interaction is tested on matched cases.

## 11. Implementation order

1. Land/review the hand-designed reference habit and its contracts.
2. Implement runtime trace, decision/outcome emission and semantic validation.
3. Close per-operation checkpoints and side-effect reconciliation.
4. Enforce the reference habit with a read-only adapter and independent later revalidation.
5. Build the raw paired-trial ledger and deterministic evaluator.
6. Run controlled retrospective adaptation experiments in shadow mode.
7. Add proposal mining from eligible evidence only.
8. Introduce durable lifecycle, human approval, drift quarantine and rollback.

Do not reverse this order to produce an impressive but ungrounded self-learning demo.
