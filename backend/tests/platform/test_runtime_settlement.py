"""P16 settlement/observation regression sources, NOT_RUN under source-only grant."""

import asyncio
import importlib.util
import os
import sys
from contextlib import suppress
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any, Literal
from uuid import uuid4

import pytest

from app import runtime_app
from app.api.schemas.capabilities import Capability
from app.assistant.budget import TurnBudget
from app.assistant.intent import TurnIntent
from app.assistant.packet import EvidencePacket
from app.assistant.provider import TransportResponse
from app.core.config import Timeouts
from app.database.store import Store, StoreError
from app.leads.projection import CsvProjector, ProjectionRun
from app.runtime_app import ApplicationComposition, RuntimeStartupError, create_runtime_app
from app.runtime_observations import RuntimeCsvProjector
from tests.assistant.conversation_fakes import ScriptedTransport, response
from tests.inventory.conftest import snapshot_candidate as snapshot_candidate
from tests.platform.assistant_http_cases import composition_for, until
from tests.platform.runtime_cases import active_runtime as active_runtime
from tests.platform.runtime_cases import runtime_clock as runtime_clock
from tests.platform.runtime_cases import runtime_composition as runtime_composition
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import runtime_store as runtime_store
from tests.platform.test_identity import call
from tests.platform.test_runtime_integration import buyer, private, session
from tests.support.harness import PROJECT, FrozenClock
from tests.transactions.lead_fixtures import save_request


def test_shutdown_foreign_pid_rejects_before_owned_objects(
    runtime_composition: ApplicationComposition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("FOREIGN_PROCESS_TOUCHED_OWNED_OBJECT")

    pid = os.getpid()
    with monkeypatch.context() as scoped:
        scoped.setattr(os, "getpid", lambda: pid + 1)
        scoped.setattr(runtime_composition.provider, "stop", forbidden)
        scoped.setattr(runtime_composition.worker, "close", forbidden)
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            asyncio.run(runtime_composition.shutdown())


def test_busy_worker_is_retained_until_real_settlement(
    runtime_composition: ApplicationComposition,
) -> None:
    composition = runtime_composition
    entered, release = Event(), Event()
    original = composition.worker

    def blocked() -> str:
        entered.set()
        if not release.wait(5):
            raise AssertionError("TEST_DID_NOT_RELEASE_WORKER")
        composition._lifetime.require_live()
        return "settled"

    async def exercise() -> None:
        task = asyncio.create_task(original.run(blocked, deadline_at=monotonic() + 4))
        try:
            await until(entered.is_set)
            assert not composition.close()
            composition._lifetime.require_live()
            assert composition.worker is original and original.pending
        finally:
            release.set()
            assert await asyncio.wait_for(task, timeout=2) == "settled"
        assert await composition.shutdown()
        with pytest.raises(StoreError):
            composition._lifetime.require_live()

    asyncio.run(exercise())


def test_resistant_provider_keeps_original_composition_until_settlement(
    runtime_store: Store,
    runtime_clock: FrozenClock,
) -> None:
    async def exercise() -> None:
        started, release = asyncio.Event(), asyncio.Event()

        async def resistant() -> TransportResponse:
            started.set()
            while not release.is_set():
                with suppress(asyncio.CancelledError):
                    await release.wait()
            return response(TurnIntent(operation="smalltalk"))

        transport = ScriptedTransport(resistant)
        timeouts = Timeouts(
            operation_seconds=1,
            confirmation_seconds=1,
            provider_connect_seconds=1,
            provider_attempt_seconds=1,
        )
        composition = composition_for(runtime_store, runtime_clock, transport, timeouts=timeouts)
        provider = composition.provider
        task = asyncio.create_task(
            provider.generate(
                EvidencePacket(message="Hello", session_revision=0),
                TurnIntent,
                budget=TurnBudget(timeouts, monotonic() + 1),
                request_id=str(uuid4()),
            )
        )
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            assert not await composition.shutdown()
            assert provider.pending and composition.provider is provider
            composition._lifetime.require_live()
            assert len(transport.requests) == 1
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=2)
            await until(lambda: not provider.pending)
            assert await composition.shutdown()
        assert composition.registry.snapshot().provider is None

    asyncio.run(exercise())


def test_explicit_empty_csv_audit_and_health_never_repairs(
    runtime_composition: ApplicationComposition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composition = runtime_composition
    assert composition.projector.capability().state == "degraded"
    assert composition.projector.repair_once().state == "empty"
    assert composition.projector.capability().state == "ready"

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("HEALTH_ATTEMPTED_REPAIR")

    monkeypatch.setattr(composition.projector, "repair_once", forbidden)
    before = composition.store.path.read_bytes()
    result = call(composition.app, composition.settings, "GET", "/api/v1/health")
    assert result.status_code == 200 and result.json()["data"]["export"]["state"] == "ready"
    assert composition.store.path.read_bytes() == before


@pytest.mark.parametrize("state", ["busy", "failed"])
def test_unpersisted_audit_failure_cannot_reuse_previous_current_csv(
    runtime_composition: ApplicationComposition,
    monkeypatch: pytest.MonkeyPatch,
    state: Literal["busy", "failed"],
) -> None:
    composition = runtime_composition
    actor = buyer(composition)
    current = session(composition, actor)
    saved = private(
        composition,
        actor,
        "POST",
        "/api/v1/leads",
        body=save_request(current["session_id"]).model_dump(mode="json"),
    )
    assert saved.status_code == 201 and composition.projector.capability().state == "ready"
    attempt = ProjectionRun(
        state=state,
        store_generation=composition.store.generation,
        canonical_version=None,
        published_version=None,
        row_count=None,
    )
    monkeypatch.setattr(CsvProjector, "repair_once", lambda *args, **kwargs: attempt)
    assert composition.projector.repair_once() is attempt
    assert composition.projector.capability().state == (
        "unavailable" if state == "failed" else "degraded"
    )


def test_unpersisted_startup_audit_failure_retires_composition(
    runtime_composition: ApplicationComposition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous = runtime_composition
    assert previous.close()
    built: list[ApplicationComposition] = []
    real_builder = runtime_app.build_composition

    def capture(*args: Any, **kwargs: Any) -> ApplicationComposition:
        value = real_builder(*args, **kwargs)
        built.append(value)
        return value

    def busy(projector: RuntimeCsvProjector, **kwargs: Any) -> ProjectionRun:
        return ProjectionRun("busy", projector.store.generation, None, None, None)

    monkeypatch.setattr(runtime_app, "build_composition", capture)
    monkeypatch.setattr(RuntimeCsvProjector, "repair_once", busy)
    with pytest.raises(RuntimeStartupError, match="CSV_STARTUP_AUDIT_UNRESOLVED"):
        create_runtime_app(previous.settings, clock=previous.clock, event_sink=lambda event: None)
    assert len(built) == 1
    with pytest.raises(StoreError):
        built[0]._lifetime.require_live()
    assert not built[0].worker.pending and not built[0].provider.pending


@pytest.mark.parametrize("retire", [False, True])
def test_health_fails_closed_when_inventory_changes_during_added_observation(
    active_runtime: ApplicationComposition,
    monkeypatch: pytest.MonkeyPatch,
    retire: bool,
) -> None:
    composition = active_runtime

    def interleave(*args: object, **kwargs: object) -> Capability:
        if retire:
            assert composition.close()
        else:
            composition.reader.invalidate()
        return Capability(state="ready", reason="Synthetic scheduling interleave.")

    monkeypatch.setattr(runtime_app, "viewing_capability", interleave)
    result = composition.app.state.readiness.health()
    assert result.inventory.state == result.viewing.state == "unavailable"
    assert result.active_snapshot_id is None
    if retire:
        assert result.store.state == result.export.state == "unavailable"


def test_root_main_is_inert_then_forwards_to_explicit_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(runtime_app, "main", lambda: calls.append("runtime"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    path: Path = PROJECT / "main.py"
    spec = importlib.util.spec_from_file_location("_p16_root_entry", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert calls == []
    module.main()
    assert calls == ["runtime"]
