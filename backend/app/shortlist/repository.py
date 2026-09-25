"""Bounded unit-local membership paging, dedupe and conservative retention."""

from dataclasses import dataclass

from sqlalchemy import func, literal, select, tuple_

from app.core.errors import ApiFailure
from app.database.models import (
    BookingDraft,
    BookingReview,
    CommandReceipt,
    Owner,
    OwnerCredential,
    ShortlistMembership,
)
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.inventory.references import ImmutableInventoryRef
from app.memory.repository import next_revision
from app.shortlist.cursors import ShortlistCursor, decode_cursor, encode_cursor
from app.shortlist.inventory import key

KIND = "shortlist.membership"


def owner(unit: OwnerUnit) -> Owner:
    row = unit.db.get(Owner, unit.owner_id)
    if row is None:
        raise StoreError("SHORTLIST_OWNER_INCOMPATIBLE")
    return row


def membership(unit: OwnerUnit, ref: ImmutableInventoryRef) -> ShortlistMembership | None:
    return unit.db.get(ShortlistMembership, (unit.owner_id, *key(ref)))


def receipt(unit: OwnerUnit, action_id: str, digest: str, now: str) -> CommandReceipt | None:
    row = unit.db.scalar(
        select(CommandReceipt).where(
            CommandReceipt.owner_id == unit.owner_id,
            CommandReceipt.command_kind == KIND,
            CommandReceipt.client_action_id == action_id,
        )
    )
    if row is not None:
        if row.payload_hash != digest:
            raise ApiFailure("IDEMPOTENCY_CONFLICT")
        if row.expires_at <= now:
            raise ApiFailure("REPLAY_EXPIRED")
        if (
            set(row.result_json) != {"version", "changed_at_apply"}
            or row.result_json["version"] != "shortlist-command-1"
            or type(row.result_json["changed_at_apply"]) is not bool
            or not 0 < row.applied_revision <= owner(unit).shortlist_revision
        ):
            raise StoreError("SHORTLIST_RECEIPT_INCOMPATIBLE")
    return row


@dataclass(frozen=True)
class SavedRef:
    ref: ImmutableInventoryRef
    added_at: str
    expires_at: str


@dataclass(frozen=True)
class MembershipPage:
    revision: int
    observed_at: str
    earliest_expiry: str | None
    items: tuple[SavedRef, ...]
    total: int
    next_cursor: str | None


def page(
    unit: OwnerUnit,
    *,
    context_id: str,
    generation: str,
    now: str,
    page_size: int,
    cursor: str | None,
) -> MembershipPage:
    revision = owner(unit).shortlist_revision
    credential = unit.db.scalar(
        select(OwnerCredential).where(
            OwnerCredential.owner_id == unit.owner_id, OwnerCredential.context_id == context_id
        )
    )
    if credential is None:
        raise ApiFailure("IDENTITY_REQUIRED")
    parsed = None if cursor is None else decode_cursor(cursor, credential.csrf_binding)
    observed = now
    if parsed is not None:
        if (parsed.owner_id, parsed.context_id, parsed.generation) != (
            unit.owner_id,
            context_id,
            generation,
        ):
            raise ApiFailure("VALIDATION_ERROR")
        if parsed.revision != revision or now >= parsed.earliest_expiry or now < parsed.observed_at:
            raise ApiFailure("REVISION_CONFLICT")
        observed = parsed.observed_at
    visible = (
        ShortlistMembership.owner_id == unit.owner_id,
        ShortlistMembership.expires_at > observed,
    )
    total, earliest = unit.db.execute(
        select(func.count(), func.min(ShortlistMembership.expires_at))
        .select_from(ShortlistMembership)
        .where(*visible)
    ).one()
    if parsed is not None and earliest != parsed.earliest_expiry:
        raise ApiFailure("REVISION_CONFLICT")
    query = select(ShortlistMembership).where(*visible)
    order = (
        ShortlistMembership.added_at,
        ShortlistMembership.namespace,
        ShortlistMembership.snapshot_id,
        ShortlistMembership.source_id,
    )
    if parsed is not None:
        boundary = (parsed.after_added_at, *key(parsed.after_ref))
        query = query.where(tuple_(*order) > tuple_(*(literal(value) for value in boundary)))
    rows = list(unit.db.scalars(query.order_by(*order).limit(page_size + 1)))
    items = tuple(
        SavedRef(
            ImmutableInventoryRef(
                namespace=row.namespace, snapshot_id=row.snapshot_id, source_id=row.source_id
            ),
            row.added_at,
            row.expires_at,
        )
        for row in rows[:page_size]
    )
    if any(not item.added_at <= observed < item.expires_at for item in items):
        raise StoreError("SHORTLIST_STATE_INCOMPATIBLE")
    next_cursor = None
    if len(rows) > page_size:
        if earliest is None:
            raise StoreError("SHORTLIST_STATE_INCOMPATIBLE")
        last = items[-1]
        next_cursor = encode_cursor(
            ShortlistCursor(
                owner_id=unit.owner_id,
                context_id=context_id,
                generation=generation,
                revision=revision,
                observed_at=observed,
                earliest_expiry=earliest,
                after_added_at=last.added_at,
                after_ref=last.ref,
            ),
            credential.csrf_binding,
        )
    return MembershipPage(revision, observed, earliest, items, total, next_cursor)


def purge_expired(unit: OwnerUnit, *, now: str, limit: int = 50) -> int:
    """Bounded operator hook; conservative whole-owner hold for submitted authority.

    A parentless submitted/consumed review holds cleanup even with an outcome row:
    relational presence alone cannot validate its retained payload or reconciliation.
    Releasing that hold requires later accepted Transactions terminal-proof integration.
    No malformed evidence is treated as absent. Explicit DELETE is separate buyer intent.
    Receipt keys and all listing/session/booking/lead/outcome rows remain untouched.
    """
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ApiFailure("VALIDATION_ERROR")
    unresolved_review = unit.db.scalar(
        select(BookingReview.id)
        .where(
            BookingReview.owner_id == unit.owner_id,
            BookingReview.state.in_(("submitted", "consumed")),
        )
        .limit(1)
    )
    unresolved_draft = unit.db.scalar(
        select(BookingDraft.id)
        .where(BookingDraft.owner_id == unit.owner_id, BookingDraft.state == "unresolved")
        .limit(1)
    )
    if unresolved_review is not None or unresolved_draft is not None:
        return 0
    rows = list(
        unit.db.scalars(
            select(ShortlistMembership)
            .where(
                ShortlistMembership.owner_id == unit.owner_id, ShortlistMembership.expires_at <= now
            )
            .order_by(
                ShortlistMembership.expires_at,
                ShortlistMembership.namespace,
                ShortlistMembership.snapshot_id,
                ShortlistMembership.source_id,
            )
            .limit(limit)
        )
    )
    if rows:
        buyer = owner(unit)
        buyer.shortlist_revision = next_revision(buyer.shortlist_revision, buyer.shortlist_revision)
        for row in rows:
            unit.db.delete(row)
    return len(rows)
