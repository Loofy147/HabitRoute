# CPM v0.5.0 source intake and verification

**Intake date:** 2026-11-06  
**Target repository:** `Loofy147/HabitRoute`  
**Target package path:** `packages/contextpm/`  
**Source distribution:** `context-package-manager-v0.5.0.zip`

## Decision

CPM v0.5.0 is the selected source baseline for the first monorepo import. It is not yet copied into the tracked package tree in this commit. This record pins and verifies the exact source artifact before import; it must not be interpreted as an integrated runtime.

## Source identity

| Field | Value |
|---|---|
| Archive size | 161,922 bytes |
| Archive SHA-256 | `9824b6ca364bac9f5634e9d05fa5731735fa937d74b23f8eb030af8e5aad83f0` |
| Distribution name | `context-package-manager` |
| Version | `0.5.0` |
| Python | `>=3.11` |
| Declared license | MIT |
| Import roots | `contextpm`, `cheg` |
| CLI entry points | `cpm`, `cheg` |
| Runtime dependencies | Standard library only |
| Optional extras | `tokenizer`, `dev` |

The archive hash was recomputed after materializing the Library artifact and matched the supplied `cpm-v0.5.0-SHA256SUMS.txt`.

## Independent test result

The extracted source was tested without modifying its package code:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

**Observed result:** 183 passed in 18.12 seconds in the current Python 3.13 environment.

The source release's own verification record reports 183 passed on Python 3.13.5. The current intake run independently reproduces the test count; it does not independently re-run every release-manifest check.

## Source layout confirmed

- `src/contextpm/` — context registry, planner, runtime, cache, policy, guard, isolation, adapters, checkpoints, ledger, experiments and CLI.
- `src/cheg/` — governance/evidence/harness package and CLI.
- `tests/` — package and regression tests.
- `skills/`, `docs/`, `examples/`, `benchmarks/` — supporting assets.

Both import roots and both CLI entry points must be preserved. Do not rename `cheg` or confuse its harness with HabitRoute's `HarnessAdapter`.

## Exclusions and cautions

1. The source ZIP contains `.cpm-runtime-cache/index.sqlite3`. This is generated runtime state, not source. It must not be imported into Git. The repository ignores `.cpm-runtime-cache/`.
2. The archive has no top-level `LICENSE` file even though `pyproject.toml` declares MIT. The monorepo's root MIT license is present. Preserve upstream attribution and confirm license provenance before publishing a standalone CPM distribution from this monorepo.
3. The reported 66.02% and 74.981% results are context-footprint reductions in specified deterministic measurements, not provider-token savings or demonstrated answer-quality parity.
4. The fixture scorer is not a semantic evaluator; the release explicitly marks quality-parity eligibility false.
5. Real Docker/Podman isolation was `NOT_RUN`; mocked isolation behavior tests are not proof of host isolation.
6. Distributed cache locking and multi-process concurrency remain out of scope.
7. The source package has not yet been wired into the root workspace, and no CPM/HabitRoute runtime integration is claimed.

## Import constraints

- Preserve the exact `contextpm` and `cheg` package roots.
- Preserve CPM's own `pyproject.toml`, tests, skills and data files in the package subtree.
- Do not import the generated SQLite cache.
- Do not rewrite CPM APIs or add a dependency on HabitRoute.
- Keep CPM independently installable and testable.
- Keep HabitRoute independently installable and testable.
- Put composition code only in `runtime/unified_agent_runtime/`.
- Record the source archive hash and import commit in the final source lock.
- Re-run CPM tests and HabitRoute tests independently, then run a combined import test.

## Status

**VERIFIED_SOURCE / NOT_YET_IMPORTED.** Source identity and test suite are verified. The actual source-tree import is a separate next commit and must be reviewed as a mechanical import, with a diff and tests.
