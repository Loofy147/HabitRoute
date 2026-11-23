# HabitRoute

**Efficient machine habits, controlled by harnesses, carried by persistent flows.**

HabitRoute is a research-to-engineering project for discovering, verifying, optimizing and reusing recurring machine-operation patterns. A machine habit is not a human habit and not an RL skill: it is an execution pattern that must preserve required results while reducing a measured cost.

## Canonical model

- **Machine Habit:** reusable optimized operation pattern with triggers, inputs, preconditions, steps, postconditions, side-effect semantics and baseline-vs-candidate efficiency evidence.
- **Execution Harness:** controlled environment wrapper for capabilities, approvals, budgets, operation invocation, validation, tracing, idempotency and recovery.
- **Persistent Flow:** versioned orchestration definition and version-pinned run instance with events, checkpoints, branches, waits, retries, pause/resume and recovery.

A flow owns progress. A habit owns reuse/optimization. A harness owns the execution boundary. See [the machine-habit and flow architecture](docs/MACHINE_HABITS_AND_FLOWS.md).

## Current implementation

- `src/habitroute/machine.py` — machine-habit model, harness profile, operation-effect semantics, authorization, aggregate efficiency gate and adapter-driven habit executor.
- `src/habitroute/flows.py` — versioned flow definitions, event reducer, persistent run controller and local append-only JSONL journal.
- `src/habitroute/worker.py` — one-node-per-dispatch worker for operation and exact-version habit nodes, backed by the harness adapter and exact-version in-memory registry.
- `src/habitroute/contracts.py` and `execution.py` — earlier RL-style route/option prototype retained for historical comparison; not canonical.
- `experiments/step_savings_v1/` — preserved synthetic transition-route and step-savings experiment.

The worker is not a distributed workflow service. The security implementation branch is stacked on draft PR #12 (`feat/per-operation-checkpoints-v0.1`), which adds per-operation flow checkpoints for multi-operation habits. Both PRs remain unmerged to `main`; the current `main` branch should not be described as having those changes yet. See [core status](docs/CORE_STATUS.md) and the [repository assessment](docs/HABITROUTE_ASSESSMENT.md).

## Autonomous runtime security

- `src/habitroute/autonomy/` — scoped short-lived capability tokens, attenuated delegation with aggregate ancestor budgets, deterministic idempotency, a SQLite-backed FlowJournal with Merkle audit, immutable trigger hydration, an egress-enforcing HarnessAdapter, provider-verified recovery gates, and shadow-replay/Control Plane promotion checks.
- [Autonomous Runtime Security Constitution](docs/AUTONOMOUS_RUNTIME_SECURITY.md) — implementation contracts, integration example and explicit trust boundaries.
- [Production Security Adapters](docs/PRODUCTION_SECURITY_ADAPTERS.md) — recommended production identity, credential, policy, egress, persistence, audit and recovery integrations with release gates.
- [Isolated Egress Lab](deploy/security-lab/compose.yaml) — executable Envoy + OPA boundary test with an agent container isolated from policy and upstream networks.

This is a reference enforcement layer, not a claim that production infrastructure is already deployed. External operations fail closed without an egress proxy; explicitly destructive operations require provider-verified recovery evidence; action-bound approvals include the exact input and idempotency digest; high-risk external operations can require an independently anchored audit head. The local HMAC broker is for tests/prototypes, not production key management. The SQLite journal is a local trust-boundary store, not a distributed workflow service.

## Research and design

- [Machine habits, harnesses and persistent flows](docs/MACHINE_HABITS_AND_FLOWS.md)
- [Machine Habit Specification v0.2](docs/HABIT_SPEC_v0.1.md) — canonical content; filename retained from the initial research branch.
- [Research review](docs/HABIT_MODEL_RESEARCH.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Contradictions in the legacy route experiment](docs/CONTRADICTIONS_AND_GAPS.md)
- [Core status](docs/CORE_STATUS.md)
- [Roadmap](docs/ROADMAP.md)
- [Decisions](docs/DECISIONS.md)
- [Repository Study and Technical Assessment](docs/HABITROUTE_ASSESSMENT.md)

## Unified Agent Runtime direction

The accepted direction is to evolve this repository into a modular monorepo hosting HabitRoute and Context Package Manager (CPM). CPM owns context selection and context-cache concerns; HabitRoute owns machine habits, harness authorization and persistent execution. A thin runtime will compose them through versioned, provider-neutral contracts. Neither package will import the other, and their stores remain separate.

This is an architecture decision and preparation effort—not a claim that CPM is already integrated. See [the decision record](docs/UNIFIED_RUNTIME_DECISION.md), [CPM integration plan](docs/CPM_INTEGRATION_PLAN.md), and [migration plan](docs/MIGRATION_PLAN.md).

## Verification principle

A habit is not promoted because it is shorter. Baseline and candidate must use a comparable input cohort and harness; output/postcondition reliability must be preserved within a declared tolerance; and at least one predeclared cost metric must improve. Other costs and quality measures remain visible.

## Persistent execution principle

The local flow journal is append-only and fsyncs events before the in-memory flow state advances. It uses a single-writer-per-run contract. This does not guarantee exactly-once external side effects: operation adapters still require idempotency, deduplication, compensation or manual reconciliation according to their side-effect class.

## Legacy experiment evidence

The original simulator studies 12-state and 24-state worlds, capacity-limited memory, audit, pruning, slips and rewiring. Its results remain experiment-specific; they do not demonstrate real API/tool workflow savings or crash-safe orchestration. Usage utility remains the default; step-savings is an opt-in policy.

## Verification status

The latest observed core test matrix is [45199663771](https://github.com/Loofy147/HabitRoute/actions/runs/45199663771), on commit `6133b46fce267981ac03ba515fa5f3f509c17340`, completed successfully across Python 3.11, 3.12 and 3.13. The Envoy + OPA integration workflow [45199663761](https://github.com/Loofy147/HabitRoute/actions/runs/45199663761) is still in progress and is not yet counted as passing. PR #18 remains a draft stacked on PR #12; neither is merged to `main`.

## Install and test

```bash
python -m pip install -e .
python -m pip install -r experiments/step_savings_v1/requirements.txt
python -m unittest discover -s tests -v
```

Python 3.11+; core modules use the standard library only. The legacy simulator tests install NumPy separately.

## License

MIT. See [LICENSE](LICENSE).


### Run the isolated egress lab

Requires Docker Engine and Docker Compose v2:

```sh
docker compose -f deploy/security-lab/compose.yaml up --build --abort-on-container-exit --exit-code-from agent
docker compose -f deploy/security-lab/compose.yaml down --volumes --remove-orphans
```

The lab verifies an allowlist decision, denied methods/paths, and the agent's inability to contact the mock upstream, policy service, or public internet directly. It demonstrates the network Policy Enforcement Point boundary only; it does not claim production workload identity, provider credentials, or capability-token validation.
