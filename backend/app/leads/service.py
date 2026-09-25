"""Shared explicit enquiry changes; caller-unit methods never commit or complete a turn."""

from sqlalchemy import select

from app.api.schemas.leads import (
    LeadRecord,
    LeadSaveRequest,
    LeadSaveResult,
    LeadUpdateRequest,
    NoLead,
)
from app.core.errors import ApiFailure
from app.database.models import CommandReceipt, Lead, StoreMetadata
from app.database.store import StoreError, assert_outside_write_transaction
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.inventory.references import ImmutableInventoryRef
from app.leads import repository as repo
from app.leads.changes import (
    LeadChangeEnvelope,
    LeadCommandAbsent,
    LeadCommandExpired,
    LeadCommandKnown,
    LeadCommandObservation,
    LeadCommandUnreconciled,
    LeadPreparation,
    PreparedLeadChange,
)
from app.sessions.repository import live_session, message_content, valid_id
from app.sessions.state import canonical, copied, fingerprint
from app.shortlist.inventory import ShortlistInventory, prepare, recheck


class LeadService:
    def __init__(
        self,
        authorization: AuthorizationService,
        *,
        inventory: ShortlistInventory | None = None,
    ) -> None:
        self.authorization, self.inventory = authorization, inventory

    def get(self, context: AuthorizedOwnerContext) -> LeadRecord | NoLead:
        def read(unit: OwnerUnit) -> LeadRecord | NoLead:
            row = repo.current(unit)
            if row is None:
                return NoLead(state="not_created")
            return repo.record(
                unit, row, context.generation, self.authorization.identity.now_text()
            )

        return self.authorization.read(context, read)

    def save(self, context: AuthorizedOwnerContext, command: LeadSaveRequest) -> LeadSaveResult:
        try:
            command = copied(LeadSaveRequest, command)
        except (AttributeError, TypeError, ValueError):
            raise ApiFailure("VALIDATION_ERROR") from None
        return self._change(context, command, lead_id=None)

    def update(
        self,
        context: AuthorizedOwnerContext,
        lead_id: str,
        command: LeadUpdateRequest,
    ) -> LeadSaveResult:
        try:
            command = copied(LeadUpdateRequest, command)
        except (AttributeError, TypeError, ValueError):
            raise ApiFailure("VALIDATION_ERROR") from None
        return self._change(context, command, lead_id=valid_id(lead_id))

    def _change(
        self,
        context: AuthorizedOwnerContext,
        command: LeadSaveRequest | LeadUpdateRequest,
        *,
        lead_id: str | None,
    ) -> LeadSaveResult:
        preparation = self.prepare_change(
            context, command, lead_id=lead_id, submitted_generation=context.generation,
        )
        if isinstance(preparation, LeadCommandExpired):
            raise ApiFailure("REPLAY_EXPIRED")
        if isinstance(preparation, LeadCommandUnreconciled) or (
            isinstance(preparation, LeadCommandKnown)
            and preparation.generation_relation != "same_generation"
        ):
            raise ApiFailure("STORE_GENERATION_CHANGED")
        if isinstance(preparation, LeadCommandKnown):
            def replay(unit: OwnerUnit) -> LeadSaveResult:
                now = self.authorization.identity.now_text()
                prior = repo.receipt(
                    unit, command.client_action_id, preparation.payload_hash,
                    context.generation, now,
                )
                if prior is None:
                    raise ApiFailure("OPERATION_UNRESOLVED")
                return LeadSaveResult(lead=prior, replayed=True)

            return self.authorization.read(context, replay)

        def write(unit: OwnerUnit) -> LeadSaveResult:
            now = self.authorization.identity.now_text()
            result = self.change_in_unit(
                unit, command, lead_id=lead_id, submitted_generation=context.generation,
                generation=context.generation, now=now,
                prepared=preparation if isinstance(preparation, PreparedLeadChange) else None,
            )
            if result.replayed:
                # Preserve the public UI's separately labelled fresh CSV observation.
                # Exact command lookup itself remains independent of this dependency.
                observed = repo.receipt(
                    unit, command.client_action_id,
                    fingerprint(dict(lead_id=lead_id, command=command.model_dump(mode="json"))),
                    context.generation, now,
                )
                if observed is None:
                    raise StoreError("LEAD_RECEIPT_INCOMPATIBLE")
                return LeadSaveResult(lead=observed, replayed=True)
            return result

        return self.authorization.write(context, write)

    @staticmethod
    def _copied_change(
        command: LeadSaveRequest | LeadUpdateRequest, lead_id: str | None,
    ) -> tuple[LeadSaveRequest | LeadUpdateRequest, str | None]:
        try:
            if isinstance(command, LeadSaveRequest) and lead_id is None:
                return copied(LeadSaveRequest, command), None
            if isinstance(command, LeadUpdateRequest) and lead_id is not None:
                return copied(LeadUpdateRequest, command), valid_id(lead_id)
        except (AttributeError, TypeError, ValueError):
            pass
        raise ApiFailure("VALIDATION_ERROR")

    @staticmethod
    def _envelope(
        unit: OwnerUnit, command: LeadSaveRequest | LeadUpdateRequest, *,
        lead_id: str | None, submitted_generation: str, source_message_id: str | None,
    ) -> LeadChangeEnvelope:
        body = command.model_dump(mode="json")
        return LeadChangeEnvelope(
            unit.owner_id, valid_id(submitted_generation),
            None if source_message_id is None else valid_id(source_message_id), lead_id,
            "save" if isinstance(command, LeadSaveRequest) else "update",
            canonical(body), fingerprint(dict(lead_id=lead_id, command=body)),
        )

    def lookup_change_in_unit(
        self, unit: OwnerUnit, command: LeadSaveRequest | LeadUpdateRequest, *,
        lead_id: str | None = None, submitted_generation: str,
        source_message_id: str | None = None, observed_generation: str, now: str,
    ) -> LeadCommandObservation:
        """Exact retained proof, never fresh CSV or a permission to replace an absent key."""
        command, lead_id = self._copied_change(command, lead_id)
        bound = self._envelope(
            unit, command, lead_id=lead_id, submitted_generation=submitted_generation,
            source_message_id=source_message_id,
        )
        observed_generation = valid_id(observed_generation)
        metadata = unit.db.get(StoreMetadata, 1)
        if metadata is None or metadata.store_generation != observed_generation:
            raise ApiFailure("STORE_GENERATION_CHANGED")
        identity = (
            command.client_action_id, bound.payload_hash,
            bound.submitted_store_generation, observed_generation,
        )
        receipt = unit.db.scalar(select(CommandReceipt).where(
            CommandReceipt.owner_id == unit.owner_id,
            CommandReceipt.command_kind == repo.KIND,
            CommandReceipt.client_action_id == command.client_action_id,
        ))
        if receipt is None:
            if submitted_generation != observed_generation:
                return LeadCommandUnreconciled(*identity, reason="generation_changed")
            return LeadCommandAbsent(*identity)
        if receipt.payload_hash != bound.payload_hash:
            raise ApiFailure("IDEMPOTENCY_CONFLICT")
        if not isinstance(receipt.result_json, dict):
            raise StoreError("LEAD_RECEIPT_INCOMPATIBLE")
        if source_message_id is not None and (
            receipt.result_json.get("source_message_id") != source_message_id
        ):
            raise ApiFailure("IDEMPOTENCY_CONFLICT")
        if receipt.expires_at <= now:
            return LeadCommandExpired(*identity, replay_valid_until=receipt.expires_at)
        try:
            saved = repo.CaptureReceipt.model_validate(receipt.result_json)
        except (TypeError, ValueError):
            raise StoreError("LEAD_RECEIPT_INCOMPATIBLE") from None
        if saved.store_generation != submitted_generation:
            return LeadCommandUnreconciled(*identity, reason="generation_changed")
        expected_revision = 1 if isinstance(command, LeadSaveRequest) else command.expected_revision + 1
        if (
            saved.lead.revision != receipt.applied_revision
            or saved.lead.revision != expected_revision
            or saved.lead.csv.store_generation != saved.store_generation
            or saved.lead.values != command.values
            or lead_id is not None and saved.lead.lead_id != lead_id
        ):
            raise StoreError("LEAD_RECEIPT_INCOMPATIBLE")
        current = unit.db.scalar(select(Lead).where(
            Lead.id == saved.lead.lead_id, Lead.owner_id == unit.owner_id,
        ))
        if current is None:
            return LeadCommandUnreconciled(*identity, reason="canonical_authority_missing")
        if current.revision < receipt.applied_revision or current.journey_id != saved.lead.journey_id:
            raise StoreError("LEAD_RECEIPT_INCOMPATIBLE")
        return LeadCommandKnown(
            *identity, accepted=saved.lead.model_copy(deep=True), accepted_at=receipt.created_at,
            replay_valid_until=receipt.expires_at,
            generation_relation=(
                "same_generation" if submitted_generation == observed_generation
                else "historical_generation"
            ),
        )

    def _validate_fresh(
        self, unit: OwnerUnit, command: LeadSaveRequest | LeadUpdateRequest, *,
        lead_id: str | None, generation: str, source_message_id: str | None, now: str,
    ) -> str:
        from app.sessions.collection_state import check_collection_command_fence

        check_collection_command_fence(
            unit, source_message_id=source_message_id,
            command_hash=fingerprint(dict(lead_id=lead_id, command=command.model_dump(mode="json"))),
        )
        session = live_session(unit, command.session_id, now)
        unit.journey(session.journey_id)
        if source_message_id is not None:
            message = unit.message(session.id, source_message_id)
            if (
                message.state != "pending" or message.accepted_revision != session.revision
                or message_content(message).assistant_result is not None
            ):
                raise ApiFailure("UNSUPPORTED_STATE")
        row = unit.lead_for_journey(session.journey_id)
        if source_message_id is not None:
            # Chat collects non-contact needs only. Existing optional form data
            # must survive exact-revision corrections without erasure/replacement.
            if isinstance(command, LeadSaveRequest):
                if "provided" in {command.values.email.state, command.values.phone.state}:
                    raise ApiFailure("VALIDATION_ERROR")
            elif row is not None:
                original = repo.values(row)
                if (command.values.email, command.values.phone) != (original.email, original.phone):
                    raise ApiFailure("VALIDATION_ERROR")
        if isinstance(command, LeadSaveRequest):
            if row is not None:
                raise ApiFailure("LEAD_EXISTS")
        else:
            if lead_id is None:
                raise ApiFailure("VALIDATION_ERROR")
            owned = unit.lead(lead_id)
            if row is None or row.id != owned.id:
                raise ApiFailure("NOT_FOUND")
            repo.record(unit, row, generation, now)
            if row.revision != command.expected_revision:
                raise ApiFailure("LEAD_REVISION_CONFLICT")
        return session.journey_id

    def prepare_change(
        self, context: AuthorizedOwnerContext, command: LeadSaveRequest | LeadUpdateRequest, *,
        lead_id: str | None = None, submitted_generation: str,
        source_message_id: str | None = None,
    ) -> LeadPreparation:
        assert_outside_write_transaction()
        command, lead_id = self._copied_change(command, lead_id)

        def inspect(unit: OwnerUnit) -> LeadChangeEnvelope | LeadCommandObservation:
            now = self.authorization.identity.now_text()
            observation = self.lookup_change_in_unit(
                unit, command, lead_id=lead_id, submitted_generation=submitted_generation,
                source_message_id=source_message_id, observed_generation=context.generation, now=now,
            )
            if not isinstance(observation, LeadCommandAbsent):
                return observation
            self._validate_fresh(
                unit, command, lead_id=lead_id, generation=context.generation,
                source_message_id=source_message_id, now=now,
            )
            return self._envelope(
                unit, command, lead_id=lead_id, submitted_generation=submitted_generation,
                source_message_id=source_message_id,
            )

        inspected = self.authorization.read(context, inspect)
        if not isinstance(inspected, LeadChangeEnvelope):
            if isinstance(inspected, LeadCommandAbsent):
                raise StoreError("LEAD_PREPARATION_INCOMPATIBLE")
            return inspected
        refs = tuple(ImmutableInventoryRef.model_validate(ref.model_dump())
                     for ref in command.values.selected_refs)
        references = prepare(self.inventory, refs, context.generation) if refs else None
        if references is not None and any(item.state == "missing" for item in references.items):
            raise ApiFailure("NOT_FOUND")
        return PreparedLeadChange(inspected, references)

    def change_in_unit(
        self, unit: OwnerUnit, command: LeadSaveRequest | LeadUpdateRequest, *,
        lead_id: str | None = None, submitted_generation: str,
        source_message_id: str | None = None, generation: str, now: str,
        prepared: PreparedLeadChange | None,
    ) -> LeadSaveResult:
        """All exceptions after entry must abort the caller's whole transaction.

        In particular enqueue may fail after lead mutation; a caller must never
        convert such an exception into a committed rejected-message result.
        """
        repo.require_write(unit)
        command, lead_id = self._copied_change(command, lead_id)
        observation = self.lookup_change_in_unit(
            unit, command, lead_id=lead_id, submitted_generation=submitted_generation,
            source_message_id=source_message_id, observed_generation=generation, now=now,
        )
        if isinstance(observation, LeadCommandExpired):
            raise ApiFailure("REPLAY_EXPIRED")
        if isinstance(observation, LeadCommandUnreconciled) or submitted_generation != generation:
            raise ApiFailure("STORE_GENERATION_CHANGED")
        if isinstance(observation, LeadCommandKnown):
            return LeadSaveResult(lead=observation.accepted.model_copy(deep=True), replayed=True)
        bound = self._envelope(
            unit, command, lead_id=lead_id, submitted_generation=submitted_generation,
            source_message_id=source_message_id,
        )
        if prepared is None or prepared.envelope != bound:
            raise ApiFailure("UNSUPPORTED_STATE")
        journey_id = self._validate_fresh(
            unit, command, lead_id=lead_id, generation=generation,
            source_message_id=source_message_id, now=now,
        )
        refs = tuple(ImmutableInventoryRef.model_validate(ref.model_dump())
                     for ref in command.values.selected_refs)
        if bool(refs) != (prepared.references is not None):
            raise ApiFailure("UNSUPPORTED_STATE")
        if prepared.references is not None:
            if tuple(item.ref for item in prepared.references.items) != refs:
                raise ApiFailure("UNSUPPORTED_STATE")
            recheck(unit, prepared.references, generation, self.inventory)
        retention = self.authorization.identity.settings.policy.terminal_record_retention_days
        if isinstance(command, LeadSaveRequest):
            row = repo.create(
                unit, journey_id=journey_id, session_id=command.session_id,
                supplied=command.values, now=now, retention_days=retention,
            )
        else:
            assert lead_id is not None
            row = unit.lead(lead_id)
            repo.advance(row, command.expected_revision, now, retention)
            row.values_json = command.values.model_dump(mode="json")
        repo.enqueue(unit, row, generation, now)
        unit.db.flush()
        saved = repo.record(unit, row, generation, now)
        repo.remember(
            unit, action_id=command.client_action_id, digest=bound.payload_hash,
            generation=generation, lead=saved, now=now, retention_days=retention,
            source_message_id=source_message_id,
        )
        return LeadSaveResult(lead=saved, replayed=False)
