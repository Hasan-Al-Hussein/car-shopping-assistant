"""Actual restore/Inventory/I9/composition source cases. NOT_COLLECTED / NOT_RUN."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.common import InventoryRef
from app.api.schemas.identity import IdentityBootstrapRequest
from app.api.schemas.operations import OperationSucceeded
from app.api.schemas.sessions import SessionCreateRequest
from app.api.schemas.viewings import AppointmentSelection, BookingDraftCreate, ViewingOptionsRequest
from app.core.config import load_settings
from app.core.readiness import InventoryObservation
from app.database.maintenance import MaintenanceError, exclusive_store_lease
from app.database.models import ActiveInventory, Booking, ExportState
from app.database.store import Store, open_store
from app.identity.credentials import decode_token
from app.inventory.snapshots import InventoryRepository
from app.leads.projection_files import CSV_NAME, ProjectionFiles
from app.operations import restored_readmission as coordinator
from app.operations.backup_files import BackupFiles
from app.operations.backup_restore import BackupService
from app.operations.restore_completion import completed_restore_scope
from app.operations.restore_files import encoded
from app.operations.restore_operator import RestoreService
from app.operations.restored_bundle_contract import ADOPTED_SNAPSHOT, RESTORED_BUNDLE_ROOT
from app.operations.restored_readmission import (
    ReadmissionError,
    ReadmissionRequest,
    ReadmissionResult,
    readmitted_runtime,
    run_readmission,
)
from app.operations.viewing_configuration import (
    ActivationRequest,
    ActivationResult,
    ViewingConfigurationOperator,
)
from app.runtime_app import build_composition
from tests.operations.activation_cases import ActivationCase, business_state
from tests.platform.test_identity import ACK
from tests.support.harness import runtime_environment
from tests.transactions.draft_fixtures import confirmation


class LostReturn(BaseException):
    """Labelled transport interruption AFTER a real effect; no rollback assertion."""


@dataclass(frozen=True)
class Case:
    store: Store
    project: Path
    request: ReadmissionRequest
    receipt_path: Path

    @property
    def records(self) -> Path:
        return self.project / "Records/operations/restored-readmission" / self.request.operation_id

    def run(self) -> ReadmissionResult:
        return run_readmission(
            str(self.store.path),
            boundary=self.store.boundary,
            project_root=self.project,
            request=self.request,
        )


@pytest.fixture
def case(activation_case: ActivationCase) -> Case:
    original = activation_case.store
    selected = BackupService(original).create()
    receipt = RestoreService(original.path, boundary=original.boundary).restore(
        selected.backup_id,
        expected_generation=original.generation,
    )
    assert receipt.format == "store-restore-receipt-2"
    store = open_store(original.path, boundary=original.boundary)
    active = InventoryRepository(store).active()
    assert active.stage is None and active.observation.active_revision == 0
    files = BackupFiles(store)
    path = files.directory(create=False) / f"restore.{receipt.intent.restore_id}.receipt.json"
    raw = path.read_bytes()
    assert raw == encoded(receipt)
    return Case(
        store,
        activation_case.project,
        ReadmissionRequest(
            operation_id=activation_case.request.operation_id,
            restore_id=receipt.intent.restore_id,
            restore_receipt_sha256=hashlib.sha256(raw).hexdigest(),
            expected_generation=store.generation,
        ),
        path,
    )


def test_actual_v2_observer_and_complete_readmission_keep_original_commands(
    case: Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_activate = ViewingConfigurationOperator.activate
    seen: list[ActivationRequest] = []

    def activate(
        operator: ViewingConfigurationOperator, request: ActivationRequest
    ) -> ActivationResult:
        # A complete original command is durable BEFORE its actual I9 effect.
        retained = coordinator._RetainedActivation.model_validate_json(
            (case.records / "activation-request.json").read_bytes()
        )
        assert retained.activation == request
        assert retained.original.request == case.request
        seen.append(request)
        return actual_activate(operator, request)

    monkeypatch.setattr(ViewingConfigurationOperator, "activate", activate)
    before = business_state(case.store)
    receipt_bytes = case.receipt_path.read_bytes()
    with completed_restore_scope(
        case.store.path,
        boundary=case.store.boundary,
        restore_id=case.request.restore_id,
        expected_receipt_sha256=case.request.restore_receipt_sha256,
        expected_generation=case.store.generation,
    ) as scope:
        assert scope.observation.receipt_format == "store-restore-receipt-2"
    result = case.run()
    assert result.inventory_action == "activated_return_observed"
    assert result.original_inventory_commit == "not_proven_by_pointer_observation"
    assert result.inventory is not None and result.inventory.snapshot_id == ADOPTED_SNAPSHOT
    assert result.inventory.active_revision == 1
    assert result.viewing.result is not None and result.viewing.result.request == seen[0]
    assert seen[0].operation_id == case.request.operation_id
    assert result.current_csv is not None and result.current_csv.projection == "current"
    assert result.current_viewing.state == "ready"
    assert result.application_launch == "not_performed"
    assert case.receipt_path.read_bytes() == receipt_bytes
    assert business_state(case.store) == before


def test_lost_inventory_return_reobserves_pointer_without_inventing_commit(
    case: Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = InventoryRepository.activate

    def activate(
        repository: InventoryRepository, snapshot_id: str, *, expected_revision: int
    ) -> InventoryObservation:
        assert (case.records / "request.json").is_file()
        original(repository, snapshot_id, expected_revision=expected_revision)
        raise LostReturn("actual Inventory activation committed; return lost")

    monkeypatch.setattr(InventoryRepository, "activate", activate)
    with pytest.raises(LostReturn):
        case.run()
    retained = (case.records / "request.json").read_bytes()
    monkeypatch.setattr(InventoryRepository, "activate", original)
    result = case.run()
    assert result.inventory_action == "existing_pointer_observed"
    assert result.original_inventory_commit == "not_proven_by_pointer_observation"
    assert result.viewing.result is not None
    assert result.viewing.result.request.operation_id == case.request.operation_id
    assert (case.records / "request.json").read_bytes() == retained


def test_lost_i9_return_reconciles_event_before_producer_or_bundle_reload(
    case: Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = ViewingConfigurationOperator.activate
    committed: list[ActivationResult] = []

    def activate(
        operator: ViewingConfigurationOperator, request: ActivationRequest
    ) -> ActivationResult:
        committed.append(original(operator, request))
        raise LostReturn("actual I9 event committed; return lost")

    monkeypatch.setattr(ViewingConfigurationOperator, "activate", activate)
    with pytest.raises(LostReturn):
        case.run()
    original_command = (case.records / "activation-request.json").read_bytes()
    bundle = case.project / (RESTORED_BUNDLE_ROOT + case.request.operation_id)
    config = bundle / "pending-viewing-configuration.json"
    config.rename(bundle / "retained-config-evidence.json")

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("original known event must precede producer/bundle reload")

    monkeypatch.setattr(coordinator, "produce_restored_inventory_bundle", forbidden)
    result = case.run()
    assert result.inventory_action == "not_attempted"
    assert result.viewing.result == committed[0]
    assert (case.records / "activation-request.json").read_bytes() == original_command


def test_known_i9_result_survives_unavailable_historical_restore_observation(case: Case) -> None:
    result = case.run()
    case.receipt_path.rename(case.receipt_path.with_suffix(".keep"))
    replay = case.run()
    assert replay.viewing.result == result.viewing.result
    assert replay.current_csv is None
    assert replay.application_launch == "not_performed"


def test_original_i9_result_is_separate_from_later_incompatible_inventory(case: Case) -> None:
    result = case.run()

    def change(db: Session) -> None:
        # Deliberate later-state adverse fixture in the actual Store, not an
        # invented producer result or a claim of another adopted activation.
        active = db.get(ActiveInventory, 1)
        assert active is not None
        active.revision += 1

    case.store.write(change)
    replay = case.run()
    assert replay.viewing == result.viewing  # Original event and rules pointer remain.
    assert replay.inventory is not None and replay.inventory.active_revision == 2
    assert replay.current_viewing.state == "unavailable"
    assert replay.current_csv is not None and replay.current_csv.projection == "current"


def test_partial_retained_request_is_preserved_before_any_activation(case: Case) -> None:
    case.records.mkdir(parents=True, exist_ok=False)
    path = case.records / "request.json"
    path.write_bytes(b'{"format":')  # Explicit partial-write adverse fixture.
    with pytest.raises(ReadmissionError, match="READMISSION_ORIGINAL_REQUEST_CHANGED"):
        case.run()
    assert path.read_bytes() == b'{"format":'
    assert InventoryRepository(case.store).active().observation.active_revision == 0


def test_missing_actual_csv_blocks_before_inventory_activation(case: Case) -> None:
    publication = ProjectionFiles(case.store)
    with publication.lock():
        path = publication.path(CSV_NAME)
        path.rename(path.with_suffix(".retained-evidence"))
    with pytest.raises(ReadmissionError, match="READMISSION_CSV_REQUIRED"):
        case.run()
    assert InventoryRepository(case.store).active().observation.active_revision == 0
    assert not case.records.exists()


def test_fresh_composition_admits_actual_inventory_viewing_and_csv_then_settles(case: Case) -> None:
    settings = load_settings(
        {
            **runtime_environment(case.store.boundary),
            "CSA_STORE_PATH": str(case.store.path),
            "CSA_ASSISTANT_ENABLED": "false",
        }
    )
    before = {
        name: rows
        for name, rows in business_state(case.store).items()
        if name not in {"export_state", "export_intents"}
    }
    with readmitted_runtime(settings, project_root=case.project, request=case.request) as (
        app,
        result,
    ):
        assert app.store.generation == case.store.generation
        assert app.admit_inventory() == result.inventory
        assert app.projector.capability().state == "ready"
        actual_export = app.store.read(
            lambda db: tuple(
                db.execute(
                    select(
                        ExportState.store_generation,
                        ExportState.canonical_version,
                        ExportState.exported_version,
                        ExportState.state,
                    )
                ).one()
            )
        )
        assert actual_export == (case.store.generation, 0, 0, "current")
        assert result.viewing.result is not None
        with (
            pytest.raises(MaintenanceError),
            exclusive_store_lease(case.store.path, boundary=case.store.boundary),
        ):
            pytest.fail("live fresh composition must exclude restore")
    with exclusive_store_lease(case.store.path, boundary=case.store.boundary) as lease:
        lease.assert_held(case.store.path, boundary=case.store.boundary)
    assert {
        name: rows
        for name, rows in business_state(case.store).items()
        if name not in {"export_state", "export_intents"}
    } == before


def test_actual_confirmed_booking_still_occupies_global_capacity_after_readmission(
    activation_case: ActivationCase,
) -> None:
    # Initial adoption uses the existing labelled I9 fixture. Booking, backup,
    # restore, new bundle, I9 re-admission and fresh options are actual services.
    setup = activation_case
    setup.operator().activate(setup.request)
    settings = load_settings(
        {
            **runtime_environment(setup.store.boundary),
            "CSA_STORE_PATH": str(setup.store.path),
            "CSA_ASSISTANT_ENABLED": "false",
        }
    )
    before = build_composition(settings, setup.store)
    ref = InventoryRef.model_validate(setup.config.eligibility.eligible_refs[0].model_dump())
    request = ViewingOptionsRequest(
        ref=ref,
        from_date=(datetime.now(UTC).date() + timedelta(days=1)).isoformat(),
        days=7,
    )
    try:
        before.admit_inventory()
        identity = before.identity.bootstrap(IdentityBootstrapRequest.model_validate(ACK), None)
        assert identity.cookie is not None
        owner = before.authorization.authorize_write(
            decode_token(identity.cookie),
            identity.identity.context_id,
            identity.identity.csrf_token,
        )
        session = before.sessions.create(owner, SessionCreateRequest(client_action_id=str(uuid4())))
        options = before.viewing_options.options(request)
        assert options.state == "available"
        slot = options.slots[0]
        draft = before.drafts.create(
            owner,
            BookingDraftCreate(
                client_action_id=str(uuid4()),
                session_id=session.session_id,
                expected_session_revision=session.revision,
                ref=ref,
                appointment=AppointmentSelection(starts_at_utc=slot.starts_at_utc),
            ),
        )
        terminal = before.viewing.confirm(owner, draft.draft_id, confirmation(draft))
        assert isinstance(terminal, OperationSucceeded)
        assert terminal.csv.state == "current"
    finally:
        assert before.close()
    original_booking = setup.store.read(
        lambda db: db.scalar(
            select(Booking.immutable_receipt_json).where(Booking.id == terminal.booking.booking_id)
        )
    )
    selected = BackupService(setup.store).create()
    receipt = RestoreService(setup.store.path, boundary=setup.store.boundary).restore(
        selected.backup_id,
        expected_generation=setup.store.generation,
    )
    restored = open_store(setup.store.path, boundary=setup.store.boundary)
    files = BackupFiles(restored)
    receipt_path = (
        files.directory(create=False) / f"restore.{receipt.intent.restore_id}.receipt.json"
    )
    admission = ReadmissionRequest(
        operation_id=str(uuid4()),
        restore_id=receipt.intent.restore_id,
        restore_receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        expected_generation=restored.generation,
    )
    with readmitted_runtime(settings, project_root=setup.project, request=admission) as (fresh, _):
        available = fresh.viewing_options.options(request)
        assert available.state == "available"
        assert slot.starts_at_utc not in {item.starts_at_utc for item in available.slots}
        assert (
            fresh.store.read(
                lambda db: db.scalar(
                    select(Booking.immutable_receipt_json).where(
                        Booking.id == terminal.booking.booking_id
                    )
                )
            )
            == original_booking
        )
