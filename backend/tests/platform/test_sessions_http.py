"""Actual BE10 routers; no Assistant route or live search is substituted."""

from typing import Any
from uuid import uuid4

import pytest

from app.api.schemas.sessions import MessageRequest
from tests.platform.session_cases import SessionHarness, make_harness, ref
from tests.platform.test_identity import call, snapshot


@pytest.fixture
def harness() -> SessionHarness:
    return make_harness()


def headers(harness: SessionHarness, who: int = 0) -> dict[str, str]:
    identity = harness.buyers[who].identity
    return {
        "X-Identity-Context": identity.context_id,
        "X-CSRF-Token": identity.csrf_token,
        "Origin": "http://127.0.0.1:5173",
    }


def test_real_create_get_transcript_and_lost_response_replay(harness: SessionHarness) -> None:
    body = {"client_action_id": str(uuid4())}
    first = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/sessions",
        body=body,
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
    )
    assert first.status_code == 201
    state = first.json()["data"]
    path = "/api/v1/sessions/" + state["session_id"]
    before = snapshot(harness.store)
    replay = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/sessions",
        body=body,
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
    )
    assert replay.json()["data"] == state
    fetched = call(
        harness.app,
        harness.settings,
        "GET",
        path,
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
    )
    assert fetched.status_code == 200 and fetched.json()["data"] == state
    empty = call(
        harness.app,
        harness.settings,
        "GET",
        path + "/messages",
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
    )
    assert empty.status_code == 200 and empty.json()["data"]["items"] == []
    assert empty.json()["meta"]["identity_context_id"] == harness.buyers[0].identity.context_id
    assert "set-cookie" not in fetched.headers
    assert snapshot(harness.store) == before


@pytest.mark.parametrize("target", ["foreign", "absent"])
def test_real_private_paths_uniform_and_state_unchanged(
    harness: SessionHarness, target: str
) -> None:
    session_id = harness.create(1).session_id if target == "foreign" else str(uuid4())
    path = "/api/v1/sessions/" + session_id
    cases: list[tuple[str, str, dict[str, Any] | None]] = [
        ("GET", path, None),
        ("GET", path + "/messages", None),
        (
            "PATCH",
            path + "/selection",
            {
                "expected_revision": 0,
                "client_action_id": str(uuid4()),
                "selected_ref": ref().model_dump(),
            },
        ),
        (
            "POST",
            path + "/presentations",
            {
                "expected_revision": 0,
                "client_action_id": str(uuid4()),
                "presentation": harness.proof().model_dump(),
            },
        ),
    ]
    before = snapshot(harness.store)
    for method, url, body in cases:
        response = call(
            harness.app,
            harness.settings,
            method,
            url,
            body=body,
            cookie=harness.buyers[0].cookie,
            overrides=headers(harness),
        )
        assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"
    assert snapshot(harness.store) == before


@pytest.mark.parametrize(
    "variant",
    ["missing_cookie", "missing_context", "missing_csrf", "foreign_origin", "extra_owner"],
)
def test_real_create_transport_and_authority_denials(harness: SessionHarness, variant: str) -> None:
    values: dict[str, str | None] = dict(headers(harness))
    body: dict[str, Any] = {"client_action_id": str(uuid4())}
    cookie: str | None = harness.buyers[0].cookie
    if variant == "missing_cookie":
        cookie = None
    elif variant == "missing_context":
        values["X-Identity-Context"] = None
    elif variant == "missing_csrf":
        values["X-CSRF-Token"] = None
    elif variant == "foreign_origin":
        values["Origin"] = "https://example.invalid"
    else:
        body["owner_id"] = str(uuid4())
    before = snapshot(harness.store)
    response = call(
        harness.app,
        harness.settings,
        "POST",
        "/api/v1/sessions",
        body=body,
        cookie=cookie,
        overrides=values,
    )
    assert response.status_code in {401, 403, 422}
    assert "set-cookie" not in response.headers
    assert snapshot(harness.store) == before


def test_real_presentation_selection_and_historical_transcript(harness: SessionHarness) -> None:
    session = harness.create()
    path = "/api/v1/sessions/" + session.session_id
    registered = call(
        harness.app,
        harness.settings,
        "POST",
        path + "/presentations",
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
        body={
            "expected_revision": 0,
            "client_action_id": str(uuid4()),
            "presentation": harness.proof().model_dump(),
        },
    )
    assert registered.status_code == 200
    owned_id = registered.json()["data"]["active_presentation_id"]
    selected = call(
        harness.app,
        harness.settings,
        "PATCH",
        path + "/selection",
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
        body={
            "expected_revision": 1,
            "client_action_id": str(uuid4()),
            "selected_ref": ref().model_dump(),
            "presentation_id": owned_id,
        },
    )
    assert selected.status_code == 200 and selected.json()["data"]["revision"] == 2
    admission = harness.service.begin(
        harness.context(),
        session.session_id,
        MessageRequest(
            client_message_id=str(uuid4()), expected_revision=2, text="Historical synthetic turn"
        ),
    )
    before = snapshot(harness.store)
    transcript = call(
        harness.app,
        harness.settings,
        "GET",
        path + "/messages?page_size=1",
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
    )
    assert transcript.status_code == 200
    item = transcript.json()["data"]["items"][0]
    assert item["message_id"] == admission.message_id and item["historical"] is True
    assert item["state"] == "pending" and item["assistant_result"] is None
    assert snapshot(harness.store) == before


@pytest.mark.parametrize("query", ["page_size=0", "page_size=51", "cursor=bad"])
def test_real_transcript_query_bounds(harness: SessionHarness, query: str) -> None:
    session = harness.create()
    before = snapshot(harness.store)
    response = call(
        harness.app,
        harness.settings,
        "GET",
        f"/api/v1/sessions/{session.session_id}/messages?{query}",
        cookie=harness.buyers[0].cookie,
        overrides=headers(harness),
    )
    assert response.status_code == 422
    assert snapshot(harness.store) == before
