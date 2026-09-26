"""Real disposable Store and backup API fixtures. No mocks for backup/file success."""

from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.database.models import StoreMetadata
from app.database.paths import RuntimeBoundary
from app.identity.service import utc_text
from app.operations.backup_restore import BackupService
from tests.operations.retention_fixtures import RetentionHarness, make_retention_harness


@dataclass
class BackupHarness:
    retention: RetentionHarness
    service: BackupService


def make_backup_harness(
    monkeypatch: pytest.MonkeyPatch,
    *,
    boundary: RuntimeBoundary | None = None,
) -> BackupHarness:
    retained = make_retention_harness(monkeypatch, boundary=boundary)
    base = retained.projection.leads.sessions

    def align_clock(db: Session) -> None:
        # Store initialization uses wall time; this isolated controlled-clock
        # fixture explicitly aligns only creation metadata before any backup.
        metadata = db.get(StoreMetadata, 1)
        assert metadata is not None
        metadata.created_at = utc_text(base.clock.now())

    base.store.write(align_clock)
    return BackupHarness(retained, BackupService(base.store, clock=base.clock.now))
