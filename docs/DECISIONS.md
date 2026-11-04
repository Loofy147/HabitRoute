# Decisions and open questions

New evidence may supersede a decision, but the reason and affected experiments must remain visible.

## D-001 — Preserve the experiment as a separate baseline

**Status: accepted**

Keep the executable research harness under experiments/step_savings_v1/. Do not refactor it in place while building the new core. It is the comparison baseline.

## D-002 — Usage utility remains the overall default

**Status: accepted**

The existing agent default remains policy="utility". Step-savings is opt-in with coverage weight 0.5. It improves some capacity-28 results but does not solve repeated regime adaptation.

## D-003 — Habit means a versioned adaptive option

**Status: proposed target contract**

A habit has a scoped initiation contract, an internal controller, a semantic goal and termination contract, safety/interruption rules, predicted effects/costs, and version-scoped evidence. Fixed macros are one controller kind, not the entire definition.

## D-004 — Unknown states fail closed

**Status: accepted design rule**

Nearest-neighbor matching can retrieve candidate habits, but cannot authorize execution. Unknown/OOD or ambiguous state must use planning or a separately validated recovery path.

## D-005 — Certificates are per-version empirical attestations

**Status: accepted design rule**

The current start/goal revision cache is an audit cache, not a certificate. A certificate identifies one immutable habit version, context and representation scope, tested envelope and evidence. It is not a formal safety proof.

## D-006 — Keep objectives and failure causes separate

**Status: accepted**

Do not collapse success probability, confidence, coverage, duration, action cost, resource use, risk, recovery cost, audit and lookup overhead into one opaque number. Each remains observable even if a task-specific scalar is later used for selection.

## Open questions

- What initiation-region calibration threshold is appropriate for each task criticality?
- What evidence volume and posterior lower bound are required for probation-to-active promotion?
- Which context variables are sufficient to distinguish regimes without fragmenting the library excessively?
- When is a fixed sequence invariant enough to suppress internal decision-making?
- Which segmentation objective best trades macro reuse against branch coverage?
- How should option-terminal distributions be estimated under partial observation?
- Which sequential detector best separates slips, burst noise, representation errors and persistent change?
- What is the correct task-specific total-cost model?
- Which persistence and schema migration contract is needed for the public library?