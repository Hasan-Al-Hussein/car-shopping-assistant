"""Owned unmounted adapters exercised only in an explicit synthetic test app."""

from uuid import uuid4

import pytest

from app.memory.router import preference_router
from app.shortlist.router import shortlist_router
from tests.platform.memory_shortlist_cases import MemoryHarness, make_memory_harness
from tests.platform.session_cases import ref
from tests.platform.test_identity import call, snapshot
from tests.platform.test_preferences import remember
from tests.platform.test_sessions_http import headers


@pytest.fixture
def harness() -> MemoryHarness:
    result = make_memory_harness()
    result.base.app.include_router(preference_router(result.preferences))
    result.base.app.include_router(shortlist_router(result.shortlist))
    return result


def test_actual_preferences_patch_get_and_cross_owner(harness: MemoryHarness) -> None:
    base = harness.base
    session = base.create()
    body = remember(session.session_id).model_dump(mode="json")
    saved = call(
        base.app,
        base.settings,
        "PATCH",
        "/api/v1/preferences",
        body=body,
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    assert saved.status_code == 200 and saved.json()["data"]["revision"] == 1
    assert saved.json()["meta"]["entity_revision"] == 1
    before = snapshot(base.store)
    replay = call(
        base.app,
        base.settings,
        "PATCH",
        "/api/v1/preferences",
        body=body,
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    assert replay.json()["data"] == saved.json()["data"]
    observed = call(
        base.app,
        base.settings,
        "GET",
        "/api/v1/preferences",
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    foreign = call(
        base.app,
        base.settings,
        "GET",
        "/api/v1/preferences",
        cookie=base.buyers[1].cookie,
        overrides=headers(base, 1),
    )
    assert (
        observed.json()["data"] == saved.json()["data"] and foreign.json()["data"]["entries"] == []
    )
    assert snapshot(base.store) == before


def test_actual_shortlist_put_delete_headers_replay_and_owner(harness: MemoryHarness) -> None:
    base = harness.base
    path = "/api/v1/shortlist/" + "/".join((ref().namespace, ref().snapshot_id, ref().source_id))
    body = {"client_action_id": str(uuid4()), "expected_revision": 0}
    saved = call(
        base.app,
        base.settings,
        "PUT",
        path,
        body=body,
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    assert saved.status_code == 200 and saved.json()["data"]["saved"]
    observed = call(
        base.app,
        base.settings,
        "GET",
        "/api/v1/shortlist?page_size=1",
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    assert observed.status_code == 200 and observed.json()["data"]["total"] == 1
    foreign = call(
        base.app,
        base.settings,
        "GET",
        "/api/v1/shortlist",
        cookie=base.buyers[1].cookie,
        overrides=headers(base, 1),
    )
    assert foreign.json()["data"]["items"] == []
    missing = call(
        base.app,
        base.settings,
        "DELETE",
        path,
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    assert missing.status_code == 422
    remove_headers = {
        **headers(base),
        "X-Client-Action-ID": str(uuid4()),
        "X-Expected-Revision": "1",
    }
    removed = call(
        base.app,
        base.settings,
        "DELETE",
        path,
        cookie=base.buyers[0].cookie,
        overrides=remove_headers,
    )
    assert removed.status_code == 200 and not removed.json()["data"]["saved"]
    replay = call(
        base.app,
        base.settings,
        "PUT",
        path,
        body=body,
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    assert replay.json()["data"]["replayed"] and not replay.json()["data"]["saved"]
    assert (
        replay.json()["data"]["applied_revision"] == 1
        and replay.json()["meta"]["entity_revision"] == 2
    )


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
@pytest.mark.parametrize("segment", [0, 1, 2])
def test_malformed_path_is_validation_denial_not_internal_error(
    harness: MemoryHarness, method: str, segment: int
) -> None:
    base = harness.base
    parts = [ref().namespace, ref().snapshot_id, ref().source_id]
    parts[segment] = "INVALID!"
    path = "/api/v1/shortlist/" + "/".join(parts)
    overrides = {**headers(base), "X-Client-Action-ID": str(uuid4()), "X-Expected-Revision": "0"}
    body = {"client_action_id": str(uuid4()), "expected_revision": 0} if method == "PUT" else None
    before = snapshot(base.store)
    response = call(
        base.app,
        base.settings,
        method,
        path,
        body=body,
        cookie=base.buyers[0].cookie,
        overrides=overrides,
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert snapshot(base.store) == before


@pytest.mark.parametrize("path", ["/api/v1/preferences", "/api/v1/shortlist"])
def test_private_reads_require_owner_context(harness: MemoryHarness, path: str) -> None:
    base = harness.base
    before = snapshot(base.store)
    response = call(base.app, base.settings, "GET", path, overrides=headers(base))
    assert response.status_code == 401
    assert snapshot(base.store) == before


@pytest.mark.parametrize("variant", ["csrf", "origin", "extra_owner", "one_off"])
def test_preference_mutation_denials_leave_state_unchanged(
    harness: MemoryHarness, variant: str
) -> None:
    base = harness.base
    session = base.create()
    body = remember(session.session_id).model_dump(mode="json")
    overrides = headers(base)
    expected = 422
    if variant == "csrf":
        overrides["X-CSRF-Token"] = "x" * 43
        expected = 403
    elif variant == "origin":
        overrides["Origin"] = "https://untrusted.invalid"
        expected = 403
    elif variant == "extra_owner":
        body["owner_id"] = str(uuid4())
    else:
        body["scope"] = "session"
    before = snapshot(base.store)
    response = call(
        base.app,
        base.settings,
        "PATCH",
        "/api/v1/preferences",
        body=body,
        cookie=base.buyers[0].cookie,
        overrides=overrides,
    )
    assert response.status_code == expected
    assert snapshot(base.store) == before


@pytest.mark.parametrize("query", ["page_size=0", "page_size=51", "cursor=invalid"])
def test_shortlist_page_contract_validation(harness: MemoryHarness, query: str) -> None:
    base = harness.base
    response = call(
        base.app,
        base.settings,
        "GET",
        "/api/v1/shortlist?" + query,
        cookie=base.buyers[0].cookie,
        overrides=headers(base),
    )
    assert response.status_code == 422
