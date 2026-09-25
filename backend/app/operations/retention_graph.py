"""Bounded operator-only retention graph inside one existing Store unit.

No row or work graph escapes the callback. This depends on Platform's actual A9
storage models; it neither decodes an invented message format nor grants access.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import JSON, LargeBinary, cast, func, select
from sqlalchemy.orm import Session

from app.api.schemas.leads import ReviewedExistingLead
from app.database import models as m
from app.identity.authorization import OwnerUnit
from app.leads.repository import CaptureReceipt
from app.sessions import repository as sessions
from app.sessions.state import SessionContent, fingerprint
from app.viewings import draft_repository as drafts

MAX_ROWS = 2_000
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ROW_JSON = 256 * 1024
MAX_REVISION = 2_147_483_647
TOMBSTONE = "expired-command-tombstone-1"
PROTECTION_REASONS = frozenset({
    "session_retention_active", "lead_retention_active", "draft_retained",
    "booking_retention_active", "outcome_replay_active", "review_retention_active",
    "unresolved_review", "unresolved_collection_command", "command_receipt_active",
    "protection_unclassified",
})

OWNED = (
    m.OwnerCredential, m.Journey, m.ConversationSession, m.Message, m.ResultPresentation,
    m.PreferenceSetting, m.Preference, m.ShortlistMembership, m.CommandReceipt,
    m.BookingDraft, m.BookingReview, m.OperationOutcome, m.Booking, m.Lead, m.LeadBooking,
)


class RetentionError(ValueError):
    """Closed operator code, without private values or paths."""


def payload(row: m.Base) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def identity(row: m.Base) -> tuple[Any, ...]:
    return tuple(getattr(row, column.name) for column in row.__table__.primary_key.columns)


@dataclass
class OwnerWork:
    owner: m.Owner
    rows: dict[type[m.Base], list[Any]]
    before: list[dict[str, Any]]
    remove: dict[type[m.Base], set[tuple[Any, ...]]] = field(default_factory=dict)
    updates: list[tuple[m.Base, dict[str, Any]]] = field(default_factory=list)
    protected: int = 0
    unresolved: int = 0
    protected_expired_leads: int = 0
    protected_expired_reasons: tuple[tuple[str, int], ...] = ()

    def delete(self, row: m.Base) -> None:
        self.remove.setdefault(type(row), set()).add(identity(row))

    def deleting(self, row: m.Base) -> bool:
        return identity(row) in self.remove.get(type(row), set())

    def change(self, row: m.Base, **values: Any) -> None:
        changed = {key: value for key, value in values.items() if getattr(row, key) != value}
        if changed:
            self.updates.append((row, changed))

    def counts(self) -> tuple[tuple[str, int], ...]:
        counts = {"delete." + model.__tablename__: len(keys) for model, keys in self.remove.items()}
        for row, _ in self.updates:
            name = "update." + row.__tablename__
            counts[name] = counts.get(name, 0) + 1
        return tuple(sorted(counts.items()))


def load(db: Session, owner: m.Owner) -> OwnerWork:
    rows: dict[type[m.Base], list[Any]] = {}
    total, json_size = 0, 0

    def bounded(model: type[m.Base], condition: Any) -> list[Any]:
        nonlocal total, json_size
        count = db.scalar(select(func.count()).select_from(model).where(condition)) or 0
        total += count
        if total > MAX_ROWS:
            raise RetentionError("RETENTION_OWNER_GRAPH_LIMIT")
        for column in model.__table__.columns:
            if isinstance(column.type, JSON):
                size = func.length(cast(column, LargeBinary))
                largest, summed = db.execute(select(func.max(size), func.sum(size)).where(condition)).one()
                json_size += summed or 0
                if (largest or 0) > MAX_ROW_JSON or json_size > MAX_JSON_BYTES:
                    raise RetentionError("RETENTION_JSON_LIMIT")
        return list(db.scalars(select(model).where(condition).order_by(*model.__table__.primary_key.columns)))

    for model in OWNED:
        rows[model] = bounded(model, model.owner_id == owner.id)
    lead_ids = [row.id for row in rows[m.Lead]]
    presentation_ids = [row.id for row in rows[m.ResultPresentation]]
    rows[m.ExportIntent] = bounded(m.ExportIntent, m.ExportIntent.lead_id.in_(lead_ids))
    rows[m.PresentationItem] = bounded(m.PresentationItem, m.PresentationItem.presentation_id.in_(presentation_ids))
    before = [{"table": "owners", "row": payload(owner)}]
    before.extend({"table": model.__tablename__, "row": payload(row)} for model, entries in rows.items() for row in entries)
    return OwnerWork(owner, rows, before)


def plan_owner(db: Session, owner: m.Owner, cutoff: str) -> OwnerWork:
    work = load(db, owner)
    rows = work.rows
    unit = OwnerUnit(db, owner)  # Trusted local operator; never a request/model owner claim.
    by_id = {model: {row.id: row for row in rows[model]} for model in (
        m.ConversationSession, m.Message, m.BookingDraft, m.BookingReview,
        m.OperationOutcome, m.Booking, m.Lead, m.CommandReceipt,
    )}
    keep = {model: set() for model in by_id}
    causes: dict[type[m.Base], dict[str, set[str]]] = {model: {} for model in by_id}
    strong_sessions: set[str] = set()
    session_content = {row.id: sessions.content(row) for row in rows[m.ConversationSession]}
    stored_reviews = {row.id: drafts.stored_review(unit, row) for row in rows[m.BookingReview]}
    outcomes_by_review = {row.review_id: row for row in rows[m.OperationOutcome]}
    bookings_by_outcome = {row.operation_id: row for row in rows[m.Booking]}

    def protect(
        model: type[m.Base], key: str | None, *, required: bool = True,
        reasons: frozenset[str] = frozenset(),
    ) -> None:
        if key is None:
            return
        if key not in by_id[model]:
            if required:
                raise RetentionError("RETENTION_PROTECTION_INCOMPATIBLE")
            return
        keep[model].add(key)
        causes[model].setdefault(key, set()).update(reasons)

    def because(model: type[m.Base], key: str) -> frozenset[str]:
        return frozenset(causes[model].get(key, ()))

    def protect_session_dependencies(session_id: str) -> None:
        content = session_content[session_id]
        reasons = because(m.ConversationSession, session_id)
        protect(m.BookingDraft, content.current_draft_id, required=False, reasons=reasons)
        pending = content.pending_intent
        if pending.kind == "viewing_review":
            protect(m.BookingReview, pending.review_id, required=False, reasons=reasons)
        elif pending.kind == "operation_unresolved":
            protect(m.BookingDraft, pending.draft_id, required=False, reasons=reasons)
            for review in rows[m.BookingReview]:
                if review.operation_key == pending.operation_key:
                    protect(m.BookingReview, review.id, reasons=reasons)

    for row in rows[m.ConversationSession]:
        if row.expires_at > cutoff:
            protect(m.ConversationSession, row.id, reasons=frozenset({"session_retention_active"}))
            strong_sessions.add(row.id)
    for row in rows[m.Lead]:
        if row.expires_at > cutoff:
            protect(m.Lead, row.id, reasons=frozenset({"lead_retention_active"}))
    for row in rows[m.BookingDraft]:
        if row.state == "unresolved" and row.active_review_id is None:
            raise RetentionError("RETENTION_UNRESOLVED_DRAFT_INVALID")
        if row.expires_at > cutoff or row.state == "unresolved":
            protect(m.BookingDraft, row.id, reasons=frozenset({"draft_retained"}))
    for row in rows[m.Booking]:
        if row.expires_at > cutoff:
            protect(m.Booking, row.id, reasons=frozenset({"booking_retention_active"}))

    for row in rows[m.BookingReview]:
        outcome = outcomes_by_review.get(row.id)
        if outcome is not None:
            if not drafts.terminal_proven(unit, row):
                raise RetentionError("RETENTION_TERMINAL_PROOF_INVALID")
            if outcome.terminal_at > cutoff:
                raise RetentionError("RETENTION_CLOCK_BEFORE_TERMINAL")
            if outcome.replay_valid_until > cutoff:
                protect(m.OperationOutcome, outcome.id, reasons=frozenset({"outcome_replay_active"}))
        elif row.state in {"submitted", "consumed"}:
            work.unresolved += 1
            reasons = frozenset({"unresolved_review"})
            protect(m.BookingReview, row.id, reasons=reasons)
            protect(m.BookingDraft, row.draft_id, required=False, reasons=reasons)
            source = stored_reviews[row.id].review
            protect(m.ConversationSession, source.session_id, required=False, reasons=reasons)
            if source.session_id in session_content:
                strong_sessions.add(source.session_id)
            if isinstance(source.lead_change, ReviewedExistingLead):
                protect(m.Lead, source.lead_change.lead_id, reasons=reasons)
        elif row.expires_at > cutoff:
            reasons = frozenset({"review_retention_active"})
            protect(m.BookingReview, row.id, reasons=reasons)
            protect(m.BookingDraft, row.draft_id, required=False, reasons=reasons)

    # Actual A9 decoding is performed by the shared repository/model. The original
    # command survives independently of collection/transcript expiry.
    for row in rows[m.Message]:
        saved = sessions.message_content(row)
        command = saved.collection_command
        if row.state in {"pending", "interrupted"} and command is not None:
            if (command.source_message_id, command.session_id, command.request_hash) != (
                row.id, row.session_id, row.payload_hash,
            ):
                raise RetentionError("RETENTION_COMMAND_PROVENANCE_INVALID")
            work.unresolved += 1
            reasons = frozenset({"unresolved_collection_command"})
            protect(m.Message, row.id, reasons=reasons)
            protect(m.ConversationSession, row.session_id, reasons=reasons)
            strong_sessions.add(row.session_id)
            protect_session_dependencies(row.session_id)
            protect(m.Lead, command.lead_id, reasons=reasons)
            protect(m.BookingDraft, command.draft_id, reasons=reasons)
            # Create may have an uncertain counterpart: retain any existing lead
            # for this journey, without treating its presence as commit proof.
            if command.kind == "lead":
                session = by_id[m.ConversationSession][row.session_id]
                for lead in rows[m.Lead]:
                    if lead.journey_id == session.journey_id:
                        protect(m.Lead, lead.id, reasons=reasons)
            kind = "lead.command" if command.kind == "lead" else "viewing.draft.command"
            for receipt in rows[m.CommandReceipt]:
                if (receipt.command_kind, receipt.client_action_id) == (kind, command.command.client_action_id):
                    protect(m.CommandReceipt, receipt.id, reasons=reasons)

    for row in rows[m.CommandReceipt]:
        if row.expires_at <= cutoff and row.id not in keep[m.CommandReceipt]:
            tombstone: dict[str, Any] = {"version": TOMBSTONE}
            # T9 checks an explicitly supplied provenance binding before expiry.
            source = row.result_json.get("source_message_id")
            if source is not None:
                tombstone["source_message_id"] = sessions.valid_id(source)
            work.change(row, result_json=tombstone)
            continue
        reasons = because(m.CommandReceipt, row.id)
        if row.expires_at > cutoff:
            reasons |= frozenset({"command_receipt_active"})
        protect(m.CommandReceipt, row.id, reasons=reasons)
        if row.command_kind == "lead.command":
            lead_receipt = CaptureReceipt.model_validate(row.result_json)
            if lead_receipt.lead.revision != row.applied_revision:
                raise RetentionError("RETENTION_RECEIPT_INVALID")
            protect(m.Lead, lead_receipt.lead.lead_id, reasons=reasons)
            for booking_id in lead_receipt.lead.booking_ids:
                protect(m.Booking, booking_id, reasons=reasons)
        elif row.command_kind == "viewing.draft.command":
            draft_receipt = drafts.DraftReceipt.model_validate(row.result_json)
            protect(m.BookingDraft, draft_receipt.draft_id, reasons=reasons)
        elif row.command_kind in {"session.create", "session.presentation", "session.selection"}:
            protect(m.ConversationSession, sessions.valid_id(row.result_json.get("session_id")), reasons=reasons)
        elif row.command_kind not in {"preference.command", "shortlist.membership"}:
            raise RetentionError("RETENTION_RECEIPT_KIND_UNSUPPORTED")

    for session_id in strong_sessions:
        protect_session_dependencies(session_id)

    # A finite monotone closure keeps terminal authority and lead/book links whole.
    def closure_size() -> tuple[int, int]:
        return (sum(map(len, keep.values())),
                sum(len(reason) for entries in causes.values() for reason in entries.values()))

    for _ in range(MAX_ROWS * len(PROTECTION_REASONS) + 1):
        previous = closure_size()
        # Membership was already protected before closure. Repeat these same
        # edges so late causes reaching an existing strong session also flow to
        # its current draft/review; this does not select additional sessions.
        for session_id in strong_sessions:
            protect_session_dependencies(session_id)
        for key in tuple(keep[m.BookingDraft]):
            row = by_id[m.BookingDraft][key]
            reasons = because(m.BookingDraft, key)
            protect(m.ConversationSession, row.session_id, reasons=reasons)
            protect(m.BookingReview, row.active_review_id, reasons=reasons)
        for key in tuple(keep[m.OperationOutcome]):
            row = by_id[m.OperationOutcome][key]
            reasons = because(m.OperationOutcome, key)
            protect(m.BookingReview, row.review_id, reasons=reasons)
            booking = bookings_by_outcome.get(row.id)
            if row.terminal_state == "SUCCEEDED" and booking is None:
                raise RetentionError("RETENTION_BOOKING_PROOF_MISSING")
            if booking is not None:
                protect(m.Booking, booking.id, reasons=reasons)
        for key in tuple(keep[m.BookingReview]):
            outcome = outcomes_by_review.get(key)
            if outcome is not None:
                protect(m.OperationOutcome, outcome.id, reasons=because(m.BookingReview, key))
        for key in tuple(keep[m.Booking]):
            row = by_id[m.Booking][key]
            reasons = because(m.Booking, key)
            protect(m.OperationOutcome, row.operation_id, reasons=reasons)
            protect(m.BookingReview, row.review_id, reasons=reasons)
        for link in rows[m.LeadBooking]:
            if link.lead_id in keep[m.Lead] or link.booking_id in keep[m.Booking]:
                reasons = because(m.Lead, link.lead_id) | because(m.Booking, link.booking_id)
                protect(m.Lead, link.lead_id, reasons=reasons)
                protect(m.Booking, link.booking_id, reasons=reasons)
        if closure_size() == previous:
            break
    else:
        raise RetentionError("RETENTION_GRAPH_DID_NOT_CONVERGE")

    work.protected = sum(map(len, keep.values()))
    reason_counts: dict[str, int] = {}
    for lead in rows[m.Lead]:
        if lead.expires_at <= cutoff and lead.id in keep[m.Lead]:
            work.protected_expired_leads += 1
            for reason in because(m.Lead, lead.id) or frozenset({"protection_unclassified"}):
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
    work.protected_expired_reasons = tuple(sorted(reason_counts.items()))
    for model in (m.Lead, m.Booking, m.OperationOutcome, m.BookingReview, m.BookingDraft):
        for row in rows[model]:
            if row.id not in keep[model]:
                work.delete(row)
    for row in rows[m.LeadBooking]:
        if row.lead_id not in keep[m.Lead] or row.booking_id not in keep[m.Booking]:
            work.delete(row)
    for row in rows[m.ExportIntent]:
        if row.lead_id not in keep[m.Lead]:
            work.delete(row)
    for row in rows[m.BookingDraft]:
        if work.deleting(row) and row.active_review_id is not None:
            work.change(row, active_review_id=None)
    for row in rows[m.BookingReview]:
        if row.draft_id is not None and row.draft_id not in keep[m.BookingDraft]:
            work.change(row, draft_id=None)

    for row in rows[m.ConversationSession]:
        if row.id not in keep[m.ConversationSession]:
            work.delete(row)
            continue
        content = session_content[row.id]
        if row.expires_at <= cutoff and row.id not in strong_sessions:
            revised = SessionContent()
        elif content.collection is not None and content.collection.expires_at <= cutoff:
            revised = SessionContent.model_validate({**content.model_dump(mode="json"), "collection": None})
        else:
            revised = content
        if revised != content:
            if row.revision >= MAX_REVISION:
                raise RetentionError("RETENTION_REVISION_EXHAUSTED")
            work.change(row, state_json=revised.model_dump(mode="json"), revision=row.revision + 1)
    expired_sessions = {row.id for row in rows[m.ConversationSession] if row.expires_at <= cutoff}
    for row in rows[m.Message]:
        if row.session_id in expired_sessions and row.id not in keep[m.Message]:
            work.delete(row)
    discarded_presentations = set()
    for row in rows[m.ResultPresentation]:
        if row.session_id in expired_sessions and row.session_id not in strong_sessions:
            work.delete(row)
            discarded_presentations.add(row.id)
    for row in rows[m.PresentationItem]:
        if row.presentation_id in discarded_presentations:
            work.delete(row)

    for row in rows[m.OwnerCredential]:
        if row.expires_at <= cutoff or row.revoked_at is not None:
            work.delete(row)
    for row in rows[m.Preference]:
        if row.expires_at <= cutoff:
            work.delete(row)
    for row in rows[m.ShortlistMembership]:
        if row.expires_at <= cutoff and not work.unresolved:
            work.delete(row)
    for model, attr in ((m.Preference, "preference_revision"), (m.ShortlistMembership, "shortlist_revision")):
        if work.remove.get(model):
            revision = getattr(owner, attr)
            if revision >= MAX_REVISION:
                raise RetentionError("RETENTION_REVISION_EXHAUSTED")
            work.change(owner, **{attr: revision + 1})
    for row in rows[m.Journey]:
        dependent = any(item.journey_id == row.id and not work.deleting(item)
                        for model in (m.ConversationSession, m.Lead) for item in rows[model])
        if not dependent:
            work.delete(row)
    remaining = any(not work.deleting(row) for model in OWNED
                    if model not in {m.CommandReceipt, m.PreferenceSetting, m.Journey}
                    for row in rows[model])
    if not remaining and not keep[m.CommandReceipt]:
        for model in (m.CommandReceipt, m.PreferenceSetting, m.Journey):
            for row in rows[model]:
                work.delete(row)
        work.delete(owner)
        work.updates = [(row, values) for row, values in work.updates if not work.deleting(row)]
    elif not any(not work.deleting(row) for row in rows[m.OwnerCredential]):
        work.change(owner, display_name=None)
    return work


DELETE_ORDER = (
    m.PresentationItem, m.LeadBooking, m.ExportIntent, m.Message, m.ResultPresentation,
    m.Booking, m.OperationOutcome, m.BookingReview, m.BookingDraft, m.Lead,
    m.ConversationSession, m.Preference, m.ShortlistMembership, m.CommandReceipt,
    m.PreferenceSetting, m.OwnerCredential, m.Journey, m.Owner,
)


def apply_owner(db: Session, work: OwnerWork) -> None:
    if db.connection().get_execution_options().get("store_write") is not True:
        raise RetentionError("RETENTION_REQUIRES_WRITE")
    for row, values in work.updates:
        for key, value in values.items():
            setattr(row, key, value)
    db.flush()  # Detach nullable origins/active review pointers before parent deletion.
    for model in DELETE_ORDER:
        for row in ([work.owner] if model is m.Owner else work.rows.get(model, [])):
            if work.deleting(row):
                db.delete(row)
        db.flush()


def graph_digest(work: OwnerWork, export_state: dict[str, Any] | None) -> str:
    return fingerprint({"rows": work.before, "export_state": export_state})
