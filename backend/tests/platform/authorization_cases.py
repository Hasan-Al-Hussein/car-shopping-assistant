"""Two independent synthetic owners; these rows are not domain-acceptance evidence."""

from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.schemas.common import InventoryRef
from app.core.config import Settings, load_settings
from app.core.diagnostics import RequestEvent
from app.database.models import Base
from app.database.store import Store, initialize_store
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.identity.credentials import credential_digest, csrf_token, encode_token
from app.identity.service import IdentityService
from app.main import create_app
from tests.platform.persistence_cases import seed_rows, uid
from tests.platform.test_identity import Clock
from tests.support.harness import configured_runtime_boundary, runtime_environment


def ident(label: str, who: str = "a") -> str:
    if label in {"owner", "journey", "session"}:
        return uid(label + "-" + who)
    return uid(label if who == "a" else label + "-" + who)


def token(who: str) -> bytes:
    return (b"a" if who == "a" else b"b") * 32


def operation_key(who: str) -> str:
    return encode_token((b"x" if who == "a" else b"y") * 32)


def ref(who: str = "a") -> InventoryRef:
    return InventoryRef(
        namespace="provided-cars-cleaned",
        snapshot_id=("1" if who == "a" else "2") * 64,
        source_id="12",
    )


@dataclass
class AuthorizationHarness:
    store: Store
    settings: Settings
    clock: Clock
    identity: IdentityService
    auth: AuthorizationService
    app: FastAPI
    events: list[RequestEvent]

    def csrf(self, who: str = "a") -> str:
        return csrf_token(
            token(who), self.store.generation, ident("context", who), encode_token(b"c" * 32)
        )

    def context(self, who: str = "a", *, write: bool = False) -> AuthorizedOwnerContext:
        if write:
            return self.auth.authorize_write(token(who), ident("context", who), self.csrf(who))
        return self.auth.authorize_read(token(who), ident("context", who))


def make_authorization_harness() -> AuthorizationHarness:
    boundary = configured_runtime_boundary()
    path = boundary.logical_root / "test-stores" / ("be09-" + str(uuid4())) / "authorization.sqlite3"
    store = initialize_store(path, boundary=boundary)
    settings = load_settings({**runtime_environment(boundary), "CSA_STORE_PATH": str(path)})
    clock = Clock()
    identity = IdentityService(settings, clock=clock.now)
    events: list[RequestEvent] = []
    app = create_app(settings, identity=identity, event_sink=events.append)
    auth: AuthorizationService = app.state.authorization

    def seed(session: Session) -> None:
        rows = seed_rows(store.generation)
        for table, values in rows:
            if table == "owner_credentials":
                values.update(
                    token_digest=credential_digest(token("a"), store.generation),
                    csrf_binding=encode_token(b"c" * 32),
                )
            for key, value in list(values.items()):
                if value == uid("operation-key"):
                    values[key] = operation_key("a")
            session.execute(Base.metadata.tables[table].insert().values(**values))

        duplicate = {
            "owner_credentials",
            "messages",
            "result_presentations",
            "presentation_items",
            "preference_settings",
            "preferences",
            "shortlist_memberships",
            "command_receipts",
            "booking_drafts",
            "booking_reviews",
            "operation_outcomes",
            "bookings",
            "leads",
            "lead_bookings",
            "export_intents",
        }
        replacements = {
            ident(label): ident(label, "b")
            for label in (
                "owner",
                "journey",
                "session",
                "credential",
                "context",
                "message",
                "presentation",
                "command",
                "draft",
                "review",
                "operation",
                "booking",
                "lead",
                "export",
                "action",
            )
        }
        replacements[operation_key("a")] = operation_key("b")
        for table, values in rows:
            if table not in duplicate:
                continue
            copied = {
                key: replacements.get(value, value) if isinstance(value, str) else value
                for key, value in values.items()
            }
            if table == "owner_credentials":
                copied["token_digest"] = credential_digest(token("b"), store.generation)
            if table in {
                "presentation_items",
                "result_presentations",
                "shortlist_memberships",
                "booking_drafts",
                "bookings",
            }:
                copied["snapshot_id"] = "2" * 64
            if table == "preferences":
                copied["key"] = "budget-b"
            session.execute(Base.metadata.tables[table].insert().values(**copied))
        for who in ("a", "b"):
            session.execute(
                Base.metadata.tables["booking_drafts"]
                .update()
                .where(Base.metadata.tables["booking_drafts"].c.id == ident("draft", who))
                .values(active_review_id=ident("review", who))
            )
        # Same-owner second parent makes relationship substitution discriminating.
        for table, values in rows:
            if table == "conversation_sessions" and values["owner_id"] == ident("owner"):
                session.execute(
                    Base.metadata.tables[table]
                    .insert()
                    .values(**{**values, "id": ident("session-other")})
                )
            if table == "booking_drafts":
                session.execute(
                    Base.metadata.tables[table]
                    .insert()
                    .values(**{**values, "id": ident("draft-other"), "active_review_id": None})
                )

    store.write(seed)
    return AuthorizationHarness(store, settings, clock, identity, auth, app, events)


KINDS = (
    "journey",
    "session",
    "message",
    "presentation",
    "presentation_item",
    "preference",
    "shortlist",
    "command_receipt",
    "draft",
    "review",
    "lead",
    "operation",
    "booking",
    "lead_booking",
    "export_intents",
)


def private_value(unit: OwnerUnit, kind: str, who: str = "a", *, missing: bool = False) -> str:
    def target(label: str) -> str:
        return ident("absent-" + label) if missing else ident(label, who)

    if kind == "journey":
        return unit.journey(target("journey")).owner_id
    if kind == "session":
        return unit.session(target("session")).owner_id
    if kind == "message":
        return unit.message(ident("session", who), target("message")).owner_id
    if kind == "presentation":
        return unit.presentation(ident("session", who), target("presentation")).owner_id
    if kind == "presentation_item":
        unit.presentation_item(
            ident("session", who), ident("presentation", who), 99 if missing else 0
        )
        return unit.owner_id
    if kind == "preference":
        return unit.preference(
            "absent" if missing else "budget" if who == "a" else "budget-b"
        ).owner_id
    if kind == "shortlist":
        selected = ref(who)
        if missing:
            selected.source_id = "absent"
        return unit.shortlist(selected).owner_id
    if kind == "command_receipt":
        return unit.command_receipt("shortlist", target("action")).owner_id
    if kind == "draft":
        return unit.draft(target("draft")).owner_id
    if kind == "review":
        return unit.review(target("review")).owner_id
    if kind == "lead":
        return unit.lead(target("lead")).owner_id
    if kind == "operation":
        return unit.operation(
            encode_token(b"z" * 32) if missing else operation_key(who)
        ).review.owner_id
    if kind == "booking":
        return unit.booking(target("booking")).owner_id
    if kind == "lead_booking":
        return unit.lead_booking(ident("lead", who), target("booking")).owner_id
    if kind == "export_intents":
        assert len(unit.export_intents(target("lead"))) == 1
        return unit.owner_id
    raise AssertionError(kind)
