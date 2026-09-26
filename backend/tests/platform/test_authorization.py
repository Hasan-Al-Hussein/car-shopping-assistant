"""BE09 seeded units and test-only HTTP adapters, not unimplemented domain routes."""

from dataclasses import asdict
from datetime import timedelta
from functools import partial
from typing import Any

import pytest
from sqlalchemy import delete, update

from app.core.errors import ApiFailure
from app.database.models import (
    Base,
    BookingDraft,
    BookingReview,
    ConversationSession,
    Message,
    OwnerCredential,
    PresentationItem,
    ResultPresentation,
    StoreMetadata,
)
from app.database.store import StoreError, open_store
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.identity.credentials import credential_digest, encode_token
from tests.platform.authorization_cases import (
    KINDS,
    AuthorizationHarness,
    ident,
    make_authorization_harness,
    operation_key,
    private_value,
    token,
)
from tests.platform.persistence_cases import NOW
from tests.platform.test_identity import snapshot


@pytest.fixture
def harness() -> AuthorizationHarness:
    return make_authorization_harness()


@pytest.mark.parametrize("kind", KINDS)
def test_own_foreign_absent_resources_and_denied_write_rollback(
    harness: AuthorizationHarness, kind: str
) -> None:
    context = harness.context(write=True)
    before = snapshot(harness.store)
    assert harness.auth.read(context, lambda unit: private_value(unit, kind)) == ident("owner")
    assert harness.auth.read(
        harness.context("b"), lambda unit: private_value(unit, kind, "b")
    ) == ident("owner", "b")
    for who, missing in (("b", False), ("a", True)):
        with pytest.raises(ApiFailure, match="^NOT_FOUND$"):
            harness.auth.read(context, partial(private_value, kind=kind, who=who, missing=missing))
        assert snapshot(harness.store) == before

        def denied(unit: OwnerUnit, who: str = who, missing: bool = missing) -> None:
            # Roll back even an earlier valid edit if subsequent ownership admission fails.
            unit.session(ident("session")).revision += 1
            private_value(unit, kind, who, missing=missing)

        with pytest.raises(ApiFailure, match="^NOT_FOUND$"):
            harness.auth.write(context, denied)
        assert snapshot(harness.store) == before


def test_collections_never_select_another_owner(harness: AuthorizationHarness) -> None:
    def collect(unit: OwnerUnit) -> dict[str, object]:
        return {
            "sessions": [row.owner_id for row in unit.sessions()],
            "messages": [row.owner_id for row in unit.messages(ident("session"))],
            "preferences": [row.owner_id for row in unit.preferences()],
            "shortlist": [row.owner_id for row in unit.shortlist_memberships()],
            "setting": unit.preference_setting().owner_id,  # type: ignore[union-attr]
            "lead": unit.lead_for_journey(ident("journey")).owner_id,  # type: ignore[union-attr]
            "export": [row.lead_id for row in unit.export_intents(ident("lead"))],
        }

    value = harness.auth.read(harness.context(), collect)
    assert value == {
        "sessions": [ident("owner"), ident("owner")],
        "messages": [ident("owner")],
        "preferences": [ident("owner")],
        "shortlist": [ident("owner")],
        "setting": ident("owner"),
        "lead": ident("owner"),
        "export": [ident("lead")],
    }
    for limit in (0, 51, True):
        with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
            harness.auth.read(harness.context(), partial(OwnerUnit.sessions, limit=limit))


@pytest.mark.parametrize(
    "kind", ["message", "presentation", "item", "review", "active", "draft", "link", "receipt"]
)
def test_wrong_relationship_is_not_sufficient_even_with_an_owned_parent(
    harness: AuthorizationHarness, kind: str
) -> None:
    def denied(unit: OwnerUnit) -> None:
        if kind == "message":
            unit.message(ident("session-other"), ident("message"))
        elif kind == "presentation":
            unit.presentation(ident("session-other"), ident("presentation"))
        elif kind == "item":
            unit.presentation_item(ident("session-other"), ident("presentation"), 0)
        elif kind == "review":
            unit.review_for_draft(ident("draft-other"), ident("review"))
        elif kind == "active":
            unit.active_review(ident("draft-other"))
        elif kind == "draft":
            unit.draft_for_session(ident("session-other"), ident("draft"))
        elif kind == "link":
            unit.lead_booking(ident("lead"), ident("booking", "b"))
        else:
            unit.command_receipt("different-command-kind", ident("action"))

    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="^NOT_FOUND$"):
        harness.auth.write(harness.context(write=True), denied)
    assert snapshot(harness.store) == before
    assert harness.auth.read(
        harness.context(), lambda unit: unit.active_review(ident("draft")).id
    ) == ident("review")


def test_opaque_context_cannot_be_supplied_by_model_or_upgraded(
    harness: AuthorizationHarness,
) -> None:
    context = harness.context()
    with pytest.raises(TypeError, match="SERVER_ISSUED_AUTHORIZATION_REQUIRED"):
        AuthorizedOwnerContext()
    with pytest.raises(AttributeError, match="IMMUTABLE"):
        context._claims = context._claims
    assert repr(context) == "<AuthorizedOwnerContext>"
    with pytest.raises(TypeError):
        asdict(context)  # type: ignore[call-overload]
    called = False

    def write(unit: OwnerUnit) -> str:
        nonlocal called
        called = True
        return unit.owner_id

    for forged in ({"owner_id": ident("owner"), "admin": True}, ident("owner"), object()):
        with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
            harness.auth.write(forged, write)  # type: ignore[arg-type]
    with pytest.raises(ApiFailure, match="CSRF_DENIED"):
        harness.auth.write(context, write)
    other_service = AuthorizationService(harness.identity)
    with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
        other_service.read(context, write)
    assert not called


def test_verified_context_propagates_to_trusted_tool_and_unit_cannot_escape(
    harness: AuthorizationHarness,
) -> None:
    context = harness.context(write=True)

    def trusted_tool(grant: AuthorizedOwnerContext, session_id: str) -> int:
        def change(unit: OwnerUnit) -> int:
            value = unit.session(session_id)
            value.revision += 1
            return value.revision

        return harness.auth.write(grant, change)

    assert trusted_tool(context, ident("session")) == 1
    assert harness.auth.read(context, lambda unit: unit.session(ident("session")).revision) == 1
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        trusted_tool(context, ident("session", "b"))
    captured: list[OwnerUnit] = []
    harness.auth.read(context, lambda unit: captured.append(unit))
    with pytest.raises(StoreError, match="OWNER_UNIT_CLOSED"):
        _ = captured[0].db
    with pytest.raises(StoreError, match="MATERIALIZED"):
        harness.auth.read(context, lambda unit: unit.session(ident("session")))


@pytest.mark.parametrize(
    "change", ["revoke", "expire", "binding", "context", "digest", "generation"]
)
@pytest.mark.parametrize("access", ["read", "write"])
def test_authority_is_revalidated_between_resolution_and_protected_unit(
    harness: AuthorizationHarness, change: str, access: str
) -> None:
    context = harness.context(write=access == "write")
    if change == "expire":
        harness.clock.value += timedelta(days=31)
    elif change == "generation":
        harness.store.write(
            lambda db: db.execute(
                update(StoreMetadata).values(store_generation=ident("new-generation"))
            ).close()
        )
        harness.store = open_store(harness.store.path, boundary=harness.store.boundary)
    else:
        updates = {
            "revoke": {"revoked_at": NOW},
            "binding": {"csrf_binding": encode_token(b"d" * 32)},
            "context": {"context_id": ident("changed-context")},
            "digest": {"token_digest": "e" * 64},
        }
        harness.store.write(
            lambda db: db.execute(
                update(OwnerCredential)
                .where(OwnerCredential.id == ident("credential"))
                .values(**updates[change])
            ).close()
        )
    before = snapshot(harness.store)
    reached = False

    def forbidden(unit: OwnerUnit) -> None:
        nonlocal reached
        reached = True
        unit.session(ident("session")).revision += 1

    with pytest.raises(
        (ApiFailure, StoreError), match="IDENTITY_REQUIRED|STORE_GENERATION_CHANGED"
    ):
        if access == "write":
            harness.auth.write(context, forbidden)
        else:
            harness.auth.read(context, forbidden)
    assert not reached
    assert snapshot(harness.store) == before


def test_retained_receipts_do_not_require_live_origin_or_current_original_generation(
    harness: AuthorizationHarness,
) -> None:
    def retain(db: Any) -> None:
        db.execute(
            update(BookingDraft)
            .where(BookingDraft.owner_id == ident("owner"))
            .values(active_review_id=None)
        )
        db.execute(
            update(BookingReview)
            .where(BookingReview.owner_id == ident("owner"))
            .values(draft_id=None, expires_at=NOW)
        )
        db.execute(delete(BookingDraft).where(BookingDraft.owner_id == ident("owner")))
        db.execute(
            delete(PresentationItem).where(
                PresentationItem.presentation_id == ident("presentation")
            )
        )
        db.execute(delete(ResultPresentation).where(ResultPresentation.owner_id == ident("owner")))
        db.execute(delete(Message).where(Message.owner_id == ident("owner")))
        db.execute(
            delete(ConversationSession).where(ConversationSession.owner_id == ident("owner"))
        )

    harness.store.write(retain)
    context = harness.context()
    assert harness.auth.read(context, lambda unit: unit.booking(ident("booking")).id) == ident(
        "booking"
    )
    assert (
        harness.auth.read(
            context, lambda unit: unit.operation(operation_key("a")).review.expires_at
        )
        == NOW
    )
    assert harness.auth.read(
        context, lambda unit: unit.preference("budget").source_session_reference
    ) == ident("session")
    assert harness.auth.read(
        context, lambda unit: unit.lead(ident("lead")).source_session_reference
    ) == ident("session")
    original_generation = harness.store.generation
    new_generation = ident("new-generation")

    # Use a deliberate test-only current credential binding, not a restore implementation.
    def trusted_test_rotation(db: Any) -> None:
        db.execute(update(StoreMetadata).values(store_generation=new_generation))
        db.execute(
            update(OwnerCredential)
            .where(OwnerCredential.id == ident("credential"))
            .values(token_digest=credential_digest(token("a"), new_generation))
        )

    harness.store.write(trusted_test_rotation)
    harness.store = open_store(harness.store.path, boundary=harness.store.boundary)
    fresh = harness.context()
    assert (
        harness.auth.read(
            fresh, lambda unit: unit.operation(operation_key("a")).review.store_generation
        )
        == original_generation
    )
    assert harness.auth.read(fresh, lambda unit: unit.booking(ident("booking")).id) == ident(
        "booking"
    )


def test_missing_outcome_still_requires_owned_retained_review(
    harness: AuthorizationHarness,
) -> None:
    key = encode_token(b"m" * 32)
    harness.store.write(
        lambda db: db.execute(
            Base.metadata.tables["booking_reviews"]
            .insert()
            .values(
                id=ident("pending-review"),
                owner_id=ident("owner"),
                draft_id=None,
                draft_revision=0,
                operation_key=key,
                payload_hash="a" * 64,
                immutable_payload_json={},
                store_generation=ident("historical-generation"),
                issued_at=NOW,
                expires_at=NOW,
                state="submitted",
            )
        ).close()
    )
    context = harness.context()
    assert harness.auth.read(context, lambda unit: unit.operation(key).outcome is None)
    assert harness.auth.read(
        context, lambda unit: unit.operation(key).review.store_generation
    ) == ident("historical-generation")
    for unknown in (encode_token(b"n" * 32), operation_key("b")):
        with pytest.raises(ApiFailure, match="NOT_FOUND"):
            harness.auth.read(context, partial(OwnerUnit.operation, operation_key=unknown))
