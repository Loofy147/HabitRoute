# Migration Plan — HabitRoute-hosted Modular Monorepo

**Mode:** preserve-first; no rewrite  
**Host:** existing `Loofy147/HabitRoute` repository  
**Initial source pins:** see [REPOSITORY_BASELINE_2026-11-06.md](REPOSITORY_BASELINE_2026-11-06.md)

## Phase 0 — Prepare and document

- [x] Choose HabitRoute as the host repository.
- [x] Choose the modular monorepo architecture.
- [x] Record the HabitRoute implementation and gap assessment.
- [x] Pin CPM v0.5.0 archive and preserve its two-package identity.
- [x] Run CPM baseline tests: 183 passed.
- [x] Add repository MIT license in the preparation branch.
- [ ] Merge reviewed preparation documentation.

## Phase 1 — Import CPM unchanged

- Add CPM v0.5.0 under `packages/contextpm/`.
- Preserve `contextpm`, `cheg`, their scripts, tests, bundled skills, docs and examples.
- Remove generated runtime caches and local machine state only.
- Keep original project metadata in the package directory.
- Record archive digest, upstream release manifest, package metadata and import commit.
- Run CPM's original test suite unchanged.
- Run existing HabitRoute tests/legacy experiment checks unchanged.

**Exit:** both packages pass their own tests and can be installed/tested independently. No cross-package imports exist.

## Phase 2 — Freeze the integration boundary

- Place JSON Schemas under `shared/contracts/v0.1/`.
- Add schema validation and compatibility fixtures.
- Define IDs, versions, units, digest algorithm, unknown/null rules, idempotency references and provenance.
- Add tests using simple producers/consumers without private module imports.

**Exit:** contract compatibility tests pass; both packages remain independently functional.

## Phase 3 — Read-only composition

- Add `runtime/unified_agent_runtime/` for task orchestration.
- CPM prepares a context manifest; HabitRoute provides matching habit candidates.
- The runtime pins both in a run manifest and emits an explainable dry-run plan.
- No operation side effects are permitted in this phase.
- Test deletion/isolation: CPM-only and HabitRoute-only use still work.

**Exit:** deterministic planning, provenance complete, read-only by construction.

## Phase 4 — Repair HabitRoute operation durability

- Split machine-habit execution into one operation invocation/result at a time.
- Persist operation intent/attempt and commit a checkpoint after every side-effecting operation before advancing.
- Record provider request identity and idempotency contract.
- Define reconciliation for unknown outcome; unknown non-repeatable outcomes must stop in NEEDS_ATTENTION.
- Add fault injection before invocation, after provider side effect, before acknowledgement, after journal append and during replay.
- Keep compensatable operations blocked until real compensation is implemented and tested.

**Exit:** tested recovery preserves or reconciles actual external state; no unproven exactly-once claim.

## Phase 5 — Evidence-backed efficiency and learning

- Replace caller-supplied aggregate profiles as the sole evidence with raw paired trial records.
- Include exact case IDs/input digests and independent verifier results.
- Add trace ingestion, candidate discovery, shadow runs, staged promotion, monitoring and quarantine.
- Propagate complete cost vectors through habit execution and flow events.
- Preserve `step_savings_v1` unchanged; add new machine-tool experiments separately.

**Exit:** mutation-tested promotion gate and reproducible baseline/candidate reports.

## Phase 6 — Concrete adapters and distributed operation

- Begin with a narrow, read-only repository adapter.
- Enforce permissions, credential isolation, egress, hard timeouts, quotas and output limits at the actual provider boundary.
- Add transactional persistence or a documented single-writer lease before multi-worker support.
- Add scheduler, approval callback and snapshot/compaction only when required.
- Perform threat modeling, failure injection, rollback tests and deployment-specific operational review.

**Exit:** evidence for a specific deployment and adapter set. Do not label the overall project production-ready by default.

## Migration discipline

Every phase records source SHA, source archive digest, exact commands, environment, test counts, diffs, known limitations and rollback procedure. Do not edit upstream package code in the same commit that imports it.
