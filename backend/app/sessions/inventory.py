"""Injected Inventory seam. No unverified production signer or search is supplied."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.inventory import PresentationProof
from app.core.errors import ApiFailure
from app.database.models import ActiveInventory, InventorySnapshot, ListingVersion
from app.identity.authorization import OwnerUnit
from app.inventory.references import ImmutableInventoryRef


@dataclass(frozen=True)
class InventoryAdmission:
    generation: str
    snapshot_id: str
    active_revision: int
    index_version: str
    refs: tuple[ImmutableInventoryRef, ...]
    identity: tuple[str, ...]


class SessionInventory(Protocol):
    """Trusted injection, never request/model input.

    prepare validates retained staged data through Inventory's real read contract,
    outside an owned write. verify is pure bounded signature/time validation,
    also outside the write; the service rechecks time locally after acquiring
    the write lock. recheck consumes the exact I5 identity inside that same write.
    """

    def verify(self, proof: PresentationProof, *, now: datetime) -> None: ...

    def prepare(
        self, refs: tuple[ImmutableInventoryRef, ...], *, snapshot_id: str
    ) -> InventoryAdmission: ...

    def recheck(self, db: Session, prepared: InventoryAdmission) -> None: ...


def check_admission(
    unit: OwnerUnit,
    prepared: InventoryAdmission,
    *,
    generation: str,
    snapshot_id: str,
    refs: tuple[ImmutableInventoryRef, ...],
    gateway: SessionInventory | None,
) -> None:
    """Recheck exact immutable identities; never decode a stage under a write lock."""
    if (
        type(prepared) is not InventoryAdmission
        or prepared.generation != generation
        or prepared.snapshot_id != snapshot_id
        or prepared.refs != refs
        or type(prepared.identity) is not tuple
        or not 1 <= len(prepared.identity) <= 128
        or any(type(part) is not str or not 1 <= len(part) <= 512 for part in prepared.identity)
    ):
        raise ApiFailure("SNAPSHOT_STALE")
    active = unit.db.get(ActiveInventory, 1)
    if (
        active is None
        or active.snapshot_id != snapshot_id
        or active.revision != prepared.active_revision
        or active.index_version != prepared.index_version
        or active.revision < 1
    ):
        raise ApiFailure("SNAPSHOT_STALE")
    snapshot = unit.db.get(InventorySnapshot, snapshot_id)
    if snapshot is None:
        raise ApiFailure("SNAPSHOT_STALE")
    for ref in refs:
        if ref.snapshot_id != snapshot_id or ref.namespace != snapshot.namespace:
            raise ApiFailure("PRESENTATION_INVALID")
        if (
            unit.db.scalar(
                select(ListingVersion.source_id).where(
                    ListingVersion.namespace == ref.namespace,
                    ListingVersion.snapshot_id == ref.snapshot_id,
                    ListingVersion.source_id == ref.source_id,
                )
            )
            is None
        ):
            raise ApiFailure("NOT_FOUND")
    if gateway is None:
        raise ApiFailure("STORE_UNAVAILABLE")
    gateway.recheck(unit.db, prepared)
