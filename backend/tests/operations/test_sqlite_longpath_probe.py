"""Bounded same-leaf diagnostic for the default Windows SQLite VFS."""

import json
import sqlite3
from contextlib import closing
from urllib.parse import quote
from uuid import uuid4

import pytest

from app.database.maintenance import initialize_maintenance_guard, shared_store_lease
from app.database.paths import _io_path, guarded_store_path
from app.operations.backup_restore import SCANS
from tests.operations.backup_fixtures import make_backup_harness


def test_same_reserved_leaf_default_vfs(monkeypatch, record_property):
    case = make_backup_harness(monkeypatch)
    store, files = case.service.store, case.service.files
    observations = {"sqlite_version": sqlite3.sqlite_version, "default_vfs": True}

    def uri(path, mode):
        native = _io_path(path)
        if native == path:
            return path.as_uri() + f"?mode={mode}"
        return f"file:/{quote(str(native), safe='')}?mode={mode}"

    with files.lock():
        destination = files.reserve(str(uuid4()))
        assert len(str(destination)) == 301
        observations["ordinary_chars"] = len(str(destination))
        observations["extended_bytes"] = len(str(_io_path(destination)).encode("utf-8"))
        with shared_store_lease(destination, boundary=store.boundary):
            assert guarded_store_path(destination, boundary=store.boundary, must_exist=True) == destination
            with pytest.raises(sqlite3.OperationalError) as original:
                with closing(sqlite3.connect(destination.as_uri() + "?mode=rw", uri=True,
                                             isolation_level=None, timeout=1)):
                    pass
            observations["ordinary_error"] = {
                "code": original.value.sqlite_errorcode,
                "name": original.value.sqlite_errorname,
                "message": str(original.value),
            }
            with closing(sqlite3.connect(uri(destination, "rw"), uri=True,
                                         isolation_level=None, timeout=1)) as target:
                assert target.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",)
                target.execute("PRAGMA synchronous=FULL")

                def copy(db):
                    connection = db.connection()
                    metadata = tuple(tuple(row) for row in connection.exec_driver_sql(
                        "SELECT * FROM store_metadata ORDER BY id").fetchall())
                    rows = {table: tuple(tuple(row) for row in connection.exec_driver_sql(
                        f"SELECT {columns} FROM {table} ORDER BY {columns}").fetchall())
                        for table, columns in SCANS}
                    source = connection.connection.driver_connection
                    assert isinstance(source, sqlite3.Connection)
                    source.backup(target, pages=128, sleep=0.01)
                    return metadata, rows

                metadata, rows = store.read(copy)
                assert target.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            with closing(sqlite3.connect(uri(destination, "ro"), uri=True,
                                         isolation_level=None, timeout=1)) as readonly:
                assert tuple(readonly.execute("SELECT * FROM store_metadata ORDER BY id")) == metadata
                for table, columns in SCANS:
                    assert tuple(readonly.execute(
                        f"SELECT {columns} FROM {table} ORDER BY {columns}")) == rows[table]
                with pytest.raises(sqlite3.OperationalError) as denied:
                    readonly.execute("CREATE TABLE forbidden_probe_write (id INTEGER)")
                assert denied.value.sqlite_errorcode == sqlite3.SQLITE_READONLY
            assert guarded_store_path(destination, boundary=store.boundary, must_exist=True) == destination
            observations["copy_integrity_metadata_records_readonly"] = "PASS"

        absent = files.path(str(uuid4()), "sqlite3")
        assert not _io_path(absent).exists()
        initialize_maintenance_guard(absent, boundary=store.boundary, must_exist=False)
        with shared_store_lease(absent, boundary=store.boundary, must_exist=False):
            for mode in ("ro", "rw"):
                with pytest.raises(sqlite3.OperationalError) as missing:
                    with closing(sqlite3.connect(uri(absent, mode), uri=True,
                                                 isolation_level=None, timeout=1)):
                        pass
                observations[f"absent_{mode}"] = missing.value.sqlite_errorname
                for suffix in ("", "-journal", "-wal", "-shm"):
                    assert not _io_path(absent.with_name(absent.name + suffix)).exists()
        observations["absent_noncreation"] = "PASS"
    record_property("sqlite_probe", json.dumps(observations, sort_keys=True))
