# HabitRoute

**Efficient machine habits, controlled by harnesses, carried by persistent flows.**

HabitRoute is a research-to-engineering project for discovering, verifying, optimizing and reusing recurring machine-operation patterns. A machine habit is not a human habit and not an RL skill: it is an execution pattern that must preserve required results while reducing a measurable cost.

## Canonical model

- **Machine Habit:** reusable optimized operation pattern with triggers, inputs, preconditions, steps, postconditions, side-effect semantics and baseline-vs-candidate efficiency evidence.
- **Execution Harness:** controlled environment wrapper for capabilities, approvals, budgets, operation invocation, validation, tracing, idempotency and recovery.
- **Persistent Flow:** durable orchestration definition and version-pinned run instance with events, checkpoints, branches, waits, retries, pause/resume and recovery.

A flow owns progress. A habit owns reuse/optimization. A harness owns the execution boundary. See [the machine-habit and flow architecture](docs/MACHINE_HABITS_AND_FLOWS.md).

## Current implementation

- `src/habitroute/machine.py` — machine habit, harness profile, operation-effect semantics and efficiency gate.
- `src/habitroute/flows.py` — versioned flow definitions, event reducer, persistent run controller and local append-only JSONL journal.
- `src/habitroute/contracts.py` and `execution.py` — earlier RL-style route/option prototype retained for historical comparison; not canonical.
- `experiments/step_savings_v1/` — preserved synthetic transition-route and step-savings experiment.

## Research and design

- [Machine habits, harnesses and persistent flows](docs/MACHINE_HABITS_AND_FLOWS.md)
- [Machine Habit Specification v0.2](docs/HABIT_SPEC_v0.1.md)
- [Research review](docs/HABIT_MODEL_RESEARCH.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Contradictions in the legacy route experiment](docs/CONTRADICTIONS_AND_GAPS.md)
- [Core status](docs/CORE_STATUS.md)
- [Roadmap](docs/ROADMAP.md)
- [Decisions](docs/DECISIONS.md)

## Verification principle

A habit is not promoted because it is shorter. Baseline and candidate must use a comparable input cohort and harness; output/postcondition reliability must be preserved within a declared tolerance; and at least one predeclared cost metric must improve. Other costs and quality measures remain visible.

## Persistent execution principle

The local flow journal is append-only and fsyncs events before the in-memory flow state advances. It uses a single-writer-per-run contract. This does not guarantee exactly-once external side effects: operation adapters still require idempotency, deduplication, compensation or manual reconciliation according to their side-effect class.

## Legacy experiment evidence

The original simulator studies 12-state and 24-state worlds, capacity-limited memory, audit, pruning, slips and rewiring. Its results remain experiment-specific; they do not yet demonstrate real API/tool workflow savings or crash-safe orchestration.

## Install and test

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
~~~

Python 3.11+; core modules use the standard library only. The legacy simulator tests install NumPy separately through `experiments/step_savings_v1/requirements.txt`.

## License

No license has been selected. Default copyright applies.