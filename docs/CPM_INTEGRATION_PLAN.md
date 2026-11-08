**Architecture note (2026-11-08):** This source-import plan is retained, but its former semantic boundary is superseded by [Machine Habit Model v0.3](MACHINE_HABIT_MODEL_V0.3.md). The habit owns context requirements and use policy; CPM is an optional repertoire capability. See also [the revised unified-runtime decision](UNIFIED_RUNTIME_DECISION.md).

# Context Package Manager Integration Plan

**Initial source:** CPM v0.5.0  
**Archive SHA-256:** `9824b6ca364bac9f5634e9d05fa5731735fa937d74b23f8eb030af8e5aad83f0`  
**Archive size:** 161,922 bytes  
**Python requirement:** >=3.11  
**Declared license:** MIT in `pyproject.toml`  
**Baseline:** 183 tests passed on Python 3.13.5 in the preparation environment

## What CPM actually contains

The inspected distribution is not a single import package. It contains:

- `contextpm`: context registry, package/skill resolution, manifests, planning, budgets, cache, checkpoints, runtime and adapters.
- `cheg`: governance, evidence, harness, metrics, orchestration and pipeline modules.
- CLI entry points: `cpm` and `cheg`.
- Bundled skills, registry data, examples, benchmark JSON and test suite.

Preserve both import packages and both CLI entry points. Do not rename `cheg` into `contextpm` or merge their modules during import.

## Landing location and packaging

Initial target: `packages/contextpm/`.

Keep the upstream distribution metadata and package structure intact in the first import. The package must remain independently installable:

```bash
python -m pip install -e packages/contextpm
cpm --help
cheg --help
PYTHONPATH=packages/contextpm/src python -m pytest -q packages/contextpm/tests
```

Do not add HabitRoute as a dependency of CPM. Do not make CPM import HabitRoute. The runtime consumes public interfaces and records references to immutable CPM outputs.

## Import rules

1. Import the exact pinned v0.5.0 source before making integration changes.
2. Exclude generated runtime state, including `.cpm-runtime-cache/`, SQLite caches, bytecode, local test caches and machine-specific state.
3. Preserve original release documentation, skill files, registry data, benchmark artifacts and test fixtures.
4. Preserve the original archive SHA in a source lock/manifest.
5. Keep upstream and local integration changes distinguishable.
6. Run upstream CPM tests unchanged before adding cross-package tests.
7. Record the Python version, commands, exit status and test count in the migration evidence.

## Revised CPM responsibility under Machine Habit Model v0.3

The Machine Habit owns its context requirements, situation model and decision about when/how to request context. CPM is a capability the habit may use to resolve package references, retrieve material, apply progressive disclosure, account for budgets and cache results. CPM returns versioned context manifests with IDs/digests and provenance; the habit records the exact manifest and decides how that context affects its strategy.

CPM remains independently installable and may retain its own registry/cache stores. This is an implementation boundary, not a claim that context management is outside the habit's governed repertoire. The habit owns the use policy; CPM supplies the context-management implementation. The host still enforces access permissions and data boundaries.

## Accounting requirements

Never label UTF-8 byte counts as actual model tokens. A context manifest must identify the tokenizer/accounting method and distinguish:

- estimated bytes;
- configured tokenizer counts;
- provider-reported input/output usage;
- cache retrieval/read/write work;
- context occupancy.

Unknown usage remains unknown, not zero. Cache hit-rate, cache reads and context footprint are separate metrics.

## CPM-specific open gates

- The v0.5.0 archive has no top-level `LICENSE` file even though `pyproject.toml` declares MIT. The repository's MIT selection is compatible at the declared-license level, but provenance and complete notices should be checked before release.
- The v0.5.0 verification record marks actual container isolation as NOT_RUN; do not describe it as proven.
- The fixture quality score is not a live semantic quality evaluation; quality parity is not established.
- Benchmark footprint reductions are not provider-reported token reductions.
- Confirm all included skills, examples and generated artifacts are distributable under the intended terms before publishing the combined distribution.

## Acceptance criteria

- Both `contextpm` and `cheg` import successfully from the nested source layout.
- `cpm` and `cheg` CLI entry points work in an isolated environment.
- CPM's original tests pass unchanged.
- HabitRoute works when the CPM package is absent.
- CPM works when HabitRoute is absent.
- Runtime integration tests pass without private-module imports.
