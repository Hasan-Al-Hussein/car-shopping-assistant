"""Explicit I5/public-signer composition for owned sessions and shortlists."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.schemas.inventory import PresentationProof
from app.core.errors import ApiFailure
from app.database.store import assert_outside_write_transaction
from app.inventory.compact_reader import CompactInventoryReader
from app.inventory.public_errors import public_read_failure
from app.inventory.public_projection import map_listing_summary
from app.inventory.references import ImmutableInventoryRef
from app.inventory.search_service import InventorySearchService
from app.inventory_signing import HmacPublicInventorySigner
from app.sessions.inventory import InventoryAdmission
from app.shortlist.inventory import ReferenceBatch, ReferenceObservation


class CompactSessionInventory:
    def __init__(self, reader: CompactInventoryReader, signer: HmacPublicInventorySigner) -> None:
        if signer.generation != reader.store.generation:
            raise ValueError("PUBLIC_SIGNER_STORE_GENERATION_MISMATCH")
        self.reader = reader
        self.signer = signer

    def verify(self, proof: PresentationProof, *, now: datetime) -> None:
        assert_outside_write_transaction()
        self.signer.verify_presentation(proof, now=now)

    def prepare(
        self, refs: tuple[ImmutableInventoryRef, ...], *, snapshot_id: str
    ) -> InventoryAdmission:
        assert_outside_write_transaction()
        try:
            batch = self.reader.read_refs(refs, expected_snapshot_id=snapshot_id)
            observation = batch.observation
            if (
                observation.generation != self.signer.generation
                or observation.snapshot_id != snapshot_id
                or observation.index_version is None
                or observation.active_revision < 1
            ):
                raise ApiFailure("SNAPSHOT_STALE")
            if tuple(item.ref for item in batch.items) != refs:
                raise ApiFailure("STORE_UNAVAILABLE")
            if any(item.state != "current" or item.listing is None for item in batch.items):
                raise ApiFailure("NOT_FOUND")
            return InventoryAdmission(
                observation.generation,
                snapshot_id,
                observation.active_revision,
                observation.index_version,
                tuple(item.ref for item in batch.items),
                batch.identity,
            )
        except ValueError as error:
            raise public_read_failure(error) from None

    def recheck(self, db: Session, prepared: InventoryAdmission) -> None:
        try:
            if prepared.generation != self.signer.generation:
                raise ApiFailure("STORE_GENERATION_CHANGED")
            self.reader.recheck_identity(db, prepared.identity, expected_refs=prepared.refs)
        except ValueError as error:
            raise public_read_failure(error) from None


class CompactShortlistInventory:
    def __init__(self, reader: CompactInventoryReader) -> None:
        self.reader = reader

    def read(self, refs: tuple[ImmutableInventoryRef, ...]) -> ReferenceBatch:
        assert_outside_write_transaction()
        if type(refs) is not tuple or not 1 <= len(refs) <= 50:
            raise ApiFailure("VALIDATION_ERROR")
        try:
            batch = self.reader.read_refs(refs)
            observation = batch.observation
            if tuple(item.ref for item in batch.items) != refs:
                raise ApiFailure("STORE_UNAVAILABLE")
            items = []
            for item in batch.items:
                if (item.state == "missing") != (item.listing is None):
                    raise ApiFailure("STORE_UNAVAILABLE")
                summary = None if item.listing is None else map_listing_summary(item.listing)
                if summary is not None and summary.ref.model_dump() != item.ref.model_dump():
                    raise ApiFailure("STORE_UNAVAILABLE")
                items.append(ReferenceObservation(item.ref, item.state, summary))
            return ReferenceBatch(
                observation.generation,
                observation.snapshot_id,
                observation.active_revision if observation.snapshot_id is not None else None,
                observation.index_version,
                tuple(items),
                batch.identity,
            )
        except ValueError as error:
            raise public_read_failure(error) from None
        except (KeyError, TypeError):
            raise ApiFailure("STORE_UNAVAILABLE") from None

    def recheck(self, db: Session, prepared: ReferenceBatch) -> None:
        try:
            if prepared.generation != self.reader.store.generation:
                raise ApiFailure("STORE_GENERATION_CHANGED")
            self.reader.recheck_identity(
                db, prepared.identity, expected_refs=tuple(item.ref for item in prepared.items)
            )
        except ValueError as error:
            raise public_read_failure(error) from None


@dataclass(frozen=True, slots=True)
class PublicInventoryServices:
    signer: HmacPublicInventorySigner
    search: InventorySearchService
    sessions: CompactSessionInventory
    shortlist: CompactShortlistInventory


def compose_public_inventory(reader: CompactInventoryReader) -> PublicInventoryServices:
    """Explicit caller-owned lifecycle: no route mounting, store creation or audit.

    Recreate this entire composition for a new process/store generation. Inventory
    owns reader admission and disposal. No secrets exist until this function runs.
    """
    signer = HmacPublicInventorySigner(reader.store.generation)
    return PublicInventoryServices(
        signer,
        InventorySearchService(reader, signer),
        CompactSessionInventory(reader, signer),
        CompactShortlistInventory(reader),
    )
