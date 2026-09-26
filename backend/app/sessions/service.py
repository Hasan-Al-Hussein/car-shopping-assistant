"""Revision-bound owned sessions and ordered turns, with no model calls."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import select

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import PresentationProof
from app.api.schemas.leads import LeadSaveRequest, LeadUpdateRequest
from app.api.schemas.memory import MembershipRequest, PreferenceCommand, PreferencesUpdate
from app.api.schemas.operations import OperationRejected, OperationSucceeded
from app.api.schemas.sessions import (
    ActionRejected,
    ClarificationIntent,
    MessageActionResults,
    MessageRequest,
    MessageResult,
    NoPendingIntent,
    PreferenceActionSucceeded,
    PresentationRegisterRequest,
    SessionCreateRequest,
    SessionSelectionRequest,
    SessionState,
    ShortlistActionSucceeded,
    TranscriptPage,
    TranscriptTurn,
)
from app.api.schemas.viewings import BookingDraftCreate, BookingDraftUpdate, ConfirmRequest
from app.core.errors import ApiFailure
from app.database.models import (
    ConversationSession,
    InventorySnapshot,
    ListingVersion,
    Message,
    OwnerCredential,
    PresentationItem,
)
from app.database.store import StoreError, assert_outside_write_transaction
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.inventory.references import ImmutableInventoryRef
from app.leads.service import LeadService
from app.memory.service import PreferenceRejected, PreferenceService
from app.sessions import repository as repo
from app.sessions.collection import CollectionSnapshot, CollectionUpdate, collection_digest
from app.sessions.collection_state import apply_update, owned_collection, unresolved_command
from app.sessions.cursors import TranscriptCursor, decode_cursor, encode_cursor
from app.sessions.inventory import InventoryAdmission, SessionInventory, check_admission
from app.sessions.state import SessionContent, StoredMessage, copied, fingerprint
from app.shortlist.inventory import ReferenceBatch
from app.shortlist.service import MembershipRejected, ShortlistService
from app.viewings.confirmation import ConfirmationParticipant
from app.viewings.drafts import DraftService

PROCESS_INSTANCE = str(uuid4())
PREFERENCE_COMMAND: TypeAdapter[PreferenceCommand] = TypeAdapter(PreferenceCommand)


@dataclass(frozen=True)
class ShortlistChange:
    ref: InventoryRef
    command: MembershipRequest
    desired: bool


@dataclass(frozen=True)
class LeadChange:
    command: LeadSaveRequest | LeadUpdateRequest
    lead_id: str | None = None


@dataclass(frozen=True)
class DraftChange:
    command: BookingDraftCreate | BookingDraftUpdate
    draft_id: str | None = None


@dataclass(frozen=True)
class OwnedPresentationView:
    """Original owned order, not current inventory or action authority."""

    session_id: str
    presentation_id: str
    snapshot_id: str
    created_revision: int
    refs: tuple[ImmutableInventoryRef, ...]


class TurnTicket:
    """Process-local completion authority for one newly accepted turn; never serialize."""

    __slots__ = ("_issuer", "_context_id", "_generation", "_session_id", "_message_id")
    _issuer: object
    _context_id: str
    _generation: str
    _session_id: str
    _message_id: str

    def __new__(cls) -> "TurnTicket":
        raise TypeError("TURN_TICKET_IS_SERVICE_ISSUED")

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("TURN_TICKET_IS_IMMUTABLE")

    def __repr__(self) -> str:
        return "<TurnTicket>"


@dataclass(frozen=True)
class TurnAdmission:
    status: Literal["accepted", "completed", "pending", "interrupted"]
    message_id: str
    session: SessionState = field(repr=False)
    request: MessageRequest = field(repr=False)
    result: MessageResult | None = field(default=None, repr=False)
    ticket: TurnTicket | None = field(default=None, repr=False)


@dataclass(frozen=True)
class _AdmissionData:
    status: Literal["accepted", "completed", "pending", "interrupted"]
    message_id: str
    session: SessionState
    request: MessageRequest
    result: MessageResult | None = None


class SessionService:
    def __init__(
        self,
        authorization: AuthorizationService,
        *,
        inventory: SessionInventory | None = None,
        instance_id: str = PROCESS_INSTANCE,
    ) -> None:
        self.authorization = authorization
        self.inventory = inventory
        self._issuer = object()
        self._epoch = repo.valid_id(instance_id)

    def _now(self) -> str:
        return self.authorization.identity.now_text()

    @property
    def retention_days(self) -> int:
        return self.authorization.identity.settings.policy.session_retention_days

    @property
    def replay_days(self) -> int:
        return self.authorization.identity.settings.policy.terminal_record_retention_days

    def get(self, context: AuthorizedOwnerContext, session_id: str) -> SessionState:
        session_id = repo.valid_id(session_id)

        def read(unit: OwnerUnit) -> SessionState:
            now = self._now()
            return repo.state(unit, repo.live_session(unit, session_id, now), now)

        return self.authorization.read(context, read)

    def create(self, context: AuthorizedOwnerContext, body: SessionCreateRequest) -> SessionState:
        body = copied(SessionCreateRequest, body)
        payload_hash = fingerprint({"command": "session.create", **body.model_dump(mode="json")})

        def write(unit: OwnerUnit) -> SessionState:
            now = self._now()
            previous = repo.receipt(
                unit, "session.create", body.client_action_id, payload_hash, now
            )
            if previous is not None:
                session_id = previous.result_json.get("session_id")
                if not isinstance(session_id, str):
                    raise StoreError("SESSION_RECEIPT_INCOMPATIBLE")
                return repo.state(unit, repo.live_session(unit, session_id, now), now)
            journey = repo.journey(unit, now)
            row = ConversationSession(
                id=str(uuid4()),
                owner_id=unit.owner_id,
                journey_id=journey.id,
                revision=0,
                state_json=SessionContent().model_dump(mode="json"),
                created_at=now,
            )
            repo.activity(row, now, self.retention_days)
            unit.db.add(row)
            unit.db.flush()
            repo.record_receipt(
                unit,
                row,
                kind="session.create",
                action_id=body.client_action_id,
                payload_hash=payload_hash,
                result={"session_id": row.id},
                now=now,
                retention_days=self.replay_days,
            )
            return repo.state(unit, row, now)

        return self.authorization.write(context, write)

    def _prepare(
        self,
        refs: tuple[ImmutableInventoryRef, ...],
        snapshot_id: str,
        proof: PresentationProof | None = None,
    ) -> InventoryAdmission:
        assert_outside_write_transaction()
        if self.inventory is None:
            raise ApiFailure("STORE_UNAVAILABLE")
        if proof is not None:
            self.inventory.verify(proof, now=datetime.fromisoformat(self._now()))
        return self.inventory.prepare(refs, snapshot_id=snapshot_id)

    def _command_replay(
        self,
        unit: OwnerUnit,
        session_id: str,
        kind: str,
        action_id: str,
        payload_hash: str,
        expected_revision: int,
        now: str,
    ) -> tuple[ConversationSession, SessionState | None]:
        row = repo.live_session(unit, session_id, now)
        previous = repo.receipt(unit, kind, action_id, payload_hash, now)
        if previous is not None:
            if previous.result_json.get("session_id") != row.id:
                raise StoreError("SESSION_RECEIPT_INCOMPATIBLE")
            return row, repo.state(unit, row, now)
        repo.revision(row, expected_revision)
        return row, None

    def register(
        self, context: AuthorizedOwnerContext, session_id: str, body: PresentationRegisterRequest
    ) -> SessionState:
        session_id = repo.valid_id(session_id)
        body = copied(PresentationRegisterRequest, body)
        proof = body.presentation
        kind = "session.presentation"
        payload_hash = fingerprint(
            {"command": kind, "session_id": session_id, "body": body.model_dump(mode="json")}
        )

        def inspect(unit: OwnerUnit) -> tuple[ConversationSession, SessionState | None]:
            return self._command_replay(
                unit,
                session_id,
                kind,
                body.client_action_id,
                payload_hash,
                body.expected_revision,
                self._now(),
            )

        # Only materialized replay data leaves the read; never an ORM row.
        replay = self.authorization.read(context, lambda unit: inspect(unit)[1])
        if replay is not None:
            return replay
        refs = tuple(
            ImmutableInventoryRef.model_validate(ref.model_dump()) for ref in proof.ordered_refs
        )
        prepared = self._prepare(refs, proof.snapshot_id, proof)

        def write(unit: OwnerUnit) -> SessionState:
            now = self._now()
            row, replay = inspect(unit)
            if replay is not None:
                return replay
            if (
                not datetime.fromisoformat(proof.issued_at)
                <= datetime.fromisoformat(now)
                < datetime.fromisoformat(proof.expires_at)
            ):
                raise ApiFailure("PRESENTATION_INVALID")
            check_admission(
                unit,
                prepared,
                generation=context.generation,
                snapshot_id=proof.snapshot_id,
                refs=refs,
                gateway=self.inventory,
            )
            row.revision += 1
            owned_id = repo.add_presentation(unit, row, proof, now)
            before = repo.content(row)
            after = SessionContent.model_validate(
                {**before.model_dump(mode="json"), "active_presentation_id": owned_id}
            )
            repo.protect_operation(before, after)
            row.state_json = after.model_dump(mode="json")
            repo.activity(row, now, self.retention_days)
            repo.record_receipt(
                unit,
                row,
                kind=kind,
                action_id=body.client_action_id,
                payload_hash=payload_hash,
                result={
                    "session_id": row.id,
                    "presentation_id": owned_id,
                    "public_proof": proof.model_dump(mode="json"),
                },
                now=now,
                retention_days=self.replay_days,
            )
            return repo.state(unit, row, now)

        return self.authorization.write(context, write)

    def select(
        self, context: AuthorizedOwnerContext, session_id: str, body: SessionSelectionRequest
    ) -> SessionState:
        session_id = repo.valid_id(session_id)
        body = copied(SessionSelectionRequest, body)
        kind = "session.selection"
        payload_hash = fingerprint(
            {"command": kind, "session_id": session_id, "body": body.model_dump(mode="json")}
        )

        def inspect(unit: OwnerUnit) -> tuple[ConversationSession, SessionState | None]:
            return self._command_replay(
                unit,
                session_id,
                kind,
                body.client_action_id,
                payload_hash,
                body.expected_revision,
                self._now(),
            )

        replay = self.authorization.read(context, lambda unit: inspect(unit)[1])
        if replay is not None:
            return replay
        ref = ImmutableInventoryRef.model_validate(body.selected_ref.model_dump())
        prepared = self._prepare((ref,), ref.snapshot_id)

        def write(unit: OwnerUnit) -> SessionState:
            now = self._now()
            row, replay = inspect(unit)
            if replay is not None:
                return replay
            check_admission(
                unit,
                prepared,
                generation=context.generation,
                snapshot_id=ref.snapshot_id,
                refs=(ref,),
                gateway=self.inventory,
            )
            if body.presentation_id is not None:
                repo.presentation_member(unit, row.id, body.presentation_id, ref)
            before = repo.content(row)
            after = SessionContent.model_validate(
                {
                    **before.model_dump(mode="json"),
                    "selected_ref": ref.model_dump(mode="json"),
                    "active_presentation_id": body.presentation_id,
                    "pending_intent": NoPendingIntent(kind="none").model_dump(mode="json"),
                }
            )
            repo.protect_operation(before, after)
            row.revision += 1
            row.state_json = after.model_dump(mode="json")
            repo.activity(row, now, self.retention_days)
            repo.record_receipt(
                unit,
                row,
                kind=kind,
                action_id=body.client_action_id,
                payload_hash=payload_hash,
                result={"session_id": row.id},
                now=now,
                retention_days=self.replay_days,
            )
            return repo.state(unit, row, now)

        return self.authorization.write(context, write)

    def _message_replay(
        self,
        unit: OwnerUnit,
        row: ConversationSession,
        body: MessageRequest,
        payload_hash: str,
        now: str,
    ) -> _AdmissionData | None:
        message = unit.db.scalar(
            select(Message).where(
                Message.owner_id == unit.owner_id,
                Message.session_id == row.id,
                Message.client_message_id == body.client_message_id,
            )
        )
        if message is None:
            repo.revision(row, body.expected_revision)
            return None
        if message.payload_hash != payload_hash:
            raise ApiFailure("IDEMPOTENCY_CONFLICT")
        saved = repo.message_content(message)
        observed = repo.state(unit, row, now)
        if saved.assistant_result is not None:
            result = MessageResult.model_validate(
                {**saved.assistant_result.model_dump(mode="json"), "current_revision": row.revision}
            )
            return _AdmissionData("completed", message.id, observed, saved.request, result)
        status: Literal["pending", "interrupted"] = (
            "pending"
            if message.state == "pending" and saved.worker_epoch == self._epoch
            else "interrupted"
        )
        return _AdmissionData(status, message.id, observed, saved.request)

    def _admission(self, context: AuthorizedOwnerContext, data: _AdmissionData) -> TurnAdmission:
        ticket = None
        if data.status == "accepted":
            ticket = object.__new__(TurnTicket)
            for key, value in {
                "_issuer": self._issuer,
                "_context_id": context.context_id,
                "_generation": context.generation,
                "_session_id": data.session.session_id,
                "_message_id": data.message_id,
            }.items():
                object.__setattr__(ticket, key, value)
        return TurnAdmission(
            data.status, data.message_id, data.session, data.request, data.result, ticket
        )

    def begin(
        self, context: AuthorizedOwnerContext, session_id: str, body: MessageRequest
    ) -> TurnAdmission:
        session_id = repo.valid_id(session_id)
        body = copied(MessageRequest, body)
        payload_hash = fingerprint(body.model_dump(mode="json"))

        def inspect(unit: OwnerUnit) -> _AdmissionData | None:
            now = self._now()
            return self._message_replay(
                unit, repo.live_session(unit, session_id, now), body, payload_hash, now
            )

        replay = self.authorization.read(context, inspect)
        if replay is not None:
            return self._admission(context, replay)
        prepared = None
        ref = None
        if body.selected_ref is not None:
            ref = ImmutableInventoryRef.model_validate(body.selected_ref.model_dump())
            prepared = self._prepare((ref,), ref.snapshot_id)

        def write(unit: OwnerUnit) -> _AdmissionData:
            now = self._now()
            row = repo.live_session(unit, session_id, now)
            replay = self._message_replay(unit, row, body, payload_hash, now)
            if replay is not None:
                return replay
            before = repo.content(row)
            values = before.model_dump(mode="json")
            if body.clarification_reply is not None:
                pending = before.pending_intent
                reply = body.clarification_reply
                if not isinstance(pending, ClarificationIntent) or (
                    pending.intent_id,
                    pending.created_revision,
                ) != (reply.intent_id, reply.created_revision):
                    raise ApiFailure("REVISION_CONFLICT")
                # Admission is not resolution. A cancelled/interrupted worker must
                # leave this question intact until current ticket-bound completion.
            if body.presentation_id is not None:
                unit.presentation(row.id, body.presentation_id)
                values["active_presentation_id"] = body.presentation_id
            if ref is not None and prepared is not None:
                check_admission(
                    unit,
                    prepared,
                    generation=context.generation,
                    snapshot_id=ref.snapshot_id,
                    refs=(ref,),
                    gateway=self.inventory,
                )
                # A newer search can coexist with a previously selected car.
                # Echoing that owned state is not a new selection from the new list.
                echoes_current_context = (
                    body.selected_ref == before.selected_ref
                    and body.presentation_id == before.active_presentation_id
                )
                if body.presentation_id is not None and not echoes_current_context:
                    repo.presentation_member(unit, row.id, body.presentation_id, ref)
                values["selected_ref"] = ref.model_dump(mode="json")
                if body.presentation_id is None:
                    values["active_presentation_id"] = None
            after = SessionContent.model_validate(values)
            repo.protect_operation(before, after)
            row.revision += 1
            repo.validate_context(unit, row, after)
            row.state_json = after.model_dump(mode="json")
            repo.activity(row, now, self.retention_days)
            message = Message(
                id=str(uuid4()),
                owner_id=unit.owner_id,
                session_id=row.id,
                client_message_id=body.client_message_id,
                payload_hash=payload_hash,
                expected_revision=body.expected_revision,
                accepted_revision=row.revision,
                result_json=StoredMessage(request=body, worker_epoch=self._epoch).model_dump(
                    mode="json"
                ),
                state="pending",
                created_at=now,
            )
            unit.db.add(message)
            return _AdmissionData("accepted", message.id, repo.state(unit, row, now), body)

        return self._admission(context, self.authorization.write(context, write))

    def complete(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
        result: MessageResult,
        *,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
        collection_update: CollectionUpdate | None = None,
    ) -> MessageResult:
        return self._complete(
            context,
            ticket,
            result,
            update=update,
            presentation=presentation,
            selection=selection,
            collection_update=collection_update,
        )

    def complete_action(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
        result: MessageResult,
        *,
        preference: PreferenceCommand | None = None,
        membership: ShortlistChange | None = None,
        preference_service: PreferenceService | None = None,
        shortlist_service: ShortlistService | None = None,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
        collection_update: CollectionUpdate | None = None,
        lead: LeadChange | None = None,
        draft: DraftChange | None = None,
        lead_service: LeadService | None = None,
        draft_service: DraftService | None = None,
    ) -> MessageResult:
        if lead is not None or draft is not None:
            if preference is not None or membership is not None:
                raise ApiFailure("VALIDATION_ERROR")
            from app.sessions.collection_actions import complete_collection_action

            return complete_collection_action(
                self,
                context,
                ticket,
                result,
                lead=lead,
                draft=draft,
                lead_service=lead_service,
                draft_service=draft_service,
                update=update,
                presentation=presentation,
                selection=selection,
                collection_update=collection_update,
            )
        return self._complete(
            context,
            ticket,
            result,
            action_mode=True,
            preference=preference,
            membership=membership,
            preference_service=preference_service,
            shortlist_service=shortlist_service,
            update=update,
            presentation=presentation,
            selection=selection,
            collection_update=collection_update,
        )

    def read_collection(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
    ) -> CollectionSnapshot:
        self._check_collection_ticket(context, ticket)

        def read(unit: OwnerUnit) -> CollectionSnapshot:
            now = self._now()
            row = repo.live_session(unit, ticket._session_id, now)
            message = unit.message(row.id, ticket._message_id)
            saved = repo.message_content(message)
            if (
                message.state != "pending"
                or saved.worker_epoch != self._epoch
                or saved.assistant_result is not None
                or row.revision != message.accepted_revision
            ):
                raise ApiFailure("REVISION_CONFLICT")
            value = owned_collection(unit, row, generation=context.generation, now=now)
            return CollectionSnapshot(
                value,
                collection_digest(value),
                value is not None
                and (
                    datetime.fromisoformat(value.expires_at) <= datetime.fromisoformat(now)
                    or value.store_generation != context.generation
                ),
                now,
                unresolved_command(unit, row.id),
            )

        return self.authorization.read(context, read)

    def _check_collection_ticket(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
    ) -> None:
        if (
            type(ticket) is not TurnTicket
            or getattr(ticket, "_issuer", None) is not self._issuer
            or ticket._context_id != context.context_id
            or ticket._generation != context.generation
        ):
            raise ApiFailure("UNSUPPORTED_STATE")

    @staticmethod
    def _action_rejected(action_id: str, error: ApiFailure) -> ActionRejected:
        # Only exact participant precondition types reach here. DTO closes the code set.
        return ActionRejected.model_validate(
            dict(state="rejected", client_action_id=action_id, code=error.code)
        )

    @staticmethod
    def _action_text(actions: MessageActionResults) -> str:
        parts = []
        if isinstance(actions.preferences, PreferenceActionSucceeded):
            parts.append("Your preference update is recorded.")
            if actions.preferences.result.collection_mode == "disabled":
                parts.append("Preference saving is off.")
        elif isinstance(actions.preferences, ActionRejected):
            parts.append(f"Your preference change was not saved ({actions.preferences.code}).")
        if isinstance(actions.shortlist, ShortlistActionSucceeded):
            parts.append(
                "This car is on your shortlist."
                if actions.shortlist.result.saved
                else "This car is not on your shortlist."
            )
        elif isinstance(actions.shortlist, ActionRejected):
            parts.append(f"Your shortlist change was not saved ({actions.shortlist.code}).")
        return " ".join(parts)

    def _complete(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
        result: MessageResult,
        *,
        action_mode: bool = False,
        preference: PreferenceCommand | None = None,
        membership: ShortlistChange | None = None,
        preference_service: PreferenceService | None = None,
        shortlist_service: ShortlistService | None = None,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
        collection_update: CollectionUpdate | None = None,
    ) -> MessageResult:
        if (
            type(ticket) is not TurnTicket
            or getattr(ticket, "_issuer", None) is not self._issuer
            or ticket._context_id != context.context_id
            or ticket._generation != context.generation
        ):
            raise ApiFailure("UNSUPPORTED_STATE")
        result = copied(MessageResult, result)
        update = copied(SessionContent, update) if update is not None else None
        collection_update = (
            copied(CollectionUpdate, collection_update) if collection_update is not None else None
        )
        if result.search is not None:
            if presentation is not None and presentation != result.search.presentation:
                raise ApiFailure("PRESENTATION_INVALID")
            presentation = result.search.presentation
        presentation = copied(PresentationProof, presentation) if presentation is not None else None
        selection = copied(InventoryRef, selection) if selection is not None else None
        material: dict[str, object] = {
            "result": result.model_dump(mode="json"),
            "update": None
            if update is None
            else update.model_dump(mode="json", exclude={"collection"}),
            "presentation": None if presentation is None else presentation.model_dump(mode="json"),
            "selection": None if selection is None else selection.model_dump(mode="json"),
        }
        if collection_update is not None:
            material["collection_update"] = collection_update.model_dump(mode="json")
        if action_mode:
            if collection_update is not None:
                raise ApiFailure("UNSUPPORTED_STATE")
            if preference is None and membership is None:
                raise ApiFailure("VALIDATION_ERROR")
            if result.operation is not None or any(
                action["state"] != "not_requested"
                for action in result.actions.model_dump().values()
            ):
                raise ApiFailure("VALIDATION_ERROR")
            if preference is not None:
                try:
                    preference = PREFERENCE_COMMAND.validate_json(preference.model_dump_json())
                except (AttributeError, TypeError, ValueError):
                    raise ApiFailure("VALIDATION_ERROR") from None
                if preference.session_id != ticket._session_id:
                    raise ApiFailure("VALIDATION_ERROR")
                if (
                    preference_service is None
                    or preference_service.authorization is not self.authorization
                ):
                    raise ApiFailure("UNSUPPORTED_STATE")
            if membership is not None:
                if type(membership) is not ShortlistChange or type(membership.desired) is not bool:
                    raise ApiFailure("VALIDATION_ERROR")
                membership = ShortlistChange(
                    copied(InventoryRef, membership.ref),
                    copied(MembershipRequest, membership.command),
                    membership.desired,
                )
                if (
                    shortlist_service is None
                    or shortlist_service.authorization is not self.authorization
                ):
                    raise ApiFailure("UNSUPPORTED_STATE")
                # Current A8 emits value commands. Coupled mode changes need a separate contract.
                if preference is not None and not isinstance(preference, PreferencesUpdate):
                    raise ApiFailure("UNSUPPORTED_STATE")
            material.update(
                action_mode="session-actions-1",
                preference=None if preference is None else preference.model_dump(mode="json"),
                membership=None
                if membership is None
                else dict(
                    ref=membership.ref.model_dump(mode="json"),
                    command=membership.command.model_dump(mode="json"),
                    desired=membership.desired,
                ),
            )
        completion_hash = fingerprint(material)

        def inspect(
            unit: OwnerUnit, now: str
        ) -> tuple[ConversationSession, Message, StoredMessage, MessageResult | None]:
            row = repo.live_session(unit, ticket._session_id, now)
            repo.validate_context(unit, row, repo.content(row))
            message = unit.message(row.id, ticket._message_id)
            saved = repo.message_content(message)
            if (result.session_id, result.client_message_id, result.turn_revision) != (
                row.id,
                message.client_message_id,
                message.accepted_revision,
            ):
                raise ApiFailure("UNSUPPORTED_STATE")
            if saved.assistant_result is not None:
                if saved.completion_hash != completion_hash:
                    raise ApiFailure("IDEMPOTENCY_CONFLICT")
                replay = MessageResult.model_validate(
                    {
                        **saved.assistant_result.model_dump(mode="json"),
                        "current_revision": row.revision,
                    }
                )
                return row, message, saved, replay
            if message.state != "pending" or saved.worker_epoch != self._epoch:
                raise ApiFailure("UNSUPPORTED_STATE")
            if saved.collection_command is not None:
                raise ApiFailure("OPERATION_UNRESOLVED")
            if (
                action_mode or collection_update is not None
            ) and row.revision != message.accepted_revision:
                raise ApiFailure("REVISION_CONFLICT")
            return row, message, saved, None

        def preflight(unit: OwnerUnit) -> tuple[MessageResult | None, bool]:
            row, message, _, replay = inspect(unit, self._now())
            return replay, row.revision == message.accepted_revision

        replay, current = self.authorization.read(context, preflight)
        if replay is not None:
            return replay
        refs: tuple[ImmutableInventoryRef, ...] = ()
        prepared = None
        snapshot_id = None
        if current and presentation is not None:
            refs = tuple(
                ImmutableInventoryRef.model_validate(ref.model_dump())
                for ref in presentation.ordered_refs
            )
            if selection is not None and not any(
                (selection.namespace, selection.snapshot_id, selection.source_id)
                == (ref.namespace, ref.snapshot_id, ref.source_id)
                for ref in refs
            ):
                raise ApiFailure("PRESENTATION_INVALID")
            snapshot_id = presentation.snapshot_id
            prepared = self._prepare(refs, snapshot_id, presentation)
        elif current and selection is not None:
            selected = ImmutableInventoryRef.model_validate(selection.model_dump())
            refs, snapshot_id = (selected,), selected.snapshot_id
            prepared = self._prepare(refs, snapshot_id)

        prepared_membership: ReferenceBatch | None = None
        if membership is not None:
            assert shortlist_service is not None
            try:
                prepared_membership = shortlist_service.prepare_change(
                    context, membership.ref, membership.command, desired=membership.desired
                )
            except MembershipRejected as exc:
                if type(exc) is not MembershipRejected:
                    raise
                # Revalidate this denial in the WRITE before any participant effects.

        def write(unit: OwnerUnit) -> MessageResult:
            now = self._now()
            row, message, saved, replay = inspect(unit, now)
            if replay is not None:
                return replay
            superseded = row.revision != message.accepted_revision
            actions = MessageActionResults()
            if membership is not None and prepared_membership is None:
                assert shortlist_service is not None
                try:
                    shortlist_service._preflight_change(
                        unit, membership.ref, membership.command, desired=membership.desired
                    )
                except MembershipRejected as exc:
                    if type(exc) is not MembershipRejected:
                        raise
                    actions.shortlist = self._action_rejected(
                        membership.command.client_action_id, exc
                    )
                else:
                    # A receipt appeared or denial cleared: retry preparation outside WRITE.
                    raise ApiFailure("REVISION_CONFLICT")
            owned_id = None
            if not superseded:
                before = repo.content(row)
                after = before if update is None else update
                after = SessionContent.model_validate(
                    {
                        **after.model_dump(mode="json"),
                        "collection": None
                        if before.collection is None
                        else before.collection.model_dump(mode="json"),
                    }
                )
                if (
                    isinstance(before.pending_intent, ClarificationIntent)
                    and result.state == "provider_unavailable"
                    and after.pending_intent != before.pending_intent
                ):
                    raise ApiFailure("UNSUPPORTED_STATE")
                if (
                    before.selected_ref != after.selected_ref
                    or before.active_presentation_id != after.active_presentation_id
                ):
                    raise ApiFailure("UNSUPPORTED_STATE")
                if prepared is not None and snapshot_id is not None:
                    check_admission(
                        unit,
                        prepared,
                        generation=context.generation,
                        snapshot_id=snapshot_id,
                        refs=refs,
                        gateway=self.inventory,
                    )
                if presentation is not None and (
                    prepared is None
                    or not datetime.fromisoformat(presentation.issued_at)
                    <= datetime.fromisoformat(now)
                    < datetime.fromisoformat(presentation.expires_at)
                ):
                    raise ApiFailure("PRESENTATION_INVALID")
                if selection is not None:
                    if prepared is None:
                        raise ApiFailure("SNAPSHOT_STALE")
                    if presentation is None and before.active_presentation_id is not None:
                        repo.presentation_member(
                            unit, row.id, before.active_presentation_id, selection
                        )
                    after = SessionContent.model_validate(
                        {
                            **after.model_dump(mode="json"),
                            "selected_ref": selection.model_dump(mode="json"),
                        }
                    )
                selected_collection = apply_update(
                    unit,
                    row,
                    message,
                    generation=context.generation,
                    now=now,
                    mutation=collection_update,
                    final_revision=message.accepted_revision + 1,
                    pending=after.pending_intent,
                    selected_ref=after.selected_ref,
                )
                after = SessionContent.model_validate(
                    {
                        **after.model_dump(mode="json"),
                        "collection": None
                        if selected_collection is None
                        else selected_collection.model_dump(mode="json"),
                    }
                )
                repo.protect_operation(before, after)
                if after != before or presentation is not None:
                    repo.revision(row, message.accepted_revision)
                    row.revision += 1
                    if presentation is not None:
                        owned_id = repo.add_presentation(unit, row, presentation, now)
                        after = SessionContent.model_validate(
                            {**after.model_dump(mode="json"), "active_presentation_id": owned_id}
                        )
                    repo.validate_context(unit, row, after)
                    row.state_json = after.model_dump(mode="json")
            if preference is not None:
                assert preference_service is not None
                try:
                    outcome = preference_service.update_in_unit(
                        unit, preference, source_message_id=message.id
                    )
                except PreferenceRejected as exc:
                    if type(exc) is not PreferenceRejected:
                        raise
                    actions.preferences = self._action_rejected(preference.client_action_id, exc)
                else:
                    actions.preferences = PreferenceActionSucceeded(
                        state="succeeded",
                        client_action_id=preference.client_action_id,
                        result=outcome,
                    )
            if membership is not None and prepared_membership is not None:
                assert shortlist_service is not None
                try:
                    member_outcome = shortlist_service.change_in_unit(
                        unit,
                        membership.ref,
                        membership.command,
                        desired=membership.desired,
                        generation=context.generation,
                        prepared=prepared_membership,
                    )
                except MembershipRejected as exc:
                    if type(exc) is not MembershipRejected:
                        raise
                    actions.shortlist = self._action_rejected(
                        membership.command.client_action_id, exc
                    )
                else:
                    actions.shortlist = ShortlistActionSucceeded(
                        state="succeeded",
                        client_action_id=membership.command.client_action_id,
                        result=member_outcome,
                    )
            finished = result.model_dump(mode="json")
            if action_mode:
                finished.update(
                    actions=actions.model_dump(mode="json"), text=self._action_text(actions)
                )
            original = MessageResult.model_validate(
                {
                    **finished,
                    "current_revision": row.revision,
                    "persistence": "saved",
                    "state": "superseded" if superseded else result.state,
                }
            )
            if not superseded and original.pending_intent != repo.content(row).pending_intent:
                raise ApiFailure("UNSUPPORTED_STATE")
            message.result_json = StoredMessage(
                request=saved.request,
                worker_epoch=saved.worker_epoch,
                assistant_result=original,
                completion_hash=completion_hash,
                applied_public_proof=None if superseded else presentation,
                applied_presentation_id=owned_id,
                applied_selection=None if superseded else selection,
            ).model_dump(mode="json")
            message.state = "completed"
            # Completing work is not a new buyer activity and cannot renew retention.
            return original

        return self.authorization.write(context, write)

    def confirm_turn(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        body: MessageRequest,
        *,
        participant: ConfirmationParticipant,
    ) -> MessageResult:
        """Typed confirmation branches before begin; T7 sees the exact reviewed R."""
        session_id, body = repo.valid_id(session_id), copied(MessageRequest, body)
        if participant.authorization is not self.authorization:
            raise ApiFailure("UNSUPPORTED_STATE")
        explicit = body.explicit_confirmation
        if explicit is None or any(
            item is not None
            for item in (body.selected_ref, body.presentation_id, body.clarification_reply)
        ):
            raise ApiFailure("VALIDATION_ERROR")
        draft_id = explicit.draft_id
        command = ConfirmRequest.model_validate(
            explicit.model_dump(mode="json", exclude={"draft_id"})
        )
        payload_hash = fingerprint(body.model_dump(mode="json"))

        def inspect(unit: OwnerUnit, now: str) -> tuple[ConversationSession, MessageResult | None]:
            row = repo.live_session(unit, session_id, now)
            replay = self._message_replay(unit, row, body, payload_hash, now)
            if replay is not None:
                if replay.status != "completed" or replay.result is None:
                    raise ApiFailure("UNSUPPORTED_STATE")
                return row, replay.result
            repo.validate_context(unit, row, repo.content(row))
            # A chat receipt has a target session. Parentless recovery remains operation status.
            if unit.draft(draft_id).session_id != row.id:
                raise ApiFailure("NOT_FOUND")
            return row, None

        def preflight(unit: OwnerUnit) -> tuple[MessageResult | None, bool]:
            now = self._now()
            _, replay = inspect(unit, now)
            if replay is not None:
                return replay, True
            terminal = participant.lookup_in_unit(
                unit, draft_id=draft_id, command=command, generation=context.generation, now=now
            )
            return None, terminal is not None

        replay, terminal_seen = self.authorization.read(context, preflight)
        if replay is not None:
            return replay
        prepared = (
            None
            if terminal_seen
            else participant.prepare(context, draft_id=draft_id, command=command)
        )

        def write(unit: OwnerUnit) -> MessageResult:
            now = self._now()
            row, replay = inspect(unit, now)
            if replay is not None:
                return replay
            # inspect checked new-message expected R; never increment it before actual T7.
            effect = participant.apply_in_unit(
                unit,
                draft_id=draft_id,
                command=command,
                generation=context.generation,
                now=now,
                prepared=prepared,
            )
            if effect.transition is not None:
                if effect.replayed or (
                    effect.transition.owner_id,
                    effect.transition.session_id,
                    effect.transition.expected_revision,
                    effect.transition.generation,
                ) != (unit.owner_id, row.id, body.expected_revision, context.generation):
                    raise StoreError("CONFIRMATION_TRANSITION_INCOMPATIBLE")
                participant.resolve_session_in_unit(unit, transition=effect.transition)
            elif not effect.replayed:
                raise StoreError("CONFIRMATION_TRANSITION_MISSING")
            repo.revision(row, body.expected_revision)
            row.revision += 1
            content = repo.content(row)
            repo.validate_context(unit, row, content)
            repo.activity(row, now, self.retention_days)
            operation = effect.terminal
            if isinstance(operation, OperationSucceeded):
                # New receipt gets a current observation, immutable terminal facts remain untouched.
                operation = OperationSucceeded.model_validate(
                    {
                        **operation.model_dump(mode="json"),
                        "csv": participant.observe_csv_in_unit(
                            unit, generation=context.generation, now=now
                        ).model_dump(mode="json"),
                    }
                )
                text = "Your simulated viewing is confirmed and your local enquiry is saved."
                if operation.csv.state == "current":
                    text += " The CSV export is current."
                elif operation.csv.state == "failed":
                    text += " The CSV export needs repair."
                else:
                    text += " The CSV export is pending."
            elif isinstance(operation, OperationRejected):
                text = (
                    f"The viewing was not confirmed ({operation.rejection_code}). "
                    "No booking was created."
                )
            else:
                raise StoreError("CONFIRMATION_TERMINAL_INCOMPATIBLE")
            original = MessageResult(
                client_message_id=body.client_message_id,
                session_id=row.id,
                turn_revision=row.revision,
                current_revision=row.revision,
                state="answered",
                text=text,
                pending_intent=content.pending_intent,
                operation=operation,
                persistence="saved",
                provider_state="not_used",
            )
            unit.db.add(
                Message(
                    id=str(uuid4()),
                    owner_id=unit.owner_id,
                    session_id=row.id,
                    client_message_id=body.client_message_id,
                    payload_hash=payload_hash,
                    expected_revision=body.expected_revision,
                    accepted_revision=row.revision,
                    result_json=StoredMessage(
                        request=body,
                        worker_epoch=self._epoch,
                        assistant_result=original,
                        completion_hash=fingerprint(
                            dict(kind="confirmation-message-1", request_hash=payload_hash)
                        ),
                    ).model_dump(mode="json"),
                    state="completed",
                    created_at=now,
                )
            )
            return original

        return self.authorization.write(context, write)

    def presentation_refs(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str
    ) -> OwnedPresentationView:
        session_id, presentation_id = repo.valid_id(session_id), repo.valid_id(presentation_id)

        def read(unit: OwnerUnit) -> OwnedPresentationView:
            session = repo.live_session(unit, session_id, self._now())
            presentation = unit.presentation(session_id, presentation_id)
            snapshot = unit.db.get(InventorySnapshot, presentation.snapshot_id)
            items = unit.db.execute(
                select(PresentationItem, ListingVersion.source_id)
                .outerjoin(
                    ListingVersion,
                    (ListingVersion.namespace == PresentationItem.namespace)
                    & (ListingVersion.snapshot_id == PresentationItem.snapshot_id)
                    & (ListingVersion.source_id == PresentationItem.source_id),
                )
                .where(PresentationItem.presentation_id == presentation_id)
                .order_by(PresentationItem.ordinal)
                .limit(51)
            ).all()
            if (
                snapshot is None
                or len(items) > 50
                or not 0 <= presentation.created_revision <= session.revision
                or any(
                    item.ordinal != ordinal
                    or item.snapshot_id != presentation.snapshot_id
                    or item.namespace != snapshot.namespace
                    or linked_source is None
                    for ordinal, (item, linked_source) in enumerate(items)
                )
            ):
                raise StoreError("SESSION_PRESENTATION_INCOMPATIBLE")
            refs = tuple(
                repo.stored(
                    ImmutableInventoryRef,
                    dict(
                        namespace=item.namespace,
                        snapshot_id=item.snapshot_id,
                        source_id=item.source_id,
                    ),
                )
                for item, _ in items
            )
            if len({(ref.namespace, ref.snapshot_id, ref.source_id) for ref in refs}) != len(refs):
                raise StoreError("SESSION_PRESENTATION_INCOMPATIBLE")
            return OwnedPresentationView(
                session_id,
                presentation_id,
                presentation.snapshot_id,
                presentation.created_revision,
                refs,
            )

        return self.authorization.read(context, read)

    def ordinal(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str, ordinal: int
    ) -> InventoryRef:
        session_id, presentation_id = repo.valid_id(session_id), repo.valid_id(presentation_id)
        if type(ordinal) is not int or not 0 <= ordinal < 50:
            raise ApiFailure("VALIDATION_ERROR")

        def read(unit: OwnerUnit) -> InventoryRef:
            repo.live_session(unit, session_id, self._now())
            item = unit.presentation_item(session_id, presentation_id, ordinal)
            return InventoryRef(
                namespace=item.namespace, snapshot_id=item.snapshot_id, source_id=item.source_id
            )

        return self.authorization.read(context, read)

    def recent_context(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        *,
        before_revision: int,
    ) -> tuple[TranscriptTurn, ...]:
        """Last six completed owned turns, before the admitted current message."""
        session_id = repo.valid_id(session_id)

        def read(unit: OwnerUnit) -> tuple[TranscriptTurn, ...]:
            row = repo.live_session(unit, session_id, self._now())
            if not 0 <= before_revision <= row.revision:
                raise ApiFailure("REVISION_CONFLICT")
            messages = unit.db.scalars(
                select(Message)
                .where(
                    Message.owner_id == unit.owner_id,
                    Message.session_id == row.id,
                    Message.accepted_revision < before_revision,
                )
                .order_by(Message.accepted_revision.desc())
                .limit(6)
            ).all()
            turns = []
            for message in reversed(messages):
                saved = repo.message_content(message)
                if saved.assistant_result is None:
                    continue
                turns.append(
                    TranscriptTurn(
                        message_id=message.id,
                        client_message_id=message.client_message_id,
                        session_id=row.id,
                        accepted_revision=message.accepted_revision,
                        accepted_at=message.created_at,
                        user_text=saved.request.text,
                        state="completed",
                        assistant_result=saved.assistant_result,
                    )
                )
            return tuple(turns)

        return self.authorization.read(context, read)

    def transcript(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        *,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> TranscriptPage:
        session_id = repo.valid_id(session_id)
        if type(page_size) is not int or not 1 <= page_size <= 50:
            raise ApiFailure("VALIDATION_ERROR")

        def read(unit: OwnerUnit) -> TranscriptPage:
            row = repo.live_session(unit, session_id, self._now())
            credential = unit.db.scalar(
                select(OwnerCredential).where(
                    OwnerCredential.owner_id == unit.owner_id,
                    OwnerCredential.context_id == context.context_id,
                )
            )
            if credential is None:
                raise ApiFailure("IDENTITY_REQUIRED")
            observed, after = row.revision, 0
            if cursor is not None:
                parsed = decode_cursor(cursor, credential.csrf_binding)
                if (parsed.owner_id, parsed.context_id, parsed.session_id, parsed.generation) != (
                    unit.owner_id,
                    context.context_id,
                    row.id,
                    context.generation,
                ):
                    raise ApiFailure("VALIDATION_ERROR")
                if parsed.observed_revision > row.revision:
                    raise ApiFailure("REVISION_CONFLICT")
                observed, after = parsed.observed_revision, parsed.after_revision
            messages = unit.db.scalars(
                select(Message)
                .where(
                    Message.owner_id == unit.owner_id,
                    Message.session_id == row.id,
                    Message.accepted_revision > after,
                    Message.accepted_revision <= observed,
                )
                .order_by(Message.accepted_revision, Message.id)
                .limit(page_size + 1)
            ).all()
            turns = []
            for message in messages[:page_size]:
                saved = repo.message_content(message)
                turn_state: Literal["completed", "pending", "interrupted"] = (
                    "completed"
                    if saved.assistant_result is not None
                    else "pending"
                    if message.state == "pending" and saved.worker_epoch == self._epoch
                    else "interrupted"
                )
                turns.append(
                    TranscriptTurn(
                        message_id=message.id,
                        client_message_id=message.client_message_id,
                        session_id=row.id,
                        accepted_revision=message.accepted_revision,
                        accepted_at=message.created_at,
                        user_text=saved.request.text,
                        state=turn_state,
                        assistant_result=saved.assistant_result,
                    )
                )
            next_cursor = None
            if len(messages) > page_size:
                next_cursor = encode_cursor(
                    TranscriptCursor(
                        owner_id=unit.owner_id,
                        context_id=context.context_id,
                        session_id=row.id,
                        generation=context.generation,
                        observed_revision=observed,
                        after_revision=turns[-1].accepted_revision,
                    ),
                    credential.csrf_binding,
                )
            return TranscriptPage(
                session_id=row.id, observed_revision=observed, items=turns, next_cursor=next_cursor
            )

        return self.authorization.read(context, read)
