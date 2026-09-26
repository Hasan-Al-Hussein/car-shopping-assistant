"""Real disposable Store/CSV fixtures plus labeled synthetic interruption seams.

These source cases do not substitute for abrupt-process/power-failure acceptance.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.identity import IdentityBootstrapRequest
from app.api.schemas.operations import OperationGenerationUnresolved
from app.core.errors import ApiFailure
from app.database.maintenance import (
    MaintenanceError,
    exclusive_store_lease,
    maintenance_paths,
    shared_store_lease,
)
from app.database.models import (
    Booking,
    ExportIntent,
    Lead,
    LeadBooking,
    OperationOutcome,
    StoreMetadata,
)
from app.database.paths import RuntimeBoundary, guarded_store_path, initialize_runtime_root
from app.database.store import StoreError, open_store
from app.identity.credentials import decode_token
from app.identity.service import utc_text
from app.leads.projection import CsvProjector
from app.leads.projection_files import ProjectionFiles
from app.operations.backup_files import BackupError
from app.operations.backup_restore import BackupService, summaries
from app.operations.restore_files import RestoreFiles
from app.operations.restore_operator import RestoreService
from app.operations.restore_transition import RestoreIntentV2
from app.viewings.confirmation import ConfirmationEffect
from tests.operations.backup_fixtures import BackupHarness, make_backup_harness
from tests.support.harness import configured_runtime_boundary
from tests.transactions.confirmation_fixtures import make_confirmation_harness
from tests.transactions.draft_fixtures import confirmation
from tests.transactions.projection_fixtures import deny_replacement


class SimulatedInterruption(BaseException):
    pass


@pytest.fixture
def backup(monkeypatch: pytest.MonkeyPatch) -> BackupHarness:
    configured = configured_runtime_boundary()
    guarded_store_path(
        configured.logical_root / "test-stores" / "boundary-probe.sqlite3",
        boundary=configured,
        must_exist=False,
    )
    physical_parent = configured.physical_root / "t"
    initialize_runtime_root(RuntimeBoundary(physical_parent, physical_parent))
    case_id = uuid4().hex[:10]
    physical = physical_parent / case_id
    physical.mkdir(exist_ok=False)
    boundary = RuntimeBoundary(configured.logical_root / "t" / case_id, physical)
    return make_backup_harness(monkeypatch, boundary=boundary)


def service_for(backup: BackupHarness) -> RestoreService:
    base = backup.retention.projection.leads.sessions
    return RestoreService(base.store.path, boundary=base.store.boundary, clock=base.clock.now)


def test_restore_preserves_earlier_ids_keeps_later_evidence_and_republishes_csv(
    backup: BackupHarness,
) -> None:
    flow = backup.retention.projection
    earlier = flow.save()
    selected = backup.service.create()
    later = flow.save(who=1)
    assert flow.projector.repair_once().state == "current"
    before = flow.store.read(summaries)
    receipt = service_for(backup).restore(
        selected.backup_id, expected_generation=flow.store.generation
    )
    restored = open_store(flow.store.path, boundary=flow.store.boundary)
    assert restored.generation == receipt.intent.candidate.new_generation != flow.store.generation
    assert restored.read(summaries) == selected.records != before
    assert restored.read(lambda db: tuple(db.scalars(select(Lead.id)))) == (earlier.lead_id,)
    assert [row["lead_id"] for row in flow.rows()] == [earlier.lead_id]
    assert flow.publication()["store_generation"] == restored.generation
    assert receipt.intent.absent_post_backup_authority == "unknown"
    prior = backup.service.files.manifest(receipt.intent.previous.backup_id)
    preserved = open_store(
        backup.service.files.path(prior.backup_id, "sqlite3"), boundary=flow.store.boundary
    )
    assert preserved.read(summaries) == before
    assert later.lead_id in preserved.read(lambda db: tuple(db.scalars(select(Lead.id))))
    assert not maintenance_paths(flow.store.path, boundary=flow.store.boundary).intent_path.exists()
    assert backup.service.files.pinned(prior.backup_id)
    assert not backup.service.files.pinned(selected.backup_id)
    assert receipt.prior_evidence == "held_pending_reconciliation"
    with pytest.raises(StoreError):
        flow.store.read(summaries)  # Old accepted Store cannot read the replacement.
    with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
        flow.leads.sessions.context()  # Actual old cookie and CSRF remain invalid.


def test_idle_shared_pin_prevents_restore_before_any_marker_or_backup(
    backup: BackupHarness,
) -> None:
    flow = backup.retention.projection
    selected = backup.service.create()
    before = backup.service.files.catalogue(), backup.retention.facts()
    with (
        shared_store_lease(flow.store.path, boundary=flow.store.boundary),
        pytest.raises(MaintenanceError),
    ):
        service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    assert (backup.service.files.catalogue(), backup.retention.facts()) == before
    assert not maintenance_paths(flow.store.path, boundary=flow.store.boundary).intent_path.exists()


def test_inflight_store_unit_excludes_restore_until_connection_disposal(
    backup: BackupHarness,
) -> None:
    flow = backup.retention.projection
    selected = backup.service.create()
    entered, release = Event(), Event()

    def hold() -> None:
        def read(db: Session) -> None:
            entered.set()
            assert release.wait(timeout=10)

        flow.store.read(read)

    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(hold)
        try:
            assert entered.wait(timeout=5)
            with pytest.raises(MaintenanceError):
                service_for(backup).restore(
                    selected.backup_id, expected_generation=flow.store.generation
                )
        finally:
            release.set()
        pending.result(timeout=5)
    assert (
        service_for(backup)
        .restore(selected.backup_id, expected_generation=flow.store.generation)
        .state
        == "restored"
    )


def test_expected_generation_mismatch_does_not_touch_canonical(backup: BackupHarness) -> None:
    selected = backup.service.create()
    before = backup.retention.facts(), backup.service.files.catalogue()
    with pytest.raises(BackupError, match="RESTORE_EXPECTED_GENERATION_CHANGED"):
        service_for(backup).restore(selected.backup_id, expected_generation=str(uuid4()))
    assert (backup.retention.facts(), backup.service.files.catalogue()) == before
    assert service_for(backup).inspect() is None


def test_completed_marker_before_swap_recovers_only_original_operation(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = backup.retention.projection
    flow.save()
    selected = backup.service.create()
    service = service_for(backup)
    continuation = service._continue

    def interrupt(*args: object) -> None:
        raise SimulatedInterruption("after complete marker before first continuation")

    monkeypatch.setattr(service, "_continue", interrupt)
    with pytest.raises(SimulatedInterruption):
        service.restore(selected.backup_id, expected_generation=flow.store.generation)
    intent = service.inspect()
    assert intent is not None
    assert backup.service.files.pinned(intent.previous.backup_id)
    with pytest.raises((StoreError, MaintenanceError)):
        open_store(flow.store.path, boundary=flow.store.boundary)
    with pytest.raises(BackupError, match="RESTORE_ID_CHANGED"):
        service.resume(restore_id=str(uuid4()))
    monkeypatch.setattr(service, "_continue", continuation)
    assert service.resume(restore_id=intent.restore_id).intent == intent
    assert service.inspect() is None


def test_actual_windows_swap_refusal_keeps_marker_and_preserved_backup(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = backup.retention.projection
    flow.save()
    selected = backup.service.create()
    original_replace = os.replace
    canonical = flow.store.path.resolve()

    def denied(source: Path, target: Path) -> None:
        if target == canonical:
            with deny_replacement(target):
                original_replace(source, target)
        else:
            original_replace(source, target)

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(OSError):
        service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    intent = service_for(backup).inspect()
    assert intent is not None
    assert backup.service.files.manifest(intent.previous.backup_id) == intent.previous
    assert backup.service.files.path(intent.candidate.candidate_id, "sqlite3").exists()
    with pytest.raises((StoreError, MaintenanceError)):
        flow.store.read(summaries)
    monkeypatch.setattr(os, "replace", original_replace)
    assert service_for(backup).resume().state == "restored"


def test_interruption_after_atomic_swap_resumes_existing_new_generation(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = backup.retention.projection
    flow.save()
    selected = backup.service.create()
    original_replace = os.replace
    canonical = flow.store.path.resolve()

    def replaced_then_interrupted(source: Path, target: Path) -> None:
        original_replace(source, target)
        if target == canonical:
            raise SimulatedInterruption("after actual canonical replacement")

    monkeypatch.setattr(os, "replace", replaced_then_interrupted)
    with pytest.raises(SimulatedInterruption):
        service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    intent = service_for(backup).inspect()
    assert intent is not None
    assert not backup.service.files.path(intent.candidate.candidate_id, "sqlite3").exists()
    with pytest.raises((StoreError, MaintenanceError)):
        open_store(flow.store.path, boundary=flow.store.boundary)
    monkeypatch.setattr(os, "replace", original_replace)
    result = service_for(backup).resume()
    assert result.intent.candidate.new_generation == intent.candidate.new_generation
    assert (
        open_store(flow.store.path, boundary=flow.store.boundary).read(summaries)
        == selected.records
    )


def test_interruption_after_actual_csv_ack_resumes_without_fresh_generation(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = backup.retention.projection
    flow.save()
    selected = backup.service.create()
    original = CsvProjector.repair_locked

    def acknowledged_then_interrupted(
        self: CsvProjector, files: ProjectionFiles, *, reconcile_from_generation: str | None = None
    ) -> None:
        assert (
            original(self, files, reconcile_from_generation=reconcile_from_generation).state
            == "current"
        )
        raise SimulatedInterruption("after actual CSV acknowledgement")

    monkeypatch.setattr(CsvProjector, "repair_locked", acknowledged_then_interrupted)
    with pytest.raises(SimulatedInterruption):
        service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    intent = service_for(backup).inspect()
    assert intent is not None
    assert flow.publication()["store_generation"] == intent.candidate.new_generation
    monkeypatch.setattr(CsvProjector, "repair_locked", original)
    assert service_for(backup).resume().intent == intent


def test_unresolved_restore_pins_survive_seven_day_expiry_and_resume(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = backup.retention.projection
    flow.save()
    flow.leads.sessions.clock.value += timedelta(days=89)
    selected = backup.service.create()
    service = service_for(backup)
    continuation = service._continue

    def interrupt(*args: object) -> None:
        raise SimulatedInterruption()

    monkeypatch.setattr(service, "_continue", interrupt)
    with pytest.raises(SimulatedInterruption):
        service.restore(selected.backup_id, expected_generation=flow.store.generation)
    intent = service.inspect()
    assert intent is not None
    flow.leads.sessions.clock.value += timedelta(days=7)
    plan = backup.service.inspect_expiry()
    assert set(plan.protected) == {selected.backup_id, intent.previous.backup_id}
    assert plan.eligible == ()
    assert backup.service.apply_expiry(plan) == ()
    monkeypatch.setattr(service, "_continue", continuation)
    receipt = service.resume()
    assert isinstance(receipt.intent, RestoreIntentV2)
    assert receipt.intent.restore_id == intent.restore_id
    assert receipt.intent.selected == intent.selected
    assert receipt.intent.previous == intent.previous
    assert receipt.intent.candidate.new_generation == intent.candidate.new_generation
    assert receipt.intent.candidate.prepared_at == intent.candidate.prepared_at
    assert receipt.intent.candidate.candidate_id != intent.candidate.candidate_id
    assert receipt.intent.revision == 1 and len(receipt.intent.retention_steps) == 1
    assert receipt.intent.retention_steps[0].protected_expired_leads == 0
    current = open_store(flow.store.path, boundary=flow.store.boundary)
    assert current.read(lambda db: db.scalar(select(func.count()).select_from(Lead))) == 0
    assert (
        current.read(lambda db: db.scalar(select(StoreMetadata.restored_at)))
        == intent.candidate.prepared_at
    )
    assert flow.rows() == []
    assert not backup.service.files.pinned(selected.backup_id)
    assert backup.service.files.pinned(intent.previous.backup_id)


def test_unrecognized_generation_never_triggers_guessed_rollback(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = backup.retention.projection
    selected = backup.service.create()
    service = service_for(backup)
    continuation = service._continue

    def interrupt(*args: object) -> None:
        raise SimulatedInterruption()

    monkeypatch.setattr(service, "_continue", interrupt)
    with pytest.raises(SimulatedInterruption):
        service.restore(selected.backup_id, expected_generation=flow.store.generation)
    with (
        flow.files.lock(),
        exclusive_store_lease(flow.store.path, boundary=flow.store.boundary) as lease,
    ):
        files = RestoreFiles(flow.store.path, boundary=flow.store.boundary, lease=lease)
        pending = files.marker()
        assert pending is not None
        current = open_store(flow.store.path, boundary=flow.store.boundary)

        def alter(db: Session) -> None:
            metadata = db.get(StoreMetadata, 1)
            assert metadata is not None
            metadata.store_generation = str(uuid4())

        current.write(alter)
    monkeypatch.setattr(service, "_continue", continuation)
    with pytest.raises(BackupError, match="RESTORE_DISK_STATE_UNKNOWN"):
        service.resume()
    assert service.inspect() == pending
    assert backup.service.files.manifest(pending.previous.backup_id) == pending.previous


def test_modified_business_content_after_swap_is_unknown_and_keeps_marker(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = backup.retention.projection
    saved = flow.save()
    selected = backup.service.create()
    finish = RestoreFiles.finish

    def interrupt(self: RestoreFiles, value: object) -> None:
        raise SimulatedInterruption("after actual CSV publication before completion")

    monkeypatch.setattr(RestoreFiles, "finish", interrupt)
    with pytest.raises(SimulatedInterruption):
        service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    pending = service_for(backup).inspect()
    assert pending is not None
    flow.leads.sessions.clock.value += timedelta(days=91)
    # Late expiry must not turn content that differs from the recorded target
    # into an authorized retention input. Identity is checked before cleanup.
    with flow.files.lock(), exclusive_store_lease(flow.store.path, boundary=flow.store.boundary):
        current = open_store(flow.store.path, boundary=flow.store.boundary)
        identity_before = current.read(summaries)

        def alter(db: Session) -> None:
            lead = db.get(Lead, saved.lead_id)
            assert lead is not None
            lead.values_json = {
                **lead.values_json,
                "requirements": ["Changed content with identical record keys"],
            }

        current.write(alter)
        assert current.read(summaries) == identity_before
    monkeypatch.setattr(RestoreFiles, "finish", finish)
    with pytest.raises(BackupError, match="RESTORE_CANONICAL_CONTENT_CHANGED"):
        service_for(backup).resume()
    assert service_for(backup).inspect() == pending
    assert backup.service.files.pinned(pending.previous.backup_id)
    with pytest.raises((StoreError, MaintenanceError)):
        open_store(flow.store.path, boundary=flow.store.boundary)


def test_original_lost_response_key_stays_unknown_after_older_restore_and_keeps_evidence(
    backup: BackupHarness,
) -> None:
    # The fixture supplied an isolated runtime boundary. This is another real
    # Store in that boundary with actual T7 domain participants, synthetic Inventory.
    flow = make_confirmation_harness()
    base = flow.drafts.base

    def align(db: Session) -> None:
        metadata = db.get(StoreMetadata, 1)
        assert metadata is not None
        metadata.created_at = utc_text(base.clock.value)

    base.store.write(align)
    backups = BackupService(base.store, clock=base.clock.now)
    retained_draft = flow.create()
    retained = flow.commit(retained_draft, flow.prepare(retained_draft))
    selected = backups.create()
    draft = flow.create(minutes=60)
    original_context = base.context()
    original_owner_id = base.auth.read(original_context, lambda unit: unit.owner_id)
    prepared = flow.prepare(draft)
    committed_effects: list[ConfirmationEffect] = []

    def submit_then_lose_response() -> None:
        committed_effects.append(flow.commit(draft, prepared))
        # Explicit synthetic transport loss AFTER the real canonical commit.
        raise SimulatedInterruption("original response was not delivered")

    with pytest.raises(SimulatedInterruption):
        submit_then_lose_response()
    assert len(committed_effects) == 1
    committed = committed_effects[0]
    assert draft.review is not None
    original_command = confirmation(draft)
    original_bytes = original_command.model_dump(mode="json")
    original_key = original_command.operation_key
    service = RestoreService(base.store.path, boundary=base.store.boundary, clock=base.clock.now)
    completed = service.restore(selected.backup_id, expected_generation=base.store.generation)
    restored = open_store(base.store.path, boundary=base.store.boundary)
    assert restored.read(summaries) == selected.records
    assert (
        restored.read(
            lambda db: db.scalar(
                select(OperationOutcome.id).where(OperationOutcome.operation_key == original_key)
            )
        )
        is None
    )
    assert completed.intent.absent_post_backup_authority == "unknown"
    assert completed.prior_evidence == "held_pending_reconciliation"

    # Restore intentionally invalidates the old browser's credential and issued
    # authorization context. Do not mint a fake restored-owner capability or use a
    # display name as recovery. Explicit bootstrap creates two genuinely new owners.
    with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
        base.context()
    with pytest.raises(StoreError, match="STORE_GENERATION_CHANGED"):
        flow.participant.status(
            original_context,
            operation_key=original_key,
            submitted_generation=original_command.store_generation,
        )
    contexts = []
    owner_ids = []
    for _ in range(2):
        created = base.auth.identity.bootstrap(
            IdentityBootstrapRequest.model_validate(
                {
                    "notice_version": "DEMO-POLICY-1",
                    "notice_acknowledged": True,
                    "display_name": "Synthetic same name",
                }
            ),
            None,
        )
        assert created.cookie is not None
        context = base.auth.authorize_write(
            decode_token(created.cookie), created.identity.context_id, created.identity.csrf_token
        )
        assert context.generation == restored.generation
        owner_id = base.auth.read(context, lambda unit: unit.owner_id)
        assert owner_id != original_owner_id
        contexts.append(context)
        owner_ids.append(owner_id)
    assert owner_ids[0] != owner_ids[1]

    def effects(db: Session) -> tuple[int, ...]:
        return tuple(
            db.scalar(select(func.count()).select_from(model)) or 0
            for model in (Booking, OperationOutcome, Lead, LeadBooking, ExportIntent)
        )

    before_retry = restored.read(effects)
    for context in contexts:
        status = flow.participant.status(
            context,
            operation_key=original_key,
            submitted_generation=original_command.store_generation,
        )
        assert isinstance(status, OperationGenerationUnresolved)
        assert status.operation_key == original_key and status.definitive_noncommit is False
        assert status.submitted_store_generation == original_command.store_generation
        assert status.observed_store_generation == restored.generation
        with pytest.raises(ApiFailure, match="STORE_GENERATION_CHANGED"):
            base.auth.write(
                context,
                lambda unit: flow.participant.apply_in_unit(
                    unit,
                    draft_id=draft.draft_id,
                    command=original_command,
                    generation=restored.generation,
                    now=utc_text(base.clock.value),
                    prepared=None,
                ),
            )
        # This draft DOES survive in the selected backup. Another owner cannot
        # reveal it using its copied locator; generic uncertainty reveals no receipt.
        with pytest.raises(ApiFailure, match="NOT_FOUND"):
            flow.drafts.service.get(context, retained_draft.draft_id)
        retained_status = flow.participant.status(
            context,
            operation_key=confirmation(retained_draft).operation_key,
            submitted_generation=original_command.store_generation,
        )
        assert isinstance(retained_status, OperationGenerationUnresolved)
        assert retained_status.model_dump(mode="json") != retained.terminal.model_dump(mode="json")
    assert restored.read(effects) == before_retry
    assert original_command.model_dump(mode="json") == original_bytes

    prior_id = completed.intent.previous.backup_id
    base.clock.value += timedelta(days=7)
    expiry = backups.inspect_expiry()
    assert prior_id in expiry.protected and selected.backup_id in expiry.eligible
    assert backups.apply_expiry(expiry) == (selected.backup_id,)
    prior = open_store(backups.files.path(prior_id, "sqlite3"), boundary=base.store.boundary)
    preserved = prior.read(
        lambda db: db.scalar(
            select(OperationOutcome.terminal_result_json).where(
                OperationOutcome.operation_key == original_key
            )
        )
    )
    assert preserved == committed.terminal.model_dump(mode="json")
    assert prior.read(lambda db: tuple(db.scalars(select(Booking.id))))
    assert backups.files.pinned(prior_id)
