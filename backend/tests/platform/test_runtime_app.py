"""Focused inert composition/lifecycle checks; runtime execution needs its own grant."""

import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi import FastAPI

from app import runtime_app
from app.api.schemas.inventory import SearchRequest
from app.api.schemas.routes import ROUTES
from app.core.config import Settings, load_settings
from app.core.readiness import InventoryObservation, ReadinessRegistry
from app.database import store as store_module
from app.database.paths import RuntimeBoundary
from app.database.store import Store, StoreError
from app.inventory.compact_reader import CompactInventoryReader
from app.inventory_signing import HmacPublicInventorySigner
from app.runtime_app import ApplicationComposition, RuntimeStartupError, build_composition
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import runtime_store as runtime_store
from tests.platform.runtime_cases import settings_for
from tests.support.harness import FrozenClock, configured_runtime_boundary, runtime_environment


def descriptor(path: Path) -> Store:
    return Store(
        path,
        str(uuid4()),
        schema_version="0002",
        inventory_mode="fts5",
        boundary=configured_runtime_boundary(),
    )


def test_module_import_does_not_open_create_admit_or_start_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("IMPORT_PERFORMED_RUNTIME_WORK")

    monkeypatch.setattr(store_module, "open_store", forbidden)
    monkeypatch.setattr(store_module, "initialize_store", forbidden)
    monkeypatch.setattr(CompactInventoryReader, "refresh", forbidden)
    monkeypatch.setattr(HmacPublicInventorySigner, "__init__", forbidden)
    spec = importlib.util.spec_from_file_location("_p13_import_probe", runtime_app.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    assert not hasattr(module, "app")


def test_builder_mounts_exact_actual_routes_and_reuses_authorization(
    runtime_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(path: Path, *, boundary: RuntimeBoundary) -> Store:
        raise AssertionError("BUILDER_OPENED_STORE_BEFORE_EXPLICIT_ADMISSION")

    monkeypatch.setattr(runtime_app, "open_store", forbidden)
    composition = build_composition(settings_for(runtime_path), descriptor(runtime_path))
    try:
        schema = composition.app.openapi()
        actual = [
            (path, method.upper(), operation)
            for path, methods in schema["paths"].items()
            for method, operation in methods.items()
            if method in {"get", "post", "put", "patch", "delete"}
        ]
        assert (
            len(actual)
            == len({operation["operationId"] for _, _, operation in actual})
            == len(ROUTES)
        )
        contracts = {route.operation_id: route for route in ROUTES}
        for path, method, operation in actual:
            contract = contracts[operation["operationId"]]
            assert path == "/api/v1" + contract.path
            assert method == contract.method
            assert operation["x-mutates-state"] == contract.mutates
            assert operation["x-private"] == contract.private
            assert operation["x-domain-owner"] == contract.owner
        ids = {operation["operationId"] for _, _, operation in actual}
        assert {"search_inventory", "get_listing", "compare_listings"} <= ids
        assert {"get_preferences", "update_preferences", "get_shortlist"} <= ids
        assert ids == set(contracts)
        assert not any("seed" in path or "activate" in path for path, _, _ in actual)
        assert composition.sessions is composition.app.state.sessions
        assert composition.authorization is composition.app.state.authorization
        assert composition.preferences.authorization is composition.authorization
        assert composition.shortlist.authorization is composition.authorization
        assert composition.leads.authorization is composition.authorization
        assert composition.drafts.authorization is composition.authorization
        assert composition.viewing_options.reader is composition.reader
        assert composition.viewing_inventory.reader is composition.reader
        assert composition.projector.store is composition.store
        assert composition.assistant is composition.app.state.assistant
        assert composition.sessions.authorization is composition.authorization
        assert composition.authorization.identity is composition.identity
        assert composition.search.reader is composition.details.reader is composition.reader
        assert composition.search.signer is composition.signer
        assert composition.registry.snapshot().inventory == "unconfigured"
        assert not runtime_path.exists()
    finally:
        composition.close()


def test_common_clock_and_explicit_disabled_assistant(runtime_path: Path) -> None:
    from datetime import UTC

    clock = FrozenClock(datetime(2030, 1, 7, 4, tzinfo=UTC))
    now = clock.now
    composition = build_composition(settings_for(runtime_path), descriptor(runtime_path), clock=now)
    try:
        assert composition.clock is composition.search.clock is now
        assert composition.identity.now_text() == "2030-01-07T04:00:00.000000Z"
        clock.advance(3600)
        assert composition.identity.now_text() == "2030-01-07T05:00:00.000000Z"
        assert composition.search.clock() == clock.now()
        assert composition.preferences._now() == composition.sessions._now()
        assert composition.shortlist._now() == composition.identity.now_text()
    finally:
        composition.close()
    enabled = load_settings({**runtime_environment(), "CSA_STORE_PATH": str(runtime_path)})
    enabled_composition = build_composition(enabled, descriptor(runtime_path))
    try:
        assert enabled_composition.settings.assistant_enabled
        assert not enabled_composition.settings.provider_configured
        assert not enabled_composition.provider.pending
        assert not enabled_composition.worker.pending
        assert not runtime_path.exists()
    finally:
        assert enabled_composition.close()
    with pytest.raises(ValueError, match="IDENTITY_CLOCK_REQUIRES_UTC"):
        build_composition(
            settings_for(runtime_path), descriptor(runtime_path), clock=lambda: datetime(2030, 1, 7)
        )


def test_builder_rejects_same_path_with_a_different_boundary(runtime_path: Path) -> None:
    store = descriptor(runtime_path)
    logical = store.boundary.logical_root
    different = RuntimeBoundary(logical, logical.with_name(logical.name + "-other-backing"))
    settings = Settings(
        store_path=runtime_path,
        runtime_boundary=different,
        assistant_enabled=False,
    )
    with pytest.raises(RuntimeStartupError):
        build_composition(settings, store)
    assert not runtime_path.exists()


def test_missing_store_factory_never_initializes(runtime_path: Path) -> None:
    with pytest.raises(RuntimeStartupError, match="RUNTIME_STORE_NOT_CONFIGURED"):
        runtime_app.create_runtime_app(load_settings({"CSA_ASSISTANT_ENABLED": "false"}))
    with pytest.raises(RuntimeStartupError, match="RUNTIME_STORE_UNAVAILABLE"):
        runtime_app.create_runtime_app(settings_for(runtime_path))
    assert not runtime_path.exists() and not runtime_path.parent.exists()


def test_foreign_process_and_closed_reader_fail_before_io(
    runtime_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composition = build_composition(settings_for(runtime_path), descriptor(runtime_path))
    pid = os.getpid()
    with monkeypatch.context() as scoped:
        scoped.setattr(os, "getpid", lambda: pid + 1)
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            composition.reader.read_refs(())
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            composition.identity.open_store()
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            composition.reader.refresh(composition.registry)
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            composition.reader.admit("a" * 64)
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            composition.reader.invalidate()
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            composition.close()
    composition.close()
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        composition.search.search(SearchRequest(client_request_id=str(uuid4())))
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        composition.admit_inventory()
    assert composition.registry.snapshot().inventory == "unavailable"
    assert not runtime_path.exists()


def test_lifespan_retires_composition(runtime_path: Path) -> None:
    import asyncio

    composition: ApplicationComposition = build_composition(
        settings_for(runtime_path), descriptor(runtime_path)
    )

    async def exercise() -> None:
        async with composition.app.router.lifespan_context(composition.app):
            assert composition.registry.snapshot().inventory == "unconfigured"

    asyncio.run(exercise())
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        composition.reader.read_refs(())
    assert composition.registry.snapshot().inventory == "unavailable"


def test_launcher_preserves_http_security_and_closes_on_server_exit(
    runtime_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uvicorn

    configured = settings_for(runtime_path)
    composition = build_composition(configured, descriptor(runtime_path))
    calls: list[dict[str, object]] = []

    def factory(settings: object) -> FastAPI:
        assert settings is configured
        return composition.app

    def run(application: FastAPI, **kwargs: object) -> None:
        assert application is composition.app
        calls.append(kwargs)

    monkeypatch.setattr(runtime_app, "load_settings", lambda: configured)
    monkeypatch.setattr(runtime_app, "create_runtime_app", factory)
    monkeypatch.setattr(uvicorn, "run", run)
    runtime_app.main()
    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 8000,
            "proxy_headers": False,
            "access_log": False,
        }
    ]
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        composition.reader.read_refs(())


@pytest.mark.parametrize("transition", ["invalidate_after_publish", "close_before_publish"])
def test_interrupted_cold_refresh_cannot_republish_ready(
    runtime_store: Store,
    monkeypatch: pytest.MonkeyPatch,
    transition: str,
) -> None:
    composition = build_composition(settings_for(runtime_store.path), runtime_store)
    reached, resume = Event(), Event()
    errors: list[BaseException] = []

    def inner_refresh(reader: CompactInventoryReader, registry: ReadinessRegistry) -> None:
        # Unit-only scheduling seam at the base call boundary; no SQL/admission
        # implementation is replaced in the real integration fixtures.
        def publish() -> None:
            registry.refresh_inventory(
                lambda: InventoryObservation(
                    generation=reader.store.generation,
                    active_revision=1,
                    snapshot_id="a" * 64,
                    index_version="b" * 64,
                    mode="fts5",
                )
            )

        if transition == "invalidate_after_publish":
            publish()
        reached.set()
        assert resume.wait(2)
        if transition == "close_before_publish":
            publish()

    def refresh() -> None:
        try:
            composition.reader.refresh(composition.registry)
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(CompactInventoryReader, "refresh", inner_refresh)
    worker = Thread(target=refresh)
    worker.start()
    try:
        try:
            assert reached.wait(2)
            if transition == "invalidate_after_publish":
                composition.reader.invalidate()
            else:
                composition.close()
        finally:
            resume.set()
            worker.join(3)
        assert not worker.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], (StoreError, ValueError))
        assert composition.registry.snapshot().inventory == "unavailable"
        assert composition.registry.snapshot().active_snapshot_id is None
    finally:
        composition.close()


def test_close_during_fresh_store_validation_rejects_returned_descriptor(
    runtime_store: Store,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = runtime_store
    composition = build_composition(settings_for(store.path), store)

    def opening(path: Path, *, boundary: RuntimeBoundary) -> Store:
        assert path == store.path
        assert boundary is store.boundary
        composition.close()
        return store

    monkeypatch.setattr(runtime_app, "open_store", opening)
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        composition.identity.open_store()
    assert composition.registry.snapshot().inventory == "unavailable"
