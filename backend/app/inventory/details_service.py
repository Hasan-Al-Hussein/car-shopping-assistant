"""Exact coherent detail/comparison reads with a separate optional eligibility authority."""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    ComparisonRequest,
    ComparisonResult,
    ListingDetail,
    ListingReadError,
    ListingResult,
    MissingListing,
)
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader, CompactReference
from app.inventory.public_errors import STALE_CODES, public_read_failure
from app.inventory.public_projection import ListingEligibility, map_listing_detail
from app.inventory.read_budget import check_deadline, read_deadline
from app.inventory.read_identity import MAX_REFERENCE_BATCH
from app.inventory.references import ImmutableInventoryRef


class PublicEligibility(Protocol):
    def resolve(
        self, session: Session, item: CompactReference, *, observation: InventoryObservation
    ) -> ListingEligibility:
        """Trusted adopted config lookup, inside the same rechecked Store.read unit."""
        ...


@dataclass(frozen=True, slots=True)
class DetailRead:
    observation: InventoryObservation
    items: tuple[ListingResult, ...]


class InventoryDetailsService:
    def __init__(
        self, reader: CompactInventoryReader, *, eligibility: PublicEligibility | None = None
    ) -> None:
        self.reader = reader
        self.eligibility = eligibility

    def read(
        self, refs: tuple[InventoryRef, ...], *, deadline_at: float | None = None
    ) -> DetailRead:
        if type(refs) is not tuple or not 0 <= len(refs) <= MAX_REFERENCE_BATCH:
            raise ApiFailure("VALIDATION_ERROR")
        deadline = read_deadline(deadline_at, seconds=5.0)
        check_deadline(deadline)
        exact = tuple(ImmutableInventoryRef.model_validate(ref.model_dump()) for ref in refs)
        try:
            anchor = self.reader.read_refs(())
            check_deadline(deadline)
            batches: list[CompactBatch] = []
            entries: dict[ImmutableInventoryRef, CompactReference] = {}
            try:
                complete = self.reader.read_refs(exact)
            except ValueError as error:
                if str(error) not in STALE_CODES:
                    raise
                complete = None
            if complete is not None:
                batches.append(complete)
            else:
                # Isolate an unavailable retained snapshot, not every listing of that snapshot.
                groups: dict[str, list[ImmutableInventoryRef]] = {}
                for ref in exact:
                    groups.setdefault(ref.snapshot_id, []).append(ref)
                for group in groups.values():
                    check_deadline(deadline)
                    try:
                        batches.append(self.reader.read_refs(tuple(group)))
                    except ValueError as error:
                        if str(error) not in STALE_CODES:
                            raise
            for batch in batches:
                if batch.observation != anchor.observation:
                    raise ApiFailure("SNAPSHOT_STALE")
                for item in batch.items:
                    if item.ref not in exact:
                        raise ValueError("INVENTORY_DETAIL_ASSOCIATION_INVALID")
                    entries[item.ref] = item
            if complete is not None and tuple(item.ref for item in complete.items) != exact:
                raise ValueError("INVENTORY_DETAIL_ASSOCIATION_INVALID")
            check_deadline(deadline)

            def project(session: Session) -> tuple[ListingResult, ...]:
                self.reader.recheck(session, anchor)
                for batch in batches:
                    self.reader.recheck(session, batch)
                check_deadline(deadline)
                output: list[ListingResult] = []
                for ref in exact:
                    item = entries.get(ref)
                    if item is None:
                        output.append(
                            ListingReadError(
                                ref=ref, code="SNAPSHOT_STALE", retryable=True, state="error"
                            )
                        )
                        continue
                    if item.state == "missing":
                        output.append(MissingListing(state="missing", ref=ref))
                        continue
                    eligible = (
                        self.eligibility.resolve(session, item, observation=anchor.observation)
                        if self.eligibility is not None and item.state == "current"
                        else None
                    )
                    try:
                        output.append(map_listing_detail(item, eligibility=eligible))
                    except (ValueError, KeyError, TypeError):
                        # Projection failure is local; a Store/integrity failure is not swallowed.
                        output.append(
                            ListingReadError(
                                ref=ref, code="INTERNAL_ERROR", retryable=False, state="error"
                            )
                        )
                check_deadline(deadline)
                return tuple(output)

            items = self.reader.store.read(project)
            check_deadline(deadline)
        except ValueError as error:
            raise public_read_failure(error) from error
        actual = tuple(
            item.listing.ref if isinstance(item, ListingDetail) else item.ref for item in items
        )
        if tuple(ref.model_dump() for ref in actual) != tuple(ref.model_dump() for ref in exact):
            raise ApiFailure("INTERNAL_ERROR")
        return DetailRead(anchor.observation, items)

    def lookup(self, ref: InventoryRef, *, deadline_at: float | None = None) -> ListingResult:
        return self.read((ref,), deadline_at=deadline_at).items[0]

    def compare(
        self, supplied: ComparisonRequest, *, deadline_at: float | None = None
    ) -> ComparisonResult:
        request = ComparisonRequest.model_validate(supplied.model_dump())
        return ComparisonResult(
            items=list(self.read(tuple(request.refs), deadline_at=deadline_at).items)
        )

    def original_batch(
        self, refs: tuple[InventoryRef, ...], *, deadline_at: float | None = None
    ) -> tuple[ListingResult, ...]:
        return self.read(refs, deadline_at=deadline_at).items
