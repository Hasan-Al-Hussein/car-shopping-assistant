"""Read-only capability observations and the application-owned CSV attempt record."""

from collections.abc import Callable
from datetime import datetime
from threading import Lock

from sqlalchemy.orm import Session

from app.api.schemas.capabilities import Capability
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.database.models import (
    ActiveInventory,
    ActiveRules,
    InventorySnapshot,
    InventoryStorageProfile,
)
from app.database.store import Store, StoreError
from app.inventory.staging_plan import STAGING_POLICY_VERSION
from app.leads import projection_repository
from app.leads.projection import CsvProjector, ProjectionRun
from app.viewings.draft_configuration import load_configuration
from app.viewings.scheduling import ViewingRules


class RuntimeCsvProjector(CsvProjector):
    """Same real projector, retaining only a bounded last attempt for health."""

    def __init__(self, store: Store, *, clock: Callable[[], datetime]) -> None:
        super().__init__(store, clock=clock)
        self._observation_lock = Lock()
        self._last_attempt: ProjectionRun | None = None

    def repair_once(self, *, reconcile_from_generation: str | None = None) -> ProjectionRun:
        try:
            result = super().repair_once(reconcile_from_generation=reconcile_from_generation)
        except Exception:
            with self._observation_lock:
                self._last_attempt = None
            raise
        with self._observation_lock:
            self._last_attempt = result
        return result

    def capability(self) -> Capability:
        def read(db: Session) -> tuple[str, int, int | None] | None:
            state = projection_repository.state(db, self.store.generation)
            return (
                None
                if state is None
                else (state.state, state.canonical_version, state.exported_version)
            )

        try:
            current = self.store.read(read)
        except (StoreError, OSError, ValueError):
            return Capability(
                state="unavailable",
                reason="Local export needs repair; saved enquiries remain separate.",
            )
        with self._observation_lock:
            attempt = self._last_attempt
        if attempt is None:
            return Capability(state="degraded", reason="Local export needs an explicit audit.")
        if attempt.state == "failed" or current is not None and current[0] == "failed":
            return Capability(
                state="unavailable",
                reason="Local export needs repair; saved enquiries remain separate.",
            )
        if current is None and attempt.state == "empty":
            return Capability(state="ready", reason="No saved enquiry needs export.")
        if (
            current is not None
            and current[0] == "current"
            and attempt.state == "current"
            and attempt.status_persisted
            and attempt.store_generation == self.store.generation
            and current[1] == current[2] == attempt.canonical_version == attempt.published_version
        ):
            return Capability(state="ready", reason=None)
        return Capability(state="degraded", reason="Local export is pending reconciliation.")


def viewing_capability(
    store: Store,
    rules: ViewingRules,
    expected: InventoryObservation | None,
) -> Capability:
    """Observe actual active configuration; never calculate slots, admit or activate."""
    if expected is None or expected.snapshot_id is None:
        return Capability(state="unavailable", reason="Simulated viewing needs current inventory.")

    def read(db: Session) -> bool:
        active = db.get(ActiveInventory, 1)
        profile = db.get(InventoryStorageProfile, 1)
        if active is None or profile is None:
            raise ApiFailure("RULES_UNAVAILABLE")
        observed = InventoryObservation.model_validate(
            dict(
                generation=store.generation,
                snapshot_id=active.snapshot_id,
                index_version=active.index_version,
                active_revision=active.revision,
                mode=profile.mode,
            )
        )
        snapshot = db.get(InventorySnapshot, active.snapshot_id)
        if (
            observed != expected
            or snapshot is None
            or snapshot.index_version != observed.index_version
        ):
            raise ApiFailure("SNAPSHOT_STALE")
        config = db.get(ActiveRules, 1)
        if config is None:
            return False
        configured = load_configuration(
            db, config.version, rules=rules, observation=observed, namespace=snapshot.namespace
        )
        stage = (
            db.connection()
            .exec_driver_sql(
                "SELECT serialization_version,CASE WHEN json_valid(payload_json) THEN "
                "CASE WHEN json_type(payload_json,'$.mapping_digest')='text' "
                "AND length(json_extract(payload_json,'$.mapping_digest'))=64 "
                "THEN json_extract(payload_json,'$.mapping_digest') END END "
                "FROM inventory_snapshot_payloads WHERE snapshot_id=?",
                (observed.snapshot_id,),
            )
            .first()
        )
        if (
            stage is None
            or stage[0] != STAGING_POLICY_VERSION
            or stage[1] != configured.mapping_digest
        ):
            raise ApiFailure("RULES_UNAVAILABLE")
        return True

    try:
        configured = store.read(read)
    except (ApiFailure, StoreError, OSError, ValueError):
        return Capability(
            state="unavailable", reason="Simulated viewing configuration is unavailable."
        )
    return (
        Capability(state="ready", reason="Simulated viewing only; no real reservation.")
        if configured
        else Capability(
            state="unconfigured",
            reason="Simulated viewing rules are not configured.",
        )
    )
