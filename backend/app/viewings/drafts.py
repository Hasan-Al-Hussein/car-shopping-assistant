"""Explicit owned draft/review lifecycle; never holds capacity or books a viewing."""

from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from app.api.schemas.common import InventoryRef
from app.api.schemas.leads import LeadValues, ReviewedExistingLead, ReviewedLeadCreation
from app.api.schemas.viewings import (
    BookingDraft,
    BookingDraftCreate,
    BookingDraftUpdate,
    BookingReview,
    ConfirmRequest,
)
from app.core.errors import ApiFailure
from app.database.models import BookingDraft as DraftRow
from app.database.models import BookingReview as ReviewRow
from app.database.models import CommandReceipt, ConversationSession, StoreMetadata
from app.database.store import StoreError, assert_outside_write_transaction
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.identity.service import utc_text
from app.sessions import repository as sessions
from app.sessions.state import canonical, copied, fingerprint
from app.viewings import draft_repository as repo
from app.viewings.draft_admission import DraftInventory, PreparedViewing, prepare, recheck
from app.viewings.draft_changes import (
    DraftChangeEffect,
    DraftCommandObservation,
    DraftSessionTransition,
    PreparedDraftChange,
)
from app.viewings.scheduling import SchedulingError, ViewingRules

if TYPE_CHECKING:
    from app.sessions.collection import DraftReplyAuthority


class DraftService:
    def __init__(
        self, authorization: AuthorizationService, *, inventory: DraftInventory | None = None
    ) -> None:
        self.authorization, self.inventory = authorization, inventory
        self.rules = ViewingRules(authorization.identity.settings.policy)

    def _now(self) -> str:
        return self.authorization.identity.now_text()

    def _view(self, unit: OwnerUnit, row: DraftRow, generation: str, now: str) -> BookingDraft:
        return repo.view(
            unit, row, now=now, generation=generation, rules=self.rules, gateway=self.inventory
        )

    def get(self, context: AuthorizedOwnerContext, draft_id: str) -> BookingDraft:
        draft_id = sessions.valid_id(draft_id)
        return self.authorization.read(
            context,
            lambda unit: self._view(
                unit,
                unit.draft(draft_id),
                context.generation,
                self._now(),
            ),
        )

    def _remember(
        self, unit: OwnerUnit, row: DraftRow, action_id: str, digest: str, generation: str, now: str,
        *, source_message_id: str | None = None,
    ) -> None:
        unit.db.add(
            CommandReceipt(
                id=str(uuid4()),
                owner_id=unit.owner_id,
                command_kind=repo.KIND,
                client_action_id=action_id,
                payload_hash=digest,
                applied_revision=row.revision,
                result_json=repo.DraftReceipt(
                    generation=generation, draft_id=row.id, source_message_id=source_message_id,
                ).model_dump(
                    mode="json"
                ),
                created_at=now,
                expires_at=utc_text(datetime.fromisoformat(now) + timedelta(days=90)),
            )
        )

    def _issue(
        self,
        unit: OwnerUnit,
        row: DraftRow,
        session: ConversationSession,
        prepared: PreparedViewing,
        now: str,
        *, final_session_revision: int,
    ) -> None:
        selected = repo.appointment(row)
        if selected is None:
            row.state = "needs_details"
            return
        start = datetime.fromisoformat(selected.starts_at_utc)
        try:
            interval = self.rules.validate_interval(
                start,
                start + timedelta(minutes=self.rules.policy.slot_minutes),
                now=datetime.fromisoformat(now),
                timezone=selected.timezone,
            )
        except (SchedulingError, OverflowError):
            raise ApiFailure("VALIDATION_ERROR") from None
        # The wire accepts equivalent UTC spellings; draft and review use one canonical spelling.
        row.appointment_json = selected.model_copy(
            update={
                "starts_at_utc": utc_text(interval.starts_at_utc),
            }
        ).model_dump(mode="json")
        lead = unit.lead_for_journey(session.journey_id)
        change: ReviewedLeadCreation | ReviewedExistingLead
        if lead is None:
            change = ReviewedLeadCreation(
                mode="create_from_review",
                source_session_revision=final_session_revision,
                values=LeadValues.model_validate(
                    dict(
                        budget={"state": "missing"},
                        email={"state": "missing"},
                        phone={"state": "missing"},
                        requirements=[],
                        selected_refs=[prepared.ref.model_dump(mode="json")],
                    )
                ),
            )
        else:
            if lead.expires_at <= now:
                raise ApiFailure("UNSUPPORTED_STATE")
            change = ReviewedExistingLead(
                mode="preserve_existing", lead_id=lead.id, expected_revision=lead.revision
            )
        review = BookingReview(
            review_id=str(uuid4()),
            draft_id=row.id,
            session_id=session.id,
            draft_revision=row.revision,
            ref=prepared.ref,
            resource_id=prepared.resource_id,
            starts_at_utc=utc_text(interval.starts_at_utc),
            ends_at_utc=utc_text(interval.ends_at_utc),
            local_start=interval.local_start,
            timezone=interval.timezone,
            venue_label="Simulated local viewing — no real venue or reservation.",
            rules_version=prepared.configuration_version,
            eligibility_version=prepared.eligibility_version,
            store_generation=prepared.generation,
            operation_key=secrets.token_urlsafe(32),
            issued_at=now,
            expires_at=repo.later(now, minutes=5),
            lead_change=change,
            state="valid",
        )
        payload = repo.StoredReview(
            owner_id=unit.owner_id,
            session_revision=final_session_revision,
            review=review,
            admission=prepared,
        )
        unit.db.add(
            ReviewRow(
                id=review.review_id,
                owner_id=unit.owner_id,
                draft_id=row.id,
                draft_revision=row.revision,
                operation_key=review.operation_key,
                payload_hash=repo.digest(payload),
                immutable_payload_json=payload.model_dump(mode="json"),
                store_generation=prepared.generation,
                issued_at=now,
                expires_at=review.expires_at,
                state="valid",
            )
        )
        unit.db.flush()
        row.active_review_id, row.state = review.review_id, "reviewable"

    @staticmethod
    def _copied_change(
        command: BookingDraftCreate | BookingDraftUpdate, draft_id: str | None,
    ) -> tuple[BookingDraftCreate | BookingDraftUpdate, str | None]:
        try:
            if isinstance(command, BookingDraftCreate) and draft_id is None:
                return copied(BookingDraftCreate, command), None
            if isinstance(command, BookingDraftUpdate) and draft_id is not None:
                return copied(BookingDraftUpdate, command), sessions.valid_id(draft_id)
        except (AttributeError, TypeError, ValueError):
            pass
        raise ApiFailure("VALIDATION_ERROR")

    @staticmethod
    def _command_hash(
        command: BookingDraftCreate | BookingDraftUpdate, draft_id: str | None,
    ) -> str:
        body = command.model_dump(mode="json")
        return fingerprint(
            dict(command="create", body=body) if isinstance(command, BookingDraftCreate)
            else dict(command="update", draft_id=draft_id, body=body)
        )

    @staticmethod
    def _generation(unit: OwnerUnit, generation: str, submitted_generation: str) -> None:
        sessions.valid_id(generation)
        sessions.valid_id(submitted_generation)
        metadata = unit.db.get(StoreMetadata, 1)
        if (
            metadata is None or metadata.store_generation != generation
            or submitted_generation != generation
        ):
            raise ApiFailure("STORE_GENERATION_CHANGED")

    @staticmethod
    def _allow_transition(
        unit: OwnerUnit, session: ConversationSession, *, generation: str,
        command_hash: str, source_message_id: str | None, now: str,
        reply: DraftReplyAuthority | None,
    ) -> None:
        if reply is None:
            repo.allow_transition(sessions.content(session))
            return
        if source_message_id is None:
            raise ApiFailure("UNSUPPORTED_STATE")
        from app.sessions.collection import check_draft_reply_in_unit

        check_draft_reply_in_unit(
            unit, reply, session_id=session.id, generation=generation,
            command_hash=command_hash, now=now,
        )

    def lookup_change_in_unit(
        self, unit: OwnerUnit, command: BookingDraftCreate | BookingDraftUpdate, *,
        draft_id: str | None = None, generation: str, submitted_generation: str,
        now: str, source_message_id: str | None = None,
    ) -> DraftCommandObservation | None:
        command, draft_id = self._copied_change(command, draft_id)
        self._generation(unit, generation, submitted_generation)
        if source_message_id is not None:
            sessions.valid_id(source_message_id)
        digest = self._command_hash(command, draft_id)
        row = repo.receipt(
            unit, command.client_action_id, digest, submitted_generation, now,
            source_message_id=source_message_id,
        )
        if row is None:
            return None  # Not definitive noncommit or permission for a replacement key.
        if row.session_id is None:
            raise ApiFailure("NOT_FOUND")
        prior = sessions.receipt(unit, repo.KIND, command.client_action_id, digest, now)
        if prior is None:
            raise StoreError("DRAFT_RECEIPT_INCOMPATIBLE")
        return DraftCommandObservation(row.id, row.session_id, prior.applied_revision)

    def _inspect_change(
        self, unit: OwnerUnit, command: BookingDraftCreate | BookingDraftUpdate, *,
        draft_id: str | None, generation: str, now: str,
        source_message_id: str | None, reply: DraftReplyAuthority | None,
    ) -> tuple[DraftRow | None, ConversationSession]:
        from app.sessions.collection_state import check_collection_command_fence

        digest = self._command_hash(command, draft_id)
        check_collection_command_fence(
            unit, source_message_id=source_message_id, command_hash=digest,
        )
        row: DraftRow | None = None
        if isinstance(command, BookingDraftCreate):
            repo.owner_uncertain(unit)
            session = sessions.live_session(unit, command.session_id, now)
            sessions.revision(session, command.expected_session_revision)
        else:
            assert draft_id is not None
            row = unit.draft(draft_id)
            repo.editable(unit, row, command.expected_revision)
            if row.session_id is None:
                raise ApiFailure("NOT_FOUND")
            session = sessions.live_session(unit, row.session_id, now)
        if session.revision >= repo.MAX_REVISION:
            raise ApiFailure("UNSUPPORTED_STATE")
        content = sessions.content(session)
        sessions.validate_context(unit, session, content)
        self._allow_transition(
            unit, session, generation=generation, command_hash=digest,
            source_message_id=source_message_id, now=now, reply=reply,
        )
        if source_message_id is not None:
            message = unit.message(session.id, sessions.valid_id(source_message_id))
            if (
                message.state != "pending" or message.accepted_revision != session.revision
                or sessions.message_content(message).assistant_result is not None
            ):
                raise ApiFailure("UNSUPPORTED_STATE")
        if row is not None:
            if content.current_draft_id != row.id:
                raise ApiFailure("REVIEW_STALE")
            self._view(unit, row, generation, now)
        elif content.current_draft_id is not None:
            prior = unit.draft_for_session(session.id, content.current_draft_id)
            proven = prior.active_review_id is not None and repo.terminal_proven(
                unit, unit.review_for_draft(prior.id, prior.active_review_id),
            )
            if prior.state not in {"discarded", "resolved"} and not proven:
                raise ApiFailure("UNSUPPORTED_STATE")
        return row, session

    def prepare_change(
        self, context: AuthorizedOwnerContext,
        command: BookingDraftCreate | BookingDraftUpdate, *,
        draft_id: str | None = None, submitted_generation: str,
        source_message_id: str | None = None, reply: DraftReplyAuthority | None = None,
    ) -> PreparedDraftChange | None:
        assert_outside_write_transaction()
        command, draft_id = self._copied_change(command, draft_id)

        def inspect(unit: OwnerUnit) -> tuple[PreparedDraftChange, InventoryRef] | None:
            now = self._now()
            if self.lookup_change_in_unit(
                unit, command, draft_id=draft_id, generation=context.generation,
                submitted_generation=submitted_generation, now=now,
                source_message_id=source_message_id,
            ) is not None:
                return None
            row, session = self._inspect_change(
                unit, command, draft_id=draft_id, generation=context.generation,
                now=now, source_message_id=source_message_id, reply=reply,
            )
            exact = command.ref
            if exact is None:
                assert row is not None
                exact = self._view(unit, row, context.generation, now).ref
            bound = PreparedDraftChange(
                unit.owner_id, context.generation, source_message_id, session.id, draft_id,
                canonical(command.model_dump(mode="json")), self._command_hash(command, draft_id),
                None,
            )
            return bound, exact

        inspected = self.authorization.read(context, inspect)
        if inspected is None:
            return None  # Consuming write must find the exact receipt or reject.
        bound, exact = inspected
        needs_inventory = isinstance(command, BookingDraftCreate) or command.intent in {
            "edit", "refresh_review",
        }
        viewing = prepare(self.inventory, exact, context.generation) if needs_inventory else None
        return replace(bound, viewing=viewing)

    def change_in_unit(
        self, unit: OwnerUnit, command: BookingDraftCreate | BookingDraftUpdate, *,
        draft_id: str | None = None, generation: str, submitted_generation: str,
        now: str, prepared: PreparedDraftChange | None, final_session_revision: int,
        source_message_id: str | None = None, reply: DraftReplyAuthority | None = None,
    ) -> DraftChangeEffect:
        """Stage domain effects only. Every later exception aborts the whole caller unit."""
        repo.require_write(unit)
        command, draft_id = self._copied_change(command, draft_id)
        prior = self.lookup_change_in_unit(
            unit, command, draft_id=draft_id, generation=generation,
            submitted_generation=submitted_generation, now=now,
            source_message_id=source_message_id,
        )
        if prior is not None:
            return DraftChangeEffect(
                prior.draft_id, prior.session_id, prior.applied_revision, True, None,
            )
        row, session = self._inspect_change(
            unit, command, draft_id=draft_id, generation=generation, now=now,
            source_message_id=source_message_id, reply=reply,
        )
        bound = PreparedDraftChange(
            unit.owner_id, generation, source_message_id, session.id, draft_id,
            canonical(command.model_dump(mode="json")), self._command_hash(command, draft_id), None,
        )
        if prepared is None or replace(prepared, viewing=None) != bound:
            raise ApiFailure("UNSUPPORTED_STATE")
        if (
            type(final_session_revision) is not int
            or final_session_revision not in {session.revision, session.revision + 1}
            or final_session_revision > repo.MAX_REVISION
        ):
            raise ApiFailure("REVISION_CONFLICT")
        needs_inventory = isinstance(command, BookingDraftCreate) or command.intent in {
            "edit", "refresh_review",
        }
        if needs_inventory != (prepared.viewing is not None):
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
        if prepared.viewing is not None:
            exact = command.ref
            if exact is None:
                assert row is not None
                exact = self._view(unit, row, generation, now).ref
            if exact.model_dump(mode="json") != prepared.viewing.ref.model_dump(mode="json"):
                raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
            recheck(unit, prepared.viewing, generation, self.rules, self.inventory)
        before = sessions.content(session)
        if isinstance(command, BookingDraftCreate):
            assert prepared.viewing is not None
            row = DraftRow(
                id=str(uuid4()), owner_id=unit.owner_id, session_id=session.id, revision=1,
                **prepared.viewing.ref.model_dump(),
                appointment_json=(
                    None if command.appointment is None
                    else command.appointment.model_dump(mode="json")
                ),
                state="needs_details", active_review_id=None, created_at=now, updated_at=now,
                expires_at=repo.later(now, minutes=30),
            )
            unit.db.add(row)
            unit.db.flush()
            self._issue(
                unit, row, session, prepared.viewing, now,
                final_session_revision=final_session_revision,
            )
        else:
            assert row is not None
            repo.invalidate(unit, row)
            row.revision += 1
            row.updated_at = now
            if command.intent in {"suspend", "discard"}:
                row.state = "suspended" if command.intent == "suspend" else "discarded"
            else:
                assert prepared.viewing is not None
                row.namespace, row.snapshot_id, row.source_id = (
                    prepared.viewing.ref.namespace, prepared.viewing.ref.snapshot_id,
                    prepared.viewing.ref.source_id,
                )
                if command.appointment is not None:
                    row.appointment_json = command.appointment.model_dump(mode="json")
                row.expires_at = repo.later(now, minutes=30)
                self._issue(
                    unit, row, session, prepared.viewing, now,
                    final_session_revision=final_session_revision,
                )
        self._remember(
            unit, row, command.client_action_id, bound.payload_hash, generation, now,
            source_message_id=source_message_id,
        )
        unit.db.flush()
        after = repo.transition_content(unit, session, row)
        if after != before and final_session_revision != session.revision + 1:
            raise ApiFailure("REVISION_CONFLICT")
        transition = DraftSessionTransition(
            unit.owner_id, generation, session.id, row.id, row.revision,
            source_message_id, bound.payload_hash, session.revision, final_session_revision,
            before.current_draft_id, canonical(before.pending_intent.model_dump(mode="json")),
            after.current_draft_id, canonical(after.pending_intent.model_dump(mode="json")),
        )
        return DraftChangeEffect(row.id, session.id, row.revision, False, transition)

    def resolve_session_in_unit(
        self, unit: OwnerUnit, *, transition: DraftSessionTransition,
        reply: DraftReplyAuthority | None = None,
    ) -> None:
        """Apply exact proven fields only; caller still owns revision/activity/message."""
        repo.require_write(unit)
        self._generation(unit, transition.generation, transition.generation)
        if transition.owner_id != unit.owner_id:
            raise ApiFailure("NOT_FOUND")
        session = unit.session(transition.session_id)
        before = sessions.content(session)
        if (
            session.revision != transition.before_revision
            or before.current_draft_id != transition.before_draft_id
            or canonical(before.pending_intent.model_dump(mode="json"))
            != transition.before_pending_json
        ):
            raise ApiFailure("REVISION_CONFLICT")
        self._allow_transition(
            unit, session, generation=transition.generation,
            command_hash=transition.command_hash, source_message_id=transition.source_message_id,
            now=self._now(), reply=reply,
        )
        row = unit.draft_for_session(session.id, transition.draft_id)
        if row.revision != transition.draft_revision:
            raise ApiFailure("REVISION_CONFLICT")
        after = repo.transition_content(unit, session, row)
        if (
            after.current_draft_id != transition.after_draft_id
            or canonical(after.pending_intent.model_dump(mode="json")) != transition.after_pending_json
        ):
            raise ApiFailure("REVIEW_STALE")
        if row.active_review_id is not None:
            authority = repo.stored_review(unit, unit.review_for_draft(row.id, row.active_review_id))
            if authority.session_revision != transition.final_revision:
                raise ApiFailure("REVIEW_STALE")
        session.state_json = after.model_dump(mode="json")

    def observe_changed_in_unit(
        self, unit: OwnerUnit, *, effect: DraftChangeEffect, generation: str, now: str,
    ) -> BookingDraft:
        row = unit.draft_for_session(effect.session_id, effect.draft_id)
        if effect.replayed:
            if row.revision < effect.applied_revision:
                raise StoreError("DRAFT_RECEIPT_INCOMPATIBLE")
        else:
            transition = effect.transition
            if transition is None or transition.owner_id != unit.owner_id:
                raise ApiFailure("UNSUPPORTED_STATE")
            session = unit.session(effect.session_id)
            content = sessions.content(session)
            if (
                row.revision != effect.applied_revision or generation != transition.generation
                or session.revision != transition.final_revision
                or content.current_draft_id != transition.after_draft_id
                or canonical(content.pending_intent.model_dump(mode="json"))
                != transition.after_pending_json
            ):
                raise ApiFailure("REVIEW_STALE")
        return self._view(unit, row, generation, now)

    def _change(
        self, context: AuthorizedOwnerContext, command: BookingDraftCreate | BookingDraftUpdate, *,
        draft_id: str | None,
    ) -> BookingDraft:
        command, draft_id = self._copied_change(command, draft_id)
        prepared = self.prepare_change(
            context, command, draft_id=draft_id, submitted_generation=context.generation,
        )
        if prepared is None:
            def replay(unit: OwnerUnit) -> BookingDraft:
                now = self._now()
                prior = self.lookup_change_in_unit(
                    unit, command, draft_id=draft_id, generation=context.generation,
                    submitted_generation=context.generation, now=now,
                )
                if prior is None:
                    raise ApiFailure("OPERATION_UNRESOLVED")
                return self._view(unit, unit.draft(prior.draft_id), context.generation, now)

            return self.authorization.read(context, replay)

        def write(unit: OwnerUnit) -> BookingDraft:
            now = self._now()
            session = unit.session(prepared.session_id)
            effect = self.change_in_unit(
                unit, command, draft_id=draft_id, generation=context.generation,
                submitted_generation=context.generation, now=now, prepared=prepared,
                final_session_revision=session.revision + 1,
            )
            if effect.transition is not None:
                self.resolve_session_in_unit(unit, transition=effect.transition)
                session.revision = effect.transition.final_revision
                sessions.activity(session, now, 7)
            return self.observe_changed_in_unit(
                unit, effect=effect, generation=context.generation, now=now,
            )

        return self.authorization.write(context, write)

    def create(self, context: AuthorizedOwnerContext, command: BookingDraftCreate) -> BookingDraft:
        return self._change(context, command, draft_id=None)

    def update(
        self, context: AuthorizedOwnerContext, draft_id: str, command: BookingDraftUpdate,
    ) -> BookingDraft:
        return self._change(context, command, draft_id=draft_id)

    def mark_submitted(
        self,
        unit: OwnerUnit,
        draft_id: str,
        command: ConfirmRequest,
        *,
        generation: str,
        now: str,
    ) -> BookingReview:
        """BE15 caller-unit seam, not a confirm endpoint or independently durable queue.

        Caller resolves prior terminal outcomes first, then validates capacity and
        commits every participant/outcome atomically. This does not advance the
        source session revision before T5's reviewed-lead participant checks it.
        """
        repo.require_write(unit)
        try:
            command = copied(ConfirmRequest, command)
        except (AttributeError, TypeError, ValueError):
            raise ApiFailure("VALIDATION_ERROR") from None
        row = unit.draft(sessions.valid_id(draft_id))
        if command.store_generation != generation:
            raise ApiFailure("STORE_GENERATION_CHANGED")
        repo.owner_uncertain(unit)
        current = self._view(unit, row, generation, now)
        review = current.review
        if (
            current.state != "reviewable"
            or review is None
            or (
                review.review_id,
                review.draft_revision,
                review.operation_key,
                review.rules_version,
            )
            != (
                command.review_id,
                command.expected_draft_revision,
                command.operation_key,
                command.rules_version,
            )
        ):
            raise ApiFailure("REVIEW_STALE")
        stored = unit.review_for_draft(row.id, review.review_id)
        stored.state, row.state = "submitted", "unresolved"
        unit.db.flush()
        return review.model_copy(update={"state": "submitted"}, deep=True)
