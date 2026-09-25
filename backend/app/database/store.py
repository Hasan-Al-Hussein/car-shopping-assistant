"""Noncreating opens and one explicit SQLAlchemy-controlled transaction strategy."""

import asyncio
import inspect
import json
import sqlite3
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from pydantic import BaseModel
from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from starlette.concurrency import run_in_threadpool

from app.database.capabilities import detect_fts5, fts5_registered
from app.database.maintenance import (
    MaintenanceBusy,
    MaintenanceError,
    assert_store_lease,
    initialize_maintenance_guard,
    shared_store_lease,
)
from app.database.models import Base
from app.database.paths import (
    RuntimeBoundary,
    StorePathError,
    _sqlite_uri,
    guarded_store_path,
    prepare_store_parent,
    reserve_new_store,
)

SCHEMA_VERSION = "0002"
SUPPORTED_SCHEMA_VERSIONS = {"0001", SCHEMA_VERSION}
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
BUSY_TIMEOUT_MS = 1000
_unit_active: ContextVar[bool] = ContextVar("database_unit_active", default=False)
_write_active: ContextVar[bool] = ContextVar("database_write_active", default=False)
T = TypeVar("T")
Trace = Callable[[str], None]


class StoreError(RuntimeError):
    """Sanitized store failure; never a terminal business rejection."""


@contextmanager
def _maintenance_errors() -> Iterator[None]:
    try:
        yield
    except MaintenanceBusy:
        raise StoreError("STORE_BUSY") from None
    except MaintenanceError:
        raise StoreError("STORE_UNAVAILABLE") from None


@contextmanager
def _shared_admission(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    must_exist: bool = True,
) -> Iterator[None]:
    with _maintenance_errors(), shared_store_lease(path, boundary=boundary, must_exist=must_exist):
        yield


def assert_outside_write_transaction() -> None:
    """Provider/network/projector adapters must call this before external work."""
    if _write_active.get():
        raise StoreError("EXTERNAL_WORK_INSIDE_WRITE_TRANSACTION")


def _assert_sync_boundary() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise StoreError("BLOCKING_DATABASE_CALL_ON_EVENT_LOOP")


def _check_result(value: object, ancestors: frozenset[int] = frozenset()) -> None:
    if value is None or isinstance(value, (str, bytes, int, float, bool, date, UUID)):
        return
    if isinstance(value, (Session, Connection, Engine, Base, Iterator)):
        raise StoreError("DATABASE_RESULT_MUST_BE_MATERIALIZED_DATA")
    if id(value) in ancestors:
        raise StoreError("DATABASE_RESULT_CONTAINS_CYCLE")
    seen = ancestors | {id(value)}
    if isinstance(value, Mapping):
        for key, item in value.items():
            _check_result(key, seen)
            _check_result(item, seen)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _check_result(item, seen)
    elif isinstance(value, BaseModel):
        _check_result(vars(value), seen)
        _check_result(value.__pydantic_private__, seen)
        _check_result(value.__pydantic_extra__, seen)
    elif is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _check_result(getattr(value, field.name), seen)
        if hasattr(value, "__dict__"):
            _check_result(vars(value), seen)
    elif isinstance(value, Enum):
        _check_result(value.value, seen)
    else:
        raise StoreError("DATABASE_RESULT_MUST_BE_MATERIALIZED_DATA")


def _connect(
    path: Path, mode: Literal["ro", "rw"], trace: Trace | None, *, boundary: RuntimeBoundary
) -> sqlite3.Connection:
    assert_store_lease(path, boundary=boundary)
    safe_path = guarded_store_path(path, boundary=boundary, must_exist=True)
    # Python accepts LEGACY_TRANSACTION_CONTROL (-1); typeshed currently permits bool only.
    db: sqlite3.Connection = sqlite3.connect(  # type: ignore[call-overload]
        _sqlite_uri(safe_path, mode),
        uri=True,
        timeout=BUSY_TIMEOUT_MS / 1000,
        isolation_level=None,
        autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL,
        check_same_thread=True,
    )
    try:
        guarded_store_path(path, boundary=boundary, must_exist=True)
        if trace is not None:
            db.set_trace_callback(trace)
        db.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        if db.execute("PRAGMA journal_mode").fetchone() != ("delete",):
            raise StoreError("STORE_JOURNAL_MODE_INCOMPATIBLE")
        if db.execute("PRAGMA foreign_keys").fetchone() != (1,):
            raise StoreError("STORE_FOREIGN_KEYS_UNAVAILABLE")
        if db.execute("PRAGMA synchronous").fetchone() != (2,):
            raise StoreError("STORE_DURABILITY_UNAVAILABLE")
        return db
    except BaseException:
        db.close()
        raise


def _schema_objects(db: sqlite3.Connection) -> list[list[str]]:
    return [
        [kind, name, " ".join(sql.split())]
        for kind, name, sql in db.execute(
            "SELECT type,name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' AND name != 'alembic_version' ORDER BY type,name"
        )
    ]


@dataclass(frozen=True)
class StoreProfile:
    generation: str
    schema_version: str
    inventory_mode: Literal["fts5", "bounded_lexical"] | None


def _validate(db: sqlite3.Connection) -> StoreProfile:
    """Validate within the caller's read transaction; never migrate or reset here."""
    if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise StoreError("STORE_CORRUPT")
    version = db.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(version) != 1 or version[0][0] not in SUPPORTED_SCHEMA_VERSIONS:
        raise StoreError("STORE_SCHEMA_INCOMPATIBLE")
    schema_version = version[0][0]
    rows = db.execute("SELECT id,schema_version,store_generation FROM store_metadata").fetchall()
    if len(rows) != 1 or rows[0][:2] != (1, schema_version):
        raise StoreError("STORE_METADATA_INCOMPATIBLE")
    generation = str(UUID(rows[0][2]))
    if generation != rows[0][2]:
        raise StoreError("STORE_GENERATION_INVALID")
    expected = json.loads((MIGRATIONS / "schema-0001.json").read_text(encoding="utf-8"))
    inventory_mode: Literal["fts5", "bounded_lexical"] | None = None
    if schema_version == "0002":
        profile = db.execute("SELECT id,mode FROM inventory_storage_profile").fetchall()
        if profile == [(1, "fts5")]:
            inventory_mode = "fts5"
        elif profile == [(1, "bounded_lexical")]:
            inventory_mode = "bounded_lexical"
        else:
            raise StoreError("STORE_INVENTORY_PROFILE_INCOMPATIBLE")
        if fts5_registered(db) != (inventory_mode == "fts5"):
            raise StoreError("STORE_INVENTORY_CAPABILITY_INCOMPATIBLE")
        additions = json.loads((MIGRATIONS / "schema-0002.json").read_text(encoding="utf-8"))
        expected = sorted(expected + additions["common"] + additions[inventory_mode])
    if _schema_objects(db) != expected:
        raise StoreError("STORE_SCHEMA_STRUCTURE_INCOMPATIBLE")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise StoreError("STORE_FOREIGN_KEY_CORRUPTION")
    if inventory_mode == "fts5":
        # Preparing/reading MATCH must work. Content completeness belongs to Inventory's
        # staged-candidate validation; read-only admission must not run integrity INSERTs.
        db.execute(
            "SELECT rowid FROM inventory_search_fts WHERE inventory_search_fts MATCH ? LIMIT 1",
            ("storecapabilitycheck",),
        ).fetchall()
    return StoreProfile(generation, schema_version, inventory_mode)


def _engine(
    path: Path, trace: Trace | None, *, validate: bool, boundary: RuntimeBoundary
) -> Engine:
    def creator() -> sqlite3.Connection:
        db = _connect(path, "rw", trace, boundary=boundary)
        try:
            if validate:
                db.execute("BEGIN")
                _validate(db)
                db.rollback()
            return db
        except BaseException:
            db.close()
            raise

    engine = create_engine("sqlite+pysqlite://", creator=creator, poolclass=NullPool)

    @event.listens_for(engine, "begin")
    def begin(connection: Connection) -> None:
        write = connection.get_execution_options().get("store_write", False)
        connection.exec_driver_sql("PRAGMA query_only=" + ("OFF" if write else "ON"))
        connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")

    return engine


@dataclass(frozen=True)
class Store:
    """No persistent connection/session. Each call opens/closes in its current thread."""

    path: Path
    generation: str
    # Tests only: never enable SQL tracing for private production data.
    trace: Trace | None = None
    schema_version: str = "0001"
    inventory_mode: Literal["fts5", "bounded_lexical"] | None = None
    boundary: RuntimeBoundary = field(kw_only=True, repr=False)

    def _run(self, work: Callable[[Session], T], *, write: bool) -> T:
        _assert_sync_boundary()
        if _unit_active.get() or inspect.iscoroutinefunction(work):
            raise StoreError("DATABASE_REQUIRES_ONE_SYNCHRONOUS_UNIT")
        with _shared_admission(self.path, boundary=self.boundary):
            return self._run_admitted(work, write=write)

    def _run_admitted(self, work: Callable[[Session], T], *, write: bool) -> T:
        unit_token = _unit_active.set(True)
        write_token = _write_active.set(write)
        engine: Engine | None = None
        try:
            engine = _engine(self.path, self.trace, validate=True, boundary=self.boundary)
            with (
                engine.connect().execution_options(store_write=write) as connection,
                connection.begin(),
            ):
                current = connection.exec_driver_sql(
                    "SELECT store_generation,schema_version FROM store_metadata WHERE id=1"
                ).one()
                if current[0] != self.generation:
                    raise StoreError("STORE_GENERATION_CHANGED")
                if current[1] != self.schema_version:
                    raise StoreError("STORE_SCHEMA_CHANGED")
                with Session(bind=connection, join_transaction_mode="rollback_only") as session:
                    result = work(session)
                    if inspect.isawaitable(result):
                        if inspect.iscoroutine(result):
                            result.close()
                        raise StoreError("DATABASE_CALLBACK_RETURNED_AWAITABLE")
                    _check_result(result)
                    session.flush()
                    if not connection.in_transaction():
                        raise StoreError("DATABASE_CALLBACK_ENDED_TRANSACTION")
                return result
        except OperationalError as exc:
            code = getattr(exc.orig, "sqlite_errorcode", None)
            if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise StoreError("STORE_BUSY") from exc
            raise StoreError("STORE_UNAVAILABLE") from exc
        except sqlite3.DatabaseError as exc:
            raise StoreError("STORE_UNAVAILABLE") from exc
        finally:
            try:
                if engine is not None:
                    engine.dispose()
            finally:
                _write_active.reset(write_token)
                _unit_active.reset(unit_token)

    def read(self, work: Callable[[Session], T]) -> T:
        return self._run(work, write=False)

    def write(self, work: Callable[[Session], T]) -> T:
        return self._run(work, write=True)

    async def read_async(self, work: Callable[[Session], T]) -> T:
        return await run_in_threadpool(self.read, work)

    async def write_async(self, work: Callable[[Session], T]) -> T:
        return await run_in_threadpool(self.write, work)


def open_store(path: Path, *, boundary: RuntimeBoundary, trace: Trace | None = None) -> Store:
    """Noncreating and read-only validation; no automatic migration or empty repair."""
    _assert_sync_boundary()
    with _shared_admission(path, boundary=boundary):
        return _open_store_admitted(path, boundary=boundary, trace=trace)


def _open_store_admitted(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    trace: Trace | None,
) -> Store:
    try:
        db = _connect(path, "ro", trace, boundary=boundary)
        try:
            db.execute("BEGIN")
            profile = _validate(db)
            db.rollback()
        finally:
            db.close()
    except StorePathError:
        raise
    except (sqlite3.DatabaseError, ValueError) as exc:
        raise StoreError("STORE_CORRUPT_OR_INCOMPATIBLE") from exc
    return Store(
        path=path,
        generation=profile.generation,
        trace=trace,
        schema_version=profile.schema_version,
        inventory_mode=profile.inventory_mode,
        boundary=boundary,
    )


def initialize_store(path: Path, *, boundary: RuntimeBoundary, trace: Trace | None = None) -> Store:
    """Explicit new store only. Failed initialization is retained for diagnosis, never reset."""
    _assert_sync_boundary()
    assert_outside_write_transaction()
    if _unit_active.get():
        raise StoreError("DATABASE_REQUIRES_ONE_SYNCHRONOUS_UNIT")
    with _maintenance_errors():
        prepare_store_parent(path, boundary=boundary)
        initialize_maintenance_guard(path, boundary=boundary, must_exist=False)
        with _shared_admission(path, boundary=boundary, must_exist=False):
            return _initialize_store_admitted(path, boundary=boundary, trace=trace)


def _initialize_store_admitted(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    trace: Trace | None,
) -> Store:
    fts5 = detect_fts5()
    reserve_new_store(path, boundary=boundary)
    engine = _engine(path, trace, validate=False, boundary=boundary)
    try:
        with (
            engine.connect().execution_options(store_write=True) as connection,
            connection.begin(),
        ):
            config = Config()
            config.set_main_option("script_location", str(MIGRATIONS))
            config.attributes["connection"] = connection
            config.attributes["inventory_fts5"] = fts5
            command.upgrade(config, SCHEMA_VERSION)
            connection.exec_driver_sql(
                "INSERT INTO store_metadata "
                "(id,schema_version,store_generation,created_at) VALUES (1,?,?,?)",
                (SCHEMA_VERSION, str(uuid4()), datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")),
            )
    finally:
        engine.dispose()
    return open_store(path, boundary=boundary, trace=trace)


def upgrade_store(
    path: Path, *, expected_generation: str, boundary: RuntimeBoundary, trace: Trace | None = None
) -> Store:
    """Explicit local operator migration; never invoked by health, startup or buyer reads.

    Capability is probed before the SQLite write lock. Exact old schema, generation, DDL and both
    version markers share one BEGIN IMMEDIATE; any failure rolls back that whole unit.
    No backfilled inventory authority or generation rotation is invented by this upgrade.
    """
    _assert_sync_boundary()
    if _unit_active.get():
        raise StoreError("DATABASE_REQUIRES_ONE_SYNCHRONOUS_UNIT")
    with _shared_admission(path, boundary=boundary):
        return _upgrade_store_admitted(
            path,
            expected_generation=expected_generation,
            boundary=boundary,
            trace=trace,
        )


def _upgrade_store_admitted(
    path: Path,
    *,
    expected_generation: str,
    boundary: RuntimeBoundary,
    trace: Trace | None,
) -> Store:
    fts5 = detect_fts5()
    engine = _engine(path, trace, validate=False, boundary=boundary)
    try:
        with (
            engine.connect().execution_options(store_write=True) as connection,
            connection.begin(),
        ):
            raw = connection.connection.driver_connection
            if not isinstance(raw, sqlite3.Connection):
                raise StoreError("STORE_DRIVER_INCOMPATIBLE")
            before = _validate(raw)
            if before.generation != expected_generation:
                raise StoreError("STORE_GENERATION_CHANGED")
            if before.schema_version == "0001":
                config = Config()
                config.set_main_option("script_location", str(MIGRATIONS))
                config.attributes["connection"] = connection
                config.attributes["inventory_fts5"] = fts5
                command.upgrade(config, SCHEMA_VERSION)
            after = _validate(raw)
            if after.generation != before.generation or after.schema_version != SCHEMA_VERSION:
                raise StoreError("STORE_UPGRADE_INCOMPATIBLE")
    except (sqlite3.DatabaseError, OperationalError, ValueError) as exc:
        raise StoreError("STORE_UPGRADE_FAILED") from exc
    finally:
        engine.dispose()
    return open_store(path, boundary=boundary, trace=trace)


def runtime_capabilities(store: Store) -> dict[str, Any]:
    """FTS probe uses a separate in-memory connection, never writes the canonical store."""
    _assert_sync_boundary()
    assert_outside_write_transaction()
    fts5 = detect_fts5()

    def read(session: Session) -> dict[str, Any]:
        connection = session.connection()
        return {
            "sqlite_version": connection.exec_driver_sql("SELECT sqlite_version()").scalar_one(),
            "sqlite_source_id": connection.exec_driver_sql(
                "SELECT sqlite_source_id()"
            ).scalar_one(),
            "fts5": fts5,
            **{
                name: connection.exec_driver_sql(f"PRAGMA {name}").scalar_one()
                for name in (
                    "journal_mode",
                    "synchronous",
                    "foreign_keys",
                    "busy_timeout",
                    "query_only",
                )
            },
        }

    return store.read(read)
