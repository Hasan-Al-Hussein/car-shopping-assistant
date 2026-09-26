"""Synthetic bounded port evidence only, never real BE07 projection proof."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.api.schemas.inventory import ListingSummary
from app.database.models import ActiveInventory, Base, ListingVersion
from app.database.store import StoreError, assert_outside_write_transaction
from app.inventory.references import ImmutableInventoryRef
from app.memory.service import PreferenceService
from app.sessions.state import fingerprint
from app.shortlist.inventory import ReferenceBatch, ReferenceObservation, key
from app.shortlist.service import ShortlistService
from tests.platform.persistence_cases import seed_rows
from tests.platform.session_cases import SessionHarness, make_harness


def summary(ref: ImmutableInventoryRef) -> ListingSummary:
    unknown = {"status": "unknown", "reason": "not_stated"}
    return ListingSummary.model_validate(
        dict(
            ref=ref.model_dump(),
            title="Synthetic " + ref.snapshot_id[:1] + "/" + ref.source_id,
            make=unknown,
            model=unknown,
            trim=unknown,
            year=unknown,
            cash_price=unknown,
            mileage_km=unknown,
            photo={"state": "missing", "url": None, "alt": "No synthetic image"},
        )
    )


def listing_identity(db: Session, ref: ImmutableInventoryRef) -> str:
    row = db.get(ListingVersion, key(ref))
    return (
        "missing"
        if row is None
        else fingerprint(
            dict(
                ref=ref.model_dump(),
                source_row=row.source_row,
                original=row.original_json,
                normalized=row.normalized_json,
            )
        )
    )


class SyntheticShortlistInventory:
    def __init__(self, harness: SessionHarness) -> None:
        self.harness = harness
        self.missing: set[tuple[str, str, str]] = set()
        self.after_read: Callable[[], None] | None = None
        self.batches: list[int] = []

    def read(self, refs: tuple[ImmutableInventoryRef, ...]) -> ReferenceBatch:
        assert_outside_write_transaction()
        self.batches.append(len(refs))

        def read(db: Session) -> ReferenceBatch:
            active = db.get(ActiveInventory, 1)
            items = []
            for ref in refs:
                state: Literal["current", "historical", "missing"] = (
                    "missing"
                    if key(ref) in self.missing or db.get(ListingVersion, key(ref)) is None
                    else "current"
                    if active is not None and active.snapshot_id == ref.snapshot_id
                    else "historical"
                )
                items.append(
                    ReferenceObservation(ref, state, None if state == "missing" else summary(ref))
                )
            return ReferenceBatch(
                self.harness.store.generation,
                None if active is None else active.snapshot_id,
                None if active is None else active.revision,
                None if active is None else active.index_version,
                tuple(items),
                tuple(listing_identity(db, ref) for ref in refs),
            )

        result = self.harness.store.read(read)
        if self.after_read is not None:
            self.after_read()
        return result

    def recheck(self, db: Session, prepared: ReferenceBatch) -> None:
        # The synthetic port checks its own small identity in this exact unit.
        # Real accepted evidence/projection checks must be supplied by BE07.
        if tuple(listing_identity(db, item.ref) for item in prepared.items) != prepared.identity:
            raise StoreError("SYNTHETIC_IDENTITY_CHANGED")


@dataclass
class MemoryHarness:
    base: SessionHarness
    preferences: PreferenceService
    shortlist: ShortlistService
    inventory: SyntheticShortlistInventory


def make_memory_harness() -> MemoryHarness:
    base = make_harness()
    inventory = SyntheticShortlistInventory(base)
    return MemoryHarness(
        base,
        PreferenceService(base.auth),
        ShortlistService(base.auth, inventory=inventory),
        inventory,
    )


def seed_operational_rows(harness: SessionHarness) -> None:
    """Retained unrelated synthetic operational rows make noninterference non-vacuous."""

    def write(db: Session) -> None:
        for table, values in seed_rows(harness.store.generation):
            if table not in {"inventory_snapshots", "listing_versions", "active_inventory"}:
                db.execute(Base.metadata.tables[table].insert().values(**values)).close()

    harness.store.write(write)


@contextmanager
def failed_commit() -> Iterator[None]:
    def fail(connection: Connection) -> None:
        if connection.get_execution_options().get("store_write"):
            raise StoreError("SYNTHETIC_COMMIT_FAILURE")

    event.listen(Engine, "commit", fail)
    try:
        yield
    finally:
        event.remove(Engine, "commit", fail)
