"""Isolated candidate proof only: no live Store swap or maintenance exclusion claim."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import load_settings
from app.core.errors import ApiFailure
from app.database.models import (
    ActiveInventory, ActiveRules, ExportIntent, ExportState, Lead, OwnerCredential, StoreMetadata,
)
from app.database.store import open_store
from app.identity.authorization import AuthorizationService
from app.identity.credentials import decode_token
from app.identity.service import IdentityService
from app.operations.backup_files import BackupError
from app.operations.backup_restore import summaries
from app.operations.restore_state import prepare_candidate
from tests.operations.backup_fixtures import make_backup_harness
from tests.support.harness import runtime_environment


def test_candidate_rotation_preserves_authority_and_invalidates_old_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = make_backup_harness(monkeypatch)
    base = flow.retention.projection.leads.sessions
    flow.retention.projection.save()
    backup = flow.service.create()
    before = flow.retention.facts()
    prepared = prepare_candidate(
        flow.service.files, backup.backup_id, now=base.clock.now(), clock=base.clock.now,
    )
    assert prepared.new_generation != prepared.original_generation == backup.original_generation
    assert prepared.records == backup.records and prepared.revoked_credentials == 2
    assert flow.retention.facts() == before
    assert flow.service.files.manifest(backup.backup_id) == backup
    path = flow.service.files.path(prepared.candidate_id, "sqlite3")
    candidate = open_store(path, boundary=base.store.boundary)
    assert candidate.read(summaries) == backup.records
    assert candidate.read(lambda db: db.get(ActiveInventory, 1) is None)
    assert candidate.read(lambda db: db.get(ActiveRules, 1) is None)
    assert candidate.read(lambda db: db.scalar(select(func.count()).select_from(OwnerCredential)
                                             .where(OwnerCredential.revoked_at.is_(None)))) == 0
    assert candidate.read(lambda db: tuple(db.scalars(select(ExportIntent.store_generation)))) == (
        prepared.new_generation,
    )
    settings = load_settings({**runtime_environment(base.store.boundary), "CSA_STORE_PATH": str(path)})
    authorization = AuthorizationService(IdentityService(settings, clock=base.clock.now))
    buyer = base.buyers[0]
    with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
        authorization.authorize_read(decode_token(buyer.cookie), buyer.identity.context_id)
    assert base.context().generation == base.store.generation
    assert candidate.read(lambda db: db.scalar(select(StoreMetadata.recovery_point))) == backup.recovery_point


def test_expired_backup_cannot_become_a_new_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = make_backup_harness(monkeypatch)
    base = flow.retention.projection.leads.sessions
    backup = flow.service.create()
    base.clock.value += timedelta(days=7)
    before = flow.retention.facts()
    with pytest.raises(BackupError, match="RESTORE_BACKUP_EXPIRED_OR_FUTURE"):
        prepare_candidate(flow.service.files, backup.backup_id, now=base.clock.now(), clock=base.clock.now)
    assert flow.retention.facts() == before


def test_candidate_reconciles_expired_lead_without_changing_source_or_live_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = make_backup_harness(monkeypatch)
    base = flow.retention.projection.leads.sessions
    flow.retention.projection.save()
    base.clock.value += timedelta(days=89)
    backup = flow.service.create()
    base.clock.value += timedelta(days=2)  # Backup is young; its retained lead is expired.
    before = flow.retention.facts()
    source_bytes = flow.service.files.path(backup.backup_id, "sqlite3").read_bytes()
    prepared = prepare_candidate(
        flow.service.files, backup.backup_id, now=base.clock.now(), clock=base.clock.now,
    )
    candidate = open_store(
        flow.service.files.path(prepared.candidate_id, "sqlite3"), boundary=base.store.boundary,
    )
    assert candidate.read(lambda db: db.scalar(select(func.count()).select_from(Lead))) == 0
    assert prepared.retention.complete is True
    assert prepared.retention.protected_expired_leads == 0
    assert prepared.retention.protected_reasons == ()
    assert prepared.retention.before_summary_sha256 != prepared.retention.after_summary_sha256
    assert prepared.canonical_projection_version == 2
    assert candidate.read(lambda db: db.scalar(select(ExportState.canonical_version))) == 2
    assert prepared.new_generation != base.store.generation
    assert flow.retention.facts() == before
    assert flow.service.files.manifest(backup.backup_id) == backup
    assert flow.service.files.path(backup.backup_id, "sqlite3").read_bytes() == source_bytes
