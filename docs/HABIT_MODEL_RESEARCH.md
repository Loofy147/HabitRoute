# HabitRoute habit-model research

**Date:** 2026-11-04  
**Status:** research synthesis; design recommendations are proposals, not validated results  
**Scope:** what a reusable habit/skill should represent, how it is learned, composed, verified, adapted, and retained.

## 1. Executive conclusion

The current implementation is a useful **verified action-macro library**, but it is not yet a complete adaptive habit/skill system.

The strongest foundation is to model each reusable habit as a **versioned, evidence-backed option**: a temporally extended controller with (a) an explicit initiation region, (b) an internal action policy, and (c) success, failure, interruption, and timeout termination conditions. A fixed action sequence remains a useful *controller type* inside this model; it should not be the only possible habit representation.

HabitRoute should combine three control levels:

1. **Goal-directed controller:** the planner and task objective decide what should be achieved now and whether a stored skill is useful.
2. **Habit/option controller:** a reusable, temporally extended behavior executes while its initiation and runtime conditions remain satisfied.
3. **Runtime monitor and recovery:** observations, uncertainty, safety constraints, and change evidence can interrupt the option and return control to planning or a separately validated fallback.

This is a hybrid design, not a claim that HabitRoute reproduces biological habit learning. In cognitive neuroscience, “habit” often means a stimulus–response process relatively insensitive to outcome revaluation; an adaptive engineering library should instead retain goal-directed supervision over its reusable skills.

## 2. Terminology: what exactly is a habit?

The word “habit” is overloaded.

### 2.1 Behavioral habit

In instrumental-learning research, goal-directed action is regulated by expected outcomes and their current value. Habitual action is more stimulus-driven and can persist after outcome devaluation or contingency degradation. Dezfouli and Balleine propose that some habitual behavior can be understood as learned action sequences, with model-based control selecting the sequence and sequence-based control executing its internal steps.

This is directly relevant to sequence chunking, but it does not imply that an engineering system should execute old routines regardless of current goals or safety conditions.

### 2.2 Action macro

An action macro is a stored sequence of primitive actions, often with a known start and expected end. It reduces repeated planning/selection overhead. A macro may be open-loop, or it may include observations and abort checks between actions.

The current HabitRoute library is closest to this category: it stores an action tuple and an expected prototype path. During execution it checks intermediate observations against the expected prototype sequence and aborts on mismatch.

### 2.3 Option / temporally extended skill

The Options framework defines a temporally extended action using three components:

- **Initiation set** I: states or conditions where the option can start.
- **Intra-option policy** pi: how it chooses actions while running.
- **Termination condition** beta: when it stops.

The option may be invoked in a region, follow a feedback policy, terminate at a subgoal, and be composed with other options in a semi-Markov decision process. This is a better target abstraction for HabitRoute than a tuple of action IDs alone.

### 2.4 Recommended project language

Use **habit** as the product/repository term, but define the software object as an **adaptive verified option**. Keep these types distinct:

| Type | Meaning | Role |
|---|---|---|
| Transition evidence | Observed state/action/outcome data | What actually happened |
| Action macro | A fixed action sequence with checkpoints | Fast execution in predictable regions |
| Reactive option | A state-conditional controller with initiation/termination | Reusable closed-loop skill |
| Goal-conditioned option | A skill parameterized by a desired subgoal | Reuse across related targets |
| Route | An ordered composition of options/macros | A solution to a particular task |
| Certificate | Scoped evidence that a particular version of a habit is applicable | Trust gate, not a policy |

Do not collapse the route, the habit, the policy, and its certificate into one record.

## 3. What the literature contributes

### 3.1 Options: the minimal skill contract

**Sutton, Precup and Singh (1999), “Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning.”**

The options framework extends primitive actions to policies that execute over time. Its key engineering consequence is that a skill needs more than an action list: it needs an initiation condition, an internal policy, and a termination rule. A set of options can be planned over using semi-Markov decision-process machinery.

**HabitRoute implication:** add initiation, feedback policy, and explicit termination/failure semantics. A fixed action sequence is allowed as one policy implementation, but it must have an initiation contract and runtime monitor.

Source: https://doi.org/10.1016/S0004-3702(99)00052-1

### 3.2 Action-sequence formation: when should a macro exist?

**Dezfouli and Balleine (2012), “Habits, action sequences and reinforcement learning.”**

The paper argues that some habitual behavior is best understood as chunked action sequences rather than simply cached action values. A sequence can be beneficial when, after a preceding action, the same next action remains appropriate across the plausible states that may follow. If different successor states call for different actions, blindly running the same sequence is not justified. The paper describes mixed model-based selection of a sequence and sequence-based execution.

**HabitRoute implication:** discover a macro only when its internal action sequence is sufficiently invariant across the states/context in which it may be executed. Where plausible successor states require different actions, use a branching/closed-loop option instead. Retain a higher-level goal-directed controller so a sequence is not selected after its goal or value has changed.

Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3325518/  
DOI: https://doi.org/10.1111/j.1460-9568.2012.08050.x

### 3.3 Option learning and termination

**Bacon, Harb and Precup (2017), “The Option-Critic Architecture.”**

Option-Critic learns an option's internal policy and termination condition together with the policy that selects among options. The paper demonstrates that policy and termination are learnable design variables, not fixed metadata.

**HabitRoute implication:** termination should be an explicit learned or estimated behavior, not merely “the fixed list ended.” Initially it can be a hand-defined verified subgoal; later it can be learned from successful trajectories and interruption outcomes.

Source: https://ojs.aaai.org/index.php/AAAI/article/view/10916

**Harutyunyan et al. (2018), “Learning With Options That Terminate Off-Policy.”**

This work highlights a trade-off: longer options can improve learning efficiency, but if the available options/termination choices are not suitable, they can constrain solution quality. The behavior termination and target termination can be decoupled.

**HabitRoute implication:** macro duration is not automatically beneficial. Keep the ability to interrupt or switch when a different route becomes better. Measure the cost of excessive switching as well as the cost of persevering in a bad option.

Source: https://ojs.aaai.org/index.php/AAAI/article/view/11740

### 3.4 Composability: why individually good habits may not chain

**Bagaria, Senthil, Slivinski and Konidaris (IJCAI 2021), “Robustly Learning Composable Options in Deep Reinforcement Learning.”**

The paper identifies non-stationary subgoal regions as a core difficulty in skill chaining. The initiation region of one option can become the target region of another, and changes in one region can propagate through the chain. The authors propose robust initiation-region classification, including optimistic and pessimistic classifiers, re-targetable policies, and model-based robustness.

**HabitRoute implication:** exact equality between one habit's terminal prototype and the next habit's cue is too brittle as the long-term composition contract. The engine should estimate whether the terminal outcome distribution of option A lands inside the safely accepted initiation region of option B. Maintain a conservative execution region separately from a broader exploratory/learning region.

Source: https://ijcai.org/proceedings/2021/298

### 3.5 State abstraction: a representation must preserve decision-relevant dynamics

**Allen, Parikh, Gottesman and Konidaris (NeurIPS 2021), “Learning Markov State Abstractions for Deep Reinforcement Learning.”**

A latent representation is not guaranteed to be Markov merely because it compresses observations. If the abstraction discards information needed to predict rewards or transition outcomes, a stationary state-dependent policy may no longer be valid. The paper develops conditions and a training procedure for learning approximately Markov abstract states.

**HabitRoute implication:** prototype identity must not be assumed to identify a unique transition state. Before a prototype can serve as a habit cue, test whether it is predictive enough for the relevant actions, outcomes, and context. When it is not, augment it with history/context or maintain a belief over possible states. “Nearest prototype” is not evidence that the current observation belongs to a skill's safe initiation region.

Source: https://proceedings.neurips.cc/paper_files/paper/2021/file/454cecc4829279e64d624cd8a8c9ddf1-Paper.pdf  
Open access abstract: https://proceedings.neurips.cc/paper/2021/hash/454cecc4829279e64d624cd8a8c9ddf1-Abstract.html

### 3.6 Successor representation: a substrate for temporal abstraction and reuse

**Machado, Barreto, Precup and Bowling (JMLR 2023), “Temporal Abstraction in Reinforcement Learning with the Successor Representation.”**

The successor representation captures expected future state visitation patterns under a policy. The paper surveys how it can support the discovery of options and shows how previously learned options can be combined into a much larger family without separately learning every combination.

**HabitRoute implication:** investigate predictive/occupancy representations for discovering useful subgoals, measuring similarity of option effects, and composing skills. Do not replace the policy with a successor representation: it is a predictive representation and discovery substrate, not by itself an executable habit.

Source: https://www.jmlr.org/papers/v24/21-1213.html

**Momennejad et al. (2017), “The successor representation in human reinforcement learning.”**

This work studies a middle ground between cached action values and full model-based planning. Successor representations can be more flexible than pure model-free cached values under reward revaluation, but less immediately flexible than a full transition model when transition structure changes.

**HabitRoute implication:** separate transition validity from task-value validity. A habit may still reach the same state but cease to be useful when costs, rewards, or goals change. Re-check the high-level objective even when the low-level transition behavior remains valid.

Source: https://www.nature.com/articles/s41562-017-0180-8

### 3.7 Lifelong and non-stationary environments

**Xie, Harrison and Finn (ICML 2021), “Deep Reinforcement Learning amidst Continual Structured Non-Stationarity.”**

The work formalizes persistent changes in environments and tasks, and notes that replaying old experience is problematic when its generating process changes. It uses latent-variable models and online inference to reason about changing context.

**HabitRoute implication:** history must be context-scoped. Do not aggregate all successful and failed executions into one stationary count if they came from different regimes. Preserve old evidence, detect a possible regime change, and maintain separate hypotheses/certificates for distinct contexts.

Source: https://proceedings.mlr.press/v139/xie21c.html

**Li, Shi, Wu and Fryzlewicz (Annals of Statistics 2025), “Testing Stationarity and Change Point Detection in Reinforcement Learning.”**

This work develops a stationarity test and a change-point procedure for RL, illustrating that non-stationarity should be treated as a statistical inference problem rather than a fixed two-error heuristic.

**HabitRoute implication:** replace the rule “at least two observations and more than half are wrong” with a calibrated sequential detector. The target is not simply to detect a wrong edge; it is to estimate whether the evidence is more consistent with a transient slip/noise event or a persistent change in the transition law.

Source: https://doi.org/10.1214/25-AOS2501  
Article PDF: https://www.imstat.org/publications/aos/aos_53_3/aos_53_3.pdf

### 3.8 Skills without hand-designed rewards

**Eysenbach et al. (ICLR 2019), “Diversity is All You Need.”**

DIAYN discovers diverse skills using an information-theoretic objective without a task reward.

**HabitRoute implication:** unsupervised diversity can help later when the system needs broad exploratory skill coverage. It is not the first fix for the current project: diversity alone does not guarantee that a skill is useful, safely initiable, composable, or valuable for the user's task distribution.

Source: https://research.google/pubs/diversity-is-all-you-need-learning-skills-without-a-reward-function/

### 3.9 Experience memory is not the same as a skill library

**Pritzel et al. (2017), “Neural Episodic Control.”**

This work stores past experiences and retrieves them rapidly to improve learning. It concerns episodic experience/value retrieval, not necessarily a temporally extended action policy.

**HabitRoute implication:** keep at least three data structures conceptually separate: raw episode memory, reusable option/habit definitions, and certificates/evidence about a particular version of a habit. They have different retention and retrieval objectives.

Source: https://proceedings.mlr.press/v70/pritzel17a.html

### 3.10 Model-based planning and learned behavior should coexist

**Sutton (1991), “Dyna, an integrated architecture for learning, planning, and reacting.”**

Dyna integrates learning a model, planning with that model, and reactive execution. A learned model can be imperfect; the design uses planning and reaction rather than making either one the entire agent.

**HabitRoute implication:** preserve the planner as the goal-directed fallback and evaluator. But be explicit that planner agreement is not empirical proof that a habit works in the live world; only execution evidence can establish that.

Source: https://doi.org/10.1145/122344.122377

## 4. Research synthesis: a stronger habit representation

The literature supports the following separation:

| Concern | Current experiment | Better target |
|---|---|---|
| Start condition | Exact prototype cue; nearest-prototype fallback is possible | Calibrated initiation region over state belief + context |
| Internal behavior | Fixed action tuple | Pluggable controller: fixed macro, guarded sequence, decision graph, or learned policy |
| Success | Expected final prototype | Explicit goal/termination region and measured outcome distribution |
| Failure | Any intermediate mismatch | Typed failure causes, interruption, timeout, and recovery contract |
| Composition | Exact prototype endpoint equality | Probabilistic terminal-region to initiation-region compatibility |
| Validity | Edge mismatch counters and global revision | Context- and representation-scoped evidence and change posterior |
| Certificate | (start, goal, revision) audit cache | Immutable empirical attestation for one habit version and scope |
| Reliability | One aggregate success ratio per stored segment | Context-conditioned posterior and calibrated uncertainty |
| Retention | Usage or marginal action-step savings | Constrained multi-objective selection over utility, risk, coverage, memory and query cost |
| Discovery | Every contiguous subpath | Segmentation and option discovery from stable, reusable, decision-relevant behavior |

### Recommended object definition

An executable HabitRoute habit should satisfy all of these:

1. It identifies **where/when it may start**, including uncertainty and context.
2. It specifies **how it acts**; a fixed sequence is one allowed controller, not the whole schema.
3. It specifies **what success looks like** in terms of a goal or termination region.
4. It specifies **how it fails or is interrupted**, including maximum duration/resource budget.
5. It predicts **outcome and duration distributions**, not only a single next-state chain.
6. It carries **scoped evidence** tied to an environment/context and a state-representation version.
7. It can be **revoked, quarantined, revalidated, or superseded** without destroying historical evidence.
8. It can be composed only when the previous option's terminal distribution is compatible with the next option's safe initiation region.

## 5. Research recommendations versus implementation priority

Not all techniques should be implemented at once.

### Build first

- Formal habit/option schema and state machine.
- Safe initiation gate; unknown/OOD state must not select a habit by nearest-neighbor fallback.
- Explicit intra-option controller interface, initially supporting the current fixed macro with per-step observation checks.
- Explicit success, failure, interruption, and timeout conditions.
- Per-habit empirical certificate and evidence ledger.
- Context/representation versioning.
- Correctness-safe composition and invalidation.

### Investigate next

- State-belief and approximately Markov representation learning.
- Pessimistic/optimistic initiation classifiers for composability.
- Sequential change detection separating slips from persistent changes.
- Goal-conditioned/parameterized options.
- Successor-representation-assisted subgoal discovery.
- Risk-aware utility and retention under memory/query costs.

### Defer

- End-to-end Option-Critic training.
- DIAYN-style unsupervised skill discovery.
- Deep hierarchical skill trees.
- Large-scale persistent policy/value stores.

These are research directions, not prerequisites for fixing the current abstraction.

## 6. Evidence limitations

- The papers use different assumptions, environments, and definitions. Their results do not establish that one combined architecture will outperform the current HabitRoute baseline.
- The current HabitRoute benchmark is a small synthetic discrete world with a learned latent representation and rewiring-based changes. It has not yet demonstrated behavior in continuous control, changing reward functions, genuinely partially observed environments, or external simulators.
- The proposed schema and architecture are engineering inferences from the literature. They require direct tests in this repository.
- Biological “habit” findings should be used as inspiration for sequence chunking and controller interaction, not as proof of the proposed engineering design.

## 7. Core references

1. Sutton, Precup & Singh (1999). *Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning.* https://doi.org/10.1016/S0004-3702(99)00052-1
2. Dezfouli & Balleine (2012). *Habits, action sequences and reinforcement learning.* https://doi.org/10.1111/j.1460-9568.2012.08050.x
3. Bacon, Harb & Precup (2017). *The Option-Critic Architecture.* https://doi.org/10.1609/aaai.v31i1.10916
4. Harutyunyan et al. (2018). *Learning With Options That Terminate Off-Policy.* https://doi.org/10.1609/aaai.v32i1.11740
5. Bagaria et al. (2021). *Robustly Learning Composable Options in Deep Reinforcement Learning.* https://doi.org/10.24963/ijcai.2021/298
6. Allen et al. (2021). *Learning Markov State Abstractions for Deep Reinforcement Learning.* NeurIPS. https://proceedings.neurips.cc/paper/2021/hash/454cecc4829279e64d624cd8a8c9ddf1-Abstract.html
7. Xie, Harrison & Finn (2021). *Deep Reinforcement Learning amidst Continual Structured Non-Stationarity.* https://proceedings.mlr.press/v139/xie21c.html
8. Machado et al. (2023). *Temporal Abstraction in Reinforcement Learning with the Successor Representation.* https://www.jmlr.org/papers/v24/21-1213.html
9. Li et al. (2025). *Testing Stationarity and Change Point Detection in Reinforcement Learning.* https://doi.org/10.1214/25-AOS2501
10. Momennejad et al. (2017). *The successor representation in human reinforcement learning.* https://doi.org/10.1038/s41562-017-0180-8
11. Eysenbach et al. (2019). *Diversity is All You Need.* https://research.google/pubs/diversity-is-all-you-need-learning-skills-without-a-reward-function/
12. Pritzel et al. (2017). *Neural Episodic Control.* https://proceedings.mlr.press/v70/pritzel17a.html
13. Sutton (1991). *Dyna, an integrated architecture for learning, planning, and reacting.* https://doi.org/10.1145/122344.122377
