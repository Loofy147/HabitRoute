# UWS / HabitRoute Portfolio Alignment and Review Record

**Review date:** 2026-11-18  
**Status:** Documentation and roadmap alignment; no runtime activation  
**Host:** HabitRoute  
**Related architecture:** [UWS Human–Machine Twin PR #24](https://github.com/Loofy147/unified-knowledge-work-system/pull/24)

## 1. Purpose

This document keeps HabitRoute's roadmap aligned with the UWS Human–Machine Twin architecture without merging the projects' authority, storage or implementation claims.

- UWS owns project intent, goals, plans, accepted evidence references and project-level decisions.
- CPM owns context packages, context selection, manifests, budgets and context-cache records.
- HabitRoute owns machine habits, harness contracts, version-pinned flows, operation attempts and execution evidence.
- The host owns effective permissions and enforces them at the actual execution boundary.
- Independent verification determines what an operation's evidence supports.

The combined runtime is an accepted architecture direction, not an implemented product. The first cross-project milestone is read-only.

## 2. Current evidence and branch truth

| Work | Ref | Evidence | Status | Limitation |
|---|---|---|---|---|
| HabitRoute per-operation checkpoints | [PR #12](https://github.com/Loofy147/HabitRoute/pull/12), `feat/per-operation-checkpoints-v0.1`, head `c505d96fe011f94af8eae90fab84f6ebcf317c81` | Recorded GitHub Actions run 42703942809: 93/93 tests on Python 3.11, 3.12 and 3.13 | IMPLEMENTED_ON_DRAFT | Draft/unmerged; local JSONL/single-writer; unknown provider outcomes still need authority-bound reconciliation |
| Capability repertoire and situation-aware planning | [PR #10](https://github.com/Loofy147/HabitRoute/pull/10), `feat/habit-repertoire-composition-v0.3`, head `dd9d88e45b2bfd2dfeaa0130439838181ccc8c15` | PR #14 inherits this lineage | IMPLEMENTED_ON_DRAFT | Draft/unmerged; planner output is not permission |
| M3 read-only repository review | [PR #14](https://github.com/Loofy147/HabitRoute/pull/14), `integration/m3-readonly-persistent-repo-review-v0.1`, head `b7055142e5d10d656161a667db150fc2fea487e7` | Recorded Actions run 43221871510 passed Python 3.11–3.13 and Windows journal qualification | IMPLEMENTED_ON_DRAFT | Local-only read-only flow; no live UWS retrieval/auth/evidence registration; no semantic code correctness or project-test claim |
| UWS HGSB persistence | [PR #23](https://github.com/Loofy147/unified-knowledge-work-system/pull/23) + repair [PR #27](https://github.com/Loofy147/unified-knowledge-work-system/pull/27), head `49066e7f8222b73a0d28e87a8c9206160c77cbfb` | Disposable MySQL 8.4.13: migrations 0001–0006 + no-op second pass; 16/16 persistence tests and 3/3 validator tests passed; routing generation 13/13 | DISPOSABLE_DB_QUALIFIED_ON_DRAFT | Draft/unmerged; full application typecheck/build and MySQL 8.0 compatibility remain; no production activation or Actions run |
| Human–Machine Twin architecture | [UWS PR #24](https://github.com/Loofy147/unified-knowledge-work-system/pull/24) | Component ownership and read-only-first sequence documented | IMPLEMENTED_ON_DRAFT | Architecture only; combined runtime not implemented |
| UWS ↔ HabitRoute M3 integration | [HabitRoute issue #13](https://github.com/Loofy147/HabitRoute/issues/13) + [UWS issue #28](https://github.com/Loofy147/unified-knowledge-work-system/issues/28) | PR #14 implements a local slice; 2026-11-18 auth/storage audit completed | OPEN | No project-scoped service principal; protected UWS routes only accept user-session JWTs; no durable artifact-upload or idempotent service evidence receipt; host attestation remains local/unverified |
| Authority-bound unknown-outcome reconciliation | [HabitRoute issue #15](https://github.com/Loofy147/HabitRoute/issues/15) | Required receipt and state-transition contract documented | OPEN | No provider-specific authenticated reconciliation adapter |

**Default-branch rule:** work on PR branches must remain marked draft-only until merged. A passing test on a draft branch does not change the main-branch release status. The 2026-11-06 `CORE_STATUS.md` source baseline remains a dated default-branch snapshot; the table above is a later draft-evidence overlay, not a claim that those PRs are merged.

## 3. Dependency and merge order

1. **PR #10 — capability repertoire:** review/resolve the v0.3 base and its capability/host-boundary contracts.
2. **PR #12 — per-operation durability:** review/resolve reducer invariants, attempt accounting, stable idempotency identity and crash windows. Unknown outcomes remain blocked pending reconciliation.
3. **PR #14 — M3 read-only slice:** review/resolve its stacked lineage and separate integrity from completeness, semantic correctness and live UWS integration.
4. **Issue #28 + issue #13 — live UWS connection:** first implement UWS project-scoped service identity, versioned goal reads, durable artifact transport and idempotent evidence receipts; then implement HabitRoute's host attestation/client. HGSB schema presence and a local evidence digest are not enough.
5. **Issue #15 — authority-bound reconciliation:** complete provider/host receipt validation before any non-repeatable side effect can be retried.
6. **CPM import and thin runtime composition:** defer until source digest, license notices, original tests and independent installability have been reviewed. CPM is not a dependency for the first read-only Git slice unless a concrete requirement proves otherwise.

Do not merge in an order that silently imports divergent draft histories. Confirm actual base/head and exact source commits before each merge.

## 4. Higher-level architecture critique

### R1 — Goal pointers are not a live interface

PR #14 preserves UWS goal/task IDs as opaque references. This is useful provenance, but it does not prove that a current user owns the goal, that the goal is current, or that its acceptance criteria were retrieved.

**Change required:** introduce a project-pinned UWS service principal with explicit `goal:read` and `evidence:append` scopes, revocation and expiry. Do not reuse a user's HS256 session JWT as a service credential. Expose a versioned read-only GoalReference/TaskBrief response with owner/project scope, exact HGSB and plan revisions, acceptance criteria, evidence refs, freshness and authorization outcome. HabitRoute must reject missing, stale, expired, revoked or cross-project references.

### R2 — HostCapabilitySnapshot is not an authenticated permission grant

PR #14 explicitly says the snapshot is a planner input and immediate re-check, not a cryptographically authenticated host attestation.

**Change required:** the host authority creates and signs/attests the effective capability snapshot. The adapter verifies issuer, subject, repository root, exact capability ID/version, READ_ONLY effect, scope, expiry and revocation immediately before invoking Git. Planner choice never authorizes.

### R3 — Evidence integrity is not semantic correctness

The read-only verifier checks immutable commit resolution, inventory and blob integrity, and a before/after working-tree marker. This does not prove code correctness, security, tests passing, source authenticity or deployability.

**Change required:** return separate fields, never a single ambiguous SUCCESS:
- `integrity_status`;
- `completeness_status`;
- `semantic_review_status`;
- `project_tests_status`;
- `working_tree_unchanged`;
- `source_authenticity_status`.

Only mark a dimension verified when its own verifier ran.

### R4 — Read-only safety is specific to this operation

The current slice is safe to replay because it inspects immutable Git objects and does not run repository scripts, project tests, shell hooks or network operations. It must not generalize this replay rule to ordinary operations or side-effecting habits.

**Change required:** preserve effect-class distinctions and fail closed on any capability or input that broadens the operation beyond the reviewed READ_ONLY contract.

### R5 — Local durability and provider truth are different

Per-run OS locking helps serialize local journal writes. It does not create multi-host coordination or prove provider-side effects. Unknown outcomes must not be replayed blindly.

**Change required:** keep local topology explicit; reconcile ambiguous external outcomes through capability-specific, attributable and fresh receipts bound to exact run, flow, operation, attempt, idempotency key and evidence digest. A reconciled "not executed" outcome still needs a separate retry authorization.

### R6 — CPM integration risks scope expansion

The CPM plan correctly preserves `contextpm` and `cheg` separately and keeps package imports acyclic. However the source preparation notes open license/notice, container isolation and token-accounting questions.

**Change required:** do not import or advertise CPM as production-integrated until upstream source digest, complete notices, unchanged tests, clean isolated install, independent installability and usage accounting are verified.

## 5. HabitRoute roadmap correction rules

The roadmap's checkboxes are the state of the default branch, not the state of every open PR. Keep implementation items unchecked on `main` until merged. Use a draft-evidence overlay to record work done on a PR branch.

Recommended status terms:

- `MAIN_IMPLEMENTED` — code is on default branch and regression-protected.
- `DRAFT_IMPLEMENTED` — code is on an unmerged PR branch.
- `CI_VERIFIED` — exact-head test evidence is available; record the run and matrix.
- `INTEGRATION_VERIFIED` — cross-component test ran using real interfaces.
- `DEPLOYMENT_VERIFIED` — named environment and commit were actually exercised.
- `OPERATIONALLY_ACTIVE` — runtime health, permissions, recovery and support obligations are qualified.

No status should silently imply the next level.

## 6. Next implementation checklist

### M3.1 — Close the live read-only UWS handoff

- [ ] Issue #28: create/revoke a project-pinned UWS service credential with minimal scopes and hashed-at-rest secret; never use user-session impersonation.
- [ ] Issue #28: fetch an owner-authorized, versioned task brief with exact goal, state and plan revisions.
- [ ] Issue #28: persist artifact bytes durably and register evidence with an immutable, idempotent receipt.
- [ ] HabitRoute: authenticate the actual host capability snapshot (issuer, subject, repository, version, READ_ONLY effect, scope and expiry) and verify immediately before Git invocation.
- [ ] Verify owner, scope, revision and freshness before planning.
- [ ] Bind the exact repository identity and immutable base/target commits.
- [ ] Obtain and verify the authenticated host permission snapshot.
- [ ] Produce a bounded dry-run plan with no side effects.
- [ ] Re-check READ_ONLY permission immediately before Git inspection.
- [ ] Persist the version-pinned flow and content-addressed evidence package.
- [ ] Independently check commit identity, diff inventory, object/blob digests, completeness and working-tree immutability.
- [ ] Register the evidence reference in UWS against the exact goal/revision and obtain a durable receipt.
- [ ] Verify a fresh UWS read can retrieve the evidence registration.
- [ ] Fail closed for stale goal revision, wrong owner, wrong repository root, unavailable capability, missing permission, incomplete object and tampered artifact.
- [ ] Preserve separate verdicts for integrity, completeness, semantic review and project tests.

### M3.2 — Reconcile durability and branch dependencies

- [ ] Review PR #12 against its exact head and all crash-window tests.
- [ ] Review PR #10 capability authorization and situation freshness.
- [ ] Review PR #14's ported checkpoint logic against PR #12; detect drift rather than assuming equivalence.
- [ ] Merge only in dependency order with exact-head CI and required reviewer sign-off.
- [ ] Keep provider-specific reconciliation open until receipts are independently validated.
- [ ] Keep multi-host execution out of scope until a transactional store/lease and deployment tests exist.

### M3.3 — Freeze shared contracts

- [ ] Version UWS task brief, context manifest reference, host capability receipt, HabitRoute run manifest, evidence package and verifier result.
- [ ] Define correlation/causation IDs, owner scope, revisions, timestamps, freshness, digests and schema compatibility.
- [ ] Add producer/consumer compatibility tests using public interfaces only.
- [ ] Prove HabitRoute works when CPM is absent.
- [ ] Prove CPM works when HabitRoute is absent.
- [ ] Compose only read-only dry-run planning before enabling any side effect.

### M3.4 — CPM source import readiness

- [ ] Verify pinned archive SHA-256 and source release.
- [ ] Verify license and complete third-party notices.
- [ ] Preserve `contextpm`, `cheg`, `cpm` and `cheg` entry points.
- [ ] Run upstream tests unchanged in a clean environment.
- [ ] Record container-isolation test as NOT_RUN until it actually runs.
- [ ] Keep byte counts, tokenizer estimates and provider-reported tokens separate.

## 7. Reusable review checklist for HabitRoute changes

- [ ] Exact repository/branch/commit recorded.
- [ ] Component ownership and source-of-truth boundaries remain intact.
- [ ] Capability ID/version, effect class and host permission are explicit.
- [ ] Authz and deny paths are tested at the host/adapter boundary.
- [ ] Intent precedes side effect; result/checkpoint precedes next operation.
- [ ] Unknown outcomes fail closed; no generic exactly-once claim.
- [ ] Crash/restart, duplicate event, partial-write and stale-worker behavior are tested for the claimed topology.
- [ ] Evidence integrity, evidence completeness and semantic correctness are reported separately.
- [ ] Output quality and total cost use matched raw cases and independent verification.
- [ ] CPM/package provenance, licenses and independent installation are preserved.
- [ ] Docs distinguish main, draft, CI-verified, integration-verified and deployed states.
- [ ] Follow-up issues include owner, discriminating test and stop condition.

## 8. Immediate decision

**Proceed with M3.1 only, read-only.** Do not add side-effecting provider actions or distributed execution. The highest-value proof is one authenticated UWS goal read that produces a HabitRoute read-only review and returns a verified, registered evidence package to that exact UWS goal revision.

## 9. References

- [UWS portfolio roadmap and review checklist](https://github.com/Loofy147/unified-knowledge-work-system/blob/docs/portfolio-review-roadmap-v0.1/docs/PORTFOLIO_ROADMAP_AND_REVIEW_CHECKLIST_v0.1.md)
- [UWS Human–Machine Twin PR #24](https://github.com/Loofy147/unified-knowledge-work-system/pull/24)
- [UWS HGSB PR #23](https://github.com/Loofy147/unified-knowledge-work-system/pull/23)
- [HabitRoute PR #10](https://github.com/Loofy147/HabitRoute/pull/10)
- [HabitRoute PR #12](https://github.com/Loofy147/HabitRoute/pull/12)
- [HabitRoute PR #14](https://github.com/Loofy147/HabitRoute/pull/14)
- [HabitRoute issue #13](https://github.com/Loofy147/HabitRoute/issues/13)
- [HabitRoute issue #15](https://github.com/Loofy147/HabitRoute/issues/15)
- [CPM integration plan](CPM_INTEGRATION_PLAN.md)
- [Unified runtime decision](UNIFIED_RUNTIME_DECISION.md)
