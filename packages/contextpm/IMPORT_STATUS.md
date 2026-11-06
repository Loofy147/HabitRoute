# CPM source intake status

**State: VERIFIED_SOURCE / NOT_YET_IMPORTED**

The selected source baseline is CPM 0.5.0. Its archive hash and independent test result are recorded in [the intake report](../../docs/CPM_SOURCE_INTAKE.md) and [SOURCES.lock.json](SOURCES.lock.json).

This file is intentionally a status marker, not a substitute for the source package. The actual `src/contextpm/`, `src/cheg/`, tests, skills, docs, examples, benchmarks and package metadata must be imported as a mechanical source snapshot in a subsequent change. Do not add the archive's generated `.cpm-runtime-cache/index.sqlite3` file.
