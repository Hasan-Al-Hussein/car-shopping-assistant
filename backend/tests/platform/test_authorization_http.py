"""BE09 isolated test-only HTTP adapters; real BE10 routes have separate domain tests."""

from typing import Annotated

import pytest
from fastapi import Depends

from app.api.dependencies import (
    DeleteCommandHeaders,
    delete_command_headers,
    private_read,
    private_write,
)
from app.api.schemas.common import InventoryRef
from app.api.schemas.sessions import SessionSelectionRequest
from app.identity.authorization import AuthorizedOwnerContext, OwnerUnit
from app.identity.credentials import encode_token
from tests.platform.authorization_cases import (
    AuthorizationHarness,
    ident,
    make_authorization_harness,
    ref,
    token,
)
from tests.platform.test_identity import PRIVATE, call, snapshot


@pytest.fixture
def harness() -> AuthorizationHarness:
    return make_authorization_harness()


def mount_test_adapters(harness: AuthorizationHarness) -> None:
    """Test-local frozen-policy routes; never installed in create_app."""
    # FastAPI may retain included routers as nested branches. Prepend only these
    # isolated admission adapters; real BE10 handlers have their own HTTP suite.
    original_routes = list(harness.app.router.routes)

    @harness.app.get("/api/v1/sessions/{session_id}")
    def read_session(
        session_id: str, context: Annotated[AuthorizedOwnerContext, Depends(private_read)]
    ) -> dict[str, object]:
        return {
            "revision": harness.auth.read(context, lambda unit: unit.session(session_id).revision)
        }

    @harness.app.patch("/api/v1/sessions/{session_id}/selection")
    def write_session(
        session_id: str,
        body: SessionSelectionRequest,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> dict[str, object]:
        def change(unit: OwnerUnit) -> int:
            value = unit.session(session_id)
            value.revision += 1
            return value.revision

        return {"revision": harness.auth.write(context, change)}

    @harness.app.delete("/api/v1/shortlist/{namespace}/{snapshot_id}/{source_id}")
    def delete_membership(
        namespace: str,
        snapshot_id: str,
        source_id: str,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
        command: Annotated[DeleteCommandHeaders, Depends(delete_command_headers)],
    ) -> dict[str, object]:
        def remove(unit: OwnerUnit) -> str:
            row = unit.shortlist(
                InventoryRef(namespace=namespace, snapshot_id=snapshot_id, source_id=source_id)
            )
            unit.db.delete(row)
            return command.client_action_id

        return {"action": harness.auth.write(context, remove)}

    adapters = harness.app.router.routes[len(original_routes) :]
    harness.app.router.routes[:] = [*adapters, *original_routes]


def private_headers(harness: AuthorizationHarness) -> dict[str, str | None]:
    return {
        "X-Identity-Context": ident("context"),
        "X-CSRF-Token": harness.csrf(),
        "Origin": "http://127.0.0.1:5173",
    }


def test_private_http_positive_and_owner_absent_equivalence(harness: AuthorizationHarness) -> None:
    mount_test_adapters(harness)
    headers = {"X-Identity-Context": ident("context")}
    for target, status in (
        (ident("session"), 200),
        (ident("session", "b"), 404),
        (ident("absent"), 404),
    ):
        response = call(
            harness.app,
            harness.settings,
            "GET",
            "/api/v1/sessions/" + target,
            cookie=encode_token(token("a")),
            overrides=headers,
        )
        assert response.status_code == status
        if status == 404:
            assert response.json()["error"]["code"] == "NOT_FOUND"
            assert "set-cookie" not in response.headers
            assert target not in response.text
    denied = call(
        harness.app,
        harness.settings,
        "GET",
        "/api/v1/sessions/" + ident("session"),
        overrides=headers,
    )
    assert denied.status_code == 401


def test_json_mutation_positive_extra_owner_fields_and_wrong_cookie_pairing(
    harness: AuthorizationHarness,
) -> None:
    mount_test_adapters(harness)
    path = "/api/v1/sessions/" + ident("session") + "/selection"
    body = {
        "expected_revision": 0,
        "client_action_id": ident("selection-action"),
        "selected_ref": ref().model_dump(),
    }
    before = snapshot(harness.store)
    for payload in ({**body, "owner_id": PRIVATE}, {**body, "admin": True}):
        rejected = call(
            harness.app,
            harness.settings,
            "PATCH",
            path,
            cookie=encode_token(token("a")),
            overrides=private_headers(harness),
            body=payload,
        )
        assert rejected.status_code == 422
        assert PRIVATE not in rejected.text
        assert snapshot(harness.store) == before
    paired = call(
        harness.app,
        harness.settings,
        "PATCH",
        path,
        cookie=encode_token(token("b")),
        overrides=private_headers(harness),
        body=body,
    )
    assert paired.status_code == 401
    assert snapshot(harness.store) == before
    wrong_content = call(
        harness.app,
        harness.settings,
        "PATCH",
        path,
        cookie=encode_token(token("a")),
        overrides={**private_headers(harness), "Content-Type": "text/plain"},
        content=b"{}",
    )
    assert wrong_content.status_code == 415
    assert snapshot(harness.store) == before
    accepted = call(
        harness.app,
        harness.settings,
        "PATCH",
        path,
        cookie=encode_token(token("a")),
        overrides=private_headers(harness),
        body=body,
    )
    assert accepted.status_code == 200
    assert accepted.json()["revision"] == 1
    assert (
        harness.auth.read(
            harness.context("b"), lambda unit: unit.session(ident("session", "b")).revision
        )
        == 0
    )


@pytest.mark.parametrize("cookie_mode", ["missing", "malformed", "duplicate", "two_headers"])
def test_private_get_cookie_denials_do_not_clear_or_write(
    harness: AuthorizationHarness, cookie_mode: str
) -> None:
    mount_test_adapters(harness)
    headers: dict[str, str | None] = {"X-Identity-Context": ident("context")}
    cookie = (
        None
        if cookie_mode == "missing"
        else PRIVATE
        if cookie_mode == "malformed"
        else encode_token(token("a"))
    )
    extra = None
    if cookie_mode == "duplicate":
        headers["Cookie"] = (
            harness.settings.cookie_name
            + "="
            + str(cookie)
            + "; "
            + harness.settings.cookie_name
            + "="
            + encode_token(token("b"))
        )
    elif cookie_mode == "two_headers":
        extra = [("Cookie", harness.settings.cookie_name + "=" + str(cookie))]
    before = snapshot(harness.store)
    response = call(
        harness.app,
        harness.settings,
        "GET",
        "/api/v1/sessions/" + ident("session"),
        cookie=cookie,
        overrides=headers,
        extra_headers=extra,
    )
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert PRIVATE not in response.text
    assert snapshot(harness.store) == before


@pytest.mark.parametrize(
    "header,value,status",
    [
        ("Origin", None, 403),
        ("Origin", "null", 403),
        ("Origin", "https://outside.example", 403),
        ("Host", "outside.example", 400),
        ("Host", "localhost:8000", 400),
        ("X-Identity-Context", None, 422),
        ("X-Identity-Context", PRIVATE, 422),
        ("X-Identity-Context", ident("context", "b"), 401),
        ("X-CSRF-Token", None, 422),
        ("X-CSRF-Token", PRIVATE, 422),
        ("X-CSRF-Token", "z" * 43, 403),
        ("X-Client-Action-ID", None, 422),
        ("X-Client-Action-ID", PRIVATE, 422),
        ("X-Expected-Revision", None, 422),
        ("X-Expected-Revision", "-1", 422),
        ("X-Expected-Revision", "2147483648", 422),
    ],
)
def test_bodyless_delete_required_security_and_command_headers(
    harness: AuthorizationHarness, header: str, value: str | None, status: int
) -> None:
    mount_test_adapters(harness)
    headers = {
        **private_headers(harness),
        "X-Client-Action-ID": ident("delete-action"),
        "X-Expected-Revision": "0",
    }
    headers[header] = value
    before = snapshot(harness.store)
    response = call(
        harness.app,
        harness.settings,
        "DELETE",
        "/api/v1/shortlist/provided-cars-cleaned/" + "1" * 64 + "/12",
        cookie=encode_token(token("a")),
        overrides=headers,
    )
    assert response.status_code == status
    assert PRIVATE not in response.text
    assert "set-cookie" not in response.headers
    assert snapshot(harness.store) == before


@pytest.mark.parametrize(
    "header",
    [
        "Origin",
        "Host",
        "X-Identity-Context",
        "X-CSRF-Token",
        "X-Client-Action-ID",
        "X-Expected-Revision",
    ],
)
def test_duplicate_security_headers_are_not_selected(
    harness: AuthorizationHarness, header: str
) -> None:
    mount_test_adapters(harness)
    headers = {
        **private_headers(harness),
        "Host": "127.0.0.1:8000",
        "X-Client-Action-ID": ident("delete-action"),
        "X-Expected-Revision": "0",
    }
    before = snapshot(harness.store)
    response = call(
        harness.app,
        harness.settings,
        "DELETE",
        "/api/v1/shortlist/provided-cars-cleaned/" + "1" * 64 + "/12",
        cookie=encode_token(token("a")),
        overrides=headers,
        extra_headers=[(header, str(headers[header]))],
    )
    assert response.status_code == 422
    assert snapshot(harness.store) == before


def test_bodyless_delete_positive_control_and_body_rejection(harness: AuthorizationHarness) -> None:
    mount_test_adapters(harness)
    headers = {
        **private_headers(harness),
        "X-Client-Action-ID": ident("delete-action"),
        "X-Expected-Revision": "0",
    }
    path = "/api/v1/shortlist/provided-cars-cleaned/" + "1" * 64 + "/12"
    before = snapshot(harness.store)
    denied = call(
        harness.app,
        harness.settings,
        "DELETE",
        path,
        cookie=encode_token(token("a")),
        overrides=headers,
        body={"owner_id": PRIVATE},
    )
    assert denied.status_code == 422
    assert snapshot(harness.store) == before
    allowed = call(
        harness.app,
        harness.settings,
        "DELETE",
        path,
        cookie=encode_token(token("a")),
        overrides=headers,
    )
    assert allowed.status_code == 200
    assert allowed.json()["action"] == ident("delete-action")
    assert harness.auth.read(harness.context(), lambda unit: len(unit.shortlist_memberships())) == 0
    assert (
        harness.auth.read(harness.context("b"), lambda unit: len(unit.shortlist_memberships())) == 1
    )
