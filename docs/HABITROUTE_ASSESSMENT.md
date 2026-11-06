# HabitRoute — Repository Study and Technical Assessment

**Assessment mode:** source-backed inspection  
**Repository:** `Loofy147/HabitRoute`  
**Inspected `main` SHA:** `43d714c8760a15026e0acb966919f483d893e7d0`  
**Commit date:** 2026-11-04 13:46:25 UTC  
**Latest observed Actions run:** `41841168040`, completed successfully for Python 3.11, 3.12 and 3.13  
**Assessment snapshot:** 2026-11-06

## 1. What the project represents

HabitRoute is not a conventional human habit tracker. It is a research-to-engineering system for discovering, verifying, optimizing and reusing recurring machine-operation patterns.

Its canonical entities are:

- **Machine Habit:** immutable/versioned reusable operation pattern with scope, trigger, input and precondition contract, steps, postconditions, side-effect semantics and baseline-versus-candidate efficiency evidence.
- **Execution Harness:** controlled execution boundary for capabilities, permissions, approvals, budgets, invocation, validation, retries, idempotency, tracing and recovery.
- **Persistent Flow:** versioned workflow definition and mutable run instance with progress, current node, exact version pins, events, waits, branches, retries, pause/resume and recovery.

The separation is sound: a flow owns progress, a habit owns reuse/optimization, and a harness owns execution authority.

Canonical design: [MACHINE_HABITS_AND_FLOWS.md](MACHINE_HABITS_AND_FLOWS.md).

## 2. Implementation inventory

| Component | Source | Status at inspected SHA |
|---|---|---|
| Machine-habit contracts | `src/habitroute/machine.py` | Implemented |
| Operation effect classification | `machine.py` | Implemented |
| Harness profile and authorization | `machine.py` | Initial contract-layer implementation |
| Efficiency gate | `machine.py` | Initial aggregate-profile implementation |
| Persistent flow definition | `src/habitroute/flows.py` | Implemented |
| Event reducer and local journal | `flows.py` | Implemented |
| Flow worker | `src/habitroute/worker.py` | Implemented, limited |
| Exact-version habit registry | `worker.py` | In-memory only |
| Production API/CLI/repository adapters | — | Not implemented |
| Automatic trace ingestion/discovery | — | Not implemented |
| Automated promotion/quarantine | — | Not implemented |
| Distributed persistence and multi-worker leases | — | Not implemented |

The worker is already present. It dispatches one flow node per call and handles ordinary operation nodes and exact-version habit nodes through a harness adapter. Its tests use a simulated `StubHarness`; no concrete production provider adapter was present in the inspected tree.

## 3. Legacy step-savings experiment

The preserved `experiments/step_savings_v1/` research compares usage utility with a step-savings retention policy in synthetic 12-state and 24-state worlds, eight paired seeds, `sigma=2`, capacity-limited experiments and repeated transition-rewiring cycles.

The retention score is:

`S(h) = P(success | h) * (coverage_weight * unique_route_coverage + marginal_steps_saved)`

The policy remains opt-in and usage utility remains the overall default.

### Capacity-28 results

| World | Metric | Utility | Step-savings (weight 0.5) |
|---|---|---:|---:|
| 12-state | D+1 success | 0.513 | 0.904 |
| 12-state | Steps | 4.271 | 2.908 |
| 24-state | D+1 success | 0.883 | 0.963 |
| 24-state | Steps | 3.746 | 3.254 |

### Fifth repeated-change cycle

| World | Metric | Utility | Step-savings (weight 0.5) |
|---|---|---:|---:|
| 12-state | Success | 0.917 | 0.915 |
| 12-state | Steps | 4.294 | 3.552 |
| 24-state | Success | 0.829 | 0.817 |
| 24-state | Steps | 4.508 | 4.577 |

Interpretation: step-savings improves the tested capacity-28 cases, but it does not consistently outperform utility during repeated changes. The 24-state fifth-cycle success and steps are slightly worse. The report contains paired directional counts and sample summaries, but no formal significance test or p-values. These are synthetic results, not proof of machine-tool or agent-runtime efficiency.

Sources: [RESULTS_REPORT.md](../experiments/step_savings_v1/RESULTS_REPORT.md) and [REPEATED_CHANGE_ANALYSIS.md](../experiments/step_savings_v1/REPEATED_CHANGE_ANALYSIS.md).

## 4. Critical and high-priority gaps

### G1 — Multi-operation habit execution lacks per-operation durable checkpoints
**Severity: Critical.** The habit execution path invokes a sequence through `execute_machine_habit()`; the worker commits its flow event after the sequence returns. If the process fails after an external step but before the habit result/event is committed, earlier side effects can exist without matching per-step flow checkpoints. This conflicts with the architecture's per-side-effect checkpoint principle.

### G2 — Durable local journal does not guarantee external-effect safety
**Severity: Critical.** The JSONL journal can append/fsync/replay local events, but it does not share an atomic transaction with remote providers. Idempotency only protects a call when the provider actually implements and honors the key. Unknown non-repeatable outcomes need provider reconciliation, compensation or manual intervention. Exactly-once external effects are not established.

### G3 — Efficiency gate accepts caller-supplied aggregates
**Severity: High.** `EfficiencyGate` checks cohort labels, sample counts, Wilson lower bounds and a declared cost metric. It does not independently verify that the same case IDs and inputs were used, that trials were paired, or that raw results came from independent verification. The gate is a useful decision rule, not a complete experiment/evidence system.

### G4 — Total economic measurement is incomplete
**Severity: High.** Operation results include duration, resource units and external cost, but habit-level execution records and flow habit metadata do not fully propagate/reconcile all dimensions. Model tokens, context occupancy, retrieval/cache work, compute, memory and recovery costs need explicit, separately typed measurements. Do not sum unlike units.

### G5 — Harness declarations are not yet production enforcement
**Severity: High.** The profile declares allowlists, approvals and attempt limits. Production controls for credentials, provider permissions, network egress, hard budgets, timeouts, cancellation, output limits and OS/cloud isolation are not implemented by the test stub. A declaration is not proof of enforcement.

### G6 — Learning lifecycle is manual
**Severity: High.** Complete trace ingestion, candidate discovery, matched trials, staged promotion, monitoring, drift detection and quarantine are not implemented. The habit registry is currently in-memory and performs exact-version lookup.

## 5. Documentation and repository inconsistencies

| Finding | Assessment |
|---|---|
| `CORE_STATUS.md` says the worker is missing | Stale; `worker.py` exists |
| README implementation list omits the worker | Incomplete |
| Roadmap does not account for the implemented worker | Needs reconciliation |
| Issue #2 still lists the worker as outstanding | Stale against the inspected tree |
| Issue #1 says it is superseded by #2 but remains open | Reconcile issue history; do not erase provenance |
| Spec file name says v0.1 while canonical content says v0.2 | Legacy filename; can be renamed in a separate cleanup |
| `pyproject.toml` describes adaptive skills/route memory | Outdated description |
| README's 77/77 test count points to an earlier SHA | Do not present it as a test count for the latest run |

## 6. Verification and maturity

At the inspected snapshot the repository was public, Python-based, 149 KB by GitHub metadata, with `main` as its only observed branch and no release/tag observed. The latest observed workflow run, `41841168040`, completed successfully on the inspected SHA for Python 3.11, 3.12 and 3.13. Its exact latest test count was not obtained; 77/77 belongs to an earlier commit and must remain historical.

There were two open issues. Issue #1 was explicitly described as superseded by #2 but remained open. Issue #2 still listed worker implementation as outstanding despite the worker source and tests being present.

The project is **not production-ready**: no production adapters, distributed store, multi-worker coordination, durable habit registry, discovery/promotion pipeline or proven cross-system recovery guarantees exist.

## 7. Integration consequence

CPM and HabitRoute should remain separate packages. A habit may declare required skill/context IDs as metadata. The runtime resolves them with CPM and records the manifest identity/digest. HabitRoute executes only under its harness and flow rules. CPM does not store habit definitions, and HabitRoute does not import or load CPM skill bodies.

This context-to-operation feedback loop is a research hypothesis. It requires controlled paired experiments before it can be described as a capability.

**Immediate blocker before side-effecting combined execution:** close G1 and G2 with per-operation checkpoints, crash injection, provider idempotency/reconciliation and recovery evidence.
