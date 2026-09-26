"""Focused real-file Windows publication/recovery tests. Authored, not executed.

Run only after coordinated portability/application and a finite runtime grant.
All faults are local synthetic injections except explicitly real Windows locks.
"""

import csv
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api.schemas.leads import ExportCurrent, ExportPending, LeadRecord
from app.api.schemas.operations import OperationSucceeded
from app.database.models import Booking, ExportIntent, ExportState, Lead, OperationOutcome
from app.database.store import Store, StoreError
from app.identity.service import utc_text
from app.leads import projection as publisher
from app.leads import projection_repository as repo
from app.leads.csv_serialization import CSV_COLUMNS
from app.leads.projection import (
    CsvProjector,
    ProjectionRun,
    constrain_observation,
    startup_admitted,
)
from app.leads.projection_files import (
    CSV_NAME,
    MANIFEST_NAME,
    PENDING_NAME,
    ProjectionFiles,
    PublicationManifest,
    manifest_bytes,
)
from tests.transactions.confirmation_fixtures import make_confirmation_harness
from tests.transactions.projection_fixtures import (
    ProjectionHarness,
    deny_replacement,
    make_projection_harness,
)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> ProjectionHarness:
    return make_projection_harness(monkeypatch)


def test_empty_store_does_not_invent_a_publication(harness: ProjectionHarness) -> None:
    result = harness.projector.repair_once()
    assert result.state == "empty" and startup_admitted(result)
    assert not harness.files.path(CSV_NAME).exists()


def test_actual_canonical_rows_unicode_formula_and_idempotence(harness: ProjectionHarness) -> None:
    first, second = harness.save(email="=buyer"), harness.save(1)
    before = harness.canonical_facts()
    result = harness.projector.repair_once()
    assert (result.state, result.canonical_version, result.published_version) == ("current", 2, 2)
    rows = harness.rows()
    assert len(rows) == 2 and tuple(rows[0]) == CSV_COLUMNS
    assert {row["lead_id"] for row in rows} == {first.lead_id, second.lead_id}
    row = next(row for row in rows if row["lead_id"] == first.lead_id)
    assert row["email_value"] == "'=buyer"
    assert "سيارة عائلية" in row["requirements_json"]
    assert row["booking_ids_json"] == "[]" and row["delivery_mode"] == "local_only"
    prior_bytes, prior_manifest = harness.files.path(CSV_NAME).read_bytes(), harness.publication()
    again = CsvProjector(harness.store, clock=harness.leads.sessions.clock.now).repair_once()
    assert again.state == "current"
    assert harness.files.path(CSV_NAME).read_bytes() == prior_bytes
    assert harness.publication() == prior_manifest
    assert harness.canonical_facts() == before
    assert harness.metadata() == ("current", 2, 2, ((1, "current"), (2, "current")))


def test_committed_confirmation_link_exports_without_rebooking(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The fixture supplies an isolated runtime; this second Store has never published.
    flow = make_confirmation_harness()
    draft = flow.create()
    accepted = flow.commit(draft, flow.prepare(draft))
    assert isinstance(accepted.terminal, OperationSucceeded)
    base = flow.drafts.base
    projector = CsvProjector(base.store, clock=base.clock.now)
    files = ProjectionFiles(base.store)
    counts = flow.counts()
    assert projector.repair_once().state == "current"
    assert projector.repair_once().state == "current"
    snapshot = base.store.read(lambda db: repo.capture(
        db, base.store.generation, utc_text(base.clock.now())
    ))
    assert snapshot is not None and len(snapshot.rows) == 1
    assert snapshot.rows[0].booking_ids == [accepted.terminal.booking.booking_id]
    rows = list(csv.DictReader(io.StringIO(files.path(CSV_NAME).read_text(encoding="utf-8-sig"))))
    assert json.loads(rows[0]["booking_ids_json"]) == [accepted.terminal.booking.booking_id]
    assert rows[0]["stage"] == "viewing_confirmed"

    def facts(db: Session) -> tuple[tuple[dict[str, Any], ...], ...]:
        return tuple(
            tuple(dict(row) for row in db.execute(select(model.__table__)).mappings())
            for model in (Lead, Booking, OperationOutcome)
        )

    before = base.store.read(facts)
    files.path(CSV_NAME).unlink()  # Current metadata must audit a missing actual CSV.

    def failed_write(*args: Any, **kwargs: Any) -> None:
        raise OSError("synthetic post-booking export failure")

    with monkeypatch.context() as fault:
        fault.setattr(ProjectionFiles, "_write", failed_write)
        assert projector.repair_once().state == "failed"
    assert base.store.read(facts) == before
    assert projector.repair_once().state == "current"
    replay = flow.commit(draft, None)
    assert replay.replayed and replay.terminal == accepted.terminal
    assert flow.counts() == counts


def test_publication_is_forbidden_inside_canonical_write(harness: ProjectionHarness) -> None:
    harness.save()
    with pytest.raises(StoreError):
        harness.store.write(lambda db: harness.projector.repair_once())
    assert not harness.files.root.exists()


@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_current_metadata_still_audits_actual_csv(
    harness: ProjectionHarness, fault: str
) -> None:
    harness.save()
    assert harness.projector.repair_once().state == "current"
    expected = harness.files.path(CSV_NAME).read_bytes()
    if fault == "missing":
        harness.files.path(CSV_NAME).unlink()
    else:
        harness.files.path(CSV_NAME).write_bytes(b"damaged")
    assert harness.projector.repair_once().state == "current"
    assert harness.files.path(CSV_NAME).read_bytes() == expected


def test_prelock_failure_never_exposes_old_current_status(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.save()
    assert harness.projector.repair_once().state == "current"
    before = harness.canonical_facts()

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("synthetic permission denial")

    with monkeypatch.context() as fault:
        fault.setattr(ProjectionFiles, "directory", denied)
        result = harness.projector.repair_once()
    assert result.state == "failed" and not result.status_persisted
    assert not startup_admitted(result)
    current = harness.leads.service.get(harness.leads.sessions.context(write=False))
    assert isinstance(current, LeadRecord) and current.csv.state == "current"
    assert constrain_observation(current.csv, result).state == "failed"
    assert harness.canonical_facts() == before
    assert harness.projector.repair_once().state == "current"


@pytest.mark.parametrize("name", [CSV_NAME, MANIFEST_NAME])
def test_real_windows_replace_lock_preserves_repairability(
    harness: ProjectionHarness, name: str
) -> None:
    harness.save()
    assert harness.projector.repair_once().state == "current"
    old = harness.files.path(CSV_NAME).read_bytes()
    harness.revise()
    before = harness.canonical_facts()
    with deny_replacement(harness.files.path(name)):
        failed = harness.projector.repair_once()
    assert failed.state == "failed" and failed.status_persisted
    assert harness.metadata()[0] == "failed"
    if name == CSV_NAME:
        assert harness.files.path(CSV_NAME).read_bytes() == old
    else:
        assert harness.files.path(PENDING_NAME).exists()
        assert harness.rows()[0]["lead_revision"] == "2"
    assert harness.canonical_facts() == before
    assert harness.projector.repair_once().state == "current"
    assert harness.rows()[0]["lead_revision"] == "2"


def test_disk_failure_retains_valid_file_and_outstanding_intent(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.save()
    assert harness.projector.repair_once().state == "current"
    old = harness.files.path(CSV_NAME).read_bytes()
    harness.revise()
    before = harness.canonical_facts()
    original = ProjectionFiles._write

    def full(files: ProjectionFiles, name: str, data: bytes) -> None:
        if name.endswith(".csv.tmp"):
            raise OSError("synthetic full disk")
        original(files, name, data)

    with monkeypatch.context() as fault:
        fault.setattr(ProjectionFiles, "_write", full)
        assert harness.projector.repair_once().state == "failed"
    assert harness.files.path(CSV_NAME).read_bytes() == old
    assert harness.metadata() == ("failed", 2, 1, ((1, "current"), (2, "failed")))
    assert harness.canonical_facts() == before
    assert harness.projector.repair_once().state == "current"


class SimulatedProcessInterruption(BaseException):
    pass


@pytest.mark.parametrize("point", ["before_csv", "before_manifest"])
def test_first_publication_crash_and_newer_save_recovers_latest(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    harness.save()
    original = os.replace

    def interrupted(source: Any, destination: Any) -> None:
        target = CSV_NAME if point == "before_csv" else MANIFEST_NAME
        if Path(destination).name == target:
            raise SimulatedProcessInterruption()
        original(source, destination)

    with monkeypatch.context() as fault:
        fault.setattr(os, "replace", interrupted)
        with pytest.raises(SimulatedProcessInterruption):
            harness.projector.repair_once()
    assert harness.files.path(PENDING_NAME).exists()
    assert not harness.files.path(MANIFEST_NAME).exists()
    if point == "before_manifest":
        assert harness.rows()[0]["lead_revision"] == "1"
    harness.revise(text="Newer canonical revision after restart")
    before = harness.canonical_facts()
    result = CsvProjector(harness.store, clock=harness.leads.sessions.clock.now).repair_once()
    assert result.state == "current" and result.published_version == 2
    assert harness.rows()[0]["lead_revision"] == "2"
    assert harness.canonical_facts() == before


@pytest.mark.parametrize("committed", [False, True], ids=["before-ack", "lost-ack-result"])
def test_missing_ack_reuses_verified_publication_without_duplicate(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch, committed: bool
) -> None:
    harness.save()
    original = Store.write

    def fail_ack(store: Store, work: Any) -> Any:
        def capture(db: Session) -> Any:
            result = work(db)
            if type(result) is int and not committed:
                raise StoreError("SYNTHETIC_ACK_FAILURE")
            return result

        result = original(store, capture)
        if type(result) is int and committed:
            raise StoreError("SYNTHETIC_LOST_ACK_RESULT")
        return result

    with monkeypatch.context() as fault:
        fault.setattr(Store, "write", fail_ack)
        result = harness.projector.repair_once()
    assert result.state == "pending" and not result.status_persisted
    assert not startup_admitted(result)
    publication = harness.publication()
    before = harness.canonical_facts()
    assert harness.projector.repair_once().state == "current"
    assert harness.publication() == publication and len(harness.rows()) == 1
    assert harness.canonical_facts() == before


def test_stale_serialization_cannot_replace_newer_canonical_version(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.save()
    assert harness.projector.repair_once().state == "current"
    old = harness.files.path(CSV_NAME).read_bytes()
    harness.revise()
    original = publisher.serialize_leads_csv

    def race(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        harness.revise(text="Save overtakes serialization")
        return result

    with monkeypatch.context() as fault:
        fault.setattr(publisher, "serialize_leads_csv", race)
        result = harness.projector.repair_once()
    assert result.state == "pending"
    assert harness.files.path(CSV_NAME).read_bytes() == old
    assert harness.metadata()[1:3] == (3, 1)
    assert harness.projector.repair_once().published_version == 3


def test_late_ack_marks_newer_canonical_version_pending(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.save()
    original = ProjectionFiles.verified

    def after_replace(files: ProjectionFiles, expected: PublicationManifest) -> bool:
        verified = original(files, expected)
        assert verified
        harness.revise(text="Save after publication before acknowledgement")
        return verified

    with monkeypatch.context() as fault:
        fault.setattr(ProjectionFiles, "verified", after_replace)
        result = harness.projector.repair_once()
    assert (result.state, result.canonical_version, result.published_version) == ("pending", 2, 1)
    assert harness.metadata() == ("pending", 2, 1, ((1, "current"), (2, "pending")))
    assert harness.projector.repair_once().published_version == 2


def test_read_fence_holds_canonical_commit_until_replacement_finishes(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.save()
    entered, staged, release = Event(), Event(), Event()
    original = ProjectionFiles.publish

    def fenced(files: ProjectionFiles, manifest: PublicationManifest) -> None:
        entered.set()
        assert release.wait(5), "bounded release timed out"
        original(files, manifest)

    def writer() -> None:
        def advance(db: Session) -> None:
            state = db.get(ExportState, 1)
            assert state is not None
            state.canonical_version += 1
            state.state = "pending"
            db.flush()
            staged.set()

        harness.store.write(advance)

    with monkeypatch.context() as fault, ThreadPoolExecutor(max_workers=2) as pool:
        fault.setattr(ProjectionFiles, "publish", fenced)
        publication = pool.submit(harness.projector.repair_once)
        writer_future = None
        try:
            assert entered.wait(5), "publisher did not reach read fence"
            writer_future = pool.submit(writer)
            assert staged.wait(5), "writer did not reach commit boundary"
            # Wait for the actual existing SQLite busy timeout, not merely a
            # scheduler instant before COMMIT. Without a held read fence this
            # write succeeds, and this assertion must fail.
            with pytest.raises(StoreError, match="STORE_BUSY"):
                writer_future.result(timeout=3)
        finally:
            release.set()
        assert publication.result(timeout=10).state == "current"
        assert writer_future is not None
    assert harness.metadata()[1:3] == (1, 1)  # timed-out writer rolled back
    writer()  # One explicit retry now that publication released its read lock.
    # This is a synthetic projection-version advance, not a booking/lead acceptance test.
    assert harness.metadata()[0] == "pending"
    assert harness.metadata()[1:3] == (2, 1)


def test_two_projectors_share_physical_lock(harness: ProjectionHarness) -> None:
    harness.save()
    second = CsvProjector(harness.store, clock=harness.leads.sessions.clock.now)
    with harness.files.lock():
        result = second.repair_once()
    assert result.state == "busy" and not startup_admitted(result)
    assert second.repair_once().state == "current"


@pytest.mark.parametrize("foreign", ["store", "generation"])
def test_foreign_publication_never_overwritten(
    harness: ProjectionHarness, foreign: str
) -> None:
    harness.save()
    assert harness.projector.repair_once().state == "current"
    old = harness.files.path(CSV_NAME).read_bytes()
    manifest = harness.files.manifest(MANIFEST_NAME)
    assert manifest is not None
    change = {"store_binding": "f" * 64} if foreign == "store" else {
        "store_generation": str(uuid4())
    }
    altered = PublicationManifest.model_validate({**manifest.model_dump(), **change})
    harness.files.path(MANIFEST_NAME).write_bytes(manifest_bytes(altered))
    result = harness.projector.repair_once()
    assert result.state == "failed"
    assert harness.files.path(CSV_NAME).read_bytes() == old
    if foreign == "generation":
        result = harness.projector.repair_once(
            reconcile_from_generation=altered.store_generation
        )
        assert result.state == "current"
        assert harness.publication()["store_generation"] == harness.store.generation


def test_restored_empty_requires_zero_version_metadata_before_reconciliation(
    harness: ProjectionHarness,
) -> None:
    harness.save()
    assert harness.projector.repair_once().state == "current"
    manifest = harness.files.manifest(MANIFEST_NAME)
    assert manifest is not None
    old_generation = str(uuid4())
    old_manifest = PublicationManifest.model_validate({
        **manifest.model_dump(), "store_generation": old_generation,
    })
    harness.files.path(MANIFEST_NAME).write_bytes(manifest_bytes(old_manifest))
    old = harness.files.path(CSV_NAME).read_bytes()

    def empty(db: Session) -> None:
        db.execute(delete(ExportIntent))
        db.execute(delete(Lead))
        db.execute(delete(ExportState))

    # Simulates already-restored canonical absence only; credentials/restore are NOT tested.
    harness.store.write(empty)
    result = harness.projector.repair_once(reconcile_from_generation=old_generation)
    assert result.state == "failed" and not startup_admitted(result)
    assert harness.files.path(CSV_NAME).read_bytes() == old
    harness.store.write(lambda db: db.add(ExportState(
        id=1, store_generation=harness.store.generation, canonical_version=0,
        exported_version=None, state="pending", updated_at=utc_text(harness.leads.sessions.clock.now()),
    )))
    assert harness.projector.repair_once(reconcile_from_generation=old_generation).state == "current"
    assert harness.rows() == [] and harness.metadata()[1:3] == (0, 0)


def test_unowned_csv_and_hardlink_are_refused(harness: ProjectionHarness) -> None:
    harness.save()
    harness.files.directory(create=True)
    target = harness.files.path(CSV_NAME)
    target.write_bytes(b"unowned existing data")
    assert harness.projector.repair_once().state == "failed"
    assert target.read_bytes() == b"unowned existing data"
    target.unlink()
    original = harness.store.boundary.physical_root / "hardlink-evidence.txt"
    original.write_bytes(b"unrelated private data")
    os.link(original, target)
    assert harness.projector.repair_once().state == "failed"
    assert original.read_bytes() == b"unrelated private data"
    target.unlink()
    assert harness.projector.repair_once().state == "current"


def test_expired_canonical_rows_fail_without_renewal_or_new_csv(harness: ProjectionHarness) -> None:
    harness.save()
    before = harness.canonical_facts()
    harness.leads.sessions.clock.value += timedelta(days=100)
    assert harness.projector.repair_once().state == "failed"
    assert not harness.files.path(CSV_NAME).exists()
    assert harness.canonical_facts() == before


def test_expiry_during_staging_is_rechecked_before_replacement(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.save()
    before = harness.canonical_facts()
    original = ProjectionFiles.stage

    def expire(files: ProjectionFiles, manifest: PublicationManifest, data: bytes) -> None:
        original(files, manifest, data)
        harness.leads.sessions.clock.value += timedelta(days=100)

    monkeypatch.setattr(ProjectionFiles, "stage", expire)
    assert harness.projector.repair_once().state == "failed"
    assert not harness.files.path(CSV_NAME).exists()
    assert harness.canonical_facts() == before


@pytest.mark.parametrize("existing_pair", [False, True], ids=["new-pair", "existing-pair"])
def test_expiry_during_verification_cannot_acknowledge_current(
    harness: ProjectionHarness, monkeypatch: pytest.MonkeyPatch, existing_pair: bool
) -> None:
    harness.save()
    if existing_pair:
        assert harness.projector.repair_once().state == "current"
    before = harness.canonical_facts()
    original = ProjectionFiles.verified

    def expire(files: ProjectionFiles, manifest: PublicationManifest) -> bool:
        result = original(files, manifest)
        harness.leads.sessions.clock.value += timedelta(days=100)
        return result

    monkeypatch.setattr(ProjectionFiles, "verified", expire)
    result = harness.projector.repair_once()
    assert result.state == "failed" and result.status_persisted
    assert harness.metadata()[0] == "failed"
    assert harness.canonical_facts() == before
    # Existing bytes are operational evidence; OP expiry cleanup is a separate gate.


def test_oversized_raw_values_fail_before_json_materialization(harness: ProjectionHarness) -> None:
    harness.save()

    def oversized(db: Session) -> None:
        db.execute(update(Lead).values(values_json={"oversize": "x" * (repo.MAX_ROW_JSON + 1)}))

    harness.store.write(oversized)
    with pytest.raises(repo.ProjectionError, match="CSV_CANONICAL_SNAPSHOT_LIMIT"):
        harness.store.read(lambda db: repo.capture(
            db, harness.store.generation, utc_text(harness.leads.sessions.clock.now())
        ))
    assert harness.projector.repair_once().state == "failed"
    assert not harness.files.path(CSV_NAME).exists()


def test_reserved_temporary_cleanup_preserves_unrelated_files(harness: ProjectionHarness) -> None:
    harness.save()
    harness.files.directory(create=True)
    orphan = harness.files.path(f"leads.{uuid4()}.json.tmp")
    orphan.write_bytes(b"interrupted descriptor")
    unrelated = harness.files.root / "operator-note.txt"
    unrelated.write_text("retain", encoding="utf-8")
    assert harness.projector.repair_once().state == "current"
    assert not orphan.exists() and unrelated.read_text(encoding="utf-8") == "retain"


def test_observation_constraint_only_preserves_exact_audited_current() -> None:
    generation = str(uuid4())
    observed = ExportCurrent(
        state="current", store_generation=generation, observed_at="2026-09-24T00:00:00Z",
        canonical_version=3, exported_version=3,
    )
    proven = ProjectionRun("current", generation, 3, 3, 1, status_persisted=True)
    assert constrain_observation(observed, proven) is observed
    for unproven in (
        replace(proven, store_generation=str(uuid4())),
        replace(proven, canonical_version=2), replace(proven, published_version=2),
        replace(proven, status_persisted=False), replace(proven, state="busy"),
    ):
        assert constrain_observation(observed, unproven).state == "pending"
    pending = ExportPending(
        **{**observed.model_dump(), "state": "pending", "code": None}
    )
    assert constrain_observation(pending, proven) is pending
