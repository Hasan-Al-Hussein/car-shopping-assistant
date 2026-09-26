"""Real disposable SQLite foundation proof. Domain/HTTP/backup acceptance is separate."""

import asyncio
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import store as store_module
from app.database.maintenance import initialize_maintenance_guard, shared_store_lease
from app.database.models import Base
from app.database.paths import (
    RuntimeBoundary,
    StorePathError,
    guarded_store_path,
    reserve_new_store,
)
from app.database.store import (
    MIGRATIONS,
    SCHEMA_VERSION,
    Store,
    StoreError,
    _connect,
    _engine,
    assert_outside_write_transaction,
    initialize_store,
    open_store,
    runtime_capabilities,
)
from tests.platform.persistence_cases import NOW, seed, seed_rows, uid
from tests.support.harness import configured_runtime_boundary

PROJECT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(
    os.environ.get("PLATFORM_TEST_EVIDENCE_DIR", PROJECT / "Records/build/BE-01/evidence")
)
RUN_ID = str(uuid4())


def evidence(name: str, value: object) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / name).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


@pytest.fixture
def path(request: pytest.FixtureRequest) -> Path:
    return (
        configured_runtime_boundary().logical_root / "test-stores" / RUN_ID
        / ("case-" + hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16])
        / "test.sqlite3"
    )


@pytest.fixture
def store(path: Path) -> Store:
    return initialize_store(path, boundary=configured_runtime_boundary())


@pytest.fixture
def populated(store: Store) -> Store:
    store.write(lambda session: seed(session, store.generation))
    return store


def count(store: Store, table: str) -> int:
    assert table in Base.metadata.tables
    return store.read(
        lambda session: int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_migration_restart_and_explicit_repeat(populated: Store) -> None:
    before = digest(populated.path)
    restarted = open_store(populated.path, boundary=populated.boundary)
    assert restarted.boundary is populated.boundary
    assert restarted.generation == populated.generation
    assert count(restarted, "owners") == 2
    assert count(restarted, "bookings") == 1
    with shared_store_lease(restarted.path, boundary=restarted.boundary):
        engine = _engine(restarted.path, None, validate=True, boundary=restarted.boundary)
        try:
            with engine.connect().execution_options(store_write=True) as conn, conn.begin():
                config = Config()
                config.set_main_option("script_location", str(MIGRATIONS))
                config.attributes["connection"] = conn
                command.upgrade(config, SCHEMA_VERSION)
        finally:
            engine.dispose()
    assert digest(populated.path) == before
    with pytest.raises(FileExistsError):
        initialize_store(populated.path, boundary=populated.boundary)
    assert digest(populated.path) == before
    evidence(
        "migration.json",
        {
            "store": str(populated.path),
            "generation": restarted.generation,
            "sha256_before_and_after": before,
            "tables": len(Base.metadata.tables),
            "owners": 2,
            "bookings": 1,
        },
    )


def test_connection_pragmas_fts5_and_real_fk_rejection(populated: Store) -> None:
    reports = []
    with (
        shared_store_lease(populated.path, boundary=populated.boundary),
        closing(_connect(populated.path, "rw", None, boundary=populated.boundary)) as left,
        closing(_connect(populated.path, "rw", None, boundary=populated.boundary)) as right,
    ):
        assert left is not right
        for db in (left, right):
            values = {
                key: db.execute(f"PRAGMA {key}").fetchone()[0]
                for key in ("foreign_keys", "journal_mode", "synchronous", "busy_timeout")
            }
            assert values == {
                "foreign_keys": 1,
                "journal_mode": "delete",
                "synchronous": 2,
                "busy_timeout": 1000,
            }
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                db.execute(
                    "INSERT INTO journeys (id,owner_id,created_at) VALUES (?,?,?)",
                    (uid("bad-journey"), uid("absent-owner"), NOW),
                )
            reports.append(values)
    runtime = runtime_capabilities(populated)
    assert runtime["fts5"] is True
    assert runtime["sqlite_version"] == sqlite3.sqlite_version
    evidence(
        "sqlite-runtime.json",
        {
            "python": sys.version,
            "executable": sys.executable,
            "distinct_connections": reports,
            "runtime": runtime,
        },
    )


@pytest.mark.parametrize("suffix", ["missing/test.sqlite3", "empty-parent/test.sqlite3"])
def test_existing_open_never_creates(path: Path, suffix: str) -> None:
    target = path.parent / suffix
    with pytest.raises((FileNotFoundError, StoreError)):
        open_store(target, boundary=configured_runtime_boundary())
    assert not target.parent.exists()


@pytest.mark.parametrize(
    "candidate",
    [
        "project", "sibling", "exports", "traversal", "relative",
        "trailing-dot", "stream", "unc",
    ],
)
def test_path_escape_rejected(candidate: str) -> None:
    boundary = configured_runtime_boundary()
    root = boundary.logical_root
    candidates = {
        "project": PROJECT / "forbidden.sqlite3",
        "sibling": root.parent / (root.name + "-other") / "stores/test.sqlite3",
        "exports": root / "exports/test.sqlite3",
        "traversal": root / "test-stores/../stores/test.sqlite3",
        "relative": Path("relative.sqlite3"),
        "trailing-dot": root / "test-stores/bad./test.sqlite3",
        "stream": root / "test-stores/test.sqlite3:stream",
        "unc": Path(r"\\localhost\C$\test.sqlite3"),
    }
    with pytest.raises(StorePathError):
        guarded_store_path(candidates[candidate], boundary=boundary, must_exist=False)


def test_real_junction_and_hardlink_and_companion_guard(path: Path) -> None:
    # A junction inside this disposable run points only at another disposable run directory.
    target = path.parent / "target"
    target.mkdir(parents=True)
    junction = path.parent / "redirect"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with pytest.raises(StorePathError, match="REPARSE"):
        guarded_store_path(
            junction / "test.sqlite3", boundary=configured_runtime_boundary(), must_exist=False
        )
    assert not (target / "test.sqlite3").exists()
    fresh = path.parent / "fresh.sqlite3"
    initialize_store(fresh, boundary=configured_runtime_boundary())
    hard = path.parent / "hard.sqlite3"
    os.link(fresh, hard)
    with pytest.raises(StorePathError, match="HARDLINK"):
        guarded_store_path(hard, boundary=configured_runtime_boundary(), must_exist=True)
    with pytest.raises(StoreError, match="^STORE_UNAVAILABLE$"):
        open_store(hard, boundary=configured_runtime_boundary())
    # Another isolated file verifies companion redirection without modifying the store.
    safe = path.parent / "safe.sqlite3"
    initialize_store(safe, boundary=configured_runtime_boundary())
    os.link(fresh, Path(str(safe) + "-journal"))
    with pytest.raises(StorePathError, match="HARDLINK"):
        guarded_store_path(safe, boundary=configured_runtime_boundary(), must_exist=True)
    with pytest.raises(StoreError, match="^STORE_UNAVAILABLE$"):
        open_store(safe, boundary=configured_runtime_boundary())
    evidence(
        "path-guards.json",
        {
            "junction": str(junction),
            "target": str(target),
            "reparse_rejected": True,
            "hardlink_rejected": True,
            "companion_rejected": True,
        },
    )


@pytest.mark.parametrize(
    "damage",
    ["bytes", "truncated", "unversioned", "future", "metadata", "structure", "foreign-key", "wal"],
)
def test_incompatible_and_corrupt_fail_closed(populated: Store, damage: str) -> None:
    target = populated.path.parent / (damage + ".sqlite3")
    reserve_new_store(target, boundary=populated.boundary)
    initialize_maintenance_guard(target, boundary=populated.boundary)
    with shared_store_lease(target, boundary=populated.boundary):
        if damage == "bytes":
            target.write_bytes(b"not a SQLite database\x00")
        elif damage == "truncated":
            target.write_bytes(populated.path.read_bytes()[:300])
        elif damage == "unversioned":
            with closing(sqlite3.connect(target)) as db:
                db.execute("CREATE TABLE unrelated (value TEXT)")
        else:
            shutil.copyfile(populated.path, target)
            with closing(sqlite3.connect(target)) as db:
                sql = {
                    "future": "UPDATE alembic_version SET version_num='9999'",
                    "metadata": "UPDATE store_metadata SET schema_version='9999'",
                    "structure": "DROP INDEX ix_booking_resource_interval",
                    "foreign-key": "UPDATE messages SET owner_id='absent'",
                    "wal": "PRAGMA journal_mode=WAL",
                }[damage]
                db.execute(sql)
                db.commit()
    before = digest(target)
    with pytest.raises(StoreError) as rejected:
        open_store(target, boundary=configured_runtime_boundary())
    assert str(rejected.value) not in {"STORE_BUSY", "STORE_UNAVAILABLE"}
    assert digest(target) == before
    assert count(populated, "bookings") == 1
    evidence(
        f"compatibility-{damage}.json",
        {
            "path": str(target),
            "sha256_unchanged": before,
            "rejected": True,
            "original_booking_retained": True,
        },
    )


@pytest.mark.parametrize(
    ("table", "patch"),
    [
        ("conversation_sessions", {"journey_id": uid("journey-b")}),
        ("messages", {"owner_id": uid("owner-b")}),
        ("result_presentations", {"owner_id": uid("owner-b")}),
        ("booking_drafts", {"owner_id": uid("owner-b")}),
        ("booking_reviews", {"owner_id": uid("owner-b")}),
        ("operation_outcomes", {"owner_id": uid("owner-b")}),
        ("operation_outcomes", {"payload_hash": "0" * 64}),
        ("bookings", {"owner_id": uid("owner-b")}),
        ("bookings", {"review_id": uid("wrong-review")}),
        ("leads", {"journey_id": uid("journey-b")}),
        ("lead_bookings", {"owner_id": uid("owner-b")}),
        ("listing_versions", {"namespace": "wrong-namespace"}),
        ("attribute_evidence", {"namespace": "wrong-namespace"}),
        ("listing_resource_mappings", {"source_id": "missing"}),
        ("shortlist_memberships", {"source_id": "missing"}),
        ("presentation_items", {"snapshot_id": "2" * 64}),
        ("active_inventory", {"index_version": "wrong-index"}),
        ("bookings", {"ends_at_utc": "2026-09-25T03:30:00.000000Z"}),
        ("operation_outcomes", {"terminal_state": "UNKNOWN"}),
        ("leads", {"stage": "sent_to_dealer"}),
        ("store_metadata", {"id": 2}),
        ("owners", {"shortlist_revision": -1}),
    ],
)
def test_relational_and_check_rejections(
    populated: Store, table: str, patch: dict[str, Any]
) -> None:
    model = Base.metadata.tables[table]
    # Restrict the only multi-owner table to A so an invalid transient pair cannot heal itself.
    statement = model.update().values(**patch)
    if table == "conversation_sessions":
        statement = statement.where(model.c.id == uid("session-a"))
    with pytest.raises(IntegrityError):
        populated.write(lambda session: session.execute(statement).close())
    assert count(populated, "bookings") == 1


@pytest.mark.parametrize(
    "table",
    [
        "owner_credentials",
        "journeys",
        "messages",
        "shortlist_memberships",
        "command_receipts",
        "booking_reviews",
        "operation_outcomes",
        "bookings",
        "leads",
        "lead_bookings",
        "export_intents",
    ],
)
def test_unique_authority_rejected(populated: Store, table: str) -> None:
    values = next(
        values.copy() for name, values in seed_rows(populated.generation) if name == table
    )
    if "id" in values:
        values["id"] = uid("duplicate-" + table)
    with pytest.raises(IntegrityError, match="UNIQUE"):
        populated.write(
            lambda session: session.execute(
                Base.metadata.tables[table].insert().values(**values)
            ).close()
        )


def test_allowed_duplicates_and_history_stays_exact(populated: Store) -> None:
    assert count(populated, "owners") == 2
    assert count(populated, "listing_versions") == 2
    populated.write(
        lambda session: session.execute(
            text("UPDATE active_inventory SET snapshot_id=:snapshot,revision=1"),
            {"snapshot": "2" * 64},
        ).close()
    )
    refs = populated.read(
        lambda session: (
            session.execute(text("SELECT snapshot_id,source_id FROM shortlist_memberships"))
            .mappings()
            .all()
        )
    )
    assert [dict(row) for row in refs] == [{"snapshot_id": "1" * 64, "source_id": "12"}]
    with pytest.raises(IntegrityError):
        populated.write(
            lambda session: session.execute(
                text("DELETE FROM inventory_snapshots WHERE snapshot_id=:snapshot"),
                {"snapshot": "1" * 64},
            ).close()
        )


def test_retention_unlinks_without_cascading_authority(populated: Store) -> None:
    def prune(session: Session) -> None:
        for sql in (
            "DELETE FROM owner_credentials",
            "DELETE FROM presentation_items",
            "DELETE FROM result_presentations",
            "DELETE FROM messages",
            "UPDATE booking_drafts SET session_id=NULL,active_review_id=NULL",
            "DELETE FROM conversation_sessions",
            "UPDATE booking_reviews SET draft_id=NULL",
            "DELETE FROM booking_drafts",
        ):
            session.execute(text(sql))

    populated.write(prune)
    for table in ("booking_reviews", "operation_outcomes", "bookings", "leads", "export_intents"):
        assert count(populated, table) == 1


def test_actual_boundaries_rollback_and_commit(store: Store) -> None:
    trace: list[str] = []
    traced = open_store(store.path, trace=trace.append, boundary=store.boundary)
    trace.clear()

    def fault(session: Session) -> None:
        seed(session, store.generation)
        raise RuntimeError("INJECTED_AFTER_RELATED_WRITES")

    with pytest.raises(RuntimeError, match="INJECTED"):
        traced.write(fault)
    failed = trace.copy()
    assert "BEGIN IMMEDIATE" in failed and failed[-1] == "ROLLBACK"
    assert next(i for i, sql in enumerate(failed) if sql == "BEGIN IMMEDIATE") < next(
        i for i, sql in enumerate(failed) if sql.startswith("INSERT INTO owners")
    )
    for table in (
        "owners",
        "booking_reviews",
        "operation_outcomes",
        "bookings",
        "leads",
        "export_intents",
    ):
        assert count(store, table) == 0
    trace.clear()
    traced.write(lambda session: seed(session, store.generation))
    committed = trace.copy()
    assert committed[-1] == "COMMIT" and committed.count("BEGIN IMMEDIATE") == 1
    trace.clear()
    assert count(traced, "bookings") == 1
    assert "BEGIN IMMEDIATE" not in trace and "BEGIN" in trace
    evidence("transaction-trace.json", {"fault": failed, "commit": committed, "read": trace})


def test_read_only_nested_external_and_session_escape_rejected(populated: Store) -> None:
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        populated.read(lambda session: session.execute(text("DELETE FROM owners")).close())
    with pytest.raises(StoreError, match="ONE_SYNCHRONOUS_UNIT"):
        populated.write(lambda session: populated.read(lambda other: 1))
    with pytest.raises(StoreError, match="EXTERNAL_WORK"):
        populated.write(lambda session: assert_outside_write_transaction())
    with pytest.raises(StoreError, match="MATERIALIZED"):
        populated.read(lambda session: {"leaked": session})
    assert_outside_write_transaction()
    assert count(populated, "owners") == 2


def test_bounded_busy_and_fresh_unit_after_failure(populated: Store) -> None:
    with (
        shared_store_lease(populated.path, boundary=populated.boundary),
        closing(_connect(populated.path, "rw", None, boundary=populated.boundary)) as blocker,
    ):
        try:
            blocker.execute("BEGIN IMMEDIATE")
            start = time.monotonic()
            with pytest.raises(StoreError, match="STORE_BUSY"):
                populated.write(
                    lambda session: session.execute(text("DELETE FROM operational_events")).close()
                )
            elapsed = time.monotonic() - start
            assert 0.8 <= elapsed < 5
        finally:
            blocker.rollback()
    populated.write(lambda session: session.execute(text("DELETE FROM operational_events")).close())
    assert count(populated, "operational_events") == 0
    evidence("busy.json", {"bounded_elapsed_seconds": elapsed, "subsequent_unit_succeeded": True})


def test_async_whole_unit_runs_in_worker_and_sync_loop_rejected(populated: Store) -> None:
    async def run() -> None:
        event_thread = threading.get_ident()
        with pytest.raises(StoreError, match="EVENT_LOOP"):
            populated.read(lambda session: 1)

        def read(session: Session) -> tuple[int, int]:
            return threading.get_ident(), int(
                session.execute(text("SELECT count(*) FROM owners")).scalar_one()
            )

        thread, owners = await populated.read_async(read)
        assert thread != event_thread and owners == 2
        evidence(
            "thread-boundary.json",
            {"event_thread": event_thread, "worker_thread": thread, "owners": owners},
        )

    asyncio.run(run())


def test_failed_migration_is_not_ready_or_reset(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(config: Config, revision: str) -> None:
        connection = config.attributes["connection"]
        connection.exec_driver_sql("CREATE TABLE partially_created (value TEXT)")
        raise RuntimeError("MIGRATION_FAULT")

    monkeypatch.setattr(command, "upgrade", fail)
    with pytest.raises(RuntimeError, match="MIGRATION_FAULT"):
        initialize_store(path, boundary=configured_runtime_boundary())
    before = digest(path)
    with pytest.raises(StoreError):
        open_store(path, boundary=configured_runtime_boundary())
    assert digest(path) == before
    with pytest.raises(FileExistsError):
        initialize_store(path, boundary=configured_runtime_boundary())


def test_generation_change_fences_existing_store_handle(populated: Store) -> None:
    populated.write(
        lambda session: session.execute(
            text("UPDATE store_metadata SET store_generation=:generation"),
            {"generation": str(uuid4())},
        ).close()
    )
    with pytest.raises(StoreError, match="GENERATION_CHANGED"):
        populated.write(
            lambda session: session.execute(text("DELETE FROM operational_events")).close()
        )
    assert count(open_store(populated.path, boundary=populated.boundary), "operational_events") == 1


@pytest.mark.parametrize("alias_state", ["absent", "different"])
def test_explicit_physical_path_independent_of_unused_logical_alias(
    store: Store, alias_state: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    physical = store.path.resolve(strict=True)
    # An ordinary installation also exercises the mapped-profile rule using an
    # unused synthetic logical alias; the physical target remains the real fixture.
    boundary = store.boundary
    if boundary.logical_root == boundary.physical_root:
        boundary = RuntimeBoundary(
            logical_root=boundary.logical_root.with_name(boundary.logical_root.name + "-alias"),
            physical_root=boundary.physical_root,
        )
    logical = boundary.logical_root / physical.relative_to(boundary.physical_root)
    original = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if path == boundary.logical_root:
            if alias_state == "absent":
                raise FileNotFoundError("SIMULATED_EXTERNAL_PROCESS_ALIAS_ABSENT")
            return boundary.logical_root
        return original(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)
    reopened = open_store(physical, boundary=boundary)
    assert reopened.generation == store.generation
    assert reopened.boundary is boundary
    with pytest.raises(StoreError, match="^STORE_UNAVAILABLE$"):
        open_store(logical, boundary=boundary)
    wrong_package = boundary.physical_root.with_name(
        boundary.physical_root.name + "-unapproved-package"
    )
    with pytest.raises(StorePathError):
        guarded_store_path(
            wrong_package / "test-stores/test.sqlite3", boundary=boundary, must_exist=False
        )


def test_utc_storage_normalizes_equivalent_wire_forms_and_rejects_reversed_interval(
    populated: Store,
) -> None:
    booking = Base.metadata.tables["bookings"]
    populated.write(
        lambda session: session.execute(
            booking.update().values(
                starts_at_utc="2026-09-25T04:00:00Z", ends_at_utc="2026-09-25T04:00:00.1Z"
            )
        ).close()
    )
    values = populated.read(
        lambda session: tuple(
            session.execute(text("SELECT starts_at_utc,ends_at_utc FROM bookings")).one()
        )
    )
    assert values == ("2026-09-25T04:00:00.000000Z", "2026-09-25T04:00:00.100000Z")
    with pytest.raises(IntegrityError, match="interval"):
        populated.write(
            lambda session: session.execute(
                booking.update().values(
                    starts_at_utc="2026-09-25T04:00:00.1Z", ends_at_utc="2026-09-25T04:00:00Z"
                )
            ).close()
        )
    populated.write(
        lambda session: session.execute(
            booking.update().values(ends_at_utc="2026-09-25T05:00:00Z")
        ).close()
    )
    for invalid in (
        "2026-09-25T04:00:00Z",
        "2026-02-30T04:00:00.000000Z",
        "2026-09-24T24:00:00.000000Z",
    ):

        def invalid_write(session: Session, value: str = invalid) -> None:
            session.execute(
                text("UPDATE bookings SET starts_at_utc=:value"), {"value": value}
            ).close()

        with pytest.raises(IntegrityError, match="utc_starts_at_utc"):
            populated.write(invalid_write)


def test_wrapped_and_cyclic_results_cannot_escape(store: Store) -> None:
    @dataclass
    class Box:
        value: object

    with pytest.raises(StoreError, match="MATERIALIZED"):
        store.read(lambda session: Box(session))
    with pytest.raises(StoreError, match="MATERIALIZED"):
        store.read(lambda session: {session: "key"})
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(StoreError, match="CONTAINS_CYCLE"):
        store.read(lambda session: cyclic)
    assert store.read(lambda session: Box({"plain": [1, "safe"]})) == Box({"plain": [1, "safe"]})


@pytest.mark.parametrize("duplicate", ["token_digest", "context_id"])
def test_credential_uniqueness_each_independent(populated: Store, duplicate: str) -> None:
    row = next(
        values.copy()
        for table, values in seed_rows(populated.generation)
        if table == "owner_credentials"
    )
    row["id"] = uid("new-credential")
    other = "context_id" if duplicate == "token_digest" else "token_digest"
    row[other] = uid("new-context") if other == "context_id" else "a" * 64
    with pytest.raises(IntegrityError, match=duplicate):
        populated.write(
            lambda session: session.execute(
                Base.metadata.tables["owner_credentials"].insert().values(**row)
            ).close()
        )


def test_same_operation_key_separate_owners_is_valid(populated: Store) -> None:
    row = next(
        values.copy()
        for table, values in seed_rows(populated.generation)
        if table == "booking_reviews"
    )
    row.update(id=uid("review-b"), owner_id=uid("owner-b"), draft_id=None)
    populated.write(
        lambda session: session.execute(
            Base.metadata.tables["booking_reviews"].insert().values(**row)
        ).close()
    )
    assert count(populated, "booking_reviews") == 2


def test_each_authority_unique_index_exists_in_migrated_store(populated: Store) -> None:
    expected: dict[str, set[tuple[str, ...]]] = {
        "booking_reviews": {("owner_id", "operation_key")},
        "operation_outcomes": {("owner_id", "operation_key"), ("review_id",)},
        "bookings": {("review_id",), ("operation_id",)},
        "owner_credentials": {("context_id",), ("token_digest",)},
    }
    observed: dict[str, list[list[str]]] = {}

    def inspect_indexes(session: Session) -> None:
        connection = session.connection()
        for table, required in expected.items():
            indexes = connection.exec_driver_sql(f"PRAGMA index_list('{table}')").all()
            actual: set[tuple[str, ...]] = set()
            for index in indexes:
                if index[2]:
                    columns = connection.exec_driver_sql(f"PRAGMA index_info('{index[1]}')").all()
                    actual.add(tuple(column[2] for column in columns))
            assert required <= actual
            observed[table] = [list(columns) for columns in sorted(actual)]
        for model_table in Base.metadata.tables.values():
            names = [constraint.name for constraint in model_table.constraints if constraint.name]
            assert len(names) == len(set(names))

    populated.read(inspect_indexes)
    evidence("unique-indexes.json", observed)


def test_failed_engine_construction_releases_context_guard(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("ENGINE_CONSTRUCTION_FAULT")

    with monkeypatch.context() as patch:
        patch.setattr(store_module, "_engine", fail)
        with pytest.raises(RuntimeError, match="ENGINE_CONSTRUCTION_FAULT"):
            store.write(lambda session: 1)
    assert_outside_write_transaction()
    assert store.read(lambda session: 1) == 1
