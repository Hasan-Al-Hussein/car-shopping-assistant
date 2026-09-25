"""Trusted compact viewing admission; no real adapter is selected by this module."""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.common import Id, InventoryRef
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.database.models import (
    ActiveInventory,
    ActiveRules,
    InventorySnapshot,
    InventoryStorageProfile,
    ListingResourceMapping,
    ListingVersion,
    StoreMetadata,
    VehicleResource,
)
from app.database.store import assert_outside_write_transaction
from app.identity.authorization import OwnerUnit
from app.inventory.references import ImmutableInventoryRef
from app.sessions.repository import valid_id
from app.viewings.draft_configuration import eligibility_version, load_configuration
from app.viewings.scheduling import ViewingRules


@dataclass(frozen=True)
class PreparedViewing:
    generation: Id
    ref: ImmutableInventoryRef
    active_revision: int
    index_version: str
    resource_id: Id
    mapping_version: str
    eligibility_version: str
    configuration_version: str
    configuration_revision: int
    identity: tuple[str, ...]


class DraftInventory(Protocol):
    def prepare(self, ref: ImmutableInventoryRef) -> PreparedViewing:
        """Outside write: admit exact current ref using BE13 explicit demo eligibility.

        Include accepted projection, mapping, allowlist and config identities; an
        ineligible/unavailable dependency raises a closed error, never defaults.
        """
        ...

    def recheck(self, db: Session, prepared: PreparedViewing) -> None:
        """Bounded identity SQL in caller unit only. No Store/file/network/full decode.

        Must bind the compact accepted projection, allowlist and configuration
        behind preparation. A no-op production implementation is prohibited.
        """
        ...


def prepare(gateway: DraftInventory | None, ref: InventoryRef, generation: str) -> PreparedViewing:
    assert_outside_write_transaction()
    if gateway is None:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    exact = ImmutableInventoryRef.model_validate(ref.model_dump())
    value = gateway.prepare(exact)
    if (
        type(value) is not PreparedViewing
        or value.generation != generation
        or value.ref != exact
        or type(value.active_revision) is not int
        or not 1 <= value.active_revision <= 2_147_483_647
        or type(value.configuration_revision) is not int
        or not 0 <= value.configuration_revision <= 2_147_483_647
        or type(value.identity) is not tuple
        or not 1 <= len(value.identity) <= 256
        or any(type(part) is not str or len(part) > 512 for part in value.identity)
        or any(
            type(part) is not str or not 1 <= len(part) <= 200
            for part in (
                value.index_version,
                value.mapping_version,
                value.eligibility_version,
                value.configuration_version,
            )
        )
    ):
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    valid_id(value.resource_id)
    return value


def recheck(
    unit: OwnerUnit,
    prepared: PreparedViewing,
    generation: str,
    rules: ViewingRules,
    gateway: DraftInventory | None,
) -> None:
    if gateway is None:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    # The real adapter must recheck its original opaque I5 token in this same unit.
    # Revocation or restart is not authority; a ValueError means unavailable.
    try:
        gateway.recheck(unit.db, prepared)
    except ValueError:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE") from None
    metadata = unit.db.get(StoreMetadata, 1)
    if (
        metadata is None
        or metadata.store_generation != generation
        or prepared.generation != generation
    ):
        raise ApiFailure("STORE_GENERATION_CHANGED")
    active = unit.db.get(ActiveInventory, 1)
    if active is None or (active.snapshot_id, active.revision, active.index_version) != (
        prepared.ref.snapshot_id,
        prepared.active_revision,
        prepared.index_version,
    ):
        raise ApiFailure("SNAPSHOT_STALE")
    exact = (prepared.ref.namespace, prepared.ref.snapshot_id, prepared.ref.source_id)
    listing = unit.db.scalar(
        select(ListingVersion.source_id).where(
            ListingVersion.namespace == exact[0],
            ListingVersion.snapshot_id == exact[1],
            ListingVersion.source_id == exact[2],
        )
    )
    if listing is None:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    active_rules = unit.db.get(ActiveRules, 1)
    if (
        active_rules is None
        or type(active_rules.revision) is not int
        or not 0 <= active_rules.revision <= 2_147_483_647
        or (active_rules.version, active_rules.revision)
        != (
            prepared.configuration_version,
            prepared.configuration_revision,
        )
    ):
        raise ApiFailure("RULES_UNAVAILABLE")
    snapshot = unit.db.get(InventorySnapshot, active.snapshot_id)
    profile = unit.db.get(InventoryStorageProfile, 1)
    if snapshot is None or profile is None or snapshot.namespace != prepared.ref.namespace:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    try:
        observation = InventoryObservation.model_validate(
            dict(
                generation=generation,
                active_revision=active.revision,
                snapshot_id=active.snapshot_id,
                index_version=active.index_version,
                mode=profile.mode,
            )
        )
    except ValueError:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE") from None
    config = load_configuration(
        unit.db,
        prepared.configuration_version,
        rules=rules,
        observation=observation,
        namespace=snapshot.namespace,
    )
    if eligibility_version(config) != prepared.eligibility_version:
        raise ApiFailure("RULES_UNAVAILABLE")
    if prepared.ref not in config.eligibility.eligible_refs:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    mapping = unit.db.get(ListingResourceMapping, exact)
    resource = unit.db.get(VehicleResource, prepared.resource_id)
    if (
        mapping is None
        or resource is None
        or (mapping.resource_id, mapping.mapping_version)
        != (
            prepared.resource_id,
            prepared.mapping_version,
        )
    ):
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
