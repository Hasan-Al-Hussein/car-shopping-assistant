"""Application lifetime and maintenance exclusion; source only until runtime grant."""

import asyncio
import os
from threading import Event
from time import monotonic

import pytest

from app.database.store import StoreError
from app.runtime_app import ApplicationComposition
from tests.platform.assistant_http_cases import until
from tests.platform.maintenance_cases import exclusion_state
from tests.platform.runtime_cases import runtime_clock as runtime_clock
from tests.platform.runtime_cases import runtime_composition as runtime_composition
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import runtime_store as runtime_store


def test_inert_builder_then_idle_admitted_application_excludes_restore(
    runtime_composition: ApplicationComposition,
) -> None:
    composition = runtime_composition
    store = composition.store
    assert exclusion_state(store.path, store.boundary) == "held"
    assert composition.identity.open_store() is store
    assert exclusion_state(store.path, store.boundary) == "busy"
    assert composition.close()
    assert exclusion_state(store.path, store.boundary) == "held"
    with pytest.raises(StoreError):
        composition.identity.open_store()
    assert exclusion_state(store.path, store.boundary) == "held"


def test_retired_pending_worker_keeps_pin_until_actual_settlement(
    runtime_composition: ApplicationComposition,
) -> None:
    composition = runtime_composition
    store = composition.store
    composition.identity.open_store()
    entered, release = Event(), Event()

    def work() -> str:
        entered.set()
        assert release.wait(20), "TEST_DID_NOT_RELEASE_WORKER"
        return "settled"

    async def exercise() -> None:
        task = asyncio.create_task(composition.worker.run(work, deadline_at=monotonic() + 18))
        try:
            await until(entered.is_set)
            # Same retirement seam as bound-opener generation/schema mismatch.
            composition._lifetime.close()
            assert not composition.close()
            with pytest.raises(StoreError):
                composition._lifetime.ensure_admitted()
            assert await asyncio.to_thread(exclusion_state, store.path, store.boundary) == "busy"
        finally:
            release.set()
            assert await asyncio.wait_for(task, 3) == "settled"
        assert await composition.shutdown()
        assert await asyncio.to_thread(exclusion_state, store.path, store.boundary) == "held"

    asyncio.run(exercise())


def test_failed_native_release_cannot_report_success_or_drop_original_pin(
    runtime_composition: ApplicationComposition, monkeypatch: pytest.MonkeyPatch,
) -> None:
    composition = runtime_composition
    store = composition.store
    composition.identity.open_store()
    original = composition._lifetime._pin._guard
    assert original is not None
    descriptor = original._descriptor
    assert descriptor is not None
    real_close = os.close

    def failed(candidate: int) -> None:
        if candidate == descriptor:
            raise OSError("CONTROLLED_RELEASE_FAILURE")
        real_close(candidate)

    with monkeypatch.context() as scoped:
        # Execute the real native close body, failing only its final os.close.
        # An early UnlockFileEx would wrongly allow the actual contender below.
        scoped.setattr(os, "close", failed)
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            composition.close()
        assert composition._lifetime._pin._guard is original
        assert original.held
        assert exclusion_state(store.path, store.boundary) == "busy"
    assert composition.close()
    assert exclusion_state(store.path, store.boundary) == "held"
