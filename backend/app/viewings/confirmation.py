"""Shared UI/chat confirmation in one caller-owned authorized write transaction.

No method commits a booking itself. An apply result is provisional until the
outer authorization write returns successfully. Preparation stays outside WRITE.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import select

from app.api.schemas.common import Id, OpaqueKey, UtcInstant
from app.api.schemas.leads import (
    ExportNotRequested,
    LeadNotRequested,
    RequestedExportOutcome,
    ReviewedLeadCreation,
)
from app.api.schemas.operations import (
    BookingNotCreated,
    BusinessRejectionCode,
    OperationGenerationUnresolved,
    OperationNotObserved,
    OperationRejected,
    OperationStatus,
    OperationSucceeded,
)
from app.api.schemas.sessions import NoPendingIntent, ViewingReviewIntent
from app.api.schemas.viewings import BookingCoreReceipt, ConfirmRequest
from app.core.errors import ApiFailure
from app.database.models import BookingReview as ReviewRow
from app.database.models import ExportState
from app.database.store import StoreError, assert_outside_write_transaction
from app.identity.authorization import AuthorizedOwnerContext, OwnerUnit
from app.identity.service import utc_text
from app.inventory.references import ImmutableInventoryRef
from app.leads import repository as lead_repository
from app.leads.participant import LeadParticipant
from app.sessions import repository as sessions
from app.sessions.state import SessionContent, fingerprint
from app.shortlist.inventory import ReferenceBatch
from app.shortlist.inventory import prepare as prepare_refs
from app.viewings import confirmation_repository as repo
from app.viewings import draft_repository as drafts
from app.viewings.draft_admission import PreparedViewing
from app.viewings.draft_admission import prepare as prepare_viewing
from app.viewings.draft_admission import recheck
from app.viewings.drafts import DraftService
from app.viewings.scheduling import SchedulingError

type TerminalOutcome = OperationSucceeded | OperationRejected

_KEY = TypeAdapter(OpaqueKey)
_ID = TypeAdapter(Id)
_TIME = TypeAdapter(UtcInstant)


@dataclass(frozen=True)
class PreparedConfirmation:
    owner_id: str
    draft_id: str
    command_hash: str
    review_hash: str
    viewing: PreparedViewing
    lead_refs: ReferenceBatch | None


@dataclass(frozen=True)
class ConfirmationTransition:
    owner_id: str
    session_id: str
    expected_revision: int
    draft_id: str
    review_id: str
    operation_key: str
    generation: str
    terminal_at: str


@dataclass(frozen=True)
class ConfirmationEffect:
    terminal: TerminalOutcome
    replayed: bool
    transition: ConfirmationTransition | None


class ConfirmationParticipant:
    def __init__(self, drafts: DraftService, *, leads: LeadParticipant) -> None:
        self.drafts, self.leads = drafts, leads
        self.authorization = drafts.authorization

    @staticmethod
    def _validated_time(now: str) -> str:
        try:
            return utc_text(datetime.fromisoformat(_TIME.validate_python(now)))
        except ValueError:
            raise ApiFailure("VALIDATION_ERROR") from None

    def lookup_in_unit(
        self,
        unit: OwnerUnit,
        *,
        draft_id: str,
        command: ConfirmRequest,
        generation: str,
        now: str,
    ) -> TerminalOutcome | None:
        draft_id, command = repo.command_copy(draft_id, command)
        now = self._validated_time(now)
        repo.generation_current(unit, generation)
        try:
            authority, _ = repo.bound_authority(unit, draft_id, command)
        except ApiFailure as exc:
            if exc.code == "NOT_FOUND" and command.store_generation != generation:
                raise ApiFailure("STORE_GENERATION_CHANGED") from None
            raise
        terminal = repo.terminal(unit, authority, now)
        if terminal is not None:
            return terminal
        if command.store_generation != generation:
            raise ApiFailure("STORE_GENERATION_CHANGED")
        return None

    @staticmethod
    def _fresh_context(unit: OwnerUnit, payload: drafts.StoredReview, now: str) -> None:
        review = payload.review
        row = unit.draft(review.draft_id)
        session = sessions.live_session(unit, review.session_id, now)
        content = sessions.content(session)
        sessions.validate_context(unit, session, content)
        pending = content.pending_intent
        if (
            row.session_id != session.id
            or row.active_review_id != review.review_id
            or row.revision != review.draft_revision
            or row.state != "reviewable"
            or row.expires_at <= now
            or review.expires_at <= now
            or session.revision != payload.session_revision
            or content.current_draft_id != row.id
            or not isinstance(pending, ViewingReviewIntent)
            or (pending.draft_id, pending.review_id, pending.operation_key)
            != (row.id, review.review_id, review.operation_key)
            or not drafts.lead_current(unit, review, session, now)
        ):
            raise ApiFailure("REVIEW_STALE")
        if session.revision >= drafts.MAX_REVISION:
            raise ApiFailure("UNSUPPORTED_STATE")

    def prepare(
        self,
        context: AuthorizedOwnerContext,
        *,
        draft_id: str,
        command: ConfirmRequest,
    ) -> PreparedConfirmation | None:
        assert_outside_write_transaction()
        draft_id, command = repo.command_copy(draft_id, command)

        def inspect(unit: OwnerUnit) -> drafts.StoredReview | None:
            now = self.authorization.identity.now_text()
            if self.lookup_in_unit(
                unit, draft_id=draft_id, command=command, generation=context.generation, now=now
            ) is not None:
                return None
            authority, payload = repo.bound_authority(unit, draft_id, command)
            if authority.review.state != "valid":
                raise ApiFailure("REVIEW_STALE")
            self._fresh_context(unit, payload, now)
            return payload

        payload = self.authorization.read(context, inspect)
        if payload is None:
            return None
        viewing = prepare_viewing(self.drafts.inventory, payload.review.ref, context.generation)
        refs = None
        change = payload.review.lead_change
        if isinstance(change, ReviewedLeadCreation) and change.values.selected_refs:
            refs = prepare_refs(
                self.leads.inventory,
                tuple(
                    ImmutableInventoryRef.model_validate(ref.model_dump())
                    for ref in change.values.selected_refs
                ),
                context.generation,
            )
        return PreparedConfirmation(
            payload.owner_id,
            draft_id,
            fingerprint(command.model_dump(mode="json")),
            drafts.digest(payload),
            viewing,
            refs,
        )

    def apply_in_unit(
        self,
        unit: OwnerUnit,
        *,
        draft_id: str,
        command: ConfirmRequest,
        generation: str,
        now: str,
        prepared: PreparedConfirmation | None,
    ) -> ConfirmationEffect:
        drafts.require_write(unit)
        draft_id, command = repo.command_copy(draft_id, command)
        now = self._validated_time(now)
        replay = self.lookup_in_unit(
            unit, draft_id=draft_id, command=command, generation=generation, now=now
        )
        if replay is not None:
            return ConfirmationEffect(replay, True, None)
        authority, payload = repo.bound_authority(unit, draft_id, command)
        if prepared is None or type(prepared) is not PreparedConfirmation or (
            prepared.owner_id,
            prepared.draft_id,
            prepared.command_hash,
            prepared.review_hash,
        ) != (
            unit.owner_id,
            draft_id,
            fingerprint(command.model_dump(mode="json")),
            drafts.digest(payload),
        ):
            raise ApiFailure("VALIDATION_ERROR")
        self._fresh_context(unit, payload, now)
        # The real BE14 participant accepts the current review without advancing session R.
        submitted = self.drafts.mark_submitted(
            unit, draft_id, command, generation=generation, now=now
        )
        accepted = BookingCoreReceipt(
            state="confirmed_simulated",
            booking_id=str(uuid4()),
            review=submitted.model_copy(update={"state": "consumed"}, deep=True),
            confirmed_at=now,
        )
        rejection = self._final_rejection(unit, payload, prepared, accepted, generation, now)
        authority.review.state = "consumed"
        unit.draft(draft_id).state = "resolved"
        outcome = repo.stage_outcome(
            unit,
            authority,
            succeeded=rejection is None,
            now=now,
            retention_days=self.drafts.rules.policy.terminal_record_retention_days,
        )
        result: TerminalOutcome
        if rejection is not None:
            result = OperationRejected(
                state="rejected",
                operation_key=command.operation_key,
                review_id=command.review_id,
                original_store_generation=generation,
                terminal_at=now,
                replay_valid_until=outcome.replay_valid_until,
                rejection_code=rejection,
                booking=BookingNotCreated(state="not_created"),
                lead=LeadNotRequested(state="not_requested"),
                csv=ExportNotRequested(state="not_requested"),
            )
        else:
            repo.stage_booking(unit, outcome, accepted)
            participating = self.leads.apply(
                unit,
                accepted=accepted,
                generation=generation,
                now=now,
                retention_days=self.drafts.rules.policy.terminal_record_retention_days,
                prepared=prepared.lead_refs,
            )
            result = OperationSucceeded(
                state="succeeded",
                operation_key=command.operation_key,
                review_id=command.review_id,
                original_store_generation=generation,
                terminal_at=now,
                replay_valid_until=outcome.replay_valid_until,
                booking=accepted,
                lead=participating.lead,
                csv=participating.csv,
            )
        outcome.terminal_result_json = result.model_dump(mode="json")
        unit.db.flush()
        proven = repo.terminal(unit, unit.operation(command.operation_key), now)
        if proven is None:
            raise StoreError("CONFIRMATION_TERMINAL_MISSING")
        transition = ConfirmationTransition(
            unit.owner_id,
            payload.review.session_id,
            payload.session_revision,
            draft_id,
            command.review_id,
            command.operation_key,
            generation,
            now,
        )
        return ConfirmationEffect(proven, False, transition)

    def _final_rejection(
        self,
        unit: OwnerUnit,
        payload: drafts.StoredReview,
        prepared: PreparedConfirmation,
        accepted: BookingCoreReceipt,
        generation: str,
        now: str,
    ) -> BusinessRejectionCode | None:
        # Only deliberate business checks before any booking/lead/outcome mutation.
        # No broad catch around participant writes: storage/unknown failures roll back.
        try:
            recheck(unit, prepared.viewing, generation, self.drafts.rules, self.drafts.inventory)
        except ApiFailure as exc:
            if exc.code == "SNAPSHOT_STALE":
                return "SNAPSHOT_STALE"
            if exc.code == "RULES_UNAVAILABLE":
                return "RULES_UNAVAILABLE"
            if exc.code == "ELIGIBILITY_UNAVAILABLE":
                return "ELIGIBILITY_UNAVAILABLE"
            raise
        if not repo.same_viewing_material(prepared.viewing, payload.admission):
            return "REVIEW_STALE"
        review = accepted.review
        try:
            self.drafts.rules.validate_interval(
                datetime.fromisoformat(review.starts_at_utc),
                datetime.fromisoformat(review.ends_at_utc),
                now=datetime.fromisoformat(now),
                timezone=review.timezone,
                local_start=review.local_start,
            )
        except (SchedulingError, OverflowError):
            return "REVIEW_STALE"
        if repo.capacity_taken(unit, accepted):
            return "CAPACITY_UNAVAILABLE"
        session = unit.session(review.session_id)
        lead = unit.lead_for_journey(session.journey_id)
        if lead is not None:
            current = lead_repository.record(unit, lead, generation, now)
            if lead.revision >= drafts.MAX_REVISION or len(current.booking_ids) >= 100:
                return "UNSUPPORTED_STATE"
        projection = unit.db.get(ExportState, 1)
        if projection is not None:
            observed = lead_repository.projection(unit, generation, now, allow_empty=True)
            if observed.canonical_version >= drafts.MAX_REVISION:
                return "UNSUPPORTED_STATE"
        return None

    def resolve_session_in_unit(
        self, unit: OwnerUnit, *, transition: ConfirmationTransition
    ) -> None:
        drafts.require_write(unit)
        if type(transition) is not ConfirmationTransition or transition.owner_id != unit.owner_id:
            raise ApiFailure("NOT_FOUND")
        repo.generation_current(unit, transition.generation)
        authority = unit.operation(transition.operation_key)
        payload = drafts.stored_review(unit, authority.review)
        terminal = repo.terminal(unit, authority, transition.terminal_at)
        session = unit.session(transition.session_id)
        before = sessions.content(session)
        pending = before.pending_intent
        if (
            terminal is None
            or terminal.terminal_at != transition.terminal_at
            or terminal.original_store_generation != transition.generation
            or authority.review.id != transition.review_id
            or payload.review.draft_id != transition.draft_id
            or payload.review.session_id != transition.session_id
            or payload.session_revision != transition.expected_revision
            or session.revision != transition.expected_revision
            or before.current_draft_id != transition.draft_id
            or not isinstance(pending, ViewingReviewIntent)
            or (pending.draft_id, pending.review_id, pending.operation_key)
            != (transition.draft_id, transition.review_id, transition.operation_key)
        ):
            raise ApiFailure("REVIEW_STALE")
        # Dedicated proven domain transition; generic protect_operation stays strict.
        after = SessionContent.model_validate(
            {
                **before.model_dump(mode="json"),
                "current_draft_id": None,
                "pending_intent": NoPendingIntent(kind="none").model_dump(mode="json"),
            }
        )
        sessions.validate_context(unit, session, after)
        session.state_json = after.model_dump(mode="json")

    def status(
        self,
        context: AuthorizedOwnerContext,
        *,
        operation_key: str,
        submitted_generation: str,
    ) -> OperationStatus:
        try:
            operation_key = _KEY.validate_python(operation_key)
            submitted_generation = _ID.validate_python(submitted_generation)
        except ValueError:
            raise ApiFailure("VALIDATION_ERROR") from None

        def read(unit: OwnerUnit) -> OperationStatus:
            repo.generation_current(unit, context.generation)
            row = unit.db.scalar(
                select(ReviewRow).where(
                    ReviewRow.owner_id == unit.owner_id,
                    ReviewRow.operation_key == operation_key,
                )
            )
            if row is not None:
                if row.store_generation != submitted_generation:
                    raise ApiFailure("IDEMPOTENCY_CONFLICT")
                authority = unit.operation(operation_key)
                # Submitted/consumed without a terminal is unknown, not a business result.
                if authority.outcome is not None:
                    now = self.authorization.identity.now_text()
                    proven = repo.terminal(unit, authority, now)
                    if proven is not None:
                        if isinstance(proven, OperationSucceeded):
                            # Current global observation is a response overlay, never an UPDATE.
                            # If projection observation fails, propagate the failure; retained
                            # terminal authority remains intact and must not be retried as new.
                            return proven.model_copy(
                                update={"csv": self.observe_csv_in_unit(
                                    unit, generation=context.generation, now=now
                                )},
                                deep=True,
                            )
                        return proven
            if submitted_generation != context.generation:
                return OperationGenerationUnresolved(
                    state="unresolved_generation",
                    operation_key=operation_key,
                    observed_store_generation=context.generation,
                    submitted_store_generation=submitted_generation,
                )
            return OperationNotObserved(
                state="not_observed",
                operation_key=operation_key,
                observed_store_generation=context.generation,
                recovery="read_original_operation",
            )

        return self.authorization.read(context, read)

    @staticmethod
    def observe_csv_in_unit(
        unit: OwnerUnit, *, generation: str, now: str
    ) -> RequestedExportOutcome:
        repo.generation_current(unit, generation)
        return lead_repository.projection(
            unit, generation, ConfirmationParticipant._validated_time(now)
        )
