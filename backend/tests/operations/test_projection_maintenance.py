"""Actual locked-projector seam cases; these do not prove Store maintenance exclusion."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest

from app.leads.projection_files import ProjectionFiles, PublicationBusy
from app.leads.projection_repository import ProjectionError
from tests.transactions.projection_fixtures import deny_replacement, make_projection_harness


def test_locked_repair_rejects_an_unheld_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = make_projection_harness(monkeypatch)
    flow.save()
    before = flow.metadata(), flow.canonical_facts()
    with pytest.raises(ProjectionError, match="CSV_PUBLICATION_LOCK_REQUIRED"):
        flow.projector.repair_locked(flow.files)
    assert (flow.metadata(), flow.canonical_facts()) == before


def test_path_locator_uses_the_existing_physical_publication_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = make_projection_harness(monkeypatch)
    located = ProjectionFiles.for_store_path(flow.store.path, boundary=flow.store.boundary)
    assert (located.root, located.store_binding) == (flow.files.root, flow.files.store_binding)
    with located.lock():
        with pytest.raises(PublicationBusy):
            with flow.files.lock():
                pytest.fail("path locator did not exclude the normal publisher")


def test_actual_held_repair_does_not_release_or_reacquire_outer_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = make_projection_harness(monkeypatch)
    saved = flow.save()
    with flow.files.lock():
        assert flow.projector.repair_locked(flow.files).state == "current"
        flow.files.assert_locked()
        competitor = ProjectionFiles(flow.store)
        with pytest.raises(PublicationBusy):
            with competitor.lock():
                pytest.fail("second publisher entered the held scope")
        assert flow.rows()[0]["lead_id"] == saved.lead_id
    with pytest.raises(ProjectionError, match="CSV_PUBLICATION_LOCK_REQUIRED"):
        flow.files.assert_locked()
    assert flow.projector.repair_once().state == "current"


def test_locked_authority_cannot_cross_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = make_projection_harness(monkeypatch)
    with flow.files.lock():
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(flow.files.assert_locked)
            with pytest.raises(ProjectionError, match="CSV_PUBLICATION_LOCK_REQUIRED"):
                future.result(timeout=5)
        flow.files.assert_locked()


def test_locked_files_cannot_publish_for_another_physical_store(monkeypatch: pytest.MonkeyPatch) -> None:
    first = make_projection_harness(monkeypatch)
    second = make_projection_harness(monkeypatch)
    with first.files.lock():
        with pytest.raises(ProjectionError, match="CSV_DIFFERENT_STORE"):
            second.projector.repair_locked(first.files)
        first.files.assert_locked()


def test_locked_publication_failure_preserves_scope_for_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = make_projection_harness(monkeypatch)
    flow.save()
    assert flow.projector.repair_once().state == "current"
    flow.revise()
    with flow.files.lock():
        with deny_replacement(flow.files.path("leads.csv")):
            failed = flow.projector.repair_locked(flow.files)
        assert failed.state == "failed"
        flow.files.assert_locked()
        assert flow.projector.repair_locked(flow.files).state == "current"


def test_same_instance_losing_entry_cannot_clear_the_winners_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = make_projection_harness(monkeypatch)
    files = flow.files
    with files.lock():
        files.assert_locked()
    original = files.directory
    both_entered, loser_finished = Barrier(2), Event()

    def enter_together(*, create: bool = False) -> Path:
        path = original(create=create)
        if create:
            # Both callers passed the initial ownership check before either OS lock.
            both_entered.wait(timeout=5)
        return path

    def contender() -> str:
        try:
            with files.lock():
                assert loser_finished.wait(timeout=5)
                files.assert_locked()
                return "held"
        except PublicationBusy:
            loser_finished.set()
            return "busy"

    monkeypatch.setattr(files, "directory", enter_together)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = (workers.submit(contender), workers.submit(contender))
        assert sorted(future.result(timeout=10) for future in futures) == ["busy", "held"]
    with pytest.raises(ProjectionError, match="CSV_PUBLICATION_LOCK_REQUIRED"):
        files.assert_locked()
