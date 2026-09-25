"""Small trusted batch port; real BE07 adapter and integrity proof remain required."""

from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import ListingSummary
from app.core.errors import ApiFailure
from app.database.models import ActiveInventory, ListingVersion
from app.database.store import assert_outside_write_transaction
from app.identity.authorization import OwnerUnit
from app.inventory.references import ImmutableInventoryRef


@dataclass(frozen=True)
class ReferenceObservation:
    ref: ImmutableInventoryRef
    state: Literal["current", "historical", "missing"]
    listing: ListingSummary | None


@dataclass(frozen=True)
class ReferenceBatch:
    generation: str
    active_snapshot_id: str | None
    active_revision: int | None
    active_index_version: str | None
    items: tuple[ReferenceObservation, ...]
    # Opaque materialized identity understood only by the trusted adapter's recheck.
    # No ORM, database connection, secret, callable or mutable global cache may escape.
    identity: tuple[str, ...]


class ShortlistInventory(Protocol):
    def read(self, refs: tuple[ImmutableInventoryRef, ...]) -> ReferenceBatch:
        """One coherent <=50 exact-ref historical/current batch outside writes.

        Storage/projection failure is an error, never a made-up missing result.
        All classifications and summaries retain the requested original refs.
        """
        ...

    def recheck(self, db: Session, prepared: ReferenceBatch) -> None:
        """Only bounded identity SQL inside the existing unit; no Store/network/full audit.

        Bind the reviewed immutable projections/publication identity underlying read.
        Caller rechecks generation/active pointer/exact refs. This callback supplies
        the BE07-specific integrity checks; a no-op production adapter is forbidden.
        """
        ...


def key(ref: InventoryRef) -> tuple[str, str, str]:
    return ref.namespace, ref.snapshot_id, ref.source_id


def prepare(
    gateway: ShortlistInventory | None, refs: tuple[ImmutableInventoryRef, ...], generation: str
) -> ReferenceBatch:
    assert_outside_write_transaction()
    if gateway is None:
        raise ApiFailure("STORE_UNAVAILABLE")
    if not 1 <= len(refs) <= 50:
        raise ApiFailure("VALIDATION_ERROR")
    batch = gateway.read(refs)
    if (
        type(batch) is not ReferenceBatch
        or batch.generation != generation
        or type(batch.items) is not tuple
        or len(batch.items) != len(refs)
        or type(batch.identity) is not tuple
        or len(batch.identity) > 256
        or any(type(part) is not str or len(part) > 512 for part in batch.identity)
    ):
        raise ApiFailure("STORE_UNAVAILABLE")
    if (batch.active_snapshot_id is None) != (batch.active_revision is None) or (
        batch.active_snapshot_id is None
    ) != (batch.active_index_version is None):
        raise ApiFailure("STORE_UNAVAILABLE")
    copied = []
    for requested, item in zip(refs, batch.items, strict=True):
        if (
            type(item) is not ReferenceObservation
            or key(item.ref) != key(requested)
            or item.state not in {"current", "historical", "missing"}
            or (item.state == "missing") != (item.listing is None)
        ):
            raise ApiFailure("STORE_UNAVAILABLE")
        listing = (
            None
            if item.listing is None
            else ListingSummary.model_validate(item.listing.model_dump(mode="json"))
        )
        if (
            listing is not None
            and key(listing.ref) != key(requested)
            or item.state == "current"
            and requested.snapshot_id != batch.active_snapshot_id
            or item.state == "historical"
            and requested.snapshot_id == batch.active_snapshot_id
        ):
            raise ApiFailure("STORE_UNAVAILABLE")
        copied.append(
            ReferenceObservation(
                ImmutableInventoryRef.model_validate(requested.model_dump()), item.state, listing
            )
        )
    return ReferenceBatch(
        batch.generation,
        batch.active_snapshot_id,
        batch.active_revision,
        batch.active_index_version,
        tuple(copied),
        batch.identity,
    )


def recheck(
    unit: OwnerUnit, batch: ReferenceBatch, generation: str, gateway: ShortlistInventory | None
) -> None:
    if gateway is None or batch.generation != generation:
        raise ApiFailure("STORE_GENERATION_CHANGED")
    active = unit.db.get(ActiveInventory, 1)
    current = (
        (None, None, None)
        if active is None
        else (active.snapshot_id, active.revision, active.index_version)
    )
    if current != (batch.active_snapshot_id, batch.active_revision, batch.active_index_version):
        raise ApiFailure("SNAPSHOT_STALE")
    for item in batch.items:
        if (
            item.state != "missing"
            and unit.db.scalar(
                select(ListingVersion.source_id).where(
                    ListingVersion.namespace == item.ref.namespace,
                    ListingVersion.snapshot_id == item.ref.snapshot_id,
                    ListingVersion.source_id == item.ref.source_id,
                )
            )
            is None
        ):
            raise ApiFailure("SNAPSHOT_STALE")
    gateway.recheck(unit.db, batch)
