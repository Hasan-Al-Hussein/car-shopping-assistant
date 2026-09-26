"""Owned child for test_projection_restart; never used by application entrypoints."""

import csv
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.operations import OperationSucceeded
from app.api.schemas.viewings import ConfirmRequest
from app.core.config import load_settings
from app.database.models import (
    Booking,
    BookingDraft,
    BookingReview,
    ConversationSession,
    ExportIntent,
    Lead,
    LeadBooking,
    OperationOutcome,
)
from app.database.paths import RuntimeBoundary, initialize_runtime_root
from app.database.store import Store, open_store
from app.identity.authorization import AuthorizationService
from app.identity.credentials import decode_token
from app.identity.service import IdentityService
from app.leads.participant import LeadParticipant
from app.leads.projection import CsvProjector
from app.leads.projection_files import CSV_NAME, MANIFEST_NAME, PENDING_NAME, ProjectionFiles
from app.viewings.application import ViewingApplication
from app.viewings.confirmation import ConfirmationParticipant
from app.viewings.drafts import DraftService
from tests.support.harness import configured_runtime_boundary, runtime_environment
from tests.transactions.confirmation_fixtures import make_confirmation_harness
from tests.transactions.draft_fixtures import confirmation

CRASH_EXIT_CODE = 73
COUNTED = (Booking, OperationOutcome, Lead, LeadBooking, ExportIntent)
CANONICAL = (
    Booking, Lead, LeadBooking, OperationOutcome, BookingDraft, BookingReview,
    ConversationSession,
)


def counts(store: Store) -> list[int]:
    return store.read(lambda db: [
        db.scalar(select(func.count()).select_from(model)) or 0 for model in COUNTED
    ])


def canonical(store: Store) -> dict[str, list[dict[str, Any]]]:
    def read(db: Session) -> dict[str, list[dict[str, Any]]]:
        return {
            model.__tablename__: [dict(row) for row in db.execute(
                select(model.__table__).order_by(*model.__table__.primary_key)
            ).mappings()]
            for model in CANONICAL
        }
    return store.read(read)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True), flush=True)


def commit_and_crash() -> None:
    boundary = configured_runtime_boundary()
    assert boundary.logical_root == boundary.physical_root
    root = boundary.physical_root
    # Bound the existing native CSV fixture spelling; no production path exemption.
    longest_csv_leaf = "leads.00000000-0000-4000-8000-000000000000.json.tmp"
    assert len(str(root / "exports" / longest_csv_leaf)) <= 259
    initialize_runtime_root(RuntimeBoundary(root.parent, root.parent))
    root.mkdir(exist_ok=False)
    initialize_runtime_root(boundary)
    flow = make_confirmation_harness()
    draft = flow.create()
    accepted = flow.commit(draft, flow.prepare(draft))
    assert isinstance(accepted.terminal, OperationSucceeded)
    base = flow.drafts.base
    assert counts(base.store) == [1, 1, 1, 1, 1]
    payload: dict[str, Any] = {
        "phase": "committed-csv-replaced-before-manifest",
        "synthetic_only": True,
        "pid": os.getpid(),
        "store": str(base.settings.store_path),
        "generation": base.store.generation,
        "clock": base.clock.value.isoformat(),
        "draft_id": draft.draft_id,
        "command": confirmation(draft).model_dump(mode="json"),
        "terminal": accepted.terminal.model_dump(mode="json"),
        "counts": counts(base.store),
        "canonical": canonical(base.store),
        "cookie": base.buyers[0].cookie,
        "context_id": base.buyers[0].identity.context_id,
        "csrf_token": base.buyers[0].identity.csrf_token,
    }
    files = ProjectionFiles(base.store)
    projector = CsvProjector(base.store, clock=base.clock.now)
    original_replace = os.replace

    def interrupt(source: Path | str, destination: Path | str) -> None:
        if Path(destination).name == MANIFEST_NAME:
            assert files.path(CSV_NAME).exists()
            assert files.path(PENDING_NAME).exists()
            assert not files.path(MANIFEST_NAME).exists()
            emit(payload)
            # Actual process exit: no Python finally, lock release or Store object reuse.
            # The next interpreter must recover the pending pair and reacquire OS locks.
            os._exit(CRASH_EXIT_CODE)
        original_replace(source, destination)

    with pytest.MonkeyPatch.context() as fault:
        fault.setattr(os, "replace", interrupt)
        projector.repair_once()
    raise AssertionError("Expected publication boundary was not reached")


def recover(payload: dict[str, Any]) -> None:
    boundary = configured_runtime_boundary()
    path = Path(payload["store"])
    assert path.is_relative_to(boundary.logical_root / "test-stores")
    store = open_store(path, boundary=boundary)
    assert store.generation == payload["generation"]
    clock = datetime.fromisoformat(payload["clock"])
    settings = load_settings({**runtime_environment(boundary), "CSA_STORE_PATH": str(path)})
    identity = IdentityService(settings, clock=lambda: clock)
    authorization = AuthorizationService(identity)
    context = authorization.authorize_write(
        decode_token(payload["cookie"]), payload["context_id"], payload["csrf_token"]
    )
    # No fresh Inventory adapter is supplied: successful original-key replay cannot
    # conceal preparing a replacement action after restart.
    participant = ConfirmationParticipant(DraftService(authorization), leads=LeadParticipant())
    projector = CsvProjector(store, clock=lambda: clock)
    application = ViewingApplication(participant, projector=projector)
    files = ProjectionFiles(store)
    expected = OperationSucceeded.model_validate(payload["terminal"])
    command = ConfirmRequest.model_validate(payload["command"])
    assert command.operation_key == expected.operation_key
    assert canonical(store) == payload["canonical"]
    assert counts(store) == payload["counts"] == [1, 1, 1, 1, 1]
    pending = files.manifest(PENDING_NAME)
    assert pending is not None and pending.store_generation == store.generation
    assert pending.projection_version == 1
    assert files.path(CSV_NAME).exists() and not files.path(MANIFEST_NAME).exists()
    initial_bytes = store.path.read_bytes()
    observed = application.status(context, command.operation_key, command.store_generation)
    assert isinstance(observed, OperationSucceeded)
    assert observed.model_dump(exclude={"csv"}) == expected.model_dump(exclude={"csv"})
    assert observed.csv.state == "pending"
    assert store.path.read_bytes() == initial_bytes
    repaired = projector.repair_once()
    assert (repaired.state, repaired.canonical_version, repaired.published_version) == (
        "current", 1, 1
    )
    manifest = files.manifest(MANIFEST_NAME)
    assert manifest is not None and files.verified(manifest)
    assert manifest.store_generation == store.generation and manifest.projection_version == 1
    assert manifest.row_count == 1 and not files.path(PENDING_NAME).exists()
    csv_bytes = files.path(CSV_NAME).read_bytes()
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["lead_id"] == expected.lead.lead_id
    assert json.loads(rows[0]["booking_ids_json"]) == [expected.booking.booking_id]
    assert rows[0]["stage"] == "viewing_confirmed"
    before_status = store.path.read_bytes()
    final = application.status(context, command.operation_key, command.store_generation)
    assert isinstance(final, OperationSucceeded) and final.csv.state == "current"
    assert final.model_dump(exclude={"csv"}) == expected.model_dump(exclude={"csv"})
    assert store.path.read_bytes() == before_status
    replay = application.confirm(context, payload["draft_id"], command)
    assert isinstance(replay, OperationSucceeded)
    assert replay.model_dump(exclude={"csv"}) == expected.model_dump(exclude={"csv"})
    assert replay.csv.state == "current"
    assert counts(store) == payload["counts"]
    assert canonical(store) == payload["canonical"]
    assert files.path(CSV_NAME).read_bytes() == csv_bytes
    assert files.manifest(MANIFEST_NAME) == manifest
    emit({
        "phase": "recovered-original-operation", "pid": os.getpid(),
        "generation": store.generation, "operation_key": expected.operation_key,
        "booking_id": expected.booking.booking_id, "lead_id": expected.lead.lead_id,
        "counts": counts(store), "canonical_unchanged": True, "csv_rows": len(rows),
        "projection_version": manifest.projection_version, "status_reads_unchanged": True,
    })


if __name__ == "__main__":
    assert len(sys.argv) == 2
    if sys.argv[1] == "commit-and-crash":
        commit_and_crash()
    else:
        assert sys.argv[1] == "recover"
        recover(json.loads(sys.stdin.read()))
