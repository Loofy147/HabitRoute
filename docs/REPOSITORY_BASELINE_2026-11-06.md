# Repository Baseline — 2026-11-06

This is a dated snapshot, not a live status page. Reinspect the branch and workflow before relying on it after this date.

## HabitRoute source pin

- Repository: `Loofy147/HabitRoute`
- Default branch: `main`
- Inspected HEAD: `43d714c8760a15026e0acb966919f483d893e7d0`
- Latest commit date: 2026-11-04T13:46:25Z
- Commit message: `Test persisted approval reason and explicit needs-attention dispatch status`
- Source paths inspected: README, pyproject, canonical machine/flow/worker modules, core status, roadmap, architecture, decisions, workflow, worker tests and experiment results.

## CI evidence

- Workflow: `.github/workflows/tests.yml`
- Latest observed run: [41841168040](https://github.com/Loofy147/HabitRoute/actions/runs/41841168040)
- Commit: `43d714c8760a15026e0acb966919f483d893e7d0`
- Conclusion: `success`
- Matrix: Python 3.11, 3.12, 3.13
- Exact test count for this run: not obtained.
- Historical 77/77 count applies to commit `090fc7c3fddbc95c7b128045fa7a20ab3dd63400`, not the latest SHA.

## Repository metadata at inspection

- Public Python repository.
- GitHub-reported size: 149 KB.
- No release/tag observed.
- Two open issues observed (#1 and #2).
- No license was selected in repository metadata at inspection; the preparation branch now adds an MIT LICENSE and declares it in project metadata. The license change is not part of historical main until merged.

## CPM source pin

- Distribution: Context Package Manager 0.5.0.
- Archive SHA-256: `9824b6ca364bac9f5634e9d05fa5731735fa937d74b23f8eb030af8e5aad83f0`.
- Archive size: 161,922 bytes.
- Distribution contains both `contextpm` and `cheg` import packages.
- CLI scripts: `cpm`, `cheg`.
- Python >=3.11; `pyproject.toml` declares MIT.
- Archive contains no top-level LICENSE file.
- Preparation environment: Python 3.13.5; CPM tests: 183 passed.
- The CPM wheel/release verification record has additional claims; only claims reproduced in this preparation run are marked tested.

## Known evidence limitations

- HabitRoute upstream CI success is not a local rerun in the monorepo.
- CPM test success does not establish compatibility with HabitRoute.
- No combined runtime test exists yet.
- The HabitRoute legacy step-savings experiment is synthetic and has no formal significance test.
- CPM footprint estimates are not provider-reported token usage; fixture score is not live semantic quality parity; container isolation was marked NOT_RUN.
