"""Transactional local flow journal, invocation ledger and Merkle audit.

SQLite WAL + FULL synchronous durability is a local single-writer trust boundary.
It is not a distributed workflow database or an externally anchored transparency log.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Iterable, Protocol


_SECRET_KEY = re.compile(r"(?:password|passwd|secret|token|private[_-]?key|authorization|api[_-]?key)", re.I)
_SECRET_VALUE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:bearer\s+[A-Za-z0-9._~+/-]{16,})|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _check_safe(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            name = str(key)
            if not name.lower().endswith(("_ref", "_uri")) and _SECRET_KEY.search(name):
                raise ValueError("refusing to persist secret-bearing field name")
            _check_safe(child)
    elif isinstance(value, str) and _SECRET_VALUE.search(value):
        raise ValueError("refusing to persist bearer-token/private-key pattern")
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_safe(child)


def _leaf(raw: str) -> bytes:
    return hashlib.sha256(b"\x00" + raw.encode("utf-8")).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _split(size: int) -> int:
    return 1 << ((size - 1).bit_length() - 1)


def merkle_root(leaves: Iterable[bytes]) -> bytes:
    values = tuple(leaves)
    if not values:
        return hashlib.sha256(b"").digest()
    if len(values) == 1:
        return values[0]
    k = _split(len(values))
    return _node(merkle_root(values[:k]), merkle_root(values[k:]))


def merkle_inclusion_proof(leaves: Iterable[bytes], index: int) -> tuple[bytes, ...]:
    values = tuple(leaves)
    if not 0 <= index < len(values):
        raise ValueError("leaf index outside tree")
    if len(values) == 1:
        return ()
    k = _split(len(values))
    if index < k:
        return merkle_inclusion_proof(values[:k], index) + (merkle_root(values[k:]),)
    return merkle_inclusion_proof(values[k:], index - k) + (merkle_root(values[:k]),)


def verify_merkle_inclusion(
    leaf_hash: bytes, leaf_index: int, tree_size: int,
    proof: Iterable[bytes], expected_root: bytes,
) -> bool:
    siblings = tuple(proof)[::-1]
    cursor = 0
    if tree_size < 1 or not 0 <= leaf_index < tree_size:
        return False

    def walk(index: int, size: int) -> bytes | None:
        nonlocal cursor
        if size == 1:
            return leaf_hash
        if cursor >= len(siblings):
            return None
        sibling = siblings[cursor]
        cursor += 1
        k = _split(size)
        if index < k:
            child = walk(index, k)
            return None if child is None else _node(child, sibling)
        child = walk(index - k, size - k)
        return None if child is None else _node(sibling, child)

    calculated = walk(leaf_index, tree_size)
    return cursor == len(siblings) and calculated == expected_root


@dataclass(frozen=True, slots=True)
class AuditHead:
    tree_size: int
    root_hash: str


class AuditAnchor(Protocol):
    def publish(self, head: AuditHead) -> str: ...
    def verify(self, head: AuditHead, receipt: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class ReconciliationEvidence:
    capability_id: str
    idempotency_key: str
    provider: str
    evidence_ref: str
    reconciled_by: str
    applied: bool
    observed_at: int
    receipt: str


class ReconciliationVerifier(Protocol):
    def verify(self, evidence: ReconciliationEvidence) -> bool: ...


@dataclass(frozen=True, slots=True)
class InvocationClaim:
    executable: bool
    attempt: int
    reason: str


class BudgetExceeded(PermissionError):
    pass


class IdempotencyConflict(ValueError):
    pass


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


class SQLiteFlowJournal:
    """FlowJournal-compatible SQLite store with transactionally paired audit leaves."""

    def __init__(self, path: str | os.PathLike[str], *, timeout: float = 30.0) -> None:
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError("journal path must not be a symbolic link")
        existed = self.path.parent.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not existed:
            os.chmod(self.path.parent, 0o700)
        self.timeout = timeout
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS flow_events(
                    run_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_id TEXT NOT NULL UNIQUE,
                    body TEXT NOT NULL, PRIMARY KEY(run_id, sequence));
                CREATE TABLE IF NOT EXISTS audit_action_ids(
                    action_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS audit_entries(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL, leaf_hash BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS audit_anchors(
                    tree_size INTEGER PRIMARY KEY, root_hash TEXT NOT NULL, receipt TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_revocations(
                    capability_id TEXT PRIMARY KEY, reason TEXT NOT NULL, revoked_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_budgets(
                    capability_id TEXT PRIMARY KEY, max_calls INTEGER NOT NULL, max_cost REAL NOT NULL,
                    used_calls INTEGER NOT NULL DEFAULT 0, used_cost REAL NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS invocations(
                    idempotency_key TEXT PRIMARY KEY, capability_id TEXT NOT NULL,
                    operation_ref TEXT NOT NULL, effect TEXT NOT NULL, input_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL, attempt INTEGER NOT NULL, last_error TEXT);
                CREATE TABLE IF NOT EXISTS trigger_receipts(
                    trigger_id TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL, run_id TEXT NOT NULL,
                    accepted_at INTEGER NOT NULL, audit_sequence INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS flow_initial_context(
                    run_id TEXT PRIMARY KEY, flow_id TEXT NOT NULL, definition_version INTEGER NOT NULL,
                    context_json TEXT NOT NULL, context_sha256 TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS audit_entries_no_update
                    BEFORE UPDATE ON audit_entries BEGIN SELECT RAISE(ABORT, 'append-only audit'); END;
                CREATE TRIGGER IF NOT EXISTS audit_entries_no_delete
                    BEFORE DELETE ON audit_entries BEGIN SELECT RAISE(ABORT, 'append-only audit'); END;
                CREATE TRIGGER IF NOT EXISTS flow_events_no_update
                    BEFORE UPDATE ON flow_events BEGIN SELECT RAISE(ABORT, 'append-only flow events'); END;
                CREATE TRIGGER IF NOT EXISTS flow_events_no_delete
                    BEFORE DELETE ON flow_events BEGIN SELECT RAISE(ABORT, 'append-only flow events'); END;
                CREATE TRIGGER IF NOT EXISTS audit_anchors_no_update
                    BEFORE UPDATE ON audit_anchors BEGIN SELECT RAISE(ABORT, 'append-only anchors'); END;
                CREATE TRIGGER IF NOT EXISTS audit_anchors_no_delete
                    BEFORE DELETE ON audit_anchors BEGIN SELECT RAISE(ABORT, 'append-only anchors'); END;
                CREATE TRIGGER IF NOT EXISTS trigger_receipts_no_update
                    BEFORE UPDATE ON trigger_receipts BEGIN SELECT RAISE(ABORT, 'append-only triggers'); END;
                CREATE TRIGGER IF NOT EXISTS trigger_receipts_no_delete
                    BEFORE DELETE ON trigger_receipts BEGIN SELECT RAISE(ABORT, 'append-only triggers'); END;
                CREATE TRIGGER IF NOT EXISTS flow_initial_context_no_update
                    BEFORE UPDATE ON flow_initial_context BEGIN SELECT RAISE(ABORT, 'immutable initial context'); END;
                CREATE TRIGGER IF NOT EXISTS flow_initial_context_no_delete
                    BEFORE DELETE ON flow_initial_context BEGIN SELECT RAISE(ABORT, 'immutable initial context'); END;
            """)
        for item in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
            if item.exists() and not item.is_symlink():
                os.chmod(item, 0o600)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=self.timeout, isolation_level=None, factory=_ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _audit(self, db: sqlite3.Connection, kind: str, body: dict[str, object]) -> int:
        safe = {"kind": kind, "at": int(time.time()), **body}
        _check_safe(safe)
        raw = _canonical(safe)
        cursor = db.execute(
            "INSERT INTO audit_entries(body, leaf_hash) VALUES(?, ?)", (raw, _leaf(raw))
        )
        return int(cursor.lastrowid)

    def append(self, event: object) -> None:
        raw = event.to_json()
        parsed = json.loads(raw)
        _check_safe(parsed)
        run_id, sequence, event_id = event.run_id, event.sequence, event.event_id
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT body FROM flow_events WHERE event_id=?", (event_id,)
            ).fetchone()
            if prior:
                if prior["body"] != raw:
                    raise IdempotencyConflict("flow event ID reused with different content")
                db.execute("COMMIT")
                return
            current = db.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS n FROM flow_events WHERE run_id=?", (run_id,)
            ).fetchone()["n"]
            if sequence != current + 1:
                raise ValueError(f"expected flow sequence {current + 1}, got {sequence}")
            db.execute(
                "INSERT INTO flow_events(run_id, sequence, event_id, body) VALUES(?, ?, ?, ?)",
                (run_id, sequence, event_id, raw),
            )
            self._audit(db, "flow_event", {
                "run_id": run_id, "sequence": sequence, "event_id": event_id,
                "event_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            })
            db.execute("COMMIT")

    def load(self, run_id: str) -> tuple[object, ...]:
        # Import lazily to avoid coupling the security layer to flow internals at import time.
        from ..flows import FlowEvent
        with self._connect() as db:
            rows = db.execute(
                "SELECT body FROM flow_events WHERE run_id=? ORDER BY sequence", (run_id,)
            ).fetchall()
        return tuple(FlowEvent.from_json(row["body"]) for row in rows)

    def audit_head(self) -> AuditHead:
        with self._connect() as db:
            rows = db.execute("SELECT leaf_hash FROM audit_entries ORDER BY sequence").fetchall()
        leaves = tuple(bytes(row["leaf_hash"]) for row in rows)
        return AuditHead(len(leaves), merkle_root(leaves).hex())

    def audit_proof(self, sequence: int) -> tuple[bytes, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT leaf_hash FROM audit_entries ORDER BY sequence").fetchall()
        leaves = tuple(bytes(row["leaf_hash"]) for row in rows)
        return merkle_inclusion_proof(leaves, sequence - 1)

    def verify_integrity(self) -> bool:
        with self._connect() as db:
            rows = db.execute("SELECT sequence, body, leaf_hash FROM audit_entries ORDER BY sequence").fetchall()
            events = db.execute("SELECT run_id, sequence, event_id, body FROM flow_events").fetchall()
            anchored = db.execute("SELECT tree_size, root_hash, receipt, receipt_sha256 FROM audit_anchors").fetchall()
        for row in rows:
            if _leaf(row["body"]) != bytes(row["leaf_hash"]):
                return False
        leaves = tuple(bytes(row["leaf_hash"]) for row in rows)
        root = merkle_root(leaves).hex()
        expected_events = {
            (row["run_id"], row["sequence"], row["event_id"],
             hashlib.sha256(row["body"].encode()).hexdigest()) for row in events
        }
        seen_events = set()
        for row in rows:
            body = json.loads(row["body"])
            if body.get("kind") == "flow_event":
                seen_events.add((
                    body.get("run_id"), body.get("sequence"), body.get("event_id"),
                    body.get("event_sha256"),
                ))
        if expected_events != seen_events:
            return False
        for row in anchored:
            prefix = merkle_root(leaves[:row["tree_size"]]).hex()
            if prefix != row["root_hash"]:
                return False
            if hashlib.sha256(row["receipt"].encode()).hexdigest() != row["receipt_sha256"]:
                return False
        return root == merkle_root(leaves).hex()

    def publish_audit_head(self, anchor: AuditAnchor) -> AuditHead:
        head = self.audit_head()
        receipt = anchor.publish(head)
        if not isinstance(receipt, str) or not receipt:
            raise ValueError("audit anchor returned an empty receipt")
        if not anchor.verify(head, receipt):
            raise PermissionError("audit anchor receipt failed verification")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO audit_anchors(tree_size, root_hash, receipt, receipt_sha256) VALUES(?, ?, ?, ?)",
                (head.tree_size, head.root_hash, receipt, hashlib.sha256(receipt.encode()).hexdigest()),
            )
            self._audit(db, "audit_anchor", {
                "tree_size": head.tree_size, "root_hash": head.root_hash,
                "receipt_sha256": hashlib.sha256(receipt.encode()).hexdigest(),
            })
            db.execute("COMMIT")
        return head

    def has_current_external_anchor(self, anchor: AuditAnchor | None) -> bool:
        if anchor is None:
            return False
        head = self.audit_head()
        with self._connect() as db:
            row = db.execute(
                "SELECT root_hash, receipt FROM audit_anchors WHERE tree_size=?",
                (head.tree_size,),
            ).fetchone()
        return bool(row and row["root_hash"] == head.root_hash
                    and anchor.verify(head, row["receipt"]))

    def require_current_external_anchor(self, anchor: AuditAnchor | None) -> None:
        if not self.has_current_external_anchor(anchor):
            raise PermissionError("current Merkle head lacks an independently verified external anchor")

    def revoke_capability(self, capability_id: str, reason: str = "revoked") -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO capability_revocations VALUES(?, ?, ?)",
                (capability_id, reason, int(time.time())),
            )
            self._audit(db, "capability_revoked", {"capability_id": capability_id, "reason": reason})
            db.execute("COMMIT")

    def is_capability_revoked(self, capability_id: str, ancestors: Iterable[str] = ()) -> bool:
        ids = tuple({capability_id, *ancestors})
        with self._connect() as db:
            row = db.execute(
                f"SELECT 1 FROM capability_revocations WHERE capability_id IN ({','.join('?' for _ in ids)}) LIMIT 1",
                ids,
            ).fetchone()
        return row is not None


    def append_audit(self, action_id: str, kind: str, body: dict[str, object]) -> int:
        """Append one idempotent audit action without storing bearer credentials."""
        if not action_id or not kind:
            raise ValueError("audit action_id and kind are required")
        safe = {"kind": kind, **body}
        _check_safe(safe)
        raw = _canonical(safe)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT sequence FROM audit_action_ids WHERE action_id=?", (action_id,)
            ).fetchone()
            if prior:
                row = db.execute(
                    "SELECT body FROM audit_entries WHERE sequence=?", (prior["sequence"],)
                ).fetchone()
                if row is None or row["body"] != raw:
                    raise IdempotencyConflict("audit action ID reused with different content")
                db.execute("COMMIT")
                return int(prior["sequence"])
            cursor = db.execute(
                "INSERT INTO audit_entries(body, leaf_hash) VALUES(?, ?)", (raw, _leaf(raw))
            )
            sequence = int(cursor.lastrowid)
            db.execute(
                "INSERT INTO audit_action_ids(action_id, sequence) VALUES(?, ?)",
                (action_id, sequence),
            )
            db.execute("COMMIT")
            return sequence

    def publish_audit_head(self, anchor: AuditAnchor) -> AuditHead:
        """Publish and persist a separately verified external tree-head receipt."""
        head = self.audit_head()
        receipt = anchor.publish(head)
        if not isinstance(receipt, str) or not receipt or not anchor.verify(head, receipt):
            raise PermissionError("external audit anchor receipt failed verification")
        digest = hashlib.sha256(receipt.encode()).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT root_hash, receipt_sha256 FROM audit_anchors WHERE tree_size=?",
                (head.tree_size,),
            ).fetchone()
            if existing and (existing["root_hash"] != head.root_hash or existing["receipt_sha256"] != digest):
                raise IdempotencyConflict("different external receipt already stored for this tree size")
            db.execute(
                "INSERT OR IGNORE INTO audit_anchors(tree_size,root_hash,receipt,receipt_sha256) VALUES(?,?,?,?)",
                (head.tree_size, head.root_hash, receipt, digest),
            )
            db.execute("COMMIT")
        return head

    def has_current_external_anchor(self, anchor: AuditAnchor | None) -> bool:
        if anchor is None:
            return False
        head = self.audit_head()
        with self._connect() as db:
            row = db.execute(
                "SELECT root_hash, receipt FROM audit_anchors WHERE tree_size=?",
                (head.tree_size,),
            ).fetchone()
        return bool(
            row and row["root_hash"] == head.root_hash
            and anchor.verify(head, row["receipt"])
        )

    def require_current_external_anchor(self, anchor: AuditAnchor | None) -> None:
        if not self.has_current_external_anchor(anchor):
            raise PermissionError("current Merkle head lacks an independently verified external anchor")

    def claim_invocation(
        self, *, capability_id: str, idempotency_key: str, operation_ref: str,
        effect: str, input_sha256: str, estimated_cost: float,
        max_calls: int, max_cost: float,
        budget_chain: Iterable[tuple[str, int, float]] = (),
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", input_sha256):
            raise ValueError("input_sha256 must be a SHA-256 digest")
        if not math.isfinite(estimated_cost) or estimated_cost < 0:
            raise ValueError("estimated_cost must be finite and non-negative")
        chain = tuple(budget_chain) + ((capability_id, max_calls, max_cost),)
        safe_effects = {"read_only", "idempotent", "deduplicated"}
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM invocations WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if row:
                identity = (row["capability_id"], row["operation_ref"], row["effect"], row["input_sha256"])
                if identity != (capability_id, operation_ref, effect, input_sha256):
                    raise IdempotencyConflict("idempotency key reused with different capability, operation, effect or input")
                if row["status"] in {"succeeded", "unknown", "running"}:
                    db.execute("COMMIT")
                    return InvocationClaim(False, row["attempt"], row["status"])
                if row["status"] == "failed" and effect not in safe_effects:
                    db.execute("COMMIT")
                    return InvocationClaim(False, row["attempt"], "unsafe_retry_blocked")
                attempt = row["attempt"] + 1
                db.execute(
                    "UPDATE invocations SET status='running', attempt=?, last_error=NULL WHERE idempotency_key=?",
                    (attempt, idempotency_key),
                )
            else:
                attempt = 1
                db.execute(
                    "INSERT INTO invocations VALUES(?, ?, ?, ?, ?, 'running', ?, NULL)",
                    (idempotency_key, capability_id, operation_ref, effect, input_sha256, attempt),
                )
            # Charge each ancestor and this capability in the same transaction.
            for budget_id, calls_limit, cost_limit in chain:
                db.execute(
                    "INSERT OR IGNORE INTO capability_budgets(capability_id,max_calls,max_cost) VALUES(?,?,?)",
                    (budget_id, calls_limit, cost_limit),
                )
                budget = db.execute(
                    "SELECT * FROM capability_budgets WHERE capability_id=?", (budget_id,)
                ).fetchone()
                if budget["max_calls"] != calls_limit or abs(budget["max_cost"] - cost_limit) > 1e-9:
                    raise PermissionError("capability budget ceiling changed after issuance")
                if budget["used_calls"] + 1 > calls_limit:
                    raise BudgetExceeded("capability call budget exhausted")
                if budget["used_cost"] + estimated_cost > cost_limit + 1e-12:
                    raise BudgetExceeded("capability cost budget exhausted")
                db.execute(
                    "UPDATE capability_budgets SET used_calls=used_calls+1, used_cost=used_cost+? WHERE capability_id=?",
                    (estimated_cost, budget_id),
                )
            self._audit(db, "invocation_reserved", {
                "capability_id": capability_id, "idempotency_key": idempotency_key,
                "operation_ref": operation_ref, "attempt": attempt, "input_sha256": input_sha256,
            })
            db.execute("COMMIT")
        return InvocationClaim(True, attempt, "reserved")

    def finish_invocation(self, idempotency_key: str, status: str, error: str | None = None) -> None:
        if status not in {"succeeded", "failed", "unknown"}:
            raise ValueError("invalid invocation terminal status")
        if error is not None and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", error):
            error = "adapter_error_redacted"
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT capability_id, operation_ref, attempt FROM invocations WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise KeyError("invocation reservation not found")
            db.execute(
                "UPDATE invocations SET status=?, last_error=? WHERE idempotency_key=?",
                (status, error, idempotency_key),
            )
            self._audit(db, "invocation_finished", {
                "capability_id": row["capability_id"], "operation_ref": row["operation_ref"],
                "idempotency_key": idempotency_key, "attempt": row["attempt"], "status": status,
            })
            db.execute("COMMIT")

    def reconcile_invocation(
        self, evidence: ReconciliationEvidence, verifier: ReconciliationVerifier,
    ) -> str:
        if not verifier.verify(evidence):
            raise PermissionError("provider reconciliation evidence failed independent verification")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT capability_id, status FROM invocations WHERE idempotency_key=?",
                (evidence.idempotency_key,),
            ).fetchone()
            if row is None or row["capability_id"] != evidence.capability_id:
                raise PermissionError("reconciliation evidence does not match a known invocation")
            if row["status"] not in {"running", "unknown"}:
                raise ValueError("only running/unknown invocations can be reconciled")
            status = "succeeded" if evidence.applied else "not_applied"
            db.execute(
                "UPDATE invocations SET status=?, last_error=NULL WHERE idempotency_key=?",
                (status, evidence.idempotency_key),
            )
            self._audit(db, "invocation_reconciled", {
                "capability_id": evidence.capability_id, "idempotency_key": evidence.idempotency_key,
                "provider": evidence.provider, "evidence_ref": evidence.evidence_ref,
                "reconciled_by": evidence.reconciled_by, "applied": evidence.applied,
                "receipt_sha256": hashlib.sha256(evidence.receipt.encode()).hexdigest(),
            })
            db.execute("COMMIT")
        return status

    def claim_trigger(
        self, *, trigger_id: str, payload_sha256: str, run_id: str,
        flow_id: str, definition_version: int, initial_context: dict[str, str],
    ) -> bool:
        _check_safe(initial_context)
        context_raw = _canonical(initial_context)
        digest = hashlib.sha256(context_raw.encode()).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT payload_sha256, run_id FROM trigger_receipts WHERE trigger_id=?",
                (trigger_id,),
            ).fetchone()
            if prior:
                if prior["payload_sha256"] != payload_sha256 or prior["run_id"] != run_id:
                    raise IdempotencyConflict("trigger ID reused with different payload or run")
                db.execute("COMMIT")
                return False
            existing = db.execute(
                "SELECT flow_id, definition_version, context_sha256 FROM flow_initial_context WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if existing and (
                existing["flow_id"] != flow_id or existing["definition_version"] != definition_version
            ):
                raise IdempotencyConflict("a run cannot change its pinned flow definition")
            self._audit(db, "trigger_accepted", {
                "trigger_id": trigger_id, "payload_sha256": payload_sha256, "run_id": run_id,
                "flow_id": flow_id, "definition_version": definition_version,
            })
            audit_seq = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO trigger_receipts VALUES(?, ?, ?, ?, ?)",
                (trigger_id, payload_sha256, run_id, int(time.time()), audit_seq),
            )
            if not existing:
                db.execute(
                    "INSERT INTO flow_initial_context VALUES(?, ?, ?, ?, ?)",
                    (run_id, flow_id, definition_version, context_raw, digest),
                )
            db.execute("COMMIT")
        return True

    def load_initial_context(self, run_id: str, flow_id: str, definition_version: int) -> dict[str, str]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM flow_initial_context WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError("trigger has not established initial flow context")
        raw = row["context_json"]
        if row["flow_id"] != flow_id or row["definition_version"] != definition_version:
            raise ValueError("flow definition/version does not match trigger receipt")
        if hashlib.sha256(raw.encode()).hexdigest() != row["context_sha256"]:
            raise ValueError("stored initial context digest mismatch")
        value = json.loads(raw)
        _check_safe(value)
        if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
            raise ValueError("stored initial context has invalid shape")
        return value
