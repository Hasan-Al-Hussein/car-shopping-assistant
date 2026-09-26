"""Certified reads detect unchanged-count and hidden posting corruption."""

import json
import sqlite3
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.database.models import InventorySnapshotPayload
from app.database.store import Store, StoreError
from app.inventory.compact_reader import CompactInventoryReader
from app.inventory.index_storage import TOKEN
from app.inventory.persisted_fingerprint import (
    FTS_SCANS,
    FingerprintLayout,
    ScalarRow,
    _fts_mirror_check,
)
from app.inventory.snapshot_codec import canonical_json, digest_text
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage
from tests.inventory.compact_cases import admitted
from tests.inventory.snapshot_cases import counts, execute, record_evidence
from tests.inventory.test_snapshot_integrity import MUTATIONS


@pytest.mark.parametrize("mutation", tuple(MUTATIONS))
def test_warm_reader_rejects_original_corruption_matrix(
    inventory_store: Store, snapshot_plan: PreparedStage, mutation: str
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    before = counts(inventory_store, snapshot_plan.index.snapshot_id)
    execute(
        inventory_store,
        MUTATIONS[mutation],
        {
            "s": snapshot_plan.index.snapshot_id,
            "wrong": "f" * 64,
        },
    )
    with pytest.raises((ValueError, StoreError)):
        reader.read_refs((snapshot_plan.candidate.manifest.reference("1"),))
    assert counts(inventory_store, snapshot_plan.index.snapshot_id) == before
    record_evidence(
        "i5-warm-" + mutation,
        {
            "mutation": mutation,
            "requested_source_id": "1",
            "rejected": True,
            "canonical_counts_unchanged": True,
        },
    )


SHADOW_MUTATIONS = {
    "config": "INSERT INTO inventory_search_fts_config(k,v) VALUES('automerge',8)",
    "content": "UPDATE inventory_search_fts_content SET c4=c4 || ' shadow change'",
    "data": "UPDATE inventory_search_fts_data SET block=zeroblob(length(block)) WHERE id>10",
    "docsize": "UPDATE inventory_search_fts_docsize SET sz=zeroblob(length(sz))",
    "idx": "UPDATE inventory_search_fts_idx SET pgno=pgno+1",
}


@pytest.mark.parametrize("shadow", tuple(SHADOW_MUTATIONS))
def test_every_shadow_stream_is_bound_after_admission(
    inventory_store: Store, snapshot_plan: PreparedStage, shadow: str
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    batch = reader.read_refs(())

    def corrupt(session: Session) -> None:
        result = session.connection().exec_driver_sql(SHADOW_MUTATIONS[shadow])
        assert result.rowcount > 0, "mutation must change a persisted shadow row"
        reader.recheck(session, batch)

    # Mutation follows Store preflight: this must reach our fingerprint, not merely
    # fail the next Store capability probe while preparing a malformed FTS index.
    with pytest.raises(ValueError, match="CERTIFIED_CONTENT_CHANGED"):
        inventory_store.write(corrupt)


type FTSCapture = tuple[tuple[ScalarRow, ...], ...]


def corrupt_postings_only(
    store: Store, plan: PreparedStage, kind: str, *, rollback: bool = False
) -> FTSCapture:
    captures: list[FTSCapture] = []
    document = next(
        item
        for item in plan.index.documents
        if len(set(TOKEN.findall(item.text))) >= 4
        and TOKEN.findall(item.text)[1:] != list(reversed(TOKEN.findall(item.text)[1:]))
    )
    tokens = TOKEN.findall(document.text)
    changed = {
        "missing-secondary": tokens[0],
        "extra-secondary": document.text + " qzxvextraterm",
        "changed-positions": " ".join([tokens[0], *reversed(tokens[1:])]),
    }[kind]

    def corrupt(session: Session) -> None:
        connection = session.connection()
        rowid, original = connection.exec_driver_sql(
            "SELECT rowid,document_text FROM inventory_search_fts "
            "WHERE namespace=? AND snapshot_id=? AND source_id=?",
            (document.ref.namespace, document.ref.snapshot_id, document.ref.source_id),
        ).one()
        connection.exec_driver_sql(
            "UPDATE inventory_search_fts SET document_text=? WHERE rowid=?", (changed, rowid)
        )
        # Restore readable content without rebuilding the deliberately wrong postings.
        connection.exec_driver_sql(
            "UPDATE inventory_search_fts_content SET c4=? WHERE id=?", (original, rowid)
        )
        assert (
            connection.exec_driver_sql(
                "SELECT document_text FROM inventory_search_fts WHERE rowid=?", (rowid,)
            ).scalar_one()
            == original
        )
        # Flush FTS's pending writer index into its shadow rows before capturing.
        # This consolidates the deliberately changed postings; it does not rebuild
        # them from the restored text. Otherwise same-length position edits can
        # remain only in the writer cache until commit and evade this test capture.
        connection.exec_driver_sql(
            "INSERT INTO inventory_search_fts(inventory_search_fts) VALUES ('optimize')"
        )
        record_evidence(
            "i5-posting-fixture-diagnostic",
            {
                "kind": kind,
                "quick_check": [
                    tuple(row) for row in connection.exec_driver_sql("PRAGMA quick_check")
                ],
            },
        )
        captures.append(
            tuple(
                tuple(
                    tuple(row)
                    for row in connection.exec_driver_sql(
                        f"SELECT {scan.columns} FROM {scan.name} ORDER BY {scan.order}"
                    )
                )
                for scan in FTS_SCANS
            )
        )
        if rollback:
            raise RuntimeError("SYNTHETIC_CAPTURE_ROLLBACK")

    if rollback:
        with pytest.raises(RuntimeError, match="SYNTHETIC_CAPTURE_ROLLBACK"):
            store.write(corrupt)
    else:
        store.write(corrupt)
    return captures[0]


@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("kind", ["missing-secondary", "extra-secondary", "changed-positions"])
def test_content_preserving_posting_corruption_fails_cold_and_warm(
    inventory_store: Store, snapshot_plan: PreparedStage, warm: bool, kind: str
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    reader = CompactInventoryReader(inventory_store)
    if warm:
        reader.admit(snapshot_plan.index.snapshot_id)
    captured = corrupt_postings_only(inventory_store, snapshot_plan, kind)
    # On this pinned SQLite build, existing quick_check already rejects these
    # posting/content disagreements. Prove both boundaries without bypassing it.
    with pytest.raises(StoreError, match="STORE_CORRUPT"):
        repo.snapshot(snapshot_plan.index.snapshot_id)
    with pytest.raises(StoreError, match="STORE_CORRUPT"):
        if warm:
            reader.read_header()
        else:
            reader.admit(snapshot_plan.index.snapshot_id)
    with pytest.raises(ValueError, match="FTS_COMPLETE_POSTING_AUDIT_FAILED"):
        _fts_mirror_check(FingerprintLayout.for_store(inventory_store), captured)
    record_evidence(
        f"i5-postings-{kind}-{'warm' if warm else 'cold'}",
        {
            "readable_content_unchanged": True,
            "existing_store_preflight_rejected": True,
            "captured_shadow_mirror_rejected": True,
            "compact_admission_or_read_rejected": True,
        },
    )


@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("mutation", ["unknown-version", "unbound-photo", "inner-index"])
def test_rehashed_envelope_never_establishes_or_preserves_admission(
    inventory_store: Store, snapshot_plan: PreparedStage, mutation: str, warm: bool
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    reader = CompactInventoryReader(inventory_store)
    if warm:
        reader.admit(snapshot_plan.index.snapshot_id)

    def corrupt(session: Session) -> None:
        row = session.get(InventorySnapshotPayload, snapshot_plan.index.snapshot_id)
        assert row is not None
        data = json.loads(canonical_json(row.payload_json))
        if mutation == "unknown-version":
            data["version"] = "inventory-stage-unsupported"
        elif mutation == "unbound-photo":
            data["candidate"]["listings"][0]["photo"]["url"] = "https://example.invalid/forged.jpg"
        else:
            data["index"]["version"] = "f" * 64
        row.payload_json = data
        row.payload_sha256 = digest_text(canonical_json(data))

    inventory_store.write(corrupt)
    with pytest.raises(ValueError):
        if warm:
            reader.read_header()
        else:
            reader.admit(snapshot_plan.index.snapshot_id)
    with pytest.raises(ValueError):
        CompactInventoryReader(inventory_store).admit(snapshot_plan.index.snapshot_id)


@pytest.mark.parametrize("corrupt", [False, True], ids=["success", "failure"])
def test_cold_fts_mirror_is_memory_only_exact_and_closed(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
    corrupt: bool,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    if corrupt:
        corrupted_capture = corrupt_postings_only(
            inventory_store, snapshot_plan, "extra-secondary", rollback=True
        )

        def fail_from_capture(layout: FingerprintLayout, captured: FTSCapture) -> None:
            assert captured != corrupted_capture
            _fts_mirror_check(layout, corrupted_capture)

        monkeypatch.setattr(
            "app.inventory.persisted_fingerprint._fts_mirror_check", fail_from_capture
        )
    original = sqlite3.connect
    memory: list[sqlite3.Connection] = []
    statements: list[list[str]] = []

    def track(database: str, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        connection: sqlite3.Connection = original(database, *args, **kwargs)
        if database == ":memory:":
            memory.append(connection)
            statements.append([])
            connection.set_trace_callback(statements[-1].append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track)
    before = inventory_store.path.read_bytes()
    reader = CompactInventoryReader(inventory_store)
    if corrupt:
        with pytest.raises(ValueError, match="FTS_COMPLETE_POSTING_AUDIT_FAILED"):
            reader.admit(snapshot_plan.index.snapshot_id)
    else:
        reader.admit(snapshot_plan.index.snapshot_id)
    assert inventory_store.path.read_bytes() == before
    assert len(memory) == 2
    for connection in memory:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
    writes = [sql for trace in statements for sql in trace if sql.startswith("INSERT INTO ")]
    assert any("VALUES ('integrity-check')" in sql for sql in writes)
    assert not any("INSERT INTO inventory_search_fts (" in sql for sql in writes)
    assert all(
        "inventory_search_fts_" in sql or "VALUES ('integrity-check')" in sql for sql in writes
    )
    assert all(
        "listing_versions" not in sql and "owners" not in sql
        for trace in statements
        for sql in trace
    )
