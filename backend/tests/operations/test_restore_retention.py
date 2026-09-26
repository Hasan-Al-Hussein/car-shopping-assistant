"""R2 source cases using real disposable Stores, T10, T8 and restore services.

Interruption hooks raise only after/before the named real operation. They are not
abrupt-process, power-loss, real Inventory admission or A9 browser-wrapper proof.
Execution, collection and static checks remain separately authorized.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.identity import IdentityBootstrapRequest
from app.api.schemas.sessions import SessionCreateRequest
from app.database.maintenance import exclusive_store_lease, maintenance_paths
from app.database.models import ExportState, Lead, Message, Owner, StoreMetadata
from app.database.store import open_store
from app.identity.service import utc_text
from app.identity.credentials import decode_token
from app.leads.projection import CsvProjector
from app.leads.projection_files import CSV_NAME, MANIFEST_NAME, ProjectionFiles
from app.leads.service import LeadService
from app.operations import restore_files, restore_operator, restore_retention, restore_transition
from app.operations.backup_files import BackupError, BackupManifest
from app.operations.backup_restore import BackupService, summaries
from app.operations.restore_files import RestoreFiles, encoded
from app.operations.restore_operator import RestoreService
from app.operations.restore_retention import ProtectedRetentionError, reconcile_candidate, summary_digest
from app.operations.restore_state import PreparedRestoreCandidate, prepare_candidate
from app.operations.restore_transition import RestoreIntentV2, parse_receipt
from tests.operations.backup_fixtures import BackupHarness, make_backup_harness
from tests.transactions.confirmation_fixtures import make_confirmation_harness
from tests.transactions.draft_fixtures import confirmation
from tests.transactions.lead_fixtures import LeadInventoryFake, save_request


class SimulatedInterruption(BaseException):
    """Synthetic control-flow loss, not a native-process crash."""


@pytest.fixture
def backup(monkeypatch: pytest.MonkeyPatch) -> BackupHarness:
    return make_backup_harness(monkeypatch)


def service_for(backup: BackupHarness) -> RestoreService:
    base = backup.retention.projection.leads.sessions
    return RestoreService(base.store.path, boundary=base.store.boundary, clock=base.clock.now)


def young_backup_with_old_lead(backup: BackupHarness, *, protected: bool = False) -> BackupManifest:
    flow = backup.retention.projection
    saved = flow.save()
    if protected:
        backup.retention.unresolved_lead_command(saved_lead=saved)
    flow.leads.sessions.clock.value += timedelta(days=89)
    return backup.service.create()


def stop_pending(
    backup: BackupHarness, selected: BackupManifest, monkeypatch: pytest.MonkeyPatch,
    *, phase: str,
) -> RestoreIntentV2:
    """Only interruption is substituted; successful work uses actual methods."""
    flow = backup.retention.projection
    service = service_for(backup)
    with monkeypatch.context() as fault:
        if phase == "before_swap":
            def before_continue(*args: object) -> None:
                raise SimulatedInterruption("after actual initial marker")
            fault.setattr(service, "_continue", before_continue)
        elif phase == "after_swap":
            original_replace = restore_operator.os.replace

            def replaced(source: Path, target: Path) -> None:
                original_replace(source, target)
                if target == flow.store.path.resolve():
                    raise SimulatedInterruption("after actual canonical swap")
            fault.setattr(restore_operator.os, "replace", replaced)
        elif phase == "after_ack":
            original_repair = CsvProjector.repair_locked

            def acknowledged(
                self: CsvProjector, files: ProjectionFiles,
                *, reconcile_from_generation: str | None = None,
            ) -> None:
                actual = original_repair(self, files, reconcile_from_generation=reconcile_from_generation)
                assert actual.state == "current" and actual.status_persisted
                raise SimulatedInterruption("after actual publication acknowledgement")
            fault.setattr(CsvProjector, "repair_locked", acknowledged)
        else:
            raise AssertionError("unsupported synthetic interruption phase")
        with pytest.raises(SimulatedInterruption):
            service.restore(selected.backup_id, expected_generation=flow.store.generation)
    pending = service.inspect()
    assert isinstance(pending, RestoreIntentV2)
    return pending


def reconcile_prepared(
    backup: BackupHarness, prepared: PreparedRestoreCandidate, *, clock: Callable[[], datetime],
) -> None:
    """Exercise real bounded sweep on a real uninstalled candidate, under its lease."""
    files = backup.service.files
    path = files.path(prepared.candidate_id, "sqlite3")
    with exclusive_store_lease(path, boundary=files.boundary) as lease:
        reconcile_candidate(
            files, prepared.candidate_id, lease=lease, expected_generation=prepared.new_generation,
            expected_semantic_sha256=prepared.semantic_sha256,
            expected_summary_sha256=summary_digest(prepared.records),
            cutoff=backup.retention.projection.leads.sessions.clock.now(), clock=clock,
        )


def test_whole_sweep_does_not_skip_later_owner_after_deleting_first(backup: BackupHarness) -> None:
    flow = backup.retention.projection
    base = flow.leads.sessions
    first = 0 if backup.retention.owners[0] < backup.retention.owners[1] else 1
    expired = flow.save(first)
    base.clock.value += timedelta(days=2)
    retained = flow.save(1 - first)
    retained_expiry = base.store.read(lambda db: db.scalar(select(Lead.expires_at).where(Lead.id == retained.lead_id)))
    base.clock.value += timedelta(days=87)
    selected = backup.service.create()
    base.clock.value += timedelta(days=2)
    before = backup.retention.facts()
    prepared = prepare_candidate(backup.service.files, selected.backup_id,
                                 now=base.clock.now(), clock=base.clock.now)
    candidate = open_store(backup.service.files.path(prepared.candidate_id, "sqlite3"), boundary=base.store.boundary)
    assert prepared.retention.owners_inspected == 2
    assert candidate.read(lambda db: db.get(Owner, backup.retention.owners[first]) is None)
    assert candidate.read(lambda db: db.get(Lead, expired.lead_id) is None)
    assert candidate.read(lambda db: tuple(db.scalars(select(Lead.id)))) == (retained.lead_id,)
    assert candidate.read(lambda db: db.scalar(select(Lead.expires_at))) == retained_expiry
    assert dict(prepared.retention.changes)["delete.leads"] == 1
    assert backup.retention.facts() == before


def test_protected_original_command_reports_exact_reason_without_live_mutation(backup: BackupHarness) -> None:
    selected = young_backup_with_old_lead(backup, protected=True)
    flow = backup.retention.projection
    base = flow.leads.sessions
    original_messages = base.store.read(lambda db: tuple(db.scalars(select(Message.result_json))))
    base.clock.value += timedelta(days=2)
    before = backup.retention.facts()
    source_bytes = backup.service.files.path(selected.backup_id, "sqlite3").read_bytes()
    with pytest.raises(ProtectedRetentionError) as failed:
        service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    assert failed.value.expired_leads == 1
    assert failed.value.reasons == (("unresolved_collection_command", 1),)
    assert backup.retention.facts() == before
    assert base.store.read(lambda db: tuple(db.scalars(select(Message.result_json)))) == original_messages
    assert backup.service.files.path(selected.backup_id, "sqlite3").read_bytes() == source_bytes
    assert service_for(backup).inspect() is None
    assert not flow.files.path(CSV_NAME).exists()


def test_actual_submitted_review_protects_existing_lead_with_review_reason(backup: BackupHarness) -> None:
    # The backup fixture establishes the approved isolated runtime. This second
    # Store uses actual domain participants; only its Inventory port is synthetic.
    flow = make_confirmation_harness()
    base = flow.drafts.base

    def align(db: Session) -> None:
        metadata = db.get(StoreMetadata, 1)
        assert metadata is not None
        metadata.created_at = utc_text(base.clock.now())

    base.store.write(align)
    leads = LeadService(base.auth, inventory=LeadInventoryFake(base))
    saved = leads.save(base.context(), save_request(flow.drafts.sessions[0])).lead
    draft = flow.create()
    assert draft.review is not None
    assert draft.review.lead_change.mode == "preserve_existing"
    base.auth.write(base.context(), lambda unit: flow.drafts.service.mark_submitted(
        unit, draft.draft_id, confirmation(draft), generation=base.store.generation,
        now=utc_text(base.clock.now()),
    ))
    base.clock.value += timedelta(days=89)
    backups = BackupService(base.store, clock=base.clock.now)
    selected = backups.create()
    source_bytes = backups.files.path(selected.backup_id, "sqlite3").read_bytes()
    base.clock.value += timedelta(days=2)
    before = base.store.read(summaries)
    with pytest.raises(ProtectedRetentionError) as failed:
        prepare_candidate(backups.files, selected.backup_id, now=base.clock.now(), clock=base.clock.now)
    assert failed.value.expired_leads == 1
    assert failed.value.reasons == (("unresolved_review", 1),)
    assert base.store.read(summaries) == before
    assert base.store.read(lambda db: db.get(Lead, saved.lead_id) is not None)
    assert backups.files.path(selected.backup_id, "sqlite3").read_bytes() == source_bytes


@pytest.mark.parametrize("phase", ["before_swap", "after_swap", "after_ack"])
def test_pending_expiry_transforms_same_operation_and_generation(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    selected = young_backup_with_old_lead(backup)
    flow = backup.retention.projection
    pending = stop_pending(backup, selected, monkeypatch, phase=phase)
    source_bytes = backup.service.files.path(selected.backup_id, "sqlite3").read_bytes()
    prior_bytes = backup.service.files.path(pending.previous.backup_id, "sqlite3").read_bytes()
    flow.leads.sessions.clock.value += timedelta(days=2)
    observed = service_for(backup).resume_observed(restore_id=pending.restore_id)
    revised = observed.receipt.intent
    assert isinstance(revised, RestoreIntentV2)
    assert revised.restore_id == pending.restore_id and revised.started_at == pending.started_at
    assert revised.candidate.new_generation == pending.candidate.new_generation
    assert revised.candidate.prepared_at == pending.candidate.prepared_at
    assert revised.candidate.recovery_point == pending.candidate.recovery_point
    assert revised.candidate.candidate_id != pending.candidate.candidate_id
    assert revised.revision == 1 and revised.superseded_candidate == pending.candidate
    assert len(revised.retention_steps) == 1
    assert revised.retention_steps[0].before_semantic_sha256 == pending.candidate.semantic_sha256
    assert revised.retention_steps[0].protected_expired_leads == 0
    assert observed.completion == "completed_current" and observed.projection == "current"
    current = open_store(flow.store.path, boundary=flow.store.boundary)
    assert current.generation == pending.candidate.new_generation
    assert current.read(lambda db: db.scalar(select(StoreMetadata.restored_at))) == pending.candidate.prepared_at
    assert current.read(lambda db: db.scalar(select(func.count()).select_from(Lead))) == 0
    assert flow.rows() == []
    assert backup.service.files.path(selected.backup_id, "sqlite3").read_bytes() == source_bytes
    assert backup.service.files.path(pending.previous.backup_id, "sqlite3").read_bytes() == prior_bytes
    assert backup.service.files.pinned(pending.previous.backup_id)
    assert service_for(backup).inspect() is None


def test_protected_post_swap_expiry_withdraws_only_owned_csv_and_keeps_original_intent(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = young_backup_with_old_lead(backup, protected=True)
    flow = backup.retention.projection
    pending = stop_pending(backup, selected, monkeypatch, phase="after_ack")
    assert flow.files.path(CSV_NAME).exists()
    flow.leads.sessions.clock.value += timedelta(days=2)
    with pytest.raises(ProtectedRetentionError) as failed:
        service_for(backup).resume(restore_id=pending.restore_id)
    assert failed.value.expired_leads == 1
    assert failed.value.reasons == (("unresolved_collection_command", 1),)
    assert service_for(backup).inspect() == pending
    assert not flow.files.path(CSV_NAME).exists()
    assert backup.service.files.pinned(pending.previous.backup_id)
    assert backup.service.files.pinned(selected.backup_id)
    with flow.files.lock(), exclusive_store_lease(flow.store.path, boundary=flow.store.boundary) as lease:
        files = RestoreFiles(flow.store.path, boundary=flow.store.boundary, lease=lease)
        current = open_store(flow.store.path, boundary=flow.store.boundary)
        assert current.read(lambda db: db.scalar(select(func.count()).select_from(Lead))) == 1
        assert current.read(lambda db: db.scalar(select(ExportState.state))) == "failed"
        assert files.receipt(pending.restore_id) is None
        assert not files.receipt_path(pending.restore_id, temporary=True).exists()


@pytest.mark.parametrize("durable", ["temporary", "final"])
def test_durable_completion_then_expiry_keeps_receipt_immutable_and_reports_retention(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch, durable: str,
) -> None:
    selected = young_backup_with_old_lead(backup)
    flow = backup.retention.projection
    marker = maintenance_paths(flow.store.path, boundary=flow.store.boundary).intent_path
    with monkeypatch.context() as fault:
        if durable == "temporary":
            original_rename = restore_files.os.rename

            def interrupt_rename(source: Path, target: Path) -> None:
                if str(source).endswith(".receipt.tmp"):
                    raise SimulatedInterruption("after real receipt fsync before rename")
                original_rename(source, target)
            fault.setattr(restore_files.os, "rename", interrupt_rename)
        else:
            original_unlink = Path.unlink

            def interrupt_unlink(self: Path, missing_ok: bool = False) -> None:
                if self == marker:
                    raise SimulatedInterruption("after real final receipt before marker unlink")
                original_unlink(self, missing_ok=missing_ok)
            fault.setattr(Path, "unlink", interrupt_unlink)
        with pytest.raises(SimulatedInterruption):
            service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    pending = service_for(backup).inspect()
    assert isinstance(pending, RestoreIntentV2)
    suffix = "tmp" if durable == "temporary" else "json"
    path = backup.service.files.directory() / f"restore.{pending.restore_id}.receipt.{suffix}"
    original_bytes = path.read_bytes()
    completed = parse_receipt(original_bytes)
    flow.leads.sessions.clock.value += timedelta(days=2)
    observed = service_for(backup).resume_observed(restore_id=pending.restore_id)
    assert observed.receipt == completed and observed.receipt.intent == pending
    assert observed.projection == "retention_required"
    assert observed.completion == "historically_completed_retention_required"
    assert observed.code == "RESTORE_POSTCOMPLETION_RETENTION_REQUIRED"
    final = backup.service.files.directory() / f"restore.{pending.restore_id}.receipt.json"
    assert final.read_bytes() == original_bytes
    assert not marker.exists() and not flow.files.path(CSV_NAME).exists()
    current = open_store(flow.store.path, boundary=flow.store.boundary)
    assert current.read(lambda db: db.scalar(select(func.count()).select_from(Lead))) == 1
    before = current.path.read_bytes(), final.read_bytes()
    repeated = service_for(backup).resume_observed(restore_id=pending.restore_id)
    assert repeated.receipt == completed and repeated.projection == "retention_required"
    assert (current.path.read_bytes(), final.read_bytes()) == before
    assert not backup.service.files.pinned(selected.backup_id)
    assert backup.service.files.pinned(pending.previous.backup_id)


@pytest.mark.parametrize("damage", ["missing", "altered"])
def test_historical_resume_checks_real_csv_without_repairing_a_current_db_bit(
    backup: BackupHarness, damage: str,
) -> None:
    flow = backup.retention.projection
    flow.save()
    selected = backup.service.create()
    completed = service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    path = flow.files.path(CSV_NAME)
    if damage == "missing":
        path.unlink()
        damaged_bytes = None
    else:
        damaged_bytes = path.read_bytes() + b"unverified extra bytes"
        path.write_bytes(damaged_bytes)
    current = open_store(flow.store.path, boundary=flow.store.boundary)
    assert current.read(lambda db: db.scalar(select(ExportState.state))) == "current"
    before = current.path.read_bytes(), flow.files.path(MANIFEST_NAME).read_bytes()
    observed = service_for(backup).resume_observed(restore_id=completed.intent.restore_id)
    assert observed.receipt == completed
    assert observed.projection == "unavailable" and observed.code == "RESTORE_CURRENT_CSV_UNVERIFIED"
    assert (current.path.read_bytes(), flow.files.path(MANIFEST_NAME).read_bytes()) == before
    assert (path.read_bytes() if path.exists() else None) == damaged_bytes


def test_historical_replay_after_selected_backup_expiry_is_read_only(backup: BackupHarness) -> None:
    selected = young_backup_with_old_lead(backup)
    flow = backup.retention.projection
    completed = service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    flow.leads.sessions.clock.value += timedelta(days=7)
    expired = backup.service.inspect_expiry()
    assert expired.eligible == (selected.backup_id,)
    assert backup.service.apply_expiry(expired) == (selected.backup_id,)
    assert not backup.service.files.path(selected.backup_id, "sqlite3").exists()
    before = flow.store.path.read_bytes(), flow.files.path(CSV_NAME).read_bytes()
    observed = service_for(backup).resume_observed(restore_id=completed.intent.restore_id)
    assert observed.receipt == completed and observed.projection == "retention_required"
    assert (flow.store.path.read_bytes(), flow.files.path(CSV_NAME).read_bytes()) == before
    assert backup.service.files.pinned(completed.intent.previous.backup_id)


def test_historical_receipt_allows_real_new_owner_writes_and_fresh_csv_proof(backup: BackupHarness) -> None:
    flow = backup.retention.projection
    base = flow.leads.sessions
    flow.save()
    selected = backup.service.create()
    completed = service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    final = backup.service.files.directory() / f"restore.{completed.intent.restore_id}.receipt.json"
    receipt_bytes = final.read_bytes()
    pin = backup.service.files.path(completed.intent.previous.backup_id, "pin.json")
    pin_bytes = pin.read_bytes()
    # Actual bootstrap creates a NEW owner. This does not recover the old owner
    # or claim that old credentials became valid after restore.
    bootstrap = base.auth.identity.bootstrap(IdentityBootstrapRequest.model_validate({
        "notice_version": "DEMO-POLICY-1", "notice_acknowledged": True,
        "display_name": "Synthetic post-restore buyer",
    }), None)
    assert bootstrap.cookie is not None
    context = base.auth.authorize_write(decode_token(bootstrap.cookie), bootstrap.identity.context_id,
                                        bootstrap.identity.csrf_token)
    assert context.generation == completed.intent.candidate.new_generation
    session = base.service.create(context, SessionCreateRequest(client_action_id=str(uuid4())))
    saved = flow.leads.service.save(context, save_request(session.session_id)).lead
    pending = service_for(backup).resume_observed(restore_id=completed.intent.restore_id)
    assert pending.receipt == completed and pending.projection == "unavailable"
    current = open_store(flow.store.path, boundary=flow.store.boundary)
    assert current.read(lambda db: db.get(Lead, saved.lead_id) is not None)
    assert CsvProjector(current, clock=base.clock.now).repair_once().state == "current"
    observed = service_for(backup).resume_observed(restore_id=completed.intent.restore_id)
    assert observed.receipt == completed and observed.projection == "current"
    assert observed.canonical_version is not None
    assert observed.canonical_version > completed.intent.candidate.canonical_projection_version
    assert final.read_bytes() == receipt_bytes and pin.read_bytes() == pin_bytes


def test_default_candidate_clock_is_fresh_utc_not_the_supplied_cutoff(backup: BackupHarness) -> None:
    base = backup.retention.projection.leads.sessions
    base.clock.value = datetime.now(UTC) - timedelta(minutes=10)

    def align(db: Session) -> None:
        metadata = db.get(StoreMetadata, 1)
        assert metadata is not None
        metadata.created_at = utc_text(base.clock.now())

    base.store.write(align)
    selected = backup.service.create()
    base.clock.value += timedelta(minutes=4)
    before = backup.retention.facts()
    with pytest.raises(BackupError, match="RESTORE_RETENTION_CLOCK_INVALID"):
        prepare_candidate(backup.service.files, selected.backup_id, now=base.clock.now())
    assert backup.retention.facts() == before


@pytest.mark.parametrize("failure", ["rollback", "future", "owners", "elapsed"])
def test_candidate_sweep_bounds_close_without_touching_live_store(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    base = backup.retention.projection.leads.sessions
    selected = backup.service.create()
    prepared = prepare_candidate(backup.service.files, selected.backup_id,
                                 now=base.clock.now(), clock=base.clock.now)
    before = backup.retention.facts()
    clock: Callable[[], datetime] = base.clock.now
    with monkeypatch.context() as fault:
        if failure == "rollback":
            wall_readings = iter((base.clock.now() + timedelta(seconds=2), base.clock.now() + timedelta(seconds=1)))
            clock = lambda: next(wall_readings)
            code = "RESTORE_RETENTION_CLOCK_INVALID"
        elif failure == "future":
            clock = lambda: base.clock.now() + timedelta(minutes=5, microseconds=1)
            code = "RESTORE_RETENTION_CLOCK_INVALID"
        elif failure == "owners":
            # Reduced numeric bound exercises the real loop on two actual owners.
            fault.setattr(restore_retention, "MAX_RETENTION_OWNERS", 1)
            code = "RESTORE_RETENTION_OWNER_LIMIT"
        else:
            elapsed_readings = iter((0.0, 31.0))
            # Replace only this module's elapsed-clock reference; do not alter
            # the stdlib time module used by SQLAlchemy/native lease machinery.
            fault.setattr(restore_retention, "time", SimpleNamespace(monotonic=lambda: next(elapsed_readings)))
            code = "RESTORE_RETENTION_TIME_LIMIT"
        with pytest.raises(BackupError, match=code):
            reconcile_prepared(backup, prepared, clock=clock)
    assert backup.retention.facts() == before
    assert service_for(backup).inspect() is None


def test_revision_budget_refuses_pending_expiry_before_new_transition(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = young_backup_with_old_lead(backup)
    pending = stop_pending(backup, selected, monkeypatch, phase="before_swap")
    backup.retention.projection.leads.sessions.clock.value += timedelta(days=2)
    # The initial genuine sweep consumes this deliberately reduced budget.
    monkeypatch.setattr(restore_operator, "MAX_SWEEPS", 1)
    with pytest.raises(BackupError, match="RESTORE_RETENTION_REVISION_LIMIT"):
        service_for(backup).resume(restore_id=pending.restore_id)
    assert service_for(backup).inspect() == pending
    assert backup.service.files.pinned(pending.selected.backup_id)


@pytest.mark.parametrize("payload", [b"{", b" " * (64 * 1024 + 1)], ids=["partial", "over_bound"])
def test_unknown_update_temporary_closes_without_erasing_predecessor(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch, payload: bytes,
) -> None:
    selected = young_backup_with_old_lead(backup)
    pending = stop_pending(backup, selected, monkeypatch, phase="before_swap")
    flow = backup.retention.projection
    marker = maintenance_paths(flow.store.path, boundary=flow.store.boundary).intent_path
    update = Path(str(marker) + ".update.tmp")
    update.write_bytes(payload)  # Explicit corruption of this test's own transient artifact.
    before = marker.read_bytes(), flow.store.path.read_bytes()
    with pytest.raises(BackupError, match="RESTORE_TRANSITION_INVALID"):
        service_for(backup).resume(restore_id=pending.restore_id)
    assert (marker.read_bytes(), flow.store.path.read_bytes()) == before
    assert update.read_bytes() == payload


def test_complete_update_fsync_gap_resumes_verified_successor(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = young_backup_with_old_lead(backup)
    pending = stop_pending(backup, selected, monkeypatch, phase="before_swap")
    flow = backup.retention.projection
    flow.leads.sessions.clock.value += timedelta(days=2)
    marker = maintenance_paths(flow.store.path, boundary=flow.store.boundary).intent_path
    update = Path(str(marker) + ".update.tmp")
    original_replace = restore_transition.os.replace

    def interrupted(source: Path, target: Path) -> None:
        if source == update and target == marker:
            raise SimulatedInterruption("complete transition fsynced before marker replace")
        original_replace(source, target)

    with monkeypatch.context() as fault:
        fault.setattr(restore_transition.os, "replace", interrupted)
        with pytest.raises(SimulatedInterruption):
            service_for(backup).resume(restore_id=pending.restore_id)
    assert marker.read_bytes() == encoded(pending)
    revised = RestoreIntentV2.model_validate_json(update.read_bytes())
    assert revised.restore_id == pending.restore_id and revised.revision == 1
    observed = service_for(backup).resume_observed(restore_id=pending.restore_id)
    assert observed.receipt.intent == revised and observed.projection == "current"
    assert not update.exists() and not marker.exists()
    assert flow.rows() == []


def test_v2_decoder_enforces_total_sweep_limit_and_started_at_cutoff(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = young_backup_with_old_lead(backup)
    pending = stop_pending(backup, selected, monkeypatch, phase="before_swap")
    backup.retention.projection.leads.sessions.clock.value += timedelta(days=2)
    completed = service_for(backup).resume(restore_id=pending.restore_id)
    intent = completed.intent
    assert isinstance(intent, RestoreIntentV2) and len(intent.retention_steps) == 1
    assert intent.initial_retention is not None
    material = intent.model_dump(mode="json")
    step = intent.retention_steps[0].model_dump(mode="json")
    # Pure rejection probes derived from a real operation; these altered DTOs
    # are never installed as markers or passed off as execution authority.
    over_limit = {**material, "revision": 32, "retention_steps": [step] * 32}
    with pytest.raises(ValueError, match="RESTORE_INTENT_INCOMPATIBLE"):
        RestoreIntentV2.model_validate(over_limit)  # Initial + 32 exceeds total 32.
    before_start = utc_text(datetime.fromisoformat(intent.started_at) - timedelta(microseconds=1))
    bad_step = {**step, "cutoff": before_start}
    with pytest.raises(ValueError, match="RESTORE_RETENTION_CHAIN_INVALID"):
        RestoreIntentV2.model_validate({**material, "retention_steps": [bad_step]})
