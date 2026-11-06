# Open Risks and Blockers

Status is for the 2026-11-06 source snapshot. Close each item only with a reproducible artifact.

| ID | Severity | Risk | Required closure evidence |
|---|---|---|---|
| HR-01 | Critical | Multi-operation habit does not checkpoint each operation | Crash injection after each step; event journal shows durable operation intent/result and exact replay behavior |
| HR-02 | Critical | Local journal is not transactionally coupled to provider effects | Provider idempotency/dedup contract and reconciliation tests across lost acknowledgements |
| HR-03 | High | EfficiencyGate accepts caller-supplied aggregate profiles | Raw paired trial ledger, exact matched case IDs, independent verifier and mutation-tested promotion gate |
| HR-04 | High | Total cost dimensions are not propagated end-to-end | Per-step/flow/context cost vector with units, unknown semantics and aggregation tests |
| HR-05 | High | Harness profile can describe controls not actually enforced | Concrete adapters with deny tests for allowlist, credentials, approvals, timeout, egress and budgets |
| HR-06 | High | No automated habit discovery/promotion/quarantine | Trace provenance, candidate generation, shadow evaluation, promotion/quarantine state-machine tests |
| HR-07 | High | HabitRegistry is in-memory only | Durable exact-version store with immutable-content conflict tests |
| HR-08 | Medium | Local JSONL journal assumes one writer per run | Explicit lock/lease or transactional store before multiple workers |
| HR-09 | Medium | No journal snapshot/compaction | Replay equivalence tests and crash-safe snapshot rotation |
| HR-10 | High | CPM v0.5 quality/footprint evidence has limits | Provider-reported metrics and live semantic quality tests; don't infer from fixture scores or bytes |
| HR-11 | Medium | Legacy simulation has narrow synthetic scope | Raw seed artifacts, clean-clone reproduction, broader environment/stochastic tests |
| HR-12 | High | Package integration could introduce circular coupling | Import-graph checks and component-absence tests in CI |
| HR-13 | High | License compatibility/provenance of imported material | File-level license inventory, dependency/SBOM scan and preserved notices |

## Stop conditions

- A side-effecting non-repeatable operation with an unknown outcome must stop for reconciliation.
- A missing/invalid permission or approval must fail closed.
- An unknown operation-effect class must not be retried.
- An evidence-gate input with no trials or incomplete cases must not pass vacuously.
- A source/version mismatch invalidates habit eligibility until revalidated.
- A cost claim with missing dimensions must state what is unknown.
- No release claim may promote a plan, mock adapter or simulated test into production evidence.
