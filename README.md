# HabitRoute

**Durable machine habits: self-contained operating behaviour with a governed repertoire.**

HabitRoute is a research-to-engineering project for building Machine Habits: durable operational systems that know how to respond to recurring classes of situations. A habit carries its purpose, situational judgement, knowledge, skills, tools, frameworks, models, procedures, execution strategies, memory, verification and learning lifecycle as one governed behavioural unit.

A habit uses the relevant small parts of its repertoire to produce an accurate result. It does not invoke every available capability or optimize step count at the expense of correctness, quality or safety.

## Proposed canonical model

The proposed v0.3 architecture is documented in [Machine Habit Model v0.3](docs/MACHINE_HABIT_MODEL_V0.3.md). The model is a documentation-first proposal pending review and implementation.

- **Purpose and outcome contract:** what the habit is responsible for achieving and what must never be violated.
- **Situation awareness:** what is happening, where, when, with what context, uncertainty and risk.
- **Governed repertoire:** skills, tools, scripts, APIs, frameworks, models, services, data, procedures and sub-habits, embedded or referenced with version, compatibility and provenance.
- **Operational judgement and composition:** when, why and how to use a capability, and how to combine the smallest sufficient set.
- **Durable execution:** strategies and Habit Episodes with decision history, operation records, checkpoints, recovery and outcomes.
- **Memory and experience:** procedural, declarative, semantic and episodic knowledge with scope, provenance and freshness.
- **Verification and evolution:** independent outcome checks, evidence-backed improvement, immutable releases, rollback and retirement.
- **Governance and portability:** explicit permissions, dependency contracts and host/runtime compatibility.

A host harness remains authoritative for actual credentials, sandboxing, approvals and side-effect permissions. A habit owns its capability-use behaviour but cannot expand its own authority.

## Current implementation is narrower than the proposed model

The current code is a useful foundation, not the complete v0.3 system:

- `src/habitroute/machine.py` — operation-pattern model, harness profile, effect semantics, authorization and adapter-driven executor.
- `src/habitroute/flows.py` — versioned flow definitions, event reducer, persistent run controller and local append-only JSONL journal.
- `src/habitroute/worker.py` — worker for operation and exact-version habit nodes.
- `src/habitroute/contracts.py` and `execution.py` — earlier RL-style route/option prototype retained for comparison.
- `experiments/step_savings_v1/` — synthetic experiment on route memory, retention, capacity, pruning and adaptation.

The existing model does not yet implement the complete repertoire, situation intelligence, minimal-sufficient composition, habit-owned episode lifecycle, portable capability bindings or whole-habit evolution. See [Core Status](docs/CORE_STATUS.md).

## Research and design

- [Machine Habit Model v0.3](docs/MACHINE_HABIT_MODEL_V0.3.md) — proposed behavioural system model.
- [Research Reassessment v0.3](docs/RESEARCH_REASSESSMENT_V0.3.md) — human habit analogy, prior art, evidence boundaries and comparative benchmark.
- [Reference Habit mapping](docs/REFERENCE_HABIT_REPOSITORY_VERIFICATION_V0.3.md) — maps the existing hand-designed repository verifier to the v0.3 model.
- [Architecture](docs/ARCHITECTURE.md) — runtime and component topology.
- [Decisions](docs/DECISIONS.md) — accepted historical decisions and proposed superseding decisions.
- [Roadmap](docs/ROADMAP.md) — revised research and implementation gates.
- [Previous machine-habit and flow model](docs/MACHINE_HABITS_AND_FLOWS.md) — historical v0.2 design; some durability mechanisms remain useful.
- [Previous Machine Habit Specification](docs/HABIT_SPEC_v0.1.md) — historical file containing v0.2 specification.
- [Previous research review](docs/HABIT_MODEL_RESEARCH.md) — earlier scope, superseded by the new reassessment.
- [Unified Agent Runtime decision](docs/UNIFIED_RUNTIME_DECISION.md) — CPM and host integration boundaries.
- [Repository assessment](docs/HABITROUTE_ASSESSMENT.md).

## Existing experiment: evidence and limits

The synthetic step-savings experiment compared usage-based retention with a counterfactual step-savings policy in 12-state and 24-state worlds. It supports a limited claim: retaining useful routes can outperform frequency-only retention in some capacity-constrained settings. The result is not universal, and repeated environment changes expose adaptation trade-offs. The report uses eight paired seeds and descriptive comparisons, not formal significance tests.

It does not prove real API/tool savings, cross-harness portability, general agent learning or durable external execution. Preserve it as an early experiment, not as validation of the full Machine Habit model.

Primary result: [step-savings report](experiments/step_savings_v1/RESULTS_REPORT.md).

## Unified runtime and CPM

The intended monorepo can include HabitRoute, Context Package Manager (CPM) and a thin host/runtime integration. Under the v0.3 model, CPM is one possible context-management capability in a habit's governed repertoire. The habit decides what context it needs and when to request it; CPM can provide package resolution, retrieval, progressive disclosure, budgeting and caching. CPM does not own the habit's operating judgement or identity.

The packages may remain independently installable and use separate stores. This is an implementation boundary, not a separation of behavioural ownership. See [Unified Agent Runtime decision](docs/UNIFIED_RUNTIME_DECISION.md) and [CPM integration plan](docs/CPM_INTEGRATION_PLAN.md), which must be reconciled before implementation.

## Verification principles

A habit is not better merely because it uses fewer steps or calls. A candidate must preserve the outcome contract and safety constraints, pass independent verification, and improve a predeclared cost objective on comparable cases. Latency, calls, tokens, context/retrieval, compute, external spend, retries, recovery and human intervention remain separately visible.

## Installation and tests

```bash
python -m pip install -e .
python -m pip install -r experiments/step_savings_v1/requirements.txt
python -m unittest discover -s tests -v
```

Python 3.11+; core modules use the standard library only. The legacy simulator tests install NumPy separately.

The current test status and exact repository baseline must be read from [Core Status](docs/CORE_STATUS.md) and the relevant GitHub Actions run. Do not reuse a historical test count as a current result.

## License

MIT. See [LICENSE](LICENSE).
