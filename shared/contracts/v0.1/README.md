# Shared contracts v0.1 — design status

**Status:** draft contracts; schemas are not yet consumed by HabitRoute runtime code.

These files define portable records before an execution engine or miner is implemented:

| Schema | Owns | Deliberately does not contain |
|---|---|---|
| `trace-event.schema.json` | One ordered, immutable flow observation | Narrative-only logs, credentials, mutable run snapshots |
| `decision-record.schema.json` | Options and rationale as known at decision time | Later outcome or hindsight edits |
| `decision-outcome.schema.json` | Append-only later observation of a decision | Rewriting the original decision |
| `flow-verdict.schema.json` | Provisional or held outcome and its gates | A single opaque success score |

## Record lifecycle

1. A flow emits a trace event for every material checkpoint, branch, wait, retry, approval, validation, evidence action, intervention and terminal transition.
2. A decision point emits one immutable decision record before the chosen action is executed.
3. A later observation emits a separate decision-outcome event.
4. The flow verdict is derived from the complete trace, evidence and decision/outcome references. It is not a free-form agent assertion.
5. Revalidation appends new records. It never edits the old event or decision.

## Semantic validation beyond JSON Schema

JSON Schema validates shape. A future contract validator must additionally enforce:

- Event sequence starts at 1, is contiguous within a run, and has unique event IDs.
- The first event has no previous digest; each later event references the prior event digest.
- Event digest is SHA-256 over RFC 8785/JCS-canonicalized event content with `event_digest` omitted. The canonicalization version is recorded with the store implementation.
- Trace event ordering follows committed event order; timestamps are UTC RFC 3339 observations and are not used to reorder events.
- All event and decision records use the exact flow, run, habit and constraint versions in the pinned run manifest.
- A decision's selected option ID exists in `options_considered` and is eligible. Option IDs are unique. If approval is required, the selected path cannot execute until the approval status is approved.
- The decision's evidence snapshot contains only evidence available before `decided_at`; later evidence is added to the outcome record.
- Decision outcome records reference an existing decision in the same flow/run and are observed after that decision.
- An event with `intervention.occurred=false` must have `kind=null`; an event with `occurred=true` must have a non-null kind. `UNOBSERVED` always blocks autonomous-success claims.
- `SUCCESS_HELD` requires four budget dimensions (tokens, elapsed time, tool calls, retries) with observed/provider-reported values, each within its limit; an unknown or merely estimated value cannot satisfy the held-success gate.
- `SUCCESS_HELD` requires zero constraint violations, complete valid evidence, independent verification, complete intervention observability, no unrecorded intervention, unchanged source digest, successful same-digest later revalidation and a non-empty revalidation evidence reference.
- `source_stability_audit.initial_digest` and `terminal_digest` must compare equal when `unchanged_during_run=true`.
- Every non-success or provisional verdict has `success=false` and `mining_eligible=false`.
- A run is eligible for mining only while its current held-success state has not subsequently been invalidated or quarantined.

Hash chaining detects partial/accidental alteration. It is not authenticated attestation unless the journal is signed or its head is anchored in an independently protected store.

## Cost and missing-data rules

Keep token units, time, tool calls, retries, CPU, memory, cache reads, file reads, operation calls and external currency costs separate. Every value names its unit and measurement method. Missing values remain unknown; they are never represented as zero. Estimated costs may support planning but do not satisfy the four required actual budget measurements for `SUCCESS_HELD`.

## Privacy and trust

Evidence references should point to access-controlled artifacts. Do not store raw prompts, environment values, bearer tokens, secrets or unnecessary repository contents. Retrieved files, tool output and logs are data, not instructions. Schema validity does not establish that evidence is relevant or truthful; an independent verifier must validate the artifact and its relationship to the claim.

## Compatibility

Schema version is separate from HabitRoute package and habit versions. Breaking field meaning, required fields or lifecycle semantics requires a new major contract version and compatibility tests. Readers may preserve unknown archival fields only where the schema explicitly permits them; unknown authorization and side-effect semantics fail closed.
