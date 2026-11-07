# Operation Checkpoints and Recovery Contract

**Status:** implemented in draft PR #8; provider-independent local protocol with deterministic fault-injection tests. Not a claim of exactly-once execution or a production provider integration.

## 1. Purpose

A Persistent Flow node may be one operation or a Machine Habit containing multiple provider operations. Recording only the final node result is insufficient: a process can terminate after an external effect but before the node-level result reaches the local journal. Replaying the node can then repeat an already-applied non-repeatable effect or replay a completed prefix.

PR #8 adds operation-level intent/result events to the existing append-only JSONL flow journal.

## 2. Event protocol

For each logical provider operation, the worker performs:

`OPERATION_INTENT -> provider invocation -> OPERATION_SUCCEEDED | OPERATION_FAILED | OPERATION_OUTCOME_UNKNOWN`

The intent includes:

- current flow node and logical operation index;
- operation reference and declared effect class;
- idempotency key and attempt number;
- SHA-256 digest of canonicalized operation inputs;
- whether the adapter contract claims provider idempotency-key support.

The intent is appended and fsynced before the adapter is called. On POSIX, the journal also fsyncs its parent directory when first creating the run file. The event does not persist the raw resolved input mapping; it persists a digest. Existing flow context and successful operation outputs are still journaled as flow state.

A successful operation event persists outputs and observed duration, resource units and external cost. It becomes a completed-operation checkpoint in the reducer. A multi-operation habit commits one result per operation. Its final flow-node success event is separate and is committed only after all operation checkpoints and postconditions are satisfied.

The reducer rejects a result that does not match the pending operation index and idempotency key. It rejects a new intent while another intent is pending or when the attempt number is not the next expected attempt. A flow node cannot be completed or failed while an operation intent remains pending.

## 3. Recovery matrix

| Journal state after restart | Effect class | Recovery behavior |
|---|---|---|
| No intent for the next operation | Any currently authorized effect | Create and fsync a new intent before invocation. |
| Intent pending, no result event | READ_ONLY | Re-invoke; the effect is defined as having no external mutation. |
| Intent pending, no result event | IDEMPOTENT | Re-invoke with the same key and unchanged input digest. This relies on the operation genuinely being idempotent. |
| Intent pending, no result event | DEDUPLICATED | Re-invoke with the same key only when the actual provider durably deduplicates by that key. The code's boolean declaration is not independent proof. |
| Intent pending, no result event | NON_REPEATABLE or COMPENSATABLE | Do not invoke again. Commit unknown outcome and move the flow to NEEDS_ATTENTION. |
| Result checkpoint committed | Any effect | Skip that completed operation. Resume from the next missing index. |
| All operation checkpoints committed, node completion absent | Any effect | Re-evaluate postconditions and finish the flow node without re-invoking operations. |

An adapter-returned UNKNOWN or adapter exception also leaves the intent pending and moves the flow to NEEDS_ATTENTION. The implementation does not reinterpret unknown as failed or absent.

## 4. Reconciliation

`PersistentFlow.reconcile_pending_operation(...)` provides a core-library primitive for an external control plane:

- `applied=True` requires an evidence reference and a reconciler label. It records the confirmed outputs as a completed operation checkpoint and returns the flow to RUNNING so the remaining habit operations or final node completion can proceed.
- `applied=False` records that the operation was not applied, clears the pending intent, and leaves the flow in NEEDS_ATTENTION. It does not silently retry a non-repeatable operation.

The library stores `reconciled_by` as audit data; it does not authenticate that identity, authorize the decision, verify the evidence reference, or prove that the referenced provider query is truthful. A service must enforce authenticated operator identity, authorization, evidence provenance and tamper-resistant audit before exposing this method. Reconciliation is not a public unauthenticated endpoint.

## 5. Idempotency scope

The legacy `idempotency_key` remains a run/node scope for compatibility. External operations now use `operation_scope_key`, which includes a node-visit counter. It is stable across retries and crash recovery for one node visit, but changes when a flow returns to the same node in a later loop iteration.

A habit operation appends the exact habit ID, version and operation index to that scope. This prevents a provider's deduplication cache from confusing a new loop visit with the previous visit while preserving key stability for recovery of the same logical step.

## 6. Fault-injection evidence

The test suite now exercises:

- failure to append the intent: the adapter is not invoked;
- abrupt process termination after provider effect but before the adapter acknowledgement: a non-repeatable pending operation is not reissued;
- successful provider acknowledgement followed by result-checkpoint write failure: the pending intent remains and requires reconciliation for a non-repeatable operation;
- multi-operation habit crash after a completed prefix: completed operations are skipped after restart;
- DEDUPLICATED provider simulation: the same key is retried after lost acknowledgement and the provider applies the effect once;
- applied reconciliation: the operation is recorded complete and the worker continues without replay;
- not-applied reconciliation: the flow remains in NEEDS_ATTENTION and does not retry automatically;
- node-loop visit: retry retains its key while a later visit to the same node gets a different key.

The provider deduplication test is a simulated adapter contract. It does not prove any real provider's implementation. Tests of that guarantee must be added for each concrete adapter and provider version.

## 7. Guarantees and limitations

### Established by this implementation and tests

- A provider call is not started unless the local intent append/fsync returns successfully.
- A committed completed-operation checkpoint survives replay and is not re-executed by the worker.
- A non-repeatable pending intent is not automatically reissued after restart.
- A checkpointed prefix of a multi-operation habit is skipped after recovery.
- A failed local result append leaves the previously committed intent available for recovery.
- Operation attempts and idempotency identity are derived from the event history and replay deterministically in the tested local journal.

### Not established

- Atomic commit across the remote provider and local JSONL journal.
- Exactly-once effects for an arbitrary external provider.
- That an adapter's `idempotency_key_supported=True` claim is true; it must be validated provider by provider.
- Correctness of an operator's reconciliation decision or evidence reference.
- Multi-process/multi-host writers for a run; JSONL retains single-writer-per-run semantics.
- Robust recovery from arbitrary media corruption, torn final records, filesystem/controller failure, disk-full conditions after partial append, or power loss on every supported platform.
- Durable HabitRegistry, snapshot compaction, distributed leases, production authentication/approval service, or provider-side reconciliation adapter.

## 8. Remaining implementation gates

1. Run crash and replay tests on target filesystems and add explicit malformed/truncated-tail handling without discarding a potentially committed intent.
2. Implement a real provider adapter with a verified idempotency/reconciliation contract and deny-path tests.
3. Put reconciliation behind an authenticated approval boundary and bind each decision to immutable provider evidence.
4. Add a durable transactional store/lease before multi-worker or multi-host use.
5. Continue structured trace/decision/outcome emission and raw paired-trial persistence only after operation-level execution evidence is complete.
