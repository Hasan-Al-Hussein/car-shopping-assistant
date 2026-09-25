"""Bounded content identity across the exact changes made by CSV reconciliation.

Caller uses an actually admitted Store READ. Schema names are obtained only from
that validated SQLite schema and quoted as identifiers, never interpolated input.
"""

import hashlib

from sqlalchemy.orm import Session

from app.operations.backup_files import MAX_BACKUP_BYTES, BackupError
from app.sessions.state import canonical

MAX_TABLES = 128
MAX_CONTENT_ROWS = 200_000
MAX_CONTENT_BYTES = 2 * MAX_BACKUP_BYTES
MAX_CELL_BYTES = 4 * 1024 * 1024
_MUTABLE = {
    "export_state": frozenset({"state", "exported_version", "updated_at"}),
    "export_intents": frozenset({"state", "attempts", "last_error_code"}),
}


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _value(value: object) -> object:
    if isinstance(value, (str, bytes)) and len(value) > MAX_CELL_BYTES:
        raise BackupError("RESTORE_CONTENT_CELL_LIMIT")
    if isinstance(value, str) and len(value.encode("utf-8")) > MAX_CELL_BYTES:
        raise BackupError("RESTORE_CONTENT_CELL_LIMIT")
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if value is None or type(value) in {str, int, float}:
        return [type(value).__name__, value]
    raise BackupError("RESTORE_CONTENT_TYPE_INCOMPATIBLE")


def semantic_digest(db: Session) -> str:
    """Bind all persisted values except the six exact mutable projector fields.

    Includes credentials, messages, reviews/outcomes, lead values, inventory/rule
    history, metadata, FTS storage and schema version. Table/column/row framing
    prevents concatenation ambiguity; duplicate equal rows retain their count.
    """
    connection = db.connection()
    tables = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 129"
    ).scalars().all()
    if len(tables) > MAX_TABLES:
        raise BackupError("RESTORE_CONTENT_TABLE_LIMIT")
    digest, rows, size = hashlib.sha256(), 0, 0

    def include(value: object) -> None:
        nonlocal size
        data = canonical(value)
        size += len(data)
        if size > MAX_CONTENT_BYTES:
            raise BackupError("RESTORE_CONTENT_BYTE_LIMIT")
        digest.update(len(data).to_bytes(8, "big") + data)

    for table in tables:
        columns = tuple(row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({_quoted(table)})"))
        if not columns or len(columns) > 128:
            raise BackupError("RESTORE_CONTENT_COLUMNS_INVALID")
        excluded = _MUTABLE.get(table, frozenset())
        if not excluded.issubset(columns):
            raise BackupError("RESTORE_CONTENT_SCHEMA_CHANGED")
        stable = tuple(name for name in columns if name not in excluded)
        if not stable:
            raise BackupError("RESTORE_CONTENT_COLUMNS_INVALID")
        identifiers = ",".join(_quoted(name) for name in stable)
        include(["table", table, stable])
        count = 0
        for row in connection.exec_driver_sql(
            f"SELECT {identifiers} FROM {_quoted(table)} ORDER BY {identifiers}"
        ):
            rows += 1
            count += 1
            if rows > MAX_CONTENT_ROWS:
                raise BackupError("RESTORE_CONTENT_ROW_LIMIT")
            include(["row", [_value(value) for value in row]])
        include(["end", table, count])
    return digest.hexdigest()
