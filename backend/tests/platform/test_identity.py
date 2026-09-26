"""BE-08 actual lifecycle units and in-process HTTP with disposable synthetic stores."""

import asyncio
import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.schemas.common import Envelope, ErrorEnvelope
from app.api.schemas.identity import AnonymousIdentity, IdentityBootstrapRequest, RecognizedIdentity
from app.core.config import Settings, Timeouts, load_settings
from app.core.diagnostics import REQUEST_EVENTS, RequestEvent
from app.database.models import Base, BookingReview, OwnerCredential, StoreMetadata
from app.database.paths import StorePathError
from app.database.store import Store, StoreError, initialize_store, open_store
from app.identity.credentials import (
    credential_digest,
    csrf_token,
    decode_token,
    encode_token,
    new_material,
)
from app.identity.service import BootstrapOutcome, IdentityService, utc_text
from app.main import create_app
from tests.platform.persistence_cases import seed, uid
from tests.support.harness import configured_runtime_boundary, runtime_environment

NOW = datetime(2026, 9, 24, 4, tzinfo=UTC)
ACK = {
    "notice_version": "DEMO-POLICY-1",
    "notice_acknowledged": True,
    "display_name": "Synthetic same name",
}
PRIVATE = "SYNTHETIC_PRIVATE_COOKIE_NAME_CONTACT_PATH"


@dataclass
class Clock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


@dataclass
class Harness:
    store: Store
    settings: Settings
    clock: Clock
    app: FastAPI
    events: list[RequestEvent]


def call(
    app: FastAPI,
    settings: Settings,
    method: str,
    path: str,
    *,
    cookie: str | None = None,
    body: object | None = None,
    overrides: Mapping[str, str | None] | None = None,
    extra_headers: list[tuple[str, str]] | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    headers = {"Origin": settings.scheme + "://127.0.0.1:5173"} if method == "POST" else {}
    if cookie is not None:
        headers["Cookie"] = settings.cookie_name + "=" + cookie
    for name, value in (overrides or {}).items():
        if value is None:
            headers.pop(name, None)
        else:
            headers[name] = value
    arguments: dict[str, Any] = {"headers": [*headers.items(), *(extra_headers or [])]}
    if body is not None:
        arguments["json"] = body
    if content is not None:
        arguments["content"] = content

    async def run() -> httpx.Response:
        async with (
            asyncio.timeout(5),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url=settings.scheme + "://127.0.0.1:8000",
            ) as client,
        ):
            return await client.request(method, path, **arguments)

    response = asyncio.run(run())
    assert REQUEST_EVENTS.wait_idle(1)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    return response


def make_harness(profile: str = "local_http") -> Harness:
    boundary = configured_runtime_boundary()
    path = boundary.logical_root / "test-stores" / ("be08-" + str(uuid4())) / "identity.sqlite3"
    # Explicit isolated test setup, never app startup.
    store = initialize_store(path, boundary=boundary)
    settings = load_settings({
        **runtime_environment(boundary), "CSA_PROFILE": profile, "CSA_STORE_PATH": str(path),
    })
    clock = Clock()
    events: list[RequestEvent] = []
    service = IdentityService(settings, clock=clock.now)
    return Harness(
        store,
        settings,
        clock,
        create_app(settings, identity=service, event_sink=events.append),
        events,
    )


@pytest.fixture
def harness() -> Harness:
    return make_harness()


def bootstrap(harness: Harness) -> tuple[str, dict[str, Any], httpx.Response]:
    response = call(harness.app, harness.settings, "POST", "/api/v1/identity/bootstrap", body=ACK)
    assert response.status_code == 201
    parsed: SimpleCookie = SimpleCookie()
    parsed.load(response.headers["set-cookie"])
    token = parsed[harness.settings.cookie_name].value
    return token, response.json()["data"], response


def snapshot(store: Store) -> dict[str, list[dict[str, Any]]]:
    def read(session: Session) -> dict[str, list[dict[str, Any]]]:
        return {
            name: [
                dict(row)
                for row in session.execute(
                    table.select().order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for name, table in Base.metadata.tables.items()
        }

    return store.read(read)


def end_headers(identity: dict[str, Any]) -> dict[str, str | None]:
    return {"X-Identity-Context": identity["context_id"], "X-CSRF-Token": identity["csrf_token"]}


def test_credential_entropy_canonical_encoding_and_separate_crypto_domains() -> None:
    calls: list[int] = []

    def entropy(size: int) -> bytes:
        calls.append(size)
        return bytes(range(size))

    material = new_material(entropy)
    token = encode_token(material)
    assert calls == [32]
    assert len(token) == 43 and decode_token(token) == material
    generation, context_id = str(uuid4()), str(uuid4())
    binding = encode_token(bytes(reversed(range(32))))
    digest = credential_digest(material, generation)
    csrf = csrf_token(material, generation, context_id, binding)
    assert len(digest) == 64 and len(csrf) == 43
    assert digest != hashlib.sha256(material).hexdigest()
    assert credential_digest(material, str(uuid4())) != digest
    assert csrf_token(material, generation, context_id, binding) == csrf
    assert csrf_token(material, str(uuid4()), context_id, binding) != csrf
    assert csrf_token(material, generation, str(uuid4()), binding) != csrf
    assert csrf_token(bytes(reversed(range(32))), generation, context_id, binding) != csrf
    for bad in (token + "=", "", "A" * 42, "A" * 44, "A" * 42 + "B", "é" * 43):
        with pytest.raises(ValueError, match="^INVALID_CREDENTIAL_MATERIAL$"):
            decode_token(bad)
    with pytest.raises(ValueError):
        new_material(lambda _: b"too-short")


@pytest.mark.parametrize("profile", ["local_http", "local_https"])
def test_actual_cookie_profiles_fixed_lifetime_and_public_fields(profile: str) -> None:
    harness = make_harness(profile)
    token, identity, response = bootstrap(harness)
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    attributes = cookie[harness.settings.cookie_name]
    assert attributes["path"] == "/"
    assert attributes["domain"] == ""
    assert attributes["httponly"] is True
    assert attributes["samesite"] == "lax"
    assert bool(attributes["secure"]) is (profile == "local_https")
    assert attributes["max-age"] == str(30 * 24 * 60 * 60)
    assert parsedate_to_datetime(attributes["expires"]) == NOW + timedelta(days=30)
    assert identity["expires_at"] == utc_text(NOW + timedelta(days=30))
    assert len(decode_token(token)) == 32
    public = Envelope[RecognizedIdentity].model_validate(response.json())
    assert public.meta.identity_context_id == public.data.context_id
    assert public.meta.store_generation == harness.store.generation
    assert public.data.continuity == "this_browser_only"
    assert set(identity) == {
        "state",
        "context_id",
        "csrf_token",
        "expires_at",
        "display_name",
        "continuity",
    }
    state = snapshot(harness.store)
    assert len(state["owners"]) == len(state["owner_credentials"]) == 1
    assert state["inventory_storage_profile"] == [{"id": 1, "mode": "fts5"}]
    assert all(
        not rows
        for table, rows in state.items()
        if table
        not in {"owners", "owner_credentials", "store_metadata", "inventory_storage_profile"}
    )
    credential = state["owner_credentials"][0]
    assert len({credential["id"], credential["owner_id"], identity["context_id"]}) == 3
    assert token not in json.dumps(state) + response.text + json.dumps(
        [asdict(event) for event in harness.events]
    )
    assert identity["csrf_token"] not in json.dumps(state) + json.dumps(
        [asdict(event) for event in harness.events]
    )
    assert credential["token_digest"] not in response.text + json.dumps(
        [asdict(event) for event in harness.events]
    )
    ended = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/identity/end",
        cookie=token,
        body={"acknowledge_loss_of_access": True},
        overrides=end_headers(identity),
    )
    rejected = call(
        harness.app, harness.settings, "POST", "/api/v1/identity/bootstrap", cookie=token, body=ACK
    )
    assert ended.status_code == 200 and rejected.status_code == 401
    for cleared in (ended, rejected):
        deletion: SimpleCookie = SimpleCookie()
        deletion.load(cleared.headers["set-cookie"])
        assert list(deletion) == [harness.settings.cookie_name]
        attributes = deletion[harness.settings.cookie_name]
        assert attributes["max-age"] == "0" and attributes["path"] == "/"
        assert attributes["domain"] == "" and attributes["httponly"] is True
        assert attributes["samesite"] == "lax"
        assert bool(attributes["secure"]) is (profile == "local_https")


def test_same_name_never_selects_or_merges_owners(harness: Harness) -> None:
    first_cookie, first, _ = bootstrap(harness)
    second_cookie, second, _ = bootstrap(harness)
    assert first_cookie != second_cookie
    assert first["context_id"] != second["context_id"]
    assert first["csrf_token"] != second["csrf_token"]
    state = snapshot(harness.store)
    assert len(state["owners"]) == len(state["owner_credentials"]) == 2
    for cookie, expected in ((first_cookie, first), (second_cookie, second)):
        response = call(harness.app, harness.settings, "GET", "/api/v1/identity", cookie=cookie)
        assert response.status_code == 200 and response.json()["data"] == expected


def test_get_and_existing_bootstrap_do_not_write_rename_rotate_or_renew(harness: Harness) -> None:
    cookie, identity, _ = bootstrap(harness)
    before = snapshot(harness.store)
    before_bytes = harness.store.path.read_bytes()
    trace: list[str] = []
    service = IdentityService(
        harness.settings,
        clock=harness.clock.now,
        store_opener=lambda path: open_store(
            path, trace=trace.append, boundary=harness.store.boundary
        ),
    )
    app = create_app(harness.settings, identity=service, event_sink=lambda _: None)
    harness.clock.value += timedelta(hours=1)
    for method, path, body in (
        ("GET", "/api/v1/identity", None),
        ("POST", "/api/v1/identity/bootstrap", {**ACK, "display_name": "Do not rename"}),
    ):
        response = call(app, harness.settings, method, path, cookie=cookie, body=body)
        assert response.status_code == 200
        assert response.json()["data"] == identity
        assert "set-cookie" not in response.headers
    assert snapshot(harness.store) == before
    assert harness.store.path.read_bytes() == before_bytes
    assert not any(
        sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE"))
        for sql in trace
    )


def test_anonymous_get_and_app_construction_do_not_open_or_initialize_store() -> None:
    attempted: list[Path] = []
    boundary = configured_runtime_boundary()
    path = (
        boundary.logical_root / "test-stores" / ("be08-missing-" + str(uuid4())) / "missing.sqlite3"
    )
    settings = Settings(store_path=path, runtime_boundary=boundary)

    def forbidden(path: Path) -> Store:
        attempted.append(path)
        raise AssertionError("NO_IDENTITY_STORE_IO_EXPECTED")

    app = create_app(
        settings,
        identity=IdentityService(settings, store_opener=forbidden),
        event_sink=lambda _: None,
    )
    response = call(app, settings, "GET", "/api/v1/identity")
    assert response.status_code == 200
    Envelope[AnonymousIdentity].model_validate(response.json())
    assert response.json()["meta"]["store_generation"] is None
    assert "set-cookie" not in response.headers
    assert attempted == [] and not path.parent.exists()


def test_explicit_bootstrap_with_missing_store_never_creates_or_repairs_it() -> None:
    boundary = configured_runtime_boundary()
    path = (
        boundary.logical_root / "test-stores" / ("be08-absent-" + str(uuid4())) / "missing.sqlite3"
    )
    settings = Settings(store_path=path, runtime_boundary=boundary)
    app = create_app(settings, event_sink=lambda _: None)
    response = call(app, settings, "POST", "/api/v1/identity/bootstrap", body=ACK)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORE_UNAVAILABLE"
    assert "set-cookie" not in response.headers and not path.parent.exists()


def invalidate(harness: Harness, reason: str, cookie: str) -> str:
    if reason == "expired":
        harness.clock.value += timedelta(days=30)
    elif reason == "revoked":
        harness.store.write(
            lambda session: session.execute(
                update(OwnerCredential).values(revoked_at=utc_text(NOW))
            ).close()
        )
    elif reason == "unknown":
        cookie = encode_token(new_material())
    elif reason == "generation":
        harness.store.write(
            lambda session: session.execute(
                update(StoreMetadata).values(store_generation=str(uuid4()))
            ).close()
        )
        harness.store = open_store(harness.store.path, boundary=harness.store.boundary)
    elif reason == "malformed":
        cookie = "not-a-valid-cookie"
    return cookie


@pytest.mark.parametrize("reason", ["expired", "revoked", "unknown", "generation", "malformed"])
def test_invalid_get_never_clears_replaces_or_exposes_identity(
    harness: Harness, reason: str
) -> None:
    cookie, _, _ = bootstrap(harness)
    cookie = invalidate(harness, reason, cookie)
    before = snapshot(harness.store)
    response = call(harness.app, harness.settings, "GET", "/api/v1/identity", cookie=cookie)
    assert response.status_code == 401
    error = ErrorEnvelope.model_validate(response.json()).error
    assert error.code == "IDENTITY_REQUIRED" and error.retry_action == "none"
    assert error.message == "A valid local identity is required."
    assert "set-cookie" not in response.headers
    assert "Synthetic same name" not in response.text
    assert snapshot(harness.store) == before


@pytest.mark.parametrize("reason", ["expired", "revoked", "unknown", "generation", "malformed"])
def test_invalid_bootstrap_clears_only_then_requires_another_explicit_action(
    harness: Harness, reason: str
) -> None:
    cookie, identity, _ = bootstrap(harness)
    cookie = invalidate(harness, reason, cookie)
    before = snapshot(harness.store)
    rejected = call(
        harness.app, harness.settings, "POST", "/api/v1/identity/bootstrap", cookie=cookie, body=ACK
    )
    assert rejected.status_code == 401
    assert rejected.json()["error"]["code"] == "IDENTITY_REQUIRED"
    cleared: SimpleCookie = SimpleCookie()
    cleared.load(rejected.headers["set-cookie"])
    assert list(cleared) == [harness.settings.cookie_name]
    assert cleared[harness.settings.cookie_name]["max-age"] == "0"
    assert cleared[harness.settings.cookie_name]["path"] == "/"
    assert cleared[harness.settings.cookie_name]["domain"] == ""
    assert snapshot(harness.store) == before
    anonymous = call(harness.app, harness.settings, "GET", "/api/v1/identity")
    assert anonymous.json()["data"]["state"] == "anonymous"
    assert snapshot(harness.store) == before
    _, replacement, _ = bootstrap(harness)  # Deliberate second user action, no automatic retry.
    assert replacement["context_id"] != identity["context_id"]
    assert len(snapshot(harness.store)["owners"]) == len(before["owners"]) + 1


@pytest.mark.parametrize("cookie", ["", '"' + "A" * 43 + '"', "A" * 42 + "B", "A" * 44])
def test_supplied_empty_quoted_or_noncanonical_cookie_is_never_anonymous(cookie: str) -> None:
    settings = Settings()
    response = call(
        create_app(settings, event_sink=lambda _: None),
        settings,
        "GET",
        "/api/v1/identity",
        cookie=cookie,
    )
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    "duplicate",
    [
        "same_header",
        "two_headers",
        "oversized",
        "valid_then_bare",
        "bare_then_valid",
        "space_then_valid",
        "valid_then_space",
    ],
)
def test_duplicate_selected_cookie_never_selects_first_or_last(
    harness: Harness, duplicate: str
) -> None:
    cookie, _, _ = bootstrap(harness)
    before = snapshot(harness.store)
    overrides = (
        {"Cookie": f"csa_owner={cookie}; csa_owner={cookie}"}
        if duplicate == "same_header"
        else None
    )
    extras = [("Cookie", "csa_owner=" + cookie)] if duplicate == "two_headers" else None
    if duplicate == "oversized":
        overrides = {"Cookie": f"csa_owner={cookie}; unrelated=" + "x" * 8192}
    elif duplicate == "valid_then_bare":
        overrides = {"Cookie": f"csa_owner={cookie}; csa_owner"}
    elif duplicate == "bare_then_valid":
        overrides = {"Cookie": f"csa_owner; csa_owner={cookie}"}
    elif duplicate == "space_then_valid":
        overrides = {"Cookie": f"csa_owner =bad; csa_owner={cookie}"}
    elif duplicate == "valid_then_space":
        overrides = {"Cookie": f"csa_owner={cookie}; csa_owner =bad"}
    response = call(
        harness.app,
        harness.settings,
        "GET",
        "/api/v1/identity",
        cookie=cookie,
        overrides=overrides,
        extra_headers=extras,
    )
    assert response.status_code == 401 and snapshot(harness.store) == before
    denied = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/identity/bootstrap",
        cookie=cookie,
        body=ACK,
        overrides=overrides,
        extra_headers=extras,
    )
    assert denied.status_code == 401 and "set-cookie" not in denied.headers
    assert snapshot(harness.store) == before
    assert (
        call(harness.app, harness.settings, "GET", "/api/v1/identity", cookie=cookie).status_code
        == 200
    )


@pytest.mark.parametrize(
    ("body", "overrides", "expected"),
    [
        ({**ACK, "notice_acknowledged": False}, {}, 422),
        ({**ACK, "notice_version": "other"}, {}, 422),
        ({**ACK, "owner_id": str(uuid4())}, {}, 422),
        ({**ACK, "role": "admin"}, {}, 422),
        (ACK, {"Origin": None}, 403),
        (ACK, {"Origin": "null"}, 403),
        (ACK, {"Origin": "https://evil.invalid"}, 403),
        (ACK, {"Host": "evil.invalid"}, 400),
        (ACK, {"Content-Type": "text/plain"}, 415),
    ],
)
def test_bad_bootstrap_request_neither_creates_nor_clears_cookie(
    body: dict[str, Any],
    overrides: dict[str, str | None],
    expected: int,
) -> None:
    settings = Settings()
    app = create_app(settings, event_sink=lambda _: None)
    response = call(
        app,
        settings,
        "POST",
        "/api/v1/identity/bootstrap",
        cookie="invalid",
        body=body,
        overrides=overrides,
    )
    assert response.status_code == expected
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    "fault",
    [
        FileNotFoundError(PRIVATE),
        PermissionError(PRIVATE),
        StorePathError(PRIVATE),
        StoreError(PRIVATE),
    ],
)
def test_store_failure_is_not_anonymous_invalid_cookie_or_cookie_clearance(
    fault: Exception,
) -> None:
    boundary = configured_runtime_boundary()
    settings = Settings(
        store_path=boundary.logical_root / "test-stores" / "be08-inert" / "inert.sqlite3",
        runtime_boundary=boundary,
    )

    def unavailable(path: Path) -> Store:
        raise fault

    app = create_app(
        settings,
        identity=IdentityService(settings, store_opener=unavailable),
        event_sink=lambda _: None,
    )
    cookie = encode_token(new_material())
    for method, path, body in (
        ("GET", "/api/v1/identity", None),
        ("POST", "/api/v1/identity/bootstrap", ACK),
        ("POST", "/api/v1/identity/end", {"acknowledge_loss_of_access": True}),
    ):
        headers = (
            {"X-Identity-Context": str(uuid4()), "X-CSRF-Token": encode_token(new_material())}
            if path.endswith("/end")
            else None
        )
        response = call(app, settings, method, path, cookie=cookie, body=body, overrides=headers)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "STORE_UNAVAILABLE"
        assert PRIVATE not in response.text and "set-cookie" not in response.headers


def test_generation_change_between_open_and_unit_does_not_clear_a_potentially_valid_cookie(
    harness: Harness,
) -> None:
    cookie, _, _ = bootstrap(harness)
    stale_store = harness.store
    invalidate(harness, "generation", cookie)
    service = IdentityService(
        harness.settings, clock=harness.clock.now, store_opener=lambda _: stale_store
    )
    app = create_app(harness.settings, identity=service, event_sink=lambda _: None)
    response = call(
        app, harness.settings, "POST", "/api/v1/identity/bootstrap", cookie=cookie, body=ACK
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STORE_GENERATION_CHANGED"
    assert response.json()["error"]["retry_action"] == "none"
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("missing_cookie", 401),
        ("wrong_cookie", 401),
        ("other_cookie", 401),
        ("wrong_context", 401),
        ("wrong_csrf", 403),
        ("missing_context", 422),
        ("missing_csrf", 422),
        ("duplicate_context", 422),
        ("duplicate_csrf", 422),
        ("no_ack", 422),
        ("wrong_origin", 403),
    ],
)
def test_end_requires_cookie_context_csrf_acknowledgement_and_origin(
    harness: Harness,
    change: str,
    expected: int,
) -> None:
    cookie, identity, _ = bootstrap(harness)
    second_cookie, second_identity, _ = bootstrap(harness)
    headers = end_headers(identity)
    extras: list[tuple[str, str]] = []
    body = {"acknowledge_loss_of_access": change != "no_ack"}
    selected: str | None = cookie
    if change == "missing_cookie":
        selected = None
    elif change == "wrong_cookie":
        selected = encode_token(new_material())
    elif change == "other_cookie":
        selected = second_cookie
    elif change == "wrong_context":
        headers["X-Identity-Context"] = second_identity["context_id"]
    elif change == "wrong_csrf":
        headers["X-CSRF-Token"] = second_identity["csrf_token"]
    elif change == "missing_context":
        headers.pop("X-Identity-Context")
    elif change == "missing_csrf":
        headers.pop("X-CSRF-Token")
    elif change == "duplicate_context":
        extras.append(("X-Identity-Context", second_identity["context_id"]))
    elif change == "duplicate_csrf":
        extras.append(("X-CSRF-Token", second_identity["csrf_token"]))
    elif change == "wrong_origin":
        headers["Origin"] = "null"
    before = snapshot(harness.store)
    response = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/identity/end",
        cookie=selected,
        body=body,
        overrides=headers,
        extra_headers=extras,
    )
    assert response.status_code == expected
    assert "set-cookie" not in response.headers
    assert snapshot(harness.store) == before
    assert (
        call(
            harness.app, harness.settings, "GET", "/api/v1/identity", cookie=second_cookie
        ).status_code
        == 200
    )


def test_end_preserves_all_operational_rows_including_unresolved_review(harness: Harness) -> None:
    material, binding = new_material(), encode_token(new_material())
    cookie = encode_token(material)

    def populate(session: Session) -> None:
        seed(session, harness.store.generation)
        session.execute(
            update(OwnerCredential).values(
                token_digest=credential_digest(material, harness.store.generation),
                csrf_binding=binding,
            )
        )
        session.add(
            BookingReview(
                id=str(uuid4()),
                owner_id=uid("owner-a"),
                draft_id=None,
                draft_revision=0,
                operation_key=encode_token(new_material()),
                payload_hash="b" * 64,
                immutable_payload_json={"synthetic_unresolved": True},
                store_generation=harness.store.generation,
                issued_at=utc_text(NOW),
                expires_at=utc_text(NOW + timedelta(minutes=5)),
                state="submitted",
            )
        )

    harness.store.write(populate)
    current = call(harness.app, harness.settings, "GET", "/api/v1/identity", cookie=cookie)
    identity = current.json()["data"]
    before = snapshot(harness.store)
    response = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/identity/end",
        cookie=cookie,
        body={"acknowledge_loss_of_access": True},
        overrides=end_headers(identity),
    )
    assert response.status_code == 200 and response.json()["data"] == {"state": "ended"}
    assert response.json()["meta"]["identity_context_id"] == identity["context_id"]
    after = snapshot(harness.store)
    assert all(after[name] == rows for name, rows in before.items() if name != "owner_credentials")
    expected = {**before["owner_credentials"][0], "revoked_at": utc_text(NOW)}
    assert after["owner_credentials"] == [expected]
    assert "Max-Age=0" in response.headers["set-cookie"]
    invalid = call(harness.app, harness.settings, "GET", "/api/v1/identity", cookie=cookie)
    assert invalid.status_code == 401 and "set-cookie" not in invalid.headers
    repeat = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/identity/end",
        cookie=cookie,
        body={"acknowledge_loss_of_access": True},
        overrides=end_headers(identity),
    )
    assert repeat.status_code == 401 and snapshot(harness.store) == after


def test_response_loss_recovery_uses_delivered_cookie_and_never_name_lookup(
    harness: Harness,
) -> None:
    cookie, identity, _ = bootstrap(harness)
    before = snapshot(harness.store)
    # The bootstrap body can be lost after Set-Cookie; discover without another write.
    discovered = call(harness.app, harness.settings, "GET", "/api/v1/identity", cookie=cookie)
    assert discovered.json()["data"] == identity and snapshot(harness.store) == before
    repeated = call(
        harness.app, harness.settings, "POST", "/api/v1/identity/bootstrap", cookie=cookie, body=ACK
    )
    assert repeated.status_code == 200 and "set-cookie" not in repeated.headers
    assert snapshot(harness.store) == before
    # Before cookie delivery there is no authority to recover that empty owner.
    lost = call(harness.app, harness.settings, "GET", "/api/v1/identity")
    assert lost.json()["data"]["state"] == "anonymous" and snapshot(harness.store) == before
    _, separate, _ = bootstrap(harness)
    assert separate["context_id"] != identity["context_id"]


def test_timed_out_bootstrap_can_finish_without_implying_rollback_or_replacement(
    harness: Harness,
) -> None:
    entered, release, finished = Event(), Event(), Event()

    def slow_clock() -> datetime:
        entered.set()
        if not release.wait(6):
            raise AssertionError("TEST_MUTATION_RELEASE_REQUIRED")
        return NOW

    class ObservedService(IdentityService):
        def bootstrap(
            self, body: IdentityBootstrapRequest, material: bytes | None
        ) -> BootstrapOutcome:
            try:
                return super().bootstrap(body, material)
            finally:
                finished.set()

    settings = Settings(
        store_path=harness.settings.store_path,
        runtime_boundary=harness.store.boundary,
        timeouts=Timeouts(
            read_seconds=1,
            operation_seconds=1,
            confirmation_seconds=1,
            provider_connect_seconds=1,
            provider_attempt_seconds=1,
        ),
    )
    service = ObservedService(settings, clock=slow_clock)
    app = create_app(settings, identity=service, event_sink=lambda _: None)
    try:
        response = call(app, settings, "POST", "/api/v1/identity/bootstrap", body=ACK)
        assert entered.is_set() and not finished.is_set()
        assert response.status_code == 504 and "set-cookie" not in response.headers
        error = response.json()["error"]
        assert error["code"] == "INTERNAL_ERROR" and error["outcome_state"] == "unresolved"
        assert error["operation_key"] is None
    finally:
        release.set()
        assert finished.wait(2)
    after = snapshot(harness.store)
    assert len(after["owners"]) == len(after["owner_credentials"]) == 1
    anonymous = call(app, settings, "GET", "/api/v1/identity")
    assert anonymous.json()["data"]["state"] == "anonymous"
    assert snapshot(harness.store) == after
