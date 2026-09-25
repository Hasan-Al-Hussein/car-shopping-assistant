"""Withdraw only owned derived bytes under the existing T8 publication lock.

Called after canonical retention commits, before repair. Descriptors remain as
same-Store recovery evidence. This is not backup/log cleanup or a restore tool.
"""

from app.database.store import assert_outside_write_transaction
from app.leads.projection_files import CSV_NAME, MAX_BYTES, ProjectionFiles
from app.leads.projection_repository import ProjectionError


def withdraw_expired(files: ProjectionFiles, *, generation: str, version: int | None) -> None:
    """Caller holds files.lock(). No nested lock or Store write is opened here."""
    assert_outside_write_transaction()
    if version is None:
        raise ProjectionError("CSV_RETENTION_VERSION_REQUIRED")
    existing, pending = files.inspect_existing(
        generation=generation, version=version, reconcile_from_generation=None,
    )
    data = files.read_bytes(CSV_NAME, MAX_BYTES)
    if data is not None:
        if not any(value is not None and files.matches(value, data) for value in (existing, pending)):
            raise ProjectionError("CSV_RETENTION_BYTES_UNVERIFIED")
        files.path(CSV_NAME).unlink()  # One fixed, guarded regular file, never a recursive delete.
    if pending is not None:
        files.discard_known_temporary(pending)
    files.prune_temporary_files()
    if files.read_bytes(CSV_NAME, MAX_BYTES) is not None:
        raise ProjectionError("CSV_RETENTION_WITHDRAWAL_UNVERIFIED")
