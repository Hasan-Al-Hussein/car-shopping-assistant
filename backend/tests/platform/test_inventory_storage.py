"""Shared additive storage tests; synthetic rows are not an accepted Inventory stage."""

import hashlib
import json
import sqlite3
from contextlib import closing
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.readiness import InventoryObservation, ReadinessRegistry
from app.database import capabilities
from app.database import store as store_module
from app.database.maintenance import initialize_maintenance_guard, shared_store_lease
from app.database.models import Base, InventorySearchDocument, InventorySnapshotPayload
from app.database.paths import reserve_new_store
from app.database.store import (
    MIGRATIONS,
    Store,
    StoreError,
    _connect,
    _engine,
    initialize_store,
    open_store,
    upgrade_store,
)
from tests.platform.persistence_cases import NOW, seed, seed_rows
from tests.support.harness import configured_runtime_boundary

RUN_ID = "platform-seam-" + str(uuid4())
SNAPSHOT = "3" * 64
INDEX = "4" * 64
REF = {"namespace": "provided-cars-cleaned", "snapshot_id": SNAPSHOT, "source_id": "12"}


@pytest.fixture
def path(request: pytest.FixtureRequest) -> Path:
    case = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16]
    return (
        configured_runtime_boundary().logical_root / "test-stores" / RUN_ID / case / "test.sqlite3"
    )


@pytest.fixture
def legacy(path: Path) -> Store:
    """Replay frozen0001 independently, with all retained domain relationships populated."""
    boundary = configured_runtime_boundary()
    reserve_new_store(path, boundary=boundary)
    initialize_maintenance_guard(path, boundary=boundary)
    generation = str(uuid4())
    with shared_store_lease(path, boundary=boundary):
        engine = _engine(path, None, validate=False, boundary=boundary)
        try:
            with engine.connect().execution_options(store_write=True) as conn, conn.begin():
                config = Config()
                config.set_main_option("script_location", str(MIGRATIONS))
                config.attributes["connection"] = conn
                command.upgrade(config, "0001")
                conn.exec_driver_sql(
                    "INSERT INTO store_metadata (id,schema_version,store_generation,created_at) "
                    "VALUES (1,'0001',?,?)",
                    (generation, NOW),
                )
        finally:
            engine.dispose()
    result = open_store(path, boundary=boundary)
    result.write(lambda session: seed(session, generation))
    return result


def legacy_rows(store: Store) -> dict[str, list[tuple[Any, ...]]]:
    schema = json.loads((MIGRATIONS / "schema-0001.json").read_text(encoding="utf-8"))
    tables = [name for kind, name, _ in schema if kind == "table" and name != "store_metadata"]
    return store.read(
        lambda session: {
            table: [
                tuple(row)
                for row in session.execute(text(f'SELECT * FROM "{table}" ORDER BY rowid'))
            ]
            for table in tables
        }
    )


def seed_inventory_parent(session: Session, generation: str) -> None:
    for name, values in seed_rows(generation):
        if name == "inventory_snapshots" and values["snapshot_id"] == "1" * 64:
            session.execute(
                Base.metadata.tables[name]
                .insert()
                .values(**{**values, "snapshot_id": SNAPSHOT, "index_version": INDEX})
            )
        if name == "listing_versions" and values["snapshot_id"] == "1" * 64:
            session.execute(
                Base.metadata.tables[name].insert().values(**{**values, "snapshot_id": SNAPSHOT})
            )


@pytest.fixture
def fresh(path: Path) -> Store:
    result = initialize_store(path, boundary=configured_runtime_boundary())
    result.write(lambda session: seed_inventory_parent(session, result.generation))
    return result


def test_populated_legacy_reads_without_upgrade_then_preserves_history(legacy: Store) -> None:
    before = legacy_rows(legacy)
    content = legacy.path.read_bytes()
    assert open_store(legacy.path, boundary=legacy.boundary).schema_version == "0001"
    assert legacy.path.read_bytes() == content
    upgraded = upgrade_store(
        legacy.path, expected_generation=legacy.generation, boundary=legacy.boundary
    )
    assert upgraded.boundary is legacy.boundary
    reopened = open_store(upgraded.path, boundary=upgraded.boundary)
    assert reopened.boundary is legacy.boundary
    assert reopened.generation == legacy.generation
    assert upgraded.schema_version == "0002"
    assert upgraded.generation == legacy.generation
    assert upgraded.inventory_mode == "fts5"
    assert legacy_rows(upgraded) == before
    assert (
        upgraded.read(
            lambda session: session.execute(
                text("SELECT count(*) FROM inventory_snapshot_payloads")
            ).scalar_one()
        )
        == 0
    )
    assert (
        upgraded.read(
            lambda session: session.execute(
                text("SELECT revision FROM active_inventory")
            ).scalar_one()
        )
        == 0
    )  # Migration did not activate or fabricate completion.
    with pytest.raises(StoreError, match="STORE_SCHEMA_CHANGED"):
        legacy.read(lambda _: None)
    upgraded_bytes = upgraded.path.read_bytes()
    upgrade_store(
        upgraded.path, expected_generation=upgraded.generation, boundary=upgraded.boundary
    )
    assert upgraded.path.read_bytes() == upgraded_bytes


@pytest.mark.parametrize("interruption", [RuntimeError, KeyboardInterrupt])
def test_failure_after_all_ddl_rolls_back_markers_and_history(
    legacy: Store, monkeypatch: pytest.MonkeyPatch, interruption: type[BaseException]
) -> None:
    original = command.upgrade
    before = legacy.path.read_bytes()

    def interrupted(config: Config, revision: str) -> None:
        original(config, revision)
        raise interruption("INJECTED_AFTER_DDL")

    monkeypatch.setattr(command, "upgrade", interrupted)
    with pytest.raises(interruption, match="INJECTED_AFTER_DDL"):
        upgrade_store(
            legacy.path, expected_generation=legacy.generation, boundary=legacy.boundary
        )
    assert legacy.path.read_bytes() == before
    assert open_store(legacy.path, boundary=legacy.boundary).schema_version == "0001"
    assert legacy_rows(legacy)


def test_upgrade_generation_and_old_schema_are_checked_under_write_lock(legacy: Store) -> None:
    before = legacy.path.read_bytes()
    with pytest.raises(StoreError, match="STORE_GENERATION_CHANGED"):
        upgrade_store(
            legacy.path, expected_generation=str(uuid4()), boundary=legacy.boundary
        )
    assert legacy.path.read_bytes() == before
    with (
        shared_store_lease(legacy.path, boundary=legacy.boundary),
        closing(_connect(legacy.path, "rw", None, boundary=legacy.boundary)) as db,
    ):
        db.execute("CREATE TABLE undeclared (id INTEGER)")
    before = legacy.path.read_bytes()
    with pytest.raises(StoreError, match="STORE_SCHEMA_STRUCTURE_INCOMPATIBLE"):
        upgrade_store(
            legacy.path, expected_generation=legacy.generation, boundary=legacy.boundary
        )
    assert legacy.path.read_bytes() == before


def test_upgrade_never_creates_missing_store(path: Path) -> None:
    with pytest.raises(StoreError, match="^STORE_UNAVAILABLE$"):
        upgrade_store(
            path, expected_generation=str(uuid4()), boundary=configured_runtime_boundary()
        )
    assert not path.parent.exists()


def test_real_fts_has_unicode_numeric_and_unindexed_semantics(fresh: Store) -> None:
    assert capabilities.detect_fts5() is True
    content = "verified سيارة 707 café"

    def insert(session: Session) -> None:
        session.add(
            InventorySearchDocument(
                **REF,
                index_version=INDEX,
                document_text=content,
                document_sha256=hashlib.sha256(content.encode()).hexdigest(),
            )
        )
        session.execute(
            text(
                "INSERT INTO inventory_search_fts "
                "(namespace,snapshot_id,source_id,index_version,document_text) "
                "VALUES (:namespace,:snapshot_id,:source_id,:index_version,:document_text)"
            ),
            {**REF, "index_version": INDEX, "document_text": content},
        )
        session.execute(
            text(
                "INSERT INTO inventory_search_fts(inventory_search_fts) VALUES ('integrity-check')"
            )
        )

    fresh.write(insert)

    def match_count(session: Session, *, query: str) -> int:
        return int(
            session.execute(
                text(
                    "SELECT count(*) FROM inventory_search_fts "
                    "WHERE inventory_search_fts MATCH :term"
                ),
                {"term": query},
            ).scalar_one()
        )

    for term, expected in (
        ("verified", 1),
        ("سيارة", 1),
        ("707", 1),
        ("café", 1),
        ("cafe", 0),
        (SNAPSHOT, 0),
        (INDEX, 0),
        ("12", 0),
    ):
        assert fresh.read(partial(match_count, query=term)) == expected
    assert open_store(fresh.path, boundary=fresh.boundary).inventory_mode == "fts5"


def test_payload_roundtrip_and_duplicate_rejection(fresh: Store) -> None:
    payload = {"name": "سيارة", "nested": {"synthetic": True}}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    values = dict(
        snapshot_id=SNAPSHOT,
        serialization_version="codec-1",
        payload_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
        payload_json=payload,
    )
    fresh.write(lambda session: session.add(InventorySnapshotPayload(**values)))
    assert (
        open_store(fresh.path, boundary=fresh.boundary).read(
            lambda session: session.query(InventorySnapshotPayload.payload_json).scalar()
        )
        == payload
    )
    with pytest.raises(IntegrityError):
        fresh.write(lambda session: session.add(InventorySnapshotPayload(**values)))


@pytest.mark.parametrize(
    "field,value",
    [
        ("payload_sha256", "g" * 64),
        ("payload_sha256", "A" * 64),
        ("payload_sha256", "a" * 63),
        ("serialization_version", ""),
        ("serialization_version", " " * 5),
        ("serialization_version", "v" * 129),
        ("payload_json", []),
        ("snapshot_id", "9" * 64),
    ],
)
def test_payload_structural_constraints(fresh: Store, field: str, value: Any) -> None:
    values = dict(
        snapshot_id=SNAPSHOT,
        serialization_version="codec-1",
        payload_sha256="a" * 64,
        payload_json={"synthetic": True},
    )
    values[field] = value
    with pytest.raises(IntegrityError):
        fresh.write(
            lambda session: session.execute(
                Base.metadata.tables["inventory_snapshot_payloads"].insert().values(**values)
            ).close()
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("document_sha256", "G" * 64),
        ("document_sha256", "a" * 63),
        ("index_version", "wrong"),
        ("index_version", "9" * 64),
        ("source_id", "absent"),
        ("namespace", "other"),
        ("snapshot_id", "9" * 64),
        ("document_text", b"binary"),
    ],
)
def test_documents_bind_full_ref_and_exact_index(fresh: Store, field: str, value: Any) -> None:
    values = {
        **REF,
        "index_version": INDEX,
        "document_text": "synthetic",
        "document_sha256": "a" * 64,
        field: value,
    }
    with pytest.raises(IntegrityError):
        fresh.write(
            lambda session: session.execute(
                Base.metadata.tables["inventory_search_documents"].insert().values(**values)
            ).close()
        )


@pytest.mark.parametrize(
    "damage",
    [
        "DROP TABLE inventory_search_fts",
        "DROP TABLE inventory_search_fts_docsize",
        "CREATE TABLE inventory_search_fts_extra (id INTEGER)",
        "UPDATE inventory_storage_profile SET mode='bounded_lexical'",
        "DELETE FROM inventory_storage_profile",
    ],
)
def test_missing_or_mismatched_fts_never_becomes_fallback(fresh: Store, damage: str) -> None:
    with (
        shared_store_lease(fresh.path, boundary=fresh.boundary),
        closing(_connect(fresh.path, "rw", None, boundary=fresh.boundary)) as db,
    ):
        db.execute(damage)
    before = fresh.path.read_bytes()
    with pytest.raises(StoreError) as rejected:
        open_store(fresh.path, boundary=fresh.boundary)
    assert str(rejected.value) not in {"STORE_BUSY", "STORE_UNAVAILABLE"}
    assert fresh.path.read_bytes() == before


def test_wrong_tokenizer_refused_even_with_all_expected_table_names(fresh: Store) -> None:
    with (
        shared_store_lease(fresh.path, boundary=fresh.boundary),
        closing(_connect(fresh.path, "rw", None, boundary=fresh.boundary)) as db,
    ):
        db.execute("DROP TABLE inventory_search_fts")
        db.execute(
            "CREATE VIRTUAL TABLE inventory_search_fts USING fts5("
            "namespace UNINDEXED, snapshot_id UNINDEXED, source_id UNINDEXED, "
            "index_version UNINDEXED, document_text, tokenize='unicode61 remove_diacritics 1')"
        )
    with pytest.raises(StoreError, match="STORE_SCHEMA_STRUCTURE_INCOMPATIBLE"):
        open_store(fresh.path, boundary=fresh.boundary)


def test_committed_pointer_survives_failed_publication_then_authoritative_refresh(
    fresh: Store,
) -> None:
    # Synthetic Store-level seam proof. Inventory's full activation validation is a later card.
    fresh.write(
        lambda session: session.execute(
            Base.metadata.tables["active_inventory"]
            .insert()
            .values(id=1, snapshot_id=SNAPSHOT, index_version=INDEX, revision=1)
        ).close()
    )
    registry = ReadinessRegistry()

    def unavailable() -> InventoryObservation:
        raise RuntimeError("INJECTED_POST_COMMIT_PUBLICATION_FAILURE")

    with pytest.raises(RuntimeError):
        registry.refresh_inventory(unavailable)
    reopened = open_store(fresh.path, boundary=fresh.boundary)

    def actual_observation() -> InventoryObservation:
        def read(session: Session) -> InventoryObservation:
            row = (
                session.execute(text("SELECT * FROM active_inventory WHERE id=1")).mappings().one()
            )
            return InventoryObservation(
                generation=reopened.generation,
                active_revision=row["revision"],
                snapshot_id=row["snapshot_id"],
                index_version=row["index_version"],
                mode="fts5",
            )

        return reopened.read(read)

    assert actual_observation().active_revision == 1
    registry.refresh_inventory(actual_observation)
    assert registry.snapshot().active_snapshot_id == SNAPSHOT
    assert actual_observation().active_revision == 1
    with pytest.raises(StoreError, match="EXTERNAL_WORK_INSIDE_WRITE_TRANSACTION"):
        fresh.write(lambda _: registry.refresh_inventory(actual_observation))


def test_injected_unavailable_profile_and_capable_runtime_refusal(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Explicit simulation: this interpreter really supports FTS5.
    with monkeypatch.context() as simulated:
        simulated.setattr(store_module, "detect_fts5", lambda: False)
        simulated.setattr(store_module, "fts5_registered", lambda _: False)
        result = initialize_store(path, boundary=configured_runtime_boundary())
        assert result.inventory_mode == "bounded_lexical"
        assert (
            result.read(
                lambda session: session.execute(
                    text("SELECT name FROM sqlite_master WHERE name LIKE 'inventory_search_fts%'")
                ).all()
            )
            == []
        )
        assert (
            open_store(path, boundary=configured_runtime_boundary()).inventory_mode
            == "bounded_lexical"
        )
    with pytest.raises(StoreError, match="STORE_INVENTORY_CAPABILITY_INCOMPATIBLE"):
        open_store(path, boundary=configured_runtime_boundary())


@pytest.mark.parametrize(
    "message,absent",
    [
        ("no such module: fts5", True),
        ("database is locked", False),
        ("no such tokenizer: unicode61", False),
        ("disk I/O error", False),
    ],
)
def test_only_exact_missing_module_permits_probe_fallback(
    monkeypatch: pytest.MonkeyPatch, message: str, absent: bool
) -> None:
    class FailingProbe:
        closed = False

        def execute(self, _: str) -> None:
            raise sqlite3.OperationalError(message)

        def close(self) -> None:
            self.closed = True

    probe = FailingProbe()
    monkeypatch.setattr(sqlite3, "connect", lambda _: probe)
    if absent:
        assert capabilities.detect_fts5() is False
    else:
        with pytest.raises(sqlite3.OperationalError, match=message):
            capabilities.detect_fts5()
    assert probe.closed
