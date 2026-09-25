"""Owner-scoped explicit commands. Successful returns occur only after commit."""

from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app.api.schemas.common import ErrorCode
from app.api.schemas.memory import PreferenceCommand, PreferenceRecord, PreferencesUpdate
from app.core.errors import ApiFailure
from app.database.models import CommandReceipt, Preference, PreferenceSetting
from app.database.store import StoreError
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.identity.service import utc_text
from app.memory import repository as repo
from app.sessions.repository import valid_id
from app.sessions.state import fingerprint

COMMAND: TypeAdapter[PreferenceCommand] = TypeAdapter(PreferenceCommand)
KIND = "preference.command"


class PreferenceRejected(ApiFailure):
    """A command precondition failed before this participant changed any row."""

    def __init__(self, code: ErrorCode) -> None:
        if code not in {"VALIDATION_ERROR", "REVISION_CONFLICT", "UNSUPPORTED_STATE"}:
            raise ValueError("INVALID_COMMAND_PRECONDITION_CODE")
        super().__init__(code)


class PreferenceService:
    def __init__(self, authorization: AuthorizationService) -> None:
        self.authorization = authorization

    def _now(self) -> str:
        return self.authorization.identity.now_text()

    def get(self, context: AuthorizedOwnerContext) -> PreferenceRecord:
        return self.authorization.read(context, lambda unit: repo.record(unit, self._now()))

    def recall(
        self,
        context: AuthorizedOwnerContext,
        *,
        keys: tuple[str, ...],
        current_keys: tuple[str, ...] = (),
    ) -> PreferenceRecord:
        """Bounded relevant subset; current explicit choices override saved values.

        Applicability remains explicit. A caller must clarify any unconfirmed/stale
        hard preference; this method never applies filters or guesses user intent.
        """
        if (
            not isinstance(keys, tuple)
            or not isinstance(current_keys, tuple)
            or len(keys) > 4
            or len(current_keys) > 4
            or any(key not in repo.KEYS for key in (*keys, *current_keys))
        ):
            raise ApiFailure("VALIDATION_ERROR")
        saved = self.get(context)
        return PreferenceRecord(
            entries=[
                item
                for item in saved.entries
                if item.preference.key in keys and item.preference.key not in current_keys
            ],
            revision=saved.revision,
            collection_mode=saved.collection_mode,
        )

    @staticmethod
    def _command(command: PreferenceCommand) -> PreferenceCommand:
        try:
            return COMMAND.validate_json(command.model_dump_json())
        except (AttributeError, TypeError, ValueError, ValidationError):
            raise PreferenceRejected("VALIDATION_ERROR") from None

    def update(
        self, context: AuthorizedOwnerContext, command: PreferenceCommand
    ) -> PreferenceRecord:
        command = self._command(command)
        return self.authorization.write(context, lambda unit: self.update_in_unit(unit, command))

    def update_in_unit(
        self,
        unit: OwnerUnit,
        command: PreferenceCommand,
        *,
        source_message_id: str | None = None,
    ) -> PreferenceRecord:
        """Provisional result; the authorized caller owns the complete transaction."""
        if unit.db.connection().get_execution_options().get("store_write") is not True:
            raise ApiFailure("UNSUPPORTED_STATE")
        command = self._command(command)
        digest = fingerprint(command.model_dump(mode="json"))
        now = self._now()
        # Replay is owner-bound, and does not depend on the original session still being live.
        prior = unit.db.scalar(
            select(CommandReceipt).where(
                CommandReceipt.owner_id == unit.owner_id,
                CommandReceipt.command_kind == KIND,
                CommandReceipt.client_action_id == command.client_action_id,
            )
        )
        if prior is not None:
            if prior.payload_hash != digest:
                raise ApiFailure("IDEMPOTENCY_CONFLICT")
            if prior.expires_at <= now:
                raise ApiFailure("REPLAY_EXPIRED")
            if prior.result_json != {"version": "preference-command-1"}:
                raise StoreError("PREFERENCE_RECEIPT_INCOMPATIBLE")
            return repo.record(unit, now)

        session = unit.session(command.session_id)
        if session.expires_at <= now:
            raise ApiFailure("NOT_FOUND")
        if source_message_id is not None:
            unit.message(command.session_id, valid_id(source_message_id))
        buyer = repo.owner(unit)
        try:
            revision = repo.next_revision(buyer.preference_revision, command.expected_revision)
        except ApiFailure as exc:
            if exc.code in {"REVISION_CONFLICT", "UNSUPPORTED_STATE"}:
                raise PreferenceRejected(exc.code) from None
            raise
        # Validate retained state before accepting another write.
        current = repo.record(unit, now)
        if isinstance(command, PreferencesUpdate):
            if current.collection_mode == "disabled" and any(
                change.value is not None and change.value != [] for change in command.changes
            ):
                raise PreferenceRejected("UNSUPPORTED_STATE")
            for change in command.changes:
                row = unit.db.get(Preference, (unit.owner_id, change.key))
                value = change.model_dump(mode="json")["value"]
                if value is None or value == []:
                    if row is not None:
                        unit.db.delete(row)
                    continue
                if (
                    row is not None
                    and row.expires_at > now
                    and row.value_json == {"value": value}
                    and row.strength == change.strength
                ):
                    continue  # Accepted no-op: preserve confirmation, provenance and expiry.
                expires = utc_text(
                    datetime.fromisoformat(now)
                    + timedelta(
                        days=self.authorization.identity.settings.policy.preference_retention_days
                    )
                )
                if row is None:
                    row = Preference(owner_id=unit.owner_id, key=change.key)
                    unit.db.add(row)
                row.value_json, row.strength = {"value": value}, change.strength
                row.source_session_reference, row.source_action_id = (
                    session.id,
                    command.client_action_id,
                )
                row.source_message_reference = source_message_id
                row.confirmed_at, row.expires_at, row.applicability = now, expires, "confirmed"
        else:
            setting = unit.preference_setting()
            if setting is None:
                setting = PreferenceSetting(
                    owner_id=unit.owner_id, collection_mode="explicit_save"
                )
                unit.db.add(setting)
            setting.collection_mode = (
                "disabled" if command.intent == "stop_saving" else "explicit_save"
            )
        buyer.preference_revision = revision
        unit.db.add(
            CommandReceipt(
                id=str(uuid4()),
                owner_id=unit.owner_id,
                command_kind=KIND,
                client_action_id=command.client_action_id,
                payload_hash=digest,
                applied_revision=revision,
                result_json={"version": "preference-command-1"},
                created_at=now,
                expires_at=utc_text(
                    datetime.fromisoformat(now)
                    + timedelta(
                        days=self.authorization.identity.settings.policy.terminal_record_retention_days
                    )
                ),
            )
        )
        unit.db.flush()
        return repo.record(unit, now)
