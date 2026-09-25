"""Verified authority and owner-scoped access inside one synchronous Store unit.

These objects are internal capabilities for trusted application code. They must
never be serialized, logged or constructed from model/request-selected IDs.
Python reflection and arbitrary trusted SQL are outside this input boundary.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.common import Id, InventoryRef
from app.core.errors import ApiFailure
from app.database.models import (
    Booking,
    BookingDraft,
    BookingReview,
    CommandReceipt,
    ConversationSession,
    ExportIntent,
    Journey,
    Lead,
    LeadBooking,
    Message,
    OperationOutcome,
    Owner,
    OwnerCredential,
    Preference,
    PreferenceSetting,
    PresentationItem,
    ResultPresentation,
    ShortlistMembership,
)
from app.database.store import Store, StoreError
from app.identity.service import IdentityService

_CONTEXT_ID = TypeAdapter(Id)


@dataclass(frozen=True, slots=True, repr=False)
class _Claims:
    owner_id: str
    credential_id: str
    context_id: str
    generation: str
    digest: str
    csrf_binding: str
    issued_at: str
    expires_at: str
    access: Literal["read", "write"]


class AuthorizedOwnerContext:
    """Opaque immutable grant, minted after canonical credential verification."""

    __slots__ = ("_issuer", "_claims")
    _issuer: object
    _claims: _Claims

    def __init__(self) -> None:
        raise TypeError("SERVER_ISSUED_AUTHORIZATION_REQUIRED")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("AUTHORIZATION_CONTEXT_IS_IMMUTABLE")

    def __repr__(self) -> str:
        return "<AuthorizedOwnerContext>"

    @property
    def context_id(self) -> str:
        return self._claims.context_id

    @property
    def generation(self) -> str:
        return self._claims.generation


@dataclass(frozen=True)
class OperationAuthority:
    """Unit-local retained authority; outcome None does not classify noncommit."""

    review: BookingReview
    outcome: OperationOutcome | None


class OwnerUnit:
    """Callback-local selectors; ORM rows/session must not escape the Store unit."""

    def __init__(self, session: Session, owner: Owner) -> None:
        self._session = session
        self._owner = owner
        self._active = True

    def _check_active(self) -> None:
        if not self._active:
            raise StoreError("OWNER_UNIT_CLOSED")

    @property
    def db(self) -> Session:
        """Trusted domain writes use this same session and verified owner_id."""
        self._check_active()
        return self._session

    @property
    def owner_id(self) -> str:
        self._check_active()
        return self._owner.id

    @staticmethod
    def _required[T](value: T | None) -> T:
        if value is None:
            raise ApiFailure("NOT_FOUND")
        return value

    @staticmethod
    def _limit(value: int) -> int:
        if type(value) is not int or not 1 <= value <= 50:
            raise ApiFailure("VALIDATION_ERROR")
        return value

    def journey(self, journey_id: str) -> Journey:
        return self._required(
            self.db.scalar(
                select(Journey).where(Journey.owner_id == self.owner_id, Journey.id == journey_id)
            )
        )

    def session(self, session_id: str) -> ConversationSession:
        return self._required(
            self.db.scalar(
                select(ConversationSession).where(
                    ConversationSession.owner_id == self.owner_id,
                    ConversationSession.id == session_id,
                )
            )
        )

    def sessions(self, *, limit: int = 50) -> list[ConversationSession]:
        return list(
            self.db.scalars(
                select(ConversationSession)
                .where(ConversationSession.owner_id == self.owner_id)
                .order_by(ConversationSession.id)
                .limit(self._limit(limit))
            )
        )

    def session_for_journey(self, journey_id: str, session_id: str) -> ConversationSession:
        self.journey(journey_id)
        value = self.session(session_id)
        if value.journey_id != journey_id:
            raise ApiFailure("NOT_FOUND")
        return value

    def message(self, session_id: str, message_id: str) -> Message:
        self.session(session_id)
        return self._required(
            self.db.scalar(
                select(Message).where(
                    Message.owner_id == self.owner_id,
                    Message.session_id == session_id,
                    Message.id == message_id,
                )
            )
        )

    def messages(self, session_id: str, *, limit: int = 50) -> list[Message]:
        self.session(session_id)
        return list(
            self.db.scalars(
                select(Message)
                .where(Message.owner_id == self.owner_id, Message.session_id == session_id)
                .order_by(Message.created_at, Message.id)
                .limit(self._limit(limit))
            )
        )

    def presentation(self, session_id: str, presentation_id: str) -> ResultPresentation:
        self.session(session_id)
        return self._required(
            self.db.scalar(
                select(ResultPresentation).where(
                    ResultPresentation.owner_id == self.owner_id,
                    ResultPresentation.session_id == session_id,
                    ResultPresentation.id == presentation_id,
                )
            )
        )

    def presentation_item(
        self, session_id: str, presentation_id: str, ordinal: int
    ) -> PresentationItem:
        self.presentation(session_id, presentation_id)
        return self._required(
            self.db.scalar(
                select(PresentationItem)
                .join(
                    ResultPresentation,
                    (ResultPresentation.id == PresentationItem.presentation_id)
                    & (ResultPresentation.snapshot_id == PresentationItem.snapshot_id),
                )
                .where(
                    ResultPresentation.owner_id == self.owner_id,
                    ResultPresentation.session_id == session_id,
                    PresentationItem.presentation_id == presentation_id,
                    PresentationItem.ordinal == ordinal,
                )
            )
        )

    def preference_setting(self) -> PreferenceSetting | None:
        return self.db.scalar(
            select(PreferenceSetting).where(PreferenceSetting.owner_id == self.owner_id)
        )

    def preference(self, key: str) -> Preference:
        return self._required(
            self.db.scalar(
                select(Preference).where(
                    Preference.owner_id == self.owner_id, Preference.key == key
                )
            )
        )

    def preferences(self, *, limit: int = 50) -> list[Preference]:
        return list(
            self.db.scalars(
                select(Preference)
                .where(Preference.owner_id == self.owner_id)
                .order_by(Preference.key)
                .limit(self._limit(limit))
            )
        )

    def shortlist(self, ref: InventoryRef) -> ShortlistMembership:
        return self._required(
            self.db.scalar(
                select(ShortlistMembership).where(
                    ShortlistMembership.owner_id == self.owner_id,
                    ShortlistMembership.namespace == ref.namespace,
                    ShortlistMembership.snapshot_id == ref.snapshot_id,
                    ShortlistMembership.source_id == ref.source_id,
                )
            )
        )

    def shortlist_memberships(self, *, limit: int = 50) -> list[ShortlistMembership]:
        return list(
            self.db.scalars(
                select(ShortlistMembership)
                .where(ShortlistMembership.owner_id == self.owner_id)
                .order_by(
                    ShortlistMembership.namespace,
                    ShortlistMembership.snapshot_id,
                    ShortlistMembership.source_id,
                )
                .limit(self._limit(limit))
            )
        )

    def command_receipt(self, command_kind: str, client_action_id: str) -> CommandReceipt:
        return self._required(
            self.db.scalar(
                select(CommandReceipt).where(
                    CommandReceipt.owner_id == self.owner_id,
                    CommandReceipt.command_kind == command_kind,
                    CommandReceipt.client_action_id == client_action_id,
                )
            )
        )

    def draft(self, draft_id: str) -> BookingDraft:
        return self._required(
            self.db.scalar(
                select(BookingDraft).where(
                    BookingDraft.owner_id == self.owner_id, BookingDraft.id == draft_id
                )
            )
        )

    def review(self, review_id: str) -> BookingReview:
        # Retained review authority may outlive its nullable draft/session and validity window.
        return self._required(
            self.db.scalar(
                select(BookingReview).where(
                    BookingReview.owner_id == self.owner_id, BookingReview.id == review_id
                )
            )
        )

    def draft_for_session(self, session_id: str, draft_id: str) -> BookingDraft:
        self.session(session_id)
        value = self.draft(draft_id)
        if value.session_id != session_id:
            raise ApiFailure("NOT_FOUND")
        return value

    def review_for_draft(self, draft_id: str, review_id: str) -> BookingReview:
        self.draft(draft_id)
        return self._required(
            self.db.scalar(
                select(BookingReview).where(
                    BookingReview.owner_id == self.owner_id,
                    BookingReview.id == review_id,
                    BookingReview.draft_id == draft_id,
                )
            )
        )

    def active_review(self, draft_id: str) -> BookingReview:
        draft = self.draft(draft_id)
        return self.review_for_draft(draft_id, self._required(draft.active_review_id))

    def lead(self, lead_id: str) -> Lead:
        return self._required(
            self.db.scalar(select(Lead).where(Lead.owner_id == self.owner_id, Lead.id == lead_id))
        )

    def lead_for_journey(self, journey_id: str) -> Lead | None:
        self.journey(journey_id)
        return self.db.scalar(
            select(Lead).where(Lead.owner_id == self.owner_id, Lead.journey_id == journey_id)
        )

    def operation(self, operation_key: str) -> OperationAuthority:
        review = self._required(
            self.db.scalar(
                select(BookingReview).where(
                    BookingReview.owner_id == self.owner_id,
                    BookingReview.operation_key == operation_key,
                )
            )
        )
        outcome = self.db.scalar(
            select(OperationOutcome).where(
                OperationOutcome.owner_id == self.owner_id,
                OperationOutcome.operation_key == operation_key,
            )
        )
        if outcome is not None and (
            outcome.review_id,
            outcome.payload_hash,
            outcome.store_generation,
        ) != (review.id, review.payload_hash, review.store_generation):
            raise StoreError("OPERATION_AUTHORITY_INCONSISTENT")
        return OperationAuthority(review, outcome)

    def booking(self, booking_id: str) -> Booking:
        return self._required(
            self.db.scalar(
                select(Booking)
                .join(
                    OperationOutcome,
                    (OperationOutcome.owner_id == Booking.owner_id)
                    & (OperationOutcome.id == Booking.operation_id)
                    & (OperationOutcome.review_id == Booking.review_id)
                    & (OperationOutcome.terminal_state == Booking.operation_state),
                )
                .where(
                    Booking.owner_id == self.owner_id,
                    Booking.id == booking_id,
                    OperationOutcome.terminal_state == "SUCCEEDED",
                )
            )
        )

    def lead_booking(self, lead_id: str, booking_id: str) -> LeadBooking:
        self.lead(lead_id)
        self.booking(booking_id)
        return self._required(
            self.db.scalar(
                select(LeadBooking).where(
                    LeadBooking.owner_id == self.owner_id,
                    LeadBooking.lead_id == lead_id,
                    LeadBooking.booking_id == booking_id,
                )
            )
        )

    def export_intents(self, lead_id: str, *, limit: int = 50) -> list[ExportIntent]:
        self.lead(lead_id)
        return list(
            self.db.scalars(
                select(ExportIntent)
                .join(Lead, Lead.id == ExportIntent.lead_id)
                .where(Lead.owner_id == self.owner_id, Lead.id == lead_id)
                .order_by(ExportIntent.projection_version, ExportIntent.id)
                .limit(self._limit(limit))
            )
        )


class AuthorizationService:
    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity
        self._issuer = object()

    @staticmethod
    def _claims(
        credential: OwnerCredential, store: Store, access: Literal["read", "write"]
    ) -> _Claims:
        return _Claims(
            credential.owner_id,
            credential.id,
            credential.context_id,
            store.generation,
            credential.token_digest,
            credential.csrf_binding,
            credential.issued_at,
            credential.expires_at,
            access,
        )

    def _resolve(
        self,
        material: bytes | None,
        context_id: str,
        csrf: str | None,
        access: Literal["read", "write"],
    ) -> AuthorizedOwnerContext:
        try:
            _CONTEXT_ID.validate_python(context_id)
        except ValidationError:
            raise ApiFailure("VALIDATION_ERROR") from None
        if material is None:
            raise ApiFailure("IDENTITY_REQUIRED")
        if access == "write" and csrf is None:
            raise ApiFailure("CSRF_DENIED")
        store = self.identity.open_store()

        def read(session: Session) -> _Claims:
            credential, _ = self.identity.authorize_in_unit(
                session, store, material, context_id, csrf
            )
            return self._claims(credential, store, access)

        claims = store.read(read)
        # Mint after the Store has verified materialization; no issuer object escapes a unit.
        context = object.__new__(AuthorizedOwnerContext)
        object.__setattr__(context, "_issuer", self._issuer)
        object.__setattr__(context, "_claims", claims)
        return context

    def authorize_read(self, material: bytes | None, context_id: str) -> AuthorizedOwnerContext:
        return self._resolve(material, context_id, None, "read")

    def authorize_write(
        self, material: bytes | None, context_id: str, csrf: str
    ) -> AuthorizedOwnerContext:
        return self._resolve(material, context_id, csrf, "write")

    def _run[T](
        self,
        context: AuthorizedOwnerContext,
        callback: Callable[[OwnerUnit], T],
        *,
        write: bool,
    ) -> T:
        if (
            type(context) is not AuthorizedOwnerContext
            or getattr(context, "_issuer", None) is not self._issuer
        ):
            raise ApiFailure("IDENTITY_REQUIRED")
        claims = context._claims
        if write and claims.access != "write":
            raise ApiFailure("CSRF_DENIED")
        store = self.identity.open_store()

        def run(session: Session) -> T:
            if store.generation != claims.generation:
                raise StoreError("STORE_GENERATION_CHANGED")
            credential, owner = self.identity.lookup_digest(
                session, claims.digest, self.identity.now_text()
            )
            if self._claims(credential, store, claims.access) != claims:
                raise ApiFailure("IDENTITY_REQUIRED")
            unit = OwnerUnit(session, owner)
            try:
                return callback(unit)
            finally:
                unit._active = False

        return store.write(run) if write else store.read(run)

    def read[T](self, context: AuthorizedOwnerContext, callback: Callable[[OwnerUnit], T]) -> T:
        return self._run(context, callback, write=False)

    def write[T](self, context: AuthorizedOwnerContext, callback: Callable[[OwnerUnit], T]) -> T:
        return self._run(context, callback, write=True)
