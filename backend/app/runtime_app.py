"""Explicit local composition. Importing this module performs no runtime I/O.

The synchronous factory must run before an ASGI event loop. Launch with
``python -m app.runtime_app``; the main function builds before uvicorn.run.
Only an existing, separately provisioned store is accepted. No seed, migration,
activation or viewing policy is installed here. Provider clients remain lazy.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import cast

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.assistant import assistant_router
from app.api.schemas.capabilities import Capability, HealthResult
from app.assistant.provider import GeminiAdapter, ProviderTransport
from app.assistant.service_adapters import AssistantService, BoundedServiceWorker
from app.assistant.transport import GoogleGenAITransport
from app.core.config import Settings, load_settings
from app.core.diagnostics import RequestEvent, emit_request_event
from app.core.readiness import InventoryObservation, ReadinessRegistry, ReadinessService
from app.database.maintenance import MaintenanceBusy, MaintenanceError, StoreLifetimeLease
from app.database.paths import StorePathError
from app.database.store import Store, StoreError, open_store
from app.identity.authorization import AuthorizationService
from app.identity.service import IdentityService, utc_text
from app.inventory.compact_reader import (
    AuditReceipt,
    CompactBatch,
    CompactInventoryReader,
    SearchAnchor,
)
from app.inventory.details_service import InventoryDetailsService
from app.inventory.references import ImmutableInventoryRef
from app.inventory.router import inventory_router
from app.inventory.search_service import InventorySearchService
from app.inventory.viewing_adapter import CompactViewingInventory
from app.inventory.viewing_options import CompactPublicEligibility, CompactViewingOptions
from app.inventory_gateways import CompactSessionInventory, CompactShortlistInventory
from app.inventory_signing import HmacPublicInventorySigner
from app.leads.participant import LeadParticipant
from app.leads.projection import startup_admitted
from app.leads.router import lead_router
from app.leads.service import LeadService
from app.memory.router import preference_router
from app.memory.service import PreferenceService
from app.runtime_observations import RuntimeCsvProjector, viewing_capability
from app.sessions.service import SessionService
from app.shortlist.router import shortlist_router
from app.shortlist.service import ShortlistService
from app.viewings.application import ViewingApplication
from app.viewings.confirmation import ConfirmationParticipant
from app.viewings.drafts import DraftService
from app.viewings.router import viewing_router
from app.viewings.scheduling import ViewingRules


class RuntimeStartupError(RuntimeError):
    """Sanitized startup failure, with no rejected path or secret in its message."""


def utc_now() -> datetime:
    return datetime.now(UTC)


class _Lifetime:
    def __init__(self, store: Store) -> None:
        self._pid = os.getpid()
        self._closed = False
        self._lock = RLock()
        self._pin = StoreLifetimeLease(store.path, boundary=store.boundary)

    def require_live(self) -> None:
        # Check process before taking a possibly inherited lock.
        if os.getpid() != self._pid:
            raise StoreError("STORE_UNAVAILABLE")
        with self._lock:
            if self._closed:
                raise StoreError("STORE_UNAVAILABLE")

    def ensure_admitted(self) -> None:
        self.require_live()
        with self._lock:
            self.require_live()
            try:
                self._pin.acquire()
            except MaintenanceBusy:
                raise StoreError("STORE_BUSY") from None
            except MaintenanceError:
                raise StoreError("STORE_UNAVAILABLE") from None

    def close(self) -> None:
        if os.getpid() != self._pid:
            raise StoreError("STORE_UNAVAILABLE")
        with self._lock:
            self._closed = True
            # A generation mismatch may retire admission from a live worker.
            # Keep the OS pin until ApplicationComposition observes settlement.
            self._pin.retire()

    def release(self) -> None:
        if os.getpid() != self._pid:
            raise StoreError("STORE_UNAVAILABLE")
        with self._lock:
            self._closed = True
            try:
                self._pin.close()
            except MaintenanceError:
                raise StoreError("STORE_UNAVAILABLE") from None


class _RuntimeReader(CompactInventoryReader):
    """Lifecycle fence only; admission, facts and identity checks stay in Inventory."""

    def __init__(self, store: Store, lifetime: _Lifetime) -> None:
        super().__init__(store)
        self._lifetime = lifetime
        self._invalidated = False
        self._invalidation_revision = 0

    @property
    def invalidated(self) -> bool:
        if os.getpid() != self._lifetime._pid:
            return True
        with self._lifetime._lock:
            return self._invalidated or self._lifetime._closed

    def invalidate(self) -> None:
        if os.getpid() != self._lifetime._pid:
            raise StoreError("STORE_UNAVAILABLE")
        with self._lifetime._lock:
            self._invalidation_revision += 1
            self._invalidated = True
            super().invalidate()

    def _begin_admission(self) -> int:
        self._lifetime.ensure_admitted()
        with self._lifetime._lock:
            self._lifetime.require_live()
            return self._invalidation_revision

    def _finish_admission(self, revision: int) -> None:
        self._lifetime.require_live()
        if revision != self._invalidation_revision:
            raise ValueError("INVENTORY_ADMISSION_INVALIDATED")

    def admit(self, snapshot_id: str) -> AuditReceipt:
        revision = self._begin_admission()
        try:
            receipt = super().admit(snapshot_id)
            with self._lifetime._lock:
                self._finish_admission(revision)
            return receipt
        except BaseException:
            self.invalidate()
            raise

    def refresh(self, registry: ReadinessRegistry) -> None:
        revision = self._begin_admission()
        try:
            # Do not hold the local lock across registry refresh: the base observer
            # may invalidate, and shutdown withdraws through the same registry.
            super().refresh(registry)
            with self._lifetime._lock:
                self._finish_admission(revision)
                self._invalidated = False
        except BaseException:
            _withdraw_inventory(registry, self)
            raise

    def read_refs(
        self, refs: tuple[ImmutableInventoryRef, ...], *, expected_snapshot_id: str | None = None
    ) -> CompactBatch:
        self._lifetime.ensure_admitted()
        result = super().read_refs(refs, expected_snapshot_id=expected_snapshot_id)
        self._lifetime.require_live()
        return result

    def read_search_anchor(self) -> SearchAnchor:
        self._lifetime.ensure_admitted()
        result = super().read_search_anchor()
        self._lifetime.require_live()
        return result

    def recheck_identity(
        self,
        session: Session,
        token: tuple[str, ...],
        *,
        expected_refs: tuple[ImmutableInventoryRef, ...],
    ) -> None:
        self._lifetime.ensure_admitted()
        super().recheck_identity(session, token, expected_refs=expected_refs)
        self._lifetime.require_live()


def _unavailable_observation() -> InventoryObservation:
    raise StoreError("STORE_UNAVAILABLE")


def _withdraw_inventory(registry: ReadinessRegistry, reader: CompactInventoryReader) -> None:
    reader.invalidate()
    # The existing registry retains its watermark and publishes unavailable.
    with suppress(StoreError):
        registry.refresh_inventory(_unavailable_observation)


class _RuntimeReadiness(ReadinessService):
    def __init__(
        self,
        settings: Settings,
        registry: ReadinessRegistry,
        *,
        reader: _RuntimeReader,
        store: Store,
        rules: ViewingRules,
        projector: RuntimeCsvProjector,
        store_opener: Callable[[Path], Store],
        clock: Callable[[], datetime],
    ) -> None:
        super().__init__(settings, registry, store_opener=store_opener, clock=clock)
        self._reader = reader
        self._store_instance, self._rules, self._projector = store, rules, projector

    def health(self) -> HealthResult:
        prior, observed = self.registry.observed_snapshot()
        inventory_version = (prior.inventory, prior.active_snapshot_id, observed)
        result = super().health()
        # Base health captures inventory before invoking the fresh Store opener.
        # A failed open in THIS observation must not return that earlier ready bit.
        if self._reader.invalidated or result.store.state in {"unavailable", "unconfigured"}:
            result = result.model_copy(
                update={
                    "inventory": Capability(
                        state="unavailable", reason="Inventory is temporarily unavailable."
                    ),
                    "active_snapshot_id": None,
                }
            )
        if result.store.state == "ready" and result.inventory.state == "ready":
            viewing = viewing_capability(self._store_instance, self._rules, observed)
        else:
            viewing = Capability(
                state="unavailable",
                reason="Simulated viewing needs current inventory and saved state.",
            )
        exported = (
            self._projector.capability()
            if result.store.state == "ready"
            else Capability(
                state="unavailable",
                reason="Local export cannot be observed while saved state is unavailable.",
            )
        )
        latest, latest_observed = self.registry.observed_snapshot()
        if (
            self._reader.invalidated
            or inventory_version
            != (
                latest.inventory,
                latest.active_snapshot_id,
                latest_observed,
            )
            or result.active_snapshot_id != prior.active_snapshot_id
        ):
            result = result.model_copy(
                update={
                    "inventory": Capability(
                        state="unavailable", reason="Inventory needs a fresh observation."
                    ),
                    "active_snapshot_id": None,
                }
            )
            viewing = Capability(
                state="unavailable", reason="Simulated viewing needs current inventory."
            )
        try:
            self._reader._lifetime.require_live()
        except StoreError:
            result = result.model_copy(
                update={
                    "store": Capability(
                        state="unavailable", reason="Local saved state is unavailable."
                    ),
                    "inventory": Capability(
                        state="unavailable", reason="Inventory is unavailable after shutdown."
                    ),
                    "active_snapshot_id": None,
                }
            )
            viewing = Capability(
                state="unavailable", reason="Simulated viewing is unavailable after shutdown."
            )
            exported = Capability(
                state="unavailable", reason="Local export cannot be observed after shutdown."
            )
        return result.model_copy(update={"viewing": viewing, "export": exported})


@dataclass(frozen=True, slots=True, repr=False)
class ApplicationComposition:
    app: FastAPI
    settings: Settings
    store: Store
    clock: Callable[[], datetime]
    registry: ReadinessRegistry
    reader: CompactInventoryReader
    signer: HmacPublicInventorySigner
    search: InventorySearchService
    details: InventoryDetailsService
    identity: IdentityService
    authorization: AuthorizationService
    sessions: SessionService
    preferences: PreferenceService
    shortlist: ShortlistService
    viewing_inventory: CompactViewingInventory
    viewing_options: CompactViewingOptions
    leads: LeadService
    drafts: DraftService
    confirmation: ConfirmationParticipant
    viewing: ViewingApplication
    projector: RuntimeCsvProjector
    provider: GeminiAdapter
    worker: BoundedServiceWorker
    assistant: AssistantService
    _lifetime: _Lifetime = field(repr=False)

    def admit_inventory(self) -> InventoryObservation:
        """Explicit read-only cold audit; never called by a buyer route or GET."""
        self._lifetime.require_live()
        self.identity.open_store()
        self.reader.refresh(self.registry)
        _, observation = self.registry.observed_snapshot()
        if observation is None:
            raise StoreError("STORE_UNAVAILABLE")
        return observation

    def close(self) -> bool:
        """Stop admission; never claim retirement while owned calls remain live."""
        if os.getpid() != self._lifetime._pid:
            raise StoreError("STORE_UNAVAILABLE")
        self.provider.stop()
        worker_closed = self.worker.close()
        if not worker_closed or self.provider.pending:
            return False
        self.viewing_inventory.close()
        self._lifetime.close()
        _withdraw_inventory(self.registry, self.reader)
        self._lifetime.release()
        return True

    async def shutdown(self) -> bool:
        """Bounded real settlement, not proof of remote cancellation or process exit."""
        if os.getpid() != self._lifetime._pid:
            raise StoreError("STORE_UNAVAILABLE")
        self.provider.stop()
        self.worker.close()
        deadline = monotonic() + self.settings.timeouts.operation_seconds
        await self.provider.close(timeout_seconds=max(0.0, deadline - monotonic()))
        while self.worker.pending and monotonic() < deadline:
            await asyncio.sleep(min(0.02, max(0.0, deadline - monotonic())))
        return self.close()


def build_composition(
    settings: Settings,
    store: Store,
    *,
    clock: Callable[[], datetime] = utc_now,
    event_sink: Callable[[RequestEvent], None] = emit_request_event,
    provider_transport: ProviderTransport | None = None,
) -> ApplicationComposition:
    """Wire a caller-opened Store without admitting, staging or activating it.

    A fixed clock or provider transport is a trusted Python test seam, never an
    HTTP input. Default composition uses the selected Developer API adapter.
    """
    if settings.store_path != store.path:
        raise RuntimeStartupError("RUNTIME_STORE_PATH_MISMATCH")
    if settings.runtime_boundary != store.boundary:
        raise RuntimeStartupError("RUNTIME_STORE_BOUNDARY_MISMATCH")
    utc_text(clock())
    lifetime = _Lifetime(store)
    registry = ReadinessRegistry()
    reader = _RuntimeReader(store, lifetime)
    signer = HmacPublicInventorySigner(store.generation)
    rules = ViewingRules(settings.policy)
    projector = RuntimeCsvProjector(store, clock=clock)

    def bound_opener(path: Path) -> Store:
        lifetime.require_live()
        try:
            if path != store.path:
                raise StoreError("STORE_UNAVAILABLE")
            lifetime.ensure_admitted()
            fresh = open_store(path, boundary=store.boundary)
            if (fresh.generation, fresh.schema_version, fresh.inventory_mode) != (
                store.generation,
                store.schema_version,
                store.inventory_mode,
            ):
                lifetime.close()
                raise StoreError("STORE_GENERATION_CHANGED")
            lifetime.require_live()
            return store
        except (OSError, StoreError, StorePathError):
            _withdraw_inventory(registry, reader)
            raise

    identity = IdentityService(settings, store_opener=bound_opener, clock=clock)
    readiness = _RuntimeReadiness(
        settings,
        registry,
        reader=reader,
        store=store,
        rules=rules,
        projector=projector,
        store_opener=bound_opener,
        clock=clock,
    )
    search = InventorySearchService(reader, signer, clock=clock)
    details = InventoryDetailsService(reader, eligibility=CompactPublicEligibility(rules))
    session_inventory = CompactSessionInventory(reader, signer)
    shortlist_inventory = CompactShortlistInventory(reader)
    # The legacy module builds an inert default app. Delay even that until this
    # explicit builder; importing runtime_app does not import app.main.
    from app.main import create_app

    application = create_app(
        settings,
        readiness=readiness,
        identity=identity,
        session_inventory=session_inventory,
        event_sink=event_sink,
    )
    authorization = cast(AuthorizationService, application.state.authorization)
    sessions = cast(SessionService, application.state.sessions)
    preferences = PreferenceService(authorization)
    shortlist = ShortlistService(authorization, inventory=shortlist_inventory)
    viewing_inventory = CompactViewingInventory(reader, rules=rules)
    viewing_options = CompactViewingOptions(reader, rules=rules, clock=clock)
    leads = LeadService(authorization, inventory=shortlist_inventory)
    drafts = DraftService(authorization, inventory=viewing_inventory)
    confirmation = ConfirmationParticipant(
        drafts, leads=LeadParticipant(inventory=shortlist_inventory)
    )
    viewing = ViewingApplication(confirmation, projector=projector)
    provider = GeminiAdapter(
        settings,
        GoogleGenAITransport(settings) if provider_transport is None else provider_transport,
        readiness=registry,
        utc_now=clock,
    )
    worker = BoundedServiceWorker()
    assistant = AssistantService(
        sessions,
        provider,
        search,
        details,
        worker,
        preferences=preferences,
        shortlist=shortlist,
        confirmation=confirmation,
        leads=leads,
        drafts=drafts,
    )
    application.include_router(inventory_router(search, details))
    application.include_router(preference_router(preferences))
    application.include_router(shortlist_router(shortlist))
    application.include_router(lead_router(leads, projector=projector))
    application.include_router(viewing_router(viewing, options=viewing_options))
    application.include_router(
        assistant_router(
            assistant, settings=settings, worker=worker, leads=leads, projector=projector
        )
    )
    composition = ApplicationComposition(
        application,
        settings,
        store,
        clock,
        registry,
        reader,
        signer,
        search,
        details,
        identity,
        authorization,
        sessions,
        preferences,
        shortlist,
        viewing_inventory,
        viewing_options,
        leads,
        drafts,
        confirmation,
        viewing,
        projector,
        provider,
        worker,
        assistant,
        lifetime,
    )
    application.state.composition = composition
    application.state.preferences = preferences
    application.state.shortlist = shortlist
    application.state.leads = leads
    application.state.drafts = drafts
    application.state.confirmation = confirmation
    application.state.viewing = viewing
    application.state.viewing_options = viewing_options
    application.state.csv_projector = projector
    application.state.assistant = assistant
    previous_lifespan = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            async with previous_lifespan(app):
                yield
        finally:
            if not await composition.shutdown():
                raise RuntimeStartupError("RUNTIME_SHUTDOWN_PENDING")

    application.router.lifespan_context = lifespan
    return composition


def create_runtime_app(
    settings: Settings | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
    event_sink: Callable[[RequestEvent], None] = emit_request_event,
) -> FastAPI:
    """Synchronous noncreating startup; call before starting the server event loop."""
    configured = settings if settings is not None else load_settings()
    if configured.store_path is None or configured.runtime_boundary is None:
        raise RuntimeStartupError("RUNTIME_STORE_NOT_CONFIGURED")
    try:
        store = open_store(configured.store_path, boundary=configured.runtime_boundary)
    except (OSError, StoreError, StorePathError):
        raise RuntimeStartupError("RUNTIME_STORE_UNAVAILABLE") from None
    composition = build_composition(configured, store, clock=clock, event_sink=event_sink)
    try:
        composition.admit_inventory()
    except (OSError, StoreError, StorePathError, ValueError):
        # Existing identity/memory remain usable where the Store is healthy.
        # The real Inventory services keep their admission errors, never empty data.
        _withdraw_inventory(composition.registry, composition.reader)
    except BaseException:
        composition.close()
        raise
    try:
        result = composition.projector.repair_once()
        composition.app.state.csv_startup_result = result
        if not startup_admitted(result):
            raise RuntimeStartupError("CSV_STARTUP_AUDIT_UNRESOLVED")
    except BaseException:
        composition.close()
        raise
    return composition.app


def main() -> None:
    import uvicorn

    settings = load_settings()
    if settings.profile != "local_http":
        raise RuntimeStartupError("RUNTIME_HTTP_ENTRYPOINT_REQUIRES_LOCAL_HTTP")
    application = create_runtime_app(settings)
    composition = cast(ApplicationComposition, application.state.composition)
    try:
        uvicorn.run(
            application,
            host=settings.bind_host,
            port=settings.bind_port,
            proxy_headers=False,
            access_log=False,
        )
    finally:
        if not composition.close():
            raise RuntimeStartupError("RUNTIME_SHUTDOWN_PENDING")


if __name__ == "__main__":
    main()
