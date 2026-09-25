"""Exact persisted scalar fingerprints; cold FTS checking never writes the live store."""

import hashlib
import json
import sqlite3
import struct
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from typing import Final

from sqlalchemy.orm import Session

from app.database.store import MIGRATIONS, Store, assert_outside_write_transaction
from app.inventory.lexical_index import IndexMode

FINGERPRINT_VERSION: Final = "inventory-persisted-1"
MAX_FINGERPRINT_BYTES = 128 * 1024 * 1024
MAX_FTS_CAPTURE_BYTES = 32 * 1024 * 1024
type Scalar = str | bytes | int | float | None
type ScalarRow = tuple[Scalar, ...]


@dataclass(frozen=True, slots=True)
class TableScan:
    name: str
    columns: str
    order: str


FTS_SCANS = (
    TableScan("inventory_search_fts_config", "k,v", "k"),
    TableScan("inventory_search_fts_content", "id,c0,c1,c2,c3,c4", "id"),
    TableScan("inventory_search_fts_data", "id,block", "id"),
    TableScan("inventory_search_fts_docsize", "id,sz", "id"),
    TableScan("inventory_search_fts_idx", "segid,term,pgno", "segid,term"),
)
SNAPSHOT_SCANS = (
    TableScan(
        "inventory_snapshots",
        "snapshot_id,namespace,workbook_sha256,sheet_name,import_version,"
        "normalization_version,extraction_version,evidence_review_version,"
        "photo_policy_version,schema_version,index_version,policy_version,"
        "accepted_count,rejected_count,created_at",
        "snapshot_id",
    ),
    TableScan(
        "inventory_snapshot_payloads",
        "snapshot_id,serialization_version,payload_sha256,payload_json",
        "snapshot_id",
    ),
    TableScan(
        "listing_versions",
        "namespace,snapshot_id,source_id,source_row,original_json,normalized_json",
        "namespace,snapshot_id,source_id",
    ),
    TableScan(
        "attribute_evidence",
        "id,namespace,snapshot_id,source_id,attribute,raw_locator_json,"
        "normalized_json,status,extraction_version",
        "id",
    ),
    TableScan(
        "inventory_search_documents",
        "namespace,snapshot_id,source_id,index_version,document_text,document_sha256",
        "namespace,snapshot_id,source_id",
    ),
    TableScan(
        "listing_resource_mappings",
        "namespace,snapshot_id,source_id,resource_id,mapping_version,provenance_json",
        "namespace,snapshot_id,source_id",
    ),
)
SCHEMA_SQL = (
    "SELECT type,name,sql FROM sqlite_master "
    "WHERE name NOT LIKE 'sqlite_%' AND name != 'alembic_version' ORDER BY type,name"
)


class _Digest:
    def __init__(self, domain: str, limit: int = MAX_FINGERPRINT_BYTES) -> None:
        self._hash = hashlib.sha256()
        self._remaining = limit
        self.scalar(FINGERPRINT_VERSION)
        self.scalar(domain)

    def scalar(self, value: Scalar) -> None:
        if value is None:
            tag, payload = b"n", b""
        elif type(value) is str:
            tag, payload = b"s", value.encode("utf-8")
        elif type(value) is bytes:
            tag, payload = b"b", value
        elif type(value) is int:
            tag, payload = b"i", str(value).encode("ascii")
        elif type(value) is float:
            tag, payload = b"f", struct.pack("!d", value)
        else:
            raise ValueError("INVENTORY_FINGERPRINT_SCALAR_INVALID")
        self._remaining -= len(payload) + 9
        if self._remaining < 0:
            raise ValueError("INVENTORY_FINGERPRINT_SIZE_LIMIT")
        self._hash.update(tag + len(payload).to_bytes(8, "big"))
        self._hash.update(payload)

    def rows(self, name: str, columns: str, rows: Iterable[ScalarRow]) -> None:
        self.scalar(name)
        self.scalar(columns)
        count = 0
        for row in rows:
            self.scalar("row")
            self.scalar(len(row))
            for value in row:
                self.scalar(value)
            count += 1
        self.scalar("count")
        self.scalar(count)

    def hexdigest(self) -> str:
        return self._hash.hexdigest()


def _schema(rows: Iterable[ScalarRow]) -> tuple[tuple[str, str, str], ...]:
    result = []
    for kind, name, sql in rows:
        if not all(type(part) is str for part in (kind, name, sql)):
            raise ValueError("INVENTORY_SCHEMA_IDENTITY_INVALID")
        assert isinstance(kind, str) and isinstance(name, str) and isinstance(sql, str)
        result.append((kind, name, " ".join(sql.split())))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class FingerprintLayout:
    schema: tuple[tuple[str, str, str], ...]
    fts_schema: tuple[tuple[str, str, str], ...]
    mode: IndexMode

    @classmethod
    def for_store(cls, store: Store) -> "FingerprintLayout":
        if store.schema_version != "0002" or store.inventory_mode not in {
            "fts5",
            "bounded_lexical",
        }:
            raise ValueError("INVENTORY_REQUIRES_EXPLICIT_SCHEMA_UPGRADE")
        base = json.loads((MIGRATIONS / "schema-0001.json").read_text(encoding="utf-8"))
        extra = json.loads((MIGRATIONS / "schema-0002.json").read_text(encoding="utf-8"))
        mode = store.inventory_mode
        assert mode is not None
        return cls(
            _schema(sorted(tuple(row) for row in base + extra["common"] + extra[mode])),
            _schema(tuple(tuple(row) for row in extra[mode])),
            mode,
        )


def _fts_mirror_check(
    layout: FingerprintLayout,
    captured: tuple[tuple[ScalarRow, ...], ...],
) -> None:
    """Copy only captured FTS bytes, not a Store connection, path or private tables.

    A fresh backup target avoids the builder's virtual-table state. Rebuilding from
    text would hide corrupt postings and is deliberately forbidden here.
    """
    assert_outside_write_transaction()
    try:
        with closing(sqlite3.connect(":memory:")) as verifier:
            with closing(sqlite3.connect(":memory:")) as builder:
                builder.execute(layout.fts_schema[0][2])
                for scan, rows in zip(FTS_SCANS, captured, strict=True):
                    builder.execute(f"DELETE FROM {scan.name}")
                    placeholders = ",".join("?" for _ in scan.columns.split(","))
                    builder.executemany(
                        f"INSERT INTO {scan.name} ({scan.columns}) VALUES ({placeholders})",
                        rows,
                    )
                builder.commit()
                builder.backup(verifier)
            if _schema(verifier.execute(SCHEMA_SQL)) != layout.fts_schema:
                raise ValueError("INVENTORY_FTS_MIRROR_SCHEMA_MISMATCH")
            for scan, expected in zip(FTS_SCANS, captured, strict=True):
                actual = tuple(
                    verifier.execute(
                        f"SELECT {scan.columns} FROM {scan.name} ORDER BY {scan.order}"
                    )
                )
                # Scalar type framing distinguishes, for example, TEXT from BLOB.
                left, right = _Digest("mirror"), _Digest("mirror")
                left.rows(scan.name, scan.columns, actual)
                right.rows(scan.name, scan.columns, expected)
                if left.hexdigest() != right.hexdigest():
                    raise ValueError("INVENTORY_FTS_MIRROR_CONTENT_MISMATCH")
            verifier.execute(
                "INSERT INTO inventory_search_fts(inventory_search_fts) VALUES ('integrity-check')"
            )
    except sqlite3.DatabaseError as exc:
        raise ValueError("INVENTORY_FTS_COMPLETE_POSTING_AUDIT_FAILED") from exc


def global_fingerprint(
    session: Session,
    store: Store,
    layout: FingerprintLayout,
    *,
    audit_postings: bool = False,
) -> str:
    """Same-unit schema/profile/generation and exact global FTS shadow streams."""
    connection = session.connection()
    schema_rows = tuple(tuple(row) for row in connection.exec_driver_sql(SCHEMA_SQL))
    if _schema(schema_rows) != layout.schema:
        raise ValueError("INVENTORY_SCHEMA_IDENTITY_MISMATCH")
    migration = tuple(
        tuple(row)
        for row in connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version ORDER BY version_num"
        )
    )
    if migration != ((store.schema_version,),):
        raise ValueError("INVENTORY_SCHEMA_VERSION_MISMATCH")
    metadata = tuple(
        tuple(row)
        for row in connection.exec_driver_sql(
            "SELECT id,schema_version,store_generation,created_at,restored_at,recovery_point "
            "FROM store_metadata ORDER BY id"
        )
    )
    if len(metadata) != 1 or metadata[0][:3] != (1, store.schema_version, store.generation):
        raise ValueError("INVENTORY_STORE_IDENTITY_MISMATCH")
    profile = tuple(
        tuple(row)
        for row in connection.exec_driver_sql(
            "SELECT id,mode FROM inventory_storage_profile ORDER BY id"
        )
    )
    if profile != ((1, layout.mode),):
        raise ValueError("INVENTORY_STORAGE_PROFILE_MISMATCH")
    digest = _Digest("global")
    digest.rows("schema", "type,name,sql", schema_rows)
    digest.rows("alembic_version", "version_num", migration)
    digest.rows("store", "id,schema,generation,created,restored,recovery", metadata)
    digest.rows("profile", "id,mode", profile)
    captured = []
    capture_limit = _Digest("capture-limit", MAX_FTS_CAPTURE_BYTES)
    if layout.mode == "fts5":
        for scan in FTS_SCANS:
            rows = (
                tuple(row)
                for row in connection.exec_driver_sql(
                    f"SELECT {scan.columns} FROM {scan.name} ORDER BY {scan.order}"
                )
            )
            if audit_postings:
                # Bound the cold copy as it is collected, not after allocation.
                table_rows = []
                for row in rows:
                    capture_limit.rows(scan.name, scan.columns, (row,))
                    table_rows.append(row)
                captured.append(tuple(table_rows))
                digest.rows(scan.name, scan.columns, table_rows)
            else:
                digest.rows(scan.name, scan.columns, rows)
        if audit_postings:
            _fts_mirror_check(layout, tuple(captured))
    return digest.hexdigest()


def snapshot_fingerprint(session: Session, snapshot_id: str) -> str:
    """Whole stored sets, including unrequested rows, and exact referenced resources."""
    digest = _Digest("snapshot")
    digest.scalar(snapshot_id)
    connection = session.connection()
    for scan in SNAPSHOT_SCANS:
        digest.rows(
            scan.name,
            scan.columns,
            (
                tuple(row)
                for row in connection.exec_driver_sql(
                    f"SELECT {scan.columns} FROM {scan.name} "
                    f"WHERE snapshot_id=? ORDER BY {scan.order}",
                    (snapshot_id,),
                )
            ),
        )
    digest.rows(
        "vehicle_resources",
        "id,mapping_version,created_at",
        (
            tuple(row)
            for row in connection.exec_driver_sql(
                "SELECT r.id,r.mapping_version,r.created_at FROM vehicle_resources r "
                "WHERE EXISTS (SELECT 1 FROM listing_resource_mappings m "
                "WHERE m.snapshot_id=? AND m.resource_id=r.id) ORDER BY r.id",
                (snapshot_id,),
            )
        ),
    )
    return digest.hexdigest()
