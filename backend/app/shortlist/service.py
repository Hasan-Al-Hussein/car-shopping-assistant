"""Desired-state exact membership commands and observational stable pages."""

from datetime import datetime, timedelta
from uuid import uuid4

from app.api.schemas.common import ErrorCode, InventoryRef
from app.api.schemas.memory import (
    MembershipRequest,
    MembershipResult,
    ShortlistItem,
    ShortlistResult,
)
from app.core.errors import ApiFailure
from app.database.models import CommandReceipt, ShortlistMembership
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.identity.service import utc_text
from app.inventory.references import ImmutableInventoryRef
from app.memory.repository import next_revision
from app.sessions.state import copied, fingerprint
from app.shortlist import repository as repo
from app.shortlist.inventory import (
    ReferenceBatch,
    ReferenceObservation,
    ShortlistInventory,
    key,
    prepare,
    recheck,
)


class MembershipRejected(ApiFailure):
    """A command precondition failed before this participant changed any row."""

    def __init__(self, code: ErrorCode) -> None:
        if code not in {"VALIDATION_ERROR", "REVISION_CONFLICT", "UNSUPPORTED_STATE"}:
            raise ValueError("INVALID_COMMAND_PRECONDITION_CODE")
        super().__init__(code)


class ShortlistService:
    def __init__(
        self, authorization: AuthorizationService, *, inventory: ShortlistInventory | None = None
    ) -> None:
        self.authorization, self.inventory = authorization, inventory

    def _now(self) -> str:
        return self.authorization.identity.now_text()

    def get(
        self, context: AuthorizedOwnerContext, *, page_size: int = 20, cursor: str | None = None
    ) -> ShortlistResult:
        if type(page_size) is not int or not 1 <= page_size <= 50:
            raise ApiFailure("VALIDATION_ERROR")

        def read(unit: OwnerUnit) -> repo.MembershipPage:
            return repo.page(
                unit,
                context_id=context.context_id,
                generation=context.generation,
                now=self._now(),
                page_size=page_size,
                cursor=cursor,
            )

        page = self.authorization.read(context, read)
        if not page.items:
            return ShortlistResult(
                revision=page.revision, items=[], total=page.total, next_cursor=None
            )
        prepared = prepare(
            self.inventory, tuple(item.ref for item in page.items), context.generation
        )

        def finish(unit: OwnerUnit) -> ShortlistResult:
            now = self._now()
            if (
                repo.owner(unit).shortlist_revision != page.revision
                or now < page.observed_at
                or page.earliest_expiry is not None
                and now >= page.earliest_expiry
            ):
                raise ApiFailure("REVISION_CONFLICT")
            recheck(unit, prepared, context.generation, self.inventory)
            items = [
                ShortlistItem.model_validate(
                    dict(
                        ref=saved.ref.model_dump(mode="json"),
                        state=observation.state,
                        listing=None
                        if observation.listing is None
                        else observation.listing.model_dump(mode="json"),
                        added_at=saved.added_at,
                        expires_at=saved.expires_at,
                    )
                )
                for saved, observation in zip(page.items, prepared.items, strict=True)
            ]
            return ShortlistResult(
                revision=page.revision, items=items, total=page.total, next_cursor=page.next_cursor
            )

        return self.authorization.read(context, finish)

    def put(
        self, context: AuthorizedOwnerContext, ref: InventoryRef, command: MembershipRequest
    ) -> MembershipResult:
        return self._change(context, ref, command, desired=True)

    def delete(
        self, context: AuthorizedOwnerContext, ref: InventoryRef, command: MembershipRequest
    ) -> MembershipResult:
        return self._change(context, ref, command, desired=False)

    @staticmethod
    def _command(
        ref: InventoryRef, command: MembershipRequest, desired: bool
    ) -> tuple[ImmutableInventoryRef, MembershipRequest, str]:
        if type(desired) is not bool:
            raise MembershipRejected("VALIDATION_ERROR")
        try:
            exact = ImmutableInventoryRef.model_validate(ref.model_dump(mode="json"))
            command = copied(MembershipRequest, command)
        except (AttributeError, TypeError, ValueError):
            raise MembershipRejected("VALIDATION_ERROR") from None
        digest = fingerprint(
            dict(
                method="PUT" if desired else "DELETE",
                ref=exact.model_dump(mode="json"),
                expected_revision=command.expected_revision,
            )
        )
        return exact, command, digest

    def _preflight_change(
        self, unit: OwnerUnit, ref: InventoryRef, command: MembershipRequest, *, desired: bool
    ) -> None:
        """Mutation-free receipt-first guard, also used to recheck a preparation denial."""
        _, command, digest = self._command(ref, command, desired)
        if repo.receipt(unit, command.client_action_id, digest, self._now()) is None:
            try:
                next_revision(repo.owner(unit).shortlist_revision, command.expected_revision)
            except ApiFailure as exc:
                if exc.code in {"REVISION_CONFLICT", "UNSUPPORTED_STATE"}:
                    raise MembershipRejected(exc.code) from None
                raise
            setting = unit.preference_setting()
            if desired and setting is not None and setting.collection_mode == "disabled":
                raise MembershipRejected("UNSUPPORTED_STATE")

    def prepare_change(
        self,
        context: AuthorizedOwnerContext,
        ref: InventoryRef,
        command: MembershipRequest,
        *,
        desired: bool,
    ) -> ReferenceBatch:
        exact, command, _ = self._command(ref, command, desired)
        self.authorization.read(
            context, lambda unit: self._preflight_change(unit, exact, command, desired=desired)
        )
        return prepare(self.inventory, (exact,), context.generation)

    def _change(
        self,
        context: AuthorizedOwnerContext,
        ref: InventoryRef,
        command: MembershipRequest,
        *,
        desired: bool,
    ) -> MembershipResult:
        exact, command, _ = self._command(ref, command, desired)
        prepared = self.prepare_change(context, exact, command, desired=desired)
        return self.authorization.write(
            context,
            lambda unit: self.change_in_unit(
                unit, exact, command, desired=desired,
                generation=context.generation, prepared=prepared,
            ),
        )

    def change_in_unit(
        self,
        unit: OwnerUnit,
        ref: InventoryRef,
        command: MembershipRequest,
        *,
        desired: bool,
        generation: str,
        prepared: ReferenceBatch,
    ) -> MembershipResult:
        """Apply inside the authorized caller's WRITE; the returned DTO is provisional."""
        if unit.db.connection().get_execution_options().get("store_write") is not True:
            raise ApiFailure("UNSUPPORTED_STATE")
        exact, command, digest = self._command(ref, command, desired)
        if (
            type(prepared) is not ReferenceBatch
            or type(prepared.items) is not tuple
            or len(prepared.items) != 1
            or type(prepared.identity) is not tuple
            or len(prepared.identity) > 256
            or any(type(part) is not str or len(part) > 512 for part in prepared.identity)
            or (prepared.active_snapshot_id is None) != (prepared.active_revision is None)
            or (prepared.active_snapshot_id is None) != (prepared.active_index_version is None)
        ):
            raise ApiFailure("VALIDATION_ERROR")
        observation = prepared.items[0]
        if (
            type(observation) is not ReferenceObservation
            or type(observation.ref) is not ImmutableInventoryRef
            or key(observation.ref) != key(exact)
            or observation.state not in {"current", "historical", "missing"}
            or (observation.state == "missing") != (observation.listing is None)
            or observation.listing is not None and key(observation.listing.ref) != key(exact)
            or observation.state == "current" and exact.snapshot_id != prepared.active_snapshot_id
            or observation.state == "historical" and exact.snapshot_id == prepared.active_snapshot_id
        ):
            raise ApiFailure("VALIDATION_ERROR")
        now = self._now()
        buyer = repo.owner(unit)
        prior = repo.receipt(unit, command.client_action_id, digest, now)
        recheck(unit, prepared, generation, self.inventory)
        row = repo.membership(unit, exact)
        saved = row is not None and row.expires_at > now
        state = prepared.items[0].state
        if prior is not None:
            return MembershipResult(
                ref=exact.model_dump(),
                client_action_id=command.client_action_id,
                saved=saved,
                changed_at_apply=prior.result_json["changed_at_apply"],
                replayed=True,
                applied_revision=prior.applied_revision,
                current_revision=buyer.shortlist_revision,
                reference_state=state,
            )
        try:
            revision = next_revision(buyer.shortlist_revision, command.expected_revision)
        except ApiFailure as exc:
            if exc.code in {"REVISION_CONFLICT", "UNSUPPORTED_STATE"}:
                raise MembershipRejected(exc.code) from None
            raise
        setting = unit.preference_setting()
        if desired and setting is not None and setting.collection_mode == "disabled":
            raise MembershipRejected("UNSUPPORTED_STATE")
        if desired and state != "current":
            raise ApiFailure("SNAPSHOT_STALE" if state == "historical" else "NOT_FOUND")
        changed = saved != desired
        if desired and not saved:
            if row is None:
                row = ShortlistMembership(owner_id=unit.owner_id, **exact.model_dump())
                unit.db.add(row)
            row.added_at, row.updated_at = now, now
            row.expires_at = utc_text(
                datetime.fromisoformat(now)
                + timedelta(
                    days=self.authorization.identity.settings.policy.shortlist_retention_days
                )
            )
        elif not desired and row is not None:
            unit.db.delete(row)
        buyer.shortlist_revision = revision
        unit.db.add(
            CommandReceipt(
                id=str(uuid4()),
                owner_id=unit.owner_id,
                command_kind=repo.KIND,
                client_action_id=command.client_action_id,
                payload_hash=digest,
                applied_revision=revision,
                result_json={"version": "shortlist-command-1", "changed_at_apply": changed},
                created_at=now,
                expires_at=utc_text(
                    datetime.fromisoformat(now)
                    + timedelta(
                        days=self.authorization.identity.settings.policy.terminal_record_retention_days
                    )
                ),
            )
        )
        return MembershipResult(
            ref=exact.model_dump(),
            client_action_id=command.client_action_id,
            saved=desired,
            changed_at_apply=changed,
            replayed=False,
            applied_revision=revision,
            current_revision=revision,
            reference_state=state,
        )
