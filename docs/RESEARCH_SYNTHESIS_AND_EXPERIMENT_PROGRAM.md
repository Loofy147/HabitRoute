# Research Synthesis and Experimental Program

**Status:** research synthesis plus bounded, executable probes. No production adaptation, mining, approval, or provider-execution feature is activated by this branch.

**Research cut-off:** 2026-11-07.  
**Repository base:** PR #6 head `98df6c0b461441afa5e8be395db5c25e43e45896`.  
**Branch:** `research/adaptation-evaluation-and-durability-v1` (draft work; dependent on PR #6, which is itself dependent on PR #4).

## 1. Purpose and scope

The previous research pass asked whether HabitRoute should use retrospective harness adaptation. This document expands that into a broader engineering research program. The important question is not merely how to mine repeated actions or write better instructions. It is how to build a system that can observe execution correctly, explain why a pattern may help, test the intervention without confounding, preserve correctness through crashes, and prevent learned changes from acquiring authority they were never granted.

The research spans six connected areas:

1. empirical self-evolving agent/harness research;
2. process mining, event abstraction and trace quality;
3. paired experimental design and causal attribution;
4. durable execution, event sourcing, idempotency and recovery;
5. independent runtime enforcement and security;
6. modularity, context selection, canarying and drift control.

The branch implements only bounded research probes. It does **not** claim to prove the value of an evolved habit, establish production-safe execution, or justify a particular production architecture.

## 2. What is established in the current repository

The following are source-level observations at the branch base, not claims about production deployment:

- `FlowWorker` dispatches one current flow node per call.
- An ordinary operation node invokes the adapter and commits one flow result event after the adapter returns.
- A machine-habit node calls `execute_machine_habit()`, which may invoke multiple adapter operations in sequence; the worker writes one flow-level result only after the sequence returns.
- `JsonlFlowJournal` persists append-only events locally and replays contiguous event sequences. It documents a single-writer-per-run contract.
- An adapter exception that reaches ordinary `Exception` handling is converted into an unknown outcome and `NEEDS_ATTENTION`. A process termination between an external effect and that handling/acknowledgement leaves no corresponding operation event.
- Habit operation idempotency keys are stable by run, habit ID/version and operation index across retries. Their safety still depends on the external adapter/provider actually enforcing deduplication.
- `HabitRegistry` is in memory and exact-versioned; there is no durable registry or real provider adapter.
- Current performance profiles are caller-supplied aggregates. Equal cohort labels and sample counts do not establish matched case identities or independently verified raw outcomes.
- PR #6 adds proposal/trial/evaluation schemas and a research protocol. It does not emit these records from runtime code or implement a production evaluator.

These observations define the experimental targets. They do not justify marking the current worker as durable exactly-once execution.

## 3. Research synthesis

### 3.1 Retrospective harness change is a hypothesis generator, not an optimizer oracle

Treude and Baltes' 2026 retrospective-adaptation study reports 30 SWE-bench Verified issue sessions and 125 proposals. The later transfer evaluation used five fresh sessions per arm. Under their informative-case rule, two changes eliminated the target behavior, one reduced it, and four did not reduce it; some changes introduced unrelated work. The paper supports the feasibility of retrospective proposal generation and transfer evaluation, but not a general claim that agents reliably improve themselves or that five cases per arm is an adequate promotion sample.

Pan et al.'s Retrospective Harness Optimization (RHO), published in Findings of EMNLP 2026, combines diverse historical-task selection, multiple re-solves, within-trajectory self-validation and cross-trajectory self-consistency before asking the model to rank candidate harness changes. Its reported improvements are promising. However, self-preference is still a model-derived selector, not independent ground truth. The existence of a strong result in one evaluation setup does not establish safe selection across models, repositories or domains.

**HabitRoute implication:** retrospective analysis may propose a testable intervention, but proposal quality, transfer effect, task quality and operational safety must be evaluated as separate claims. A repeated action is not necessarily wasteful; it may be a necessary validation, a response to a new input, or an action that prevented a failure.

### 3.2 Contrast successful and failed execution, but do not confuse diagnosis with proof

ModularRSI proposes a benchmark-disjoint, contrastive and modular approach. It compares successful and failed trajectories for the same task, aggregates recurring deficiencies across tasks, evolves bounded harness modules independently, then evaluates integration and transfer. BenchTrace separately evaluates reflection/diagnosis and whether the resulting reflection prevents a target failure in later cases. BenchTrace reports that diagnosis itself is difficult and that noise or over-specific lessons can produce forgetting and negative transfer.

The 2026 study *Harness Updating Is Not Harness Benefit* adds another important distinction: a harness can be updated without the task-solving agent benefiting from it. Two distinct failure modes are failure to activate/load the relevant artifact and failure to follow it after loading. These should not be collapsed into one "instruction worked" metric.

**HabitRoute implication:**

- A failed trace can be diagnostic evidence about a failure mechanism.
- A successful, independently revalidated trace can support the claim that a pattern worked under a specified scope.
- Neither trace alone proves that a new intervention caused improvement.
- Load/activation, adherence/action, and task outcome must be independently observable fields.
- Contrastive evidence should be matched on task signature and context. A success from one environment is not a direct counterfactual for a failure in another.
- Candidate changes should be restricted to one logical mechanism at a time. Whole-harness rewrites confound attribution and increase the risk of unrelated regressions.

This refines rather than removes PR #6's held-success eligibility rule: failed runs may help diagnose and define the target, but they are not evidence that the proposed replacement is safe or effective.

### 3.3 Trace quality and event granularity are upstream engineering requirements

Process mining conventionally separates process discovery, conformance checking and enhancement. All depend on event logs that accurately represent the process being studied. Research on event abstraction shows that mixed event granularity can make discovered models too complex and can make conformance checks invalid when the log and reference model describe different levels of activity. A 2026 systematic review on event-log generation identifies data quality and upstream event-generation requirements as a central problem.

HabitRoute's current flow journal records flow-level transitions. It does not yet provide a complete per-operation trace for every operation inside a multi-operation habit. Counting flow-level events as though they were operation-level events would produce invalid recurrence and cost estimates.

**HabitRoute implication:** preserve raw provider observations, but analyse normalized logical operations. Each event needs a stable run/step/attempt identity, causal ordering, a declared granularity, operation and artifact versions, and explicit unknown/missing states. Never infer "action absent" from an incomplete trace. Never count several transport retries as several independent opportunities unless the research question explicitly concerns retries.

### 3.4 Paired evaluation must preserve assignment, opportunity and uncertainty

The research on agentic software engineering reproducibility finds poor reporting of exact harness versions, run dates and complete session traces across the papers it reviewed. This makes feature attribution difficult when model, task, harness and user interaction vary together.

A practical HabitRoute trial should therefore pin:

- task input and task-signature digests;
- baseline and treatment harness versions/fingerprints;
- model and agent configuration;
- environment and relevant dependency fingerprints;
- proposal/artifact digest and preregistered evaluation-plan digest;
- raw trial references, trace completeness and independent outcome evidence.

The target opportunity must be defined independently of whether the agent performs the target action. The target action itself is a separate observation. An adaptation can be assigned but not loaded; that treatment case remains in the intention-to-treat result, while loading rate is reported separately. This prevents the analysis from silently discarding failed activation.

For a binary target-action recurrence measured on matched pairs, the four paired cells must be retained: both recur, neither recurs, baseline-only recurrence, and adapted-only recurrence. The experimental probe in this branch computes the paired risk difference and an exact two-sided McNemar p-value from discordant pairs. It does not select a sample size, calculate quality non-inferiority confidence bounds, or issue a promotion verdict.

**Important limitation:** the helper is an analysis primitive, not a complete causal-inference platform. A real study still needs a preregistered randomization/counterbalancing plan, power/sample-size rationale based on the minimum useful effect, data-quality checks, independent outcome verification, treatment-drift checks and a plan for multiple comparisons/optional stopping.

### 3.5 Durable execution is a separate prerequisite from adaptation

Temporal's workflow model records ordered event history and replays workflow decisions from that history. External interactions such as API calls, database calls and file I/O are put behind activities; completed activity results are returned from history during replay rather than being repeated as workflow-side effects.

AWS Durable Execution documentation makes an important distinction: at-least-once execution can repeat operations; at-most-once-per-retry does not by itself guarantee one execution across the whole workflow. A no-retry policy or a provider-enforced stable idempotency key is needed for the relevant guarantee. When the provider cannot deduplicate, an ambiguous outcome requires reconciliation rather than blind replay.

**HabitRoute implication:** one flow-node completion event is too coarse a recovery boundary for a habit containing multiple external operations. The next durability design should be evaluated at the logical operation boundary, with explicit intent, provider outcome, and reconciliation state. A possible state sequence to test is:

`PLANNED -> INTENT_COMMITTED -> INVOKING -> SUCCEEDED | FAILED | UNKNOWN -> RECONCILED`

This is a research candidate, not a claim that a local JSONL write can be atomic with an arbitrary remote API. Stable keys help only when the receiver enforces them. Where no idempotency contract exists, the safe recovery path is lookup/reconciliation or human handoff, not automatic replay. Compensation is a domain-specific new side effect, not a generic rollback.

### 3.6 Security authority must not evolve with performance

A 2026 systematic review of 58 runtime-enforcement studies finds that many systems enforce at the tool/action boundary or inside the agent runtime; authorization and action validation are common mechanisms. The recurring architecture is that a model proposes an action while an independent enforcement point decides whether the action may take external effect.

**HabitRoute implication:** learned habits, context packages, model judgments and retrospective proposals may suggest actions, but cannot grant credentials, expand allowlists, remove approval requirements, change egress rights, or relax safety constraints. Authorization must remain independently enforced at the provider/action boundary. A constraint violation is a hard blocker; no token, latency or call saving can offset it.

### 3.7 Modular changes and context integration need isolated experiments

ModularRSI motivates bounded evolution scopes. For HabitRoute, candidate experimental scopes include context selection/retrieval, action planning, tool invocation, observation/trace management and task-completion verification. These are useful experimental categories, not an instruction to create five production modules now.

For the CPM + HabitRoute integration, test a factorial design rather than assuming the benefits add together:

| Condition | Context packaging | Machine habit |
|---|---:|---:|
| A | off | off |
| B | on | off |
| C | off | on |
| D | on | on |

Pin the same task cohort and model/harness versions. Measure provider-reported tokens, context assembly/retrieval cost, tool calls, wall-clock time, compute where available, task success, contract correctness and recovery/human intervention separately. The interaction term matters: combined performance may be additive, synergistic, neutral or harmful.

### 3.8 Canarying and drift control are part of evaluation, not release polish

Google SRE's canary guidance compares a small, time-limited treatment population with a control and expands exposure in stages while monitoring absolute and relative guardrails. Microsoft ExP's experimentation guidance distinguishes overall evaluation criteria, local diagnostics, guardrails and data-quality metrics such as sample-ratio mismatch.

**HabitRoute implication:** a successful offline paired test is not sufficient for indefinite activation. Any future activation should begin in shadow mode or a narrow canary with explicit stop/rollback criteria. Model, tool, schema, repository, environment or context-source changes can invalidate prior evidence. The correct response may be revalidation, quarantine or revocation rather than assuming the previous result transfers.

## 4. Evidence ledger

| Claim | Status | Evidence and limit |
|---|---|---|
| Retrospective harness changes can reduce selected repeated behaviors in some transfer settings | EXPERIMENTALLY_SUPPORTED | Treude & Baltes; narrow setting and small per-arm transfer sample |
| Model-generated self-preference can select useful harness changes in a tested benchmark setting | EXPERIMENTALLY_SUPPORTED | RHO / Findings EMNLP 2026; not an independent safety oracle |
| Contrastive successful/failed traces and bounded module evolution may improve transfer | EXPERIMENTALLY_SUPPORTED | ModularRSI; benchmark/task/model limits remain |
| Reflection and target-failure diagnosis are error-prone; over-specific lessons can transfer badly | EXPERIMENTALLY_SUPPORTED | BenchTrace |
| Loading an adaptation and following it are distinct events | ESTABLISHED AS AN EVALUATION DISTINCTION | Harness Updating Is Not Harness Benefit |
| Event-log quality and granularity affect process-mining validity | ESTABLISHED | Process-mining event-abstraction literature and 2026 event-log-generation review |
| Replay/retry can repeat external operations; idempotency and reconciliation are necessary at provider boundaries | ESTABLISHED | Temporal and AWS durable-execution guidance |
| Learned policy must not control its own execution authority | ESTABLISHED DESIGN REQUIREMENT | Runtime-enforcement systematic review and least-privilege architecture |
| A HabitRoute paired evaluator improves candidate selection on real tasks | HYPOTHESIS / OPEN | Only analysis mechanics are tested in this branch |
| Modular evolution will reduce interference in HabitRoute | HYPOTHESIS / OPEN | Requires controlled module-scope experiment |
| CPM × HabitRoute produces additive or synergistic improvement | HYPOTHESIS / OPEN | Requires the four-condition factorial experiment |
| Per-operation intent/result journaling plus provider reconciliation will close HabitRoute's crash windows | HYPOTHESIS / OPEN | Requires runtime design, adapter contract and crash-injection evidence |

## 5. Repository experiments added by this branch

### 5.1 Paired-trial evaluation probe

Location: `experiments/adaptation_eval_v1/`

The dependency-free helper:

- groups baseline/adapted trials by pair ID;
- rejects duplicate arms and mismatched case/input/task/base-harness/environment/agent/model fingerprints;
- excludes absent/unknown opportunities, incomplete traces, mismatched opportunities and unknown action observations with explicit reasons;
- keeps assigned adapted trials in the intention-to-treat recurrence denominator even when the artifact was not loaded;
- reports loading separately;
- computes all four paired recurrence cells, paired risk difference and exact two-sided McNemar p-value;
- reports task-success and contract-pass differences separately;
- keeps cost metrics and units separate;
- surfaces constraint violations and unrelated work separately;
- returns no promotion verdict.

Its test fixtures are synthetic and deterministic. They exercise analysis semantics only; they are not HabitRoute task results and must not enter the mining dataset.

### 5.2 Crash-window characterization against the real worker

Location: `tests/test_crash_window_characterization.py`

The tests simulate abrupt worker termination after a test adapter applies an external effect but before the adapter result is acknowledged and a flow event is committed.

The test adapter raises a `BaseException` subclass to model termination outside ordinary application exception handling. After restoring the flow from the actual JSONL journal, the worker dispatches the same logical node again.

The tests are expected to reproduce two current behaviors:

1. a non-repeatable operation node can be invoked a second time after recovery despite `max_attempts=1`, because no durable invocation intent/result exists in the journal;
2. a multi-operation habit replays its completed prefix and repeats the non-repeatable operation after a crash in a later operation, because the worker commits only one flow-level event after the sequence returns.

These are **characterization tests for known defects**, not accepted runtime semantics and not closure evidence for HR-01/HR-02. Passing means the defect was reproduced deterministically. A future durability fix must replace these expectations with tests proving safe recovery under the declared provider contract.

## 6. What this branch does not prove or change

- It does not mine historical logs, conversations or unverified trace material.
- It does not emit production trace/decision/outcome records.
- It does not add an adaptation registry, background miner, automatic rewrite, activation or promotion service.
- It does not change the current worker or provider authorization behavior.
- It does not solve the remote-side-effect/local-journal atomicity problem.
- It does not prove a real provider will honor idempotency keys.
- It does not establish statistical power, a quality non-inferiority bound, production utility or generalization to new models.
- It does not integrate CPM internals or assert a benefit from context packaging.

## 7. Research and test sequence

The following is an evidence sequence, not a commitment to a particular implementation:

1. **Freeze current semantics.** Preserve the crash-window characterization and current adapter contracts as a baseline.
2. **Specify per-operation durability.** Compare provider idempotency, transactional outbox/command ledger, explicit unknown state and provider reconciliation. Do not use "exactly once" without stating the boundary and contract.
3. **Implement the smallest runtime checkpoint experiment.** Add intent/result records for one ordinary operation and then for each habit operation; use crash injection before invocation, after provider effect, after response, before journal append and after journal fsync.
4. **Test recovery contracts.** Cover provider supports idempotency, provider does not support idempotency but has lookup/reconciliation, and provider cannot determine outcome. Last case must remain UNKNOWN/human handoff.
5. **Validate structured event generation.** Add event provenance, opportunity, action, loaded/activation, adherence, outcome, cost, intervention, environment and trace-completeness fields. Preserve raw events and normalized logical-operation views.
6. **Build an independent paired-trial ledger.** Verify matched identity, randomization, raw outcome evidence, missingness, uncertainty and evaluator reproducibility before any miner is considered.
7. **Run controlled candidate experiments.** Compare one narrow change against a frozen baseline using fresh matched tasks. Report target recurrence, task quality, constraints, all cost dimensions and unrelated work.
8. **Test modularity and CPM integration.** Use separately versioned changes and the four-condition factorial design. Test cross-task, cross-repository and cross-model transfer only after in-domain results.
9. **Use shadow/canary and drift gates.** Require independent enforcement, human approval, explicit rollback, revalidation on material version changes, and quarantine when the validity envelope is exceeded.

## 8. References

1. Sebastian Baltes and Christoph Treude, [Toward Evidence-Based Agentic Software Engineering](https://arxiv.org/abs/2610.35348), arXiv, 2026.
2. Christoph Treude and Sebastian Baltes, [How Do Coding-Agent Harnesses Self-Evolve? An Empirical Study of Retrospective Adaptation](https://arxiv.org/abs/2610.34938), arXiv, 2026. See also the [replication package](https://doi.org/10.5281/zenodo.23653700).
3. Wenbo Pan et al., [Evolving Agents in the Dark: Retrospective Harness Optimization via Self-Preference](https://aclanthology.org/2026.findings-emnlp.2439/), Findings of EMNLP 2026.
4. Siwei Wu et al., [ModularRSI: Modular and Generalizable Recursive Harness Self-Improvement](https://arxiv.org/abs/2609.14857), arXiv, 2026.
5. Minhua Lin et al., [Harness Updating Is Not Harness Benefit](https://aclanthology.org/2026.emnlp-main.2326/), EMNLP 2026.
6. Jiahao Huang et al., [BenchTrace: A Benchmark for Testing Reflection Ability and Controlled Evolution in LLM Agents](https://arxiv.org/abs/2605.29225), arXiv, 2026.
7. Ghita El Alaoui Talibi, Oleksandr Kosenkov and Anastasija Nikiforova, [Data-Related Challenges and Requirements for Event Log Generation in Process Mining: A Systematic Literature Review](https://arxiv.org/abs/2609.04211), 2026.
8. Sebastiaan J. van Zelst et al., [Event abstraction in process mining: literature review and taxonomy](https://doi.org/10.1007/s41066-020-00226-2), *Granular Computing*, 2021.
9. Jimmy Ming-Tai Wu et al., [Beyond Guardrails: Runtime Enforcement for Secure AI Agents—A Systematic Review](https://doi.org/10.62762/JRSC.2026.526903), 2026.
10. [Temporal Workflow documentation](https://docs.temporal.io/workflows) and [Temporal Tasks/replay documentation](https://docs.temporal.io/tasks).
11. [AWS Durable Execution: Idempotency and retries](https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/).
12. Google SRE, [Canarying Releases](https://sre.google/workbook/canarying-releases/).
13. Microsoft Research, [Patterns of Trustworthy Experimentation: During-Experiment Stage](https://www.microsoft.com/en-us/research/articles/patterns-of-trustworthy-experimentation-during-experiment-stage/).

---

**Interpretation rule:** a test that reproduces a known failure is evidence of the failure, not a successful reliability result. A passing synthetic evaluator test is evidence that the code implements its declared analysis rules, not evidence that an adapted agent is better. Production claims require independently reproducible provider-backed artifacts.
