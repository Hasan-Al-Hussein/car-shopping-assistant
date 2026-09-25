"""Read-only capability observations. Health never invokes a provider or a writer."""

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Literal, Self

from pydantic import model_validator

from app.api.schemas.capabilities import Capability, HealthResult
from app.api.schemas.common import Digest, Id, Revision
from app.core.config import FrozenSettings, Settings
from app.database.paths import StorePathError
from app.database.store import Store, StoreError, assert_outside_write_transaction, open_store

# Bound the process-local replay fence without evicting remembered generations.
# Exhaustion needs coordinated observer quiescence and a fresh registry, not silent reuse.
MAX_RETIRED_INVENTORY_GENERATIONS = 64


class ProviderObservation(FrozenSettings):
    state: Literal["ready", "unavailable"]
    observed_at: datetime

    @model_validator(mode="after")
    def utc_observation(self) -> Self:
        if self.observed_at.utcoffset() != timedelta(0):
            raise ValueError("UTC_OBSERVATION_REQUIRED")
        return self


class DependencySnapshot(FrozenSettings):
    """Published by later adapters after actual observations, never by a buyer request."""

    inventory: Literal["unconfigured", "ready", "unavailable", "degraded"] = "unconfigured"
    active_snapshot_id: Digest | None = None
    viewing: Literal["unconfigured", "ready", "unavailable"] = "unconfigured"
    export: Literal["unconfigured", "ready", "unavailable", "degraded"] = "unconfigured"
    provider: ProviderObservation | None = None

    @model_validator(mode="after")
    def snapshot_identity(self) -> Self:
        if (self.inventory in {"ready", "degraded"}) != (self.active_snapshot_id is not None):
            raise ValueError("INVENTORY_OBSERVATION_REQUIRES_EXACT_SNAPSHOT")
        return self


class InventoryObservation(FrozenSettings):
    """Internal complete active-state observation, not authority to activate inventory."""

    generation: Id
    active_revision: Revision
    snapshot_id: Digest | None = None
    index_version: Digest | None = None
    mode: Literal["fts5", "bounded_lexical"] | None = None

    @model_validator(mode="after")
    def active_tuple(self) -> Self:
        if self.snapshot_id is None:
            if self.active_revision != 0 or self.index_version is not None or self.mode is not None:
                raise ValueError("INVENTORY_ABSENCE_REQUIRES_ZERO_REVISION")
        elif self.active_revision < 1 or self.index_version is None or self.mode is None:
            raise ValueError("INVENTORY_OBSERVATION_REQUIRES_COMPLETE_ACTIVE_TUPLE")
        return self


class InventoryObservationConflict(ValueError):
    """A stale/incompatible observation was rejected; the current one remains intact."""


class ReadinessRegistry:
    """Atomic independent updates and serialized fresh inventory observe/merge.

    Lock order is inventory-refresh then snapshot. Update callbacks must not reenter
    the registry; observation callbacks must not recursively refresh inventory.
    Only the inventory callback performs I/O, outside the snapshot lock.
    """

    def __init__(self, initial: DependencySnapshot | None = None) -> None:
        self._value = initial or DependencySnapshot()
        self._lock = Lock()
        self._inventory_lock = Lock()
        self._last_inventory: InventoryObservation | None = None
        self._retired_generations: set[str] = set()

    def snapshot(self) -> DependencySnapshot:
        with self._lock:
            return self._value

    def observed_snapshot(self) -> tuple[DependencySnapshot, InventoryObservation | None]:
        """Capture published state and its generation watermark under one lock."""
        with self._lock:
            return self._value, self._last_inventory

    @staticmethod
    def _same_inventory(left: DependencySnapshot, right: DependencySnapshot) -> bool:
        return (left.inventory, left.active_snapshot_id) == (
            right.inventory,
            right.active_snapshot_id,
        )

    def publish(self, value: DependencySnapshot, *, expected: DependencySnapshot) -> bool:
        """Compare-and-swap a prior snapshot; inventory changes require fresh observation."""
        with self._lock:
            if self._value is not expected:
                return False
            if not self._same_inventory(value, expected):
                raise ValueError("INVENTORY_REQUIRES_COORDINATED_REFRESH")
            self._value = value
            return True

    def update(self, change: Callable[[DependencySnapshot], DependencySnapshot]) -> None:
        """Merge provider/export/viewing using the current value; callback is short and pure."""
        with self._lock:
            value = change(self._value)
            if not self._same_inventory(value, self._value):
                raise ValueError("INVENTORY_REQUIRES_COORDINATED_REFRESH")
            self._value = value

    def refresh_inventory(self, observe: Callable[[], InventoryObservation]) -> None:
        """Serialize a NEW authoritative Store read with inventory-only publication.

        Call only after activation's write has returned. Never pass cached/precomputed
        observations. Failure is observation failure, never rollback/noncommit proof.
        The private watermark survives failures; no-active/lower revisions and retired
        generations cannot replace a previously observed newer active state.
        """
        assert_outside_write_transaction()
        with self._inventory_lock:
            try:
                observed = observe()
                with self._lock:
                    previous = self._last_inventory
                    if observed.generation in self._retired_generations:
                        raise InventoryObservationConflict("INVENTORY_GENERATION_RETIRED")
                    if previous is not None and previous.generation == observed.generation:
                        if observed.active_revision < previous.active_revision:
                            raise InventoryObservationConflict("INVENTORY_OBSERVATION_STALE")
                        if (
                            observed.active_revision == previous.active_revision
                            and observed != previous
                        ):
                            raise InventoryObservationConflict(
                                "INVENTORY_REVISION_CONTENT_CONFLICT"
                            )
                    if (
                        previous is not None
                        and previous.generation != observed.generation
                        and len(self._retired_generations) >= MAX_RETIRED_INVENTORY_GENERATIONS
                    ):
                        raise RuntimeError("INVENTORY_GENERATION_FENCE_EXHAUSTED")
                    state = (
                        "unconfigured"
                        if observed.snapshot_id is None
                        else ("ready" if observed.mode == "fts5" else "degraded")
                    )
                    data = self._value.model_dump()
                    data.update(inventory=state, active_snapshot_id=observed.snapshot_id)
                    value = DependencySnapshot.model_validate(data)
                    if previous is not None and previous.generation != observed.generation:
                        self._retired_generations.add(previous.generation)
                    self._last_inventory = observed
                    self._value = value
            except InventoryObservationConflict:
                raise
            except Exception:
                with self._lock:
                    data = self._value.model_dump()
                    data.update(inventory="unavailable", active_snapshot_id=None)
                    self._value = DependencySnapshot.model_validate(data)
                raise


class ReadinessService:
    def __init__(
        self,
        settings: Settings,
        registry: ReadinessRegistry,
        *,
        store_opener: Callable[[Path], Store] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        can_write: Callable[[Path], bool] = lambda path: (
            os.access(path, os.W_OK) and os.access(path.parent, os.W_OK)
        ),
    ) -> None:
        self.settings = settings
        self.registry = registry
        boundary = settings.runtime_boundary

        def configured_opener(path: Path) -> Store:
            if boundary is None:
                raise StoreError("STORE_UNAVAILABLE")
            return open_store(path, boundary=boundary)

        self._open_store = configured_opener if store_opener is None else store_opener
        self._clock = clock
        self._can_write = can_write

    def _store(self) -> tuple[Capability, str | None]:
        path = self.settings.store_path
        if path is None:
            return (
                Capability(state="unconfigured", reason="Local saved state is not configured."),
                None,
            )
        try:
            store = self._open_store(path)
            if not self._can_write(store.path):
                return (
                    Capability(state="degraded", reason="Local saved state is not writable."),
                    store.generation,
                )
        except (OSError, StoreError, StorePathError):
            return (
                Capability(state="unavailable", reason="Local saved state is unavailable."),
                None,
            )
        return (
            Capability(
                state="ready",
                reason="Local saved state passed read checks; writes are checked on submission.",
            ),
            store.generation,
        )

    def _assistant(self, snapshot: DependencySnapshot) -> Capability:
        if not self.settings.assistant_enabled:
            return Capability(state="unconfigured", reason="Assistant support is disabled.")
        if not self.settings.provider_configured:
            return Capability(state="unconfigured", reason="Assistant access is not configured.")
        observation = snapshot.provider
        if observation is None:
            return Capability(
                state="degraded", reason="Assistant access is configured but not yet verified."
            )
        age = (self._clock() - observation.observed_at).total_seconds()
        if not 0 <= age <= self.settings.timeouts.provider_observation_seconds:
            return Capability(
                state="degraded", reason="Assistant availability needs a fresh observation."
            )
        if observation.state == "unavailable":
            return Capability(
                state="unavailable", reason="Assistant support is temporarily unavailable."
            )
        return Capability(state="ready", reason="Assistant access was recently observed.")

    def health(self) -> HealthResult:
        """Called in a worker thread; the BE-01 read-only opener never creates a store."""
        snapshot, observed = self.registry.observed_snapshot()
        store, generation = self._store()
        if observed is not None and generation is not None and observed.generation != generation:
            data = snapshot.model_dump()
            data.update(inventory="unavailable", active_snapshot_id=None)
            snapshot = DependencySnapshot.model_validate(data)
        inventory_reasons = {
            "ready": None,
            "unconfigured": "Inventory has not been activated.",
            "unavailable": "Inventory is temporarily unavailable.",
            "degraded": "Previously loaded inventory is available with limitations.",
        }
        inventory = Capability(
            state=snapshot.inventory, reason=inventory_reasons[snapshot.inventory]
        )
        if snapshot.viewing == "unconfigured":
            viewing = Capability(
                state="unconfigured", reason="Simulated viewing rules are not configured."
            )
        elif snapshot.viewing == "unavailable":
            viewing = Capability(state="unavailable", reason="Simulated viewing is unavailable.")
        elif store.state != "ready" or inventory.state != "ready":
            viewing = Capability(
                state="unavailable",
                reason="Simulated viewing needs current inventory and local saved state.",
            )
        else:
            viewing = Capability(
                state="ready", reason="Simulated viewing only; no real reservation."
            )
        export_reasons = {
            "ready": None,
            "unconfigured": "Local export is not configured.",
            "unavailable": "Local export needs repair; saved enquiries remain separate.",
            "degraded": "Local export is pending reconciliation.",
        }
        export = Capability(state=snapshot.export, reason=export_reasons[snapshot.export])
        if export.state == "ready" and store.state != "ready":
            export = Capability(
                state="degraded",
                reason="Local export cannot be reconciled while saved state is unavailable.",
            )
        return HealthResult(
            inventory=inventory,
            store=store,
            viewing=viewing,
            export=export,
            assistant=self._assistant(snapshot),
            active_snapshot_id=snapshot.active_snapshot_id,
        )
