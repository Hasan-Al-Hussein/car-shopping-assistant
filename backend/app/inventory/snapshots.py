"""Local operator staging/activation and coherent read-only inventory observations."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.api.schemas.common import Revision
from app.core.readiness import InventoryObservation, ReadinessRegistry
from app.database.models import (
    ActiveInventory,
    AttributeEvidence,
    InventorySnapshot,
    InventorySnapshotPayload,
    ListingVersion,
)
from app.database.paths import RuntimeBoundary
from app.database.store import Store, open_store
from app.inventory.extraction import ExtractedCandidate
from app.inventory.index_storage import insert_index
from app.inventory.lexical_index import IndexMode
from app.inventory.references import ImmutableInventoryRef
from app.inventory.resource_lineage import ReviewedResourceMapping
from app.inventory.snapshot_codec import ListingRow, digest_text
from app.inventory.snapshot_storage import (
    check_profile,
    insert_lineage,
    load_dependencies,
    load_stage,
    load_stage_set,
    snapshot_values,
    validate_stored,
)
from app.inventory.staging_plan import (
    STAGING_POLICY_VERSION,
    PreparedStage,
    prepare_stage,
    stage_payload,
    validate_stage,
)

REVISION = TypeAdapter(Revision)


@dataclass(frozen=True)
class StageReceipt:
    snapshot_id: str
    index_version: str
    payload_sha256: str
    listing_count: int
    evidence_count: int
    reused: bool


@dataclass(frozen=True)
class ActiveSnapshot:
    observation: InventoryObservation
    stage: PreparedStage | None = field(repr=False)


@dataclass(frozen=True)
class ListingLookup:
    ref: ImmutableInventoryRef
    state: Literal["current", "historical", "missing"]
    listing: ListingRow | None = field(repr=False)


def _no_checkpoint(phase: str) -> None:
    """Test seam for bounded failure/interleaving evidence; production does no work."""


class InventoryRepository:
    """An explicit callable, never registered as a buyer write route."""

    def __init__(
        self,
        store: Store,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        _checkpoint: Callable[[str], None] = _no_checkpoint,
    ) -> None:
        if store.schema_version != "0002" or store.inventory_mode not in {
            "fts5",
            "bounded_lexical",
        }:
            raise ValueError("INVENTORY_REQUIRES_EXPLICIT_SCHEMA_UPGRADE")
        self.store = store
        self.mode: IndexMode = store.inventory_mode
        self._clock = clock
        self._checkpoint = _checkpoint

    def prepare(
        self,
        candidate: ExtractedCandidate,
        *,
        policy_version: str,
        mappings: tuple[ReviewedResourceMapping, ...] = (),
    ) -> PreparedStage:
        plan = prepare_stage(candidate, policy_version=policy_version, mappings=mappings)
        if plan.index.mode != self.mode:
            raise ValueError("INVENTORY_CAPABILITY_PROFILE_MISMATCH")
        return plan

    def stage(self, plan: PreparedStage) -> StageReceipt:
        validate_stage(plan)
        if plan.index.mode != self.mode:
            raise ValueError("INVENTORY_CAPABILITY_PROFILE_MISMATCH")
        now = self._clock()
        if now.utcoffset() != timedelta(0):
            raise ValueError("INVENTORY_CLOCK_UTC_REQUIRED")
        created_at = now.isoformat(timespec="microseconds").replace("+00:00", "Z")
        payload = stage_payload(plan)
        dependencies = self.store.read(lambda session: load_dependencies(session, plan, self.mode))
        self._checkpoint("stage.prepared")

        def write(session: Session) -> StageReceipt:
            check_profile(session, self.mode)
            reused = session.get(InventorySnapshot, plan.index.snapshot_id) is not None
            if not reused:
                session.add(InventorySnapshot(**snapshot_values(plan), created_at=created_at))
                session.flush()
                session.add(
                    InventorySnapshotPayload(
                        snapshot_id=plan.index.snapshot_id,
                        serialization_version=STAGING_POLICY_VERSION,
                        payload_sha256=digest_text(payload),
                        payload_json=json.loads(payload),
                    )
                )
                session.flush()
                self._checkpoint("stage.snapshot")
                for listing in plan.candidate.listings:
                    session.add(
                        ListingVersion(
                            **listing.ref.model_dump(),
                            source_row=listing.source_row,
                            original_json=json.loads(listing.original_json),
                            normalized_json=json.loads(listing.normalized_json),
                        )
                    )
                session.flush()
                self._checkpoint("stage.listings")
                for evidence in plan.candidate.evidence:
                    session.add(
                        AttributeEvidence(
                            id=evidence.evidence_id,
                            **evidence.ref.model_dump(),
                            attribute=evidence.attribute,
                            raw_locator_json=json.loads(evidence.raw_locator_json),
                            normalized_json=json.loads(evidence.normalized_json),
                            status=evidence.status,
                            extraction_version=evidence.extraction_version,
                        )
                    )
                session.flush()
                self._checkpoint("stage.evidence")
                insert_lineage(session, plan, created_at, dependencies)
                insert_index(session, plan.index)
                self._checkpoint("stage.index")
            validate_stored(session, plan, writable=True, dependencies=dependencies)
            self._checkpoint("stage.validated")
            return StageReceipt(
                plan.index.snapshot_id,
                plan.index.version,
                digest_text(payload),
                len(plan.candidate.listings),
                len(plan.candidate.evidence),
                reused,
            )

        result = self.store.write(write)
        self._checkpoint("stage.committed")
        return result

    def snapshot(self, snapshot_id: str) -> PreparedStage | None:
        return self.store.read(lambda session: load_stage(session, snapshot_id, self.mode))

    def activate(self, snapshot_id: str, *, expected_revision: int) -> InventoryObservation:
        REVISION.validate_python(expected_revision, strict=True)
        loaded = self.store.read(lambda session: load_stage_set(session, snapshot_id, self.mode))
        if loaded is None:
            raise ValueError("INVENTORY_SNAPSHOT_NOT_STAGED")
        plan, dependencies = loaded
        self._checkpoint("activation.prepared")

        def write(session: Session) -> InventoryObservation:
            validate_stored(session, plan, writable=True, dependencies=dependencies)
            active = session.get(ActiveInventory, 1)
            revision = 0 if active is None else active.revision
            if revision != expected_revision:
                raise ValueError("INVENTORY_ACTIVATION_REVISION_CONFLICT")
            if active is not None and active.snapshot_id == snapshot_id:
                if active.index_version != plan.index.version or revision < 1:
                    raise ValueError("INVENTORY_ACTIVE_TUPLE_INVALID")
                return self._observation(active)
            next_revision = REVISION.validate_python(revision + 1, strict=True)
            if active is None:
                active = ActiveInventory(
                    id=1,
                    snapshot_id=snapshot_id,
                    index_version=plan.index.version,
                    revision=next_revision,
                )
                session.add(active)
            else:
                active.snapshot_id = snapshot_id
                active.index_version = plan.index.version
                active.revision = next_revision
            session.flush()
            self._checkpoint("activation.pointer")
            return self._observation(active)

        result = self.store.write(write)
        self._checkpoint("activation.committed")
        return result

    def _observation(self, active: ActiveInventory | None) -> InventoryObservation:
        return InventoryObservation(
            generation=self.store.generation,
            active_revision=0 if active is None else active.revision,
            snapshot_id=None if active is None else active.snapshot_id,
            index_version=None if active is None else active.index_version,
            mode=None if active is None else self.mode,
        )

    def active(self) -> ActiveSnapshot:
        def read(session: Session) -> ActiveSnapshot:
            check_profile(session, self.mode)
            active = session.get(ActiveInventory, 1)
            self._checkpoint("read.active_selected")
            observation = self._observation(active)
            if active is None:
                return ActiveSnapshot(observation, None)
            plan = load_stage(session, active.snapshot_id, self.mode)
            if plan is None or plan.index.version != active.index_version:
                raise ValueError("INVENTORY_ACTIVE_TUPLE_INVALID")
            return ActiveSnapshot(observation, plan)

        return self.store.read(read)

    def listing(self, ref: ImmutableInventoryRef) -> ListingLookup:
        ref = ImmutableInventoryRef.model_validate(ref.model_dump())

        def read(session: Session) -> ListingLookup:
            plan = load_stage(session, ref.snapshot_id, self.mode)
            if plan is None:
                return ListingLookup(ref, "missing", None)
            listing = next((item for item in plan.candidate.listings if item.ref == ref), None)
            if listing is None:
                return ListingLookup(ref, "missing", None)
            active = session.get(ActiveInventory, 1)
            state: Literal["current", "historical"] = "historical"
            if active is not None and active.snapshot_id == ref.snapshot_id:
                if active.index_version != plan.index.version or active.revision < 1:
                    raise ValueError("INVENTORY_ACTIVE_TUPLE_INVALID")
                state = "current"
            return ListingLookup(ref, state, listing)

        return self.store.read(read)

    def refresh(self, registry: ReadinessRegistry) -> None:
        """Separate from commit; failure is observation uncertainty, never rollback."""
        registry.refresh_inventory(lambda: observe_inventory(self.store.path, boundary=self.store.boundary))


def observe_inventory(path: Path, *, boundary: RuntimeBoundary) -> InventoryObservation:
    """NEW noncreating open/read, invoked inside the shared refresh coordinator."""
    return InventoryRepository(open_store(path, boundary=boundary)).active().observation
