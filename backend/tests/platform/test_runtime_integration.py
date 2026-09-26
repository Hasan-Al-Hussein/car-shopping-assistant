"""Real composed HTTP/services on disposable stores; authored, not runtime evidence."""

from dataclasses import dataclass
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.schemas.inventory import PresentationProof, SearchRequest
from app.core.errors import ApiFailure
from app.database.models import InventorySnapshotPayload, StoreMetadata
from app.database.store import Store, StoreError
from app.runtime_app import ApplicationComposition, create_runtime_app
from tests.inventory.conftest import snapshot_candidate as snapshot_candidate
from tests.platform.runtime_cases import ACCEPTED_SNAPSHOT
from tests.platform.runtime_cases import active_runtime as active_runtime
from tests.platform.runtime_cases import runtime_clock as runtime_clock
from tests.platform.runtime_cases import runtime_composition as runtime_composition
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import runtime_store as runtime_store
from tests.platform.test_identity import ACK, call
from tests.platform.test_preferences import remember
from tests.support.harness import FrozenClock


@dataclass(frozen=True, repr=False)
class Buyer:
    cookie: str
    context: str
    csrf: str

    def headers(self) -> dict[str, str]:
        return {
            "Origin": "http://127.0.0.1:5173",
            "X-Identity-Context": self.context,
            "X-CSRF-Token": self.csrf,
        }


def buyer(composition: ApplicationComposition) -> Buyer:
    response = call(
        composition.app, composition.settings, "POST", "/api/v1/identity/bootstrap", body=ACK
    )
    assert response.status_code == 201
    cookies: SimpleCookie = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    data = response.json()["data"]
    return Buyer(
        cookies[composition.settings.cookie_name].value, data["context_id"], data["csrf_token"]
    )


def private(
    composition: ApplicationComposition,
    actor: Buyer,
    method: str,
    path: str,
    *,
    body: object | None = None,
    extra: dict[str, str] | None = None,
) -> httpx.Response:
    return call(
        composition.app,
        composition.settings,
        method,
        path,
        cookie=actor.cookie,
        body=body,
        overrides={**actor.headers(), **(extra or {})},
    )


def session(composition: ApplicationComposition, actor: Buyer) -> dict[str, Any]:
    response = private(
        composition,
        actor,
        "POST",
        "/api/v1/sessions",
        body={"client_action_id": str(uuid4())},
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json()["data"])


def search(composition: ApplicationComposition, **criteria: object) -> dict[str, Any]:
    response = call(
        composition.app,
        composition.settings,
        "POST",
        "/api/v1/inventory/search",
        body={"client_request_id": str(uuid4()), **criteria},
    )
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    return cast(dict[str, Any], response.json()["data"])


def test_exact_100_public_navigation_is_read_only(active_runtime: ApplicationComposition) -> None:
    composition = active_runtime
    before = composition.store.path.read_bytes()
    first = search(composition, page_size=50)
    second = search(composition, page_size=50, cursor=first["next_cursor"])
    items = first["items"] + second["items"]
    assert [item["ref"]["source_id"] for item in items] == sorted(str(i) for i in range(1, 101))
    assert first["supported_total"] == second["supported_total"] == 100
    assert second["next_cursor"] is None
    assert {item["ref"]["snapshot_id"] for item in items} == {ACCEPTED_SNAPSHOT}
    refs = [items[0]["ref"], items[1]["ref"]]
    path = "/api/v1/listings/" + "/".join(
        refs[0][key] for key in ("namespace", "snapshot_id", "source_id")
    )
    detail = call(composition.app, composition.settings, "GET", path)
    compared = call(
        composition.app, composition.settings, "POST", "/api/v1/comparisons", body={"refs": refs}
    )
    assert detail.status_code == compared.status_code == 200
    assert detail.json()["data"]["listing"]["ref"] == refs[0]
    assert detail.json()["data"]["eligibility"] == "configuration_missing"
    assert [item["listing"]["ref"] for item in compared.json()["data"]["items"]] == refs
    health = call(composition.app, composition.settings, "GET", "/api/v1/health")
    config = call(composition.app, composition.settings, "GET", "/api/v1/config")
    identity = call(composition.app, composition.settings, "GET", "/api/v1/identity")
    assert health.json()["data"]["active_snapshot_id"] == ACCEPTED_SNAPSHOT
    assert health.json()["data"]["inventory"]["state"] in {"ready", "degraded"}
    assert all(
        health.json()["data"][name]["state"] == "unconfigured" for name in ("assistant", "viewing")
    )
    assert health.json()["data"]["export"]["state"] == "degraded"
    assert identity.json()["data"]["state"] == "anonymous"
    assert all(
        "set-cookie" not in response.headers
        for response in (detail, compared, health, config, identity)
    )
    # Expected IDs are independently recorded in fixtures/inventory/search-expected.json.
    filtered = search(composition, filters={"makes": ["  FoRd  "]})
    assert [item["ref"]["source_id"] for item in filtered["items"]] == ["1", "20", "53", "55", "62"]
    empty = search(composition, filters={"makes": ["not-a-real-make"]})
    assert empty["state"] == "no_supported_matches" and empty["items"] == []
    assert empty["supported_total"] == 0 and empty["constraints_relaxed"] is False
    assert composition.store.path.read_bytes() == before


def test_search_proof_registers_and_selects_using_common_clock(
    active_runtime: ApplicationComposition,
    runtime_clock: FrozenClock,
) -> None:
    composition = active_runtime
    found = search(composition, page_size=2)
    proof = PresentationProof.model_validate(found["presentation"])
    assert datetime.fromisoformat(proof.issued_at) == runtime_clock.now()
    actor = buyer(composition)
    created = session(composition, actor)
    base = "/api/v1/sessions/" + created["session_id"]
    registered = private(
        composition,
        actor,
        "POST",
        base + "/presentations",
        body={
            "client_action_id": str(uuid4()),
            "expected_revision": 0,
            "presentation": found["presentation"],
        },
    )
    assert registered.status_code == 200
    saved = registered.json()["data"]
    selected = private(
        composition,
        actor,
        "PATCH",
        base + "/selection",
        body={
            "client_action_id": str(uuid4()),
            "expected_revision": saved["revision"],
            "selected_ref": found["items"][1]["ref"],
            "presentation_id": saved["active_presentation_id"],
        },
    )
    assert selected.status_code == 200
    assert selected.json()["data"]["selected_ref"] == found["items"][1]["ref"]
    before = composition.store.path.read_bytes()
    observed = private(composition, actor, "GET", base)
    transcript = private(composition, actor, "GET", base + "/messages")
    assert observed.json()["data"] == selected.json()["data"] and transcript.status_code == 200
    assert composition.store.path.read_bytes() == before


def test_new_session_and_new_composition_recall_saved_preferences(
    runtime_composition: ApplicationComposition,
) -> None:
    composition = runtime_composition
    actor = buyer(composition)
    created = session(composition, actor)
    saved = private(
        composition,
        actor,
        "PATCH",
        "/api/v1/preferences",
        body=remember(created["session_id"]).model_dump(mode="json"),
    )
    assert saved.status_code == 200
    assert session(composition, actor)["recalled_preferences"] == saved.json()["data"]
    composition.close()
    app = create_runtime_app(
        composition.settings, clock=composition.clock, event_sink=lambda event: None
    )
    replacement = cast(ApplicationComposition, app.state.composition)
    try:
        recalled = session(replacement, actor)
        assert recalled["session_id"] != created["session_id"]
        assert recalled["recalled_preferences"] == saved.json()["data"]
        assert replacement.signer is not composition.signer
    finally:
        replacement.close()


def test_private_isolation_csrf_and_revision_denials_preserve_state(
    runtime_composition: ApplicationComposition,
) -> None:
    composition = runtime_composition
    actor, foreign = buyer(composition), buyer(composition)
    created = session(composition, actor)
    command = remember(created["session_id"]).model_dump(mode="json")
    before = composition.store.path.read_bytes()
    denied_csrf = private(
        composition,
        actor,
        "PATCH",
        "/api/v1/preferences",
        body=command,
        extra={"X-CSRF-Token": "x" * 43},
    )
    denied_origin = private(
        composition,
        actor,
        "PATCH",
        "/api/v1/preferences",
        body=command,
        extra={"Origin": "https://untrusted.invalid"},
    )
    wrong_owner = private(composition, foreign, "PATCH", "/api/v1/preferences", body=command)
    hidden = private(composition, foreign, "GET", "/api/v1/sessions/" + created["session_id"])
    missing_header = call(composition.app, composition.settings, "GET", "/api/v1/preferences")
    anonymous = call(
        composition.app,
        composition.settings,
        "GET",
        "/api/v1/preferences",
        extra_headers=[("X-Identity-Context", str(uuid4()))],
    )
    assert missing_header.status_code == 422
    assert denied_csrf.status_code == denied_origin.status_code == 403
    assert wrong_owner.status_code == hidden.status_code == 404
    assert anonymous.status_code == 401
    assert composition.store.path.read_bytes() == before
    saved = private(composition, actor, "PATCH", "/api/v1/preferences", body=command)
    assert saved.status_code == 200
    before = composition.store.path.read_bytes()
    stale = private(
        composition,
        actor,
        "PATCH",
        "/api/v1/preferences",
        body=remember(created["session_id"]).model_dump(mode="json"),
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REVISION_CONFLICT"
    foreign_preferences = private(composition, foreign, "GET", "/api/v1/preferences")
    assert foreign_preferences.json()["data"]["entries"] == []
    assert composition.store.path.read_bytes() == before


def test_shortlist_survives_new_composition_and_replays_after_removal(
    active_runtime: ApplicationComposition,
) -> None:
    composition = active_runtime
    actor, foreign = buyer(composition), buyer(composition)
    ref = search(composition, page_size=1)["items"][0]["ref"]
    path = "/api/v1/shortlist/" + "/".join(
        ref[key] for key in ("namespace", "snapshot_id", "source_id")
    )
    command = {"client_action_id": str(uuid4()), "expected_revision": 0}
    saved = private(composition, actor, "PUT", path, body=command)
    assert saved.status_code == 200 and saved.json()["data"]["saved"]
    assert private(composition, foreign, "GET", "/api/v1/shortlist").json()["data"]["items"] == []
    composition.close()
    app = create_runtime_app(
        composition.settings, clock=composition.clock, event_sink=lambda event: None
    )
    replacement = cast(ApplicationComposition, app.state.composition)
    try:
        before = replacement.store.path.read_bytes()
        observed = private(replacement, actor, "GET", "/api/v1/shortlist")
        assert observed.status_code == 200 and observed.json()["data"]["total"] == 1
        assert replacement.store.path.read_bytes() == before
        removed = private(
            replacement,
            actor,
            "DELETE",
            path,
            extra={"X-Client-Action-ID": str(uuid4()), "X-Expected-Revision": "1"},
        )
        assert removed.status_code == 200 and not removed.json()["data"]["saved"]
        replay = private(replacement, actor, "PUT", path, body=command)
        assert replay.json()["data"]["replayed"] and not replay.json()["data"]["saved"]
    finally:
        replacement.close()


def test_expired_or_different_composition_proof_cannot_register(
    active_runtime: ApplicationComposition,
    runtime_clock: FrozenClock,
) -> None:
    composition = active_runtime
    found = composition.search.search(SearchRequest(client_request_id=str(uuid4()), page_size=1))
    proof = found.presentation
    app = create_runtime_app(
        composition.settings, clock=composition.clock, event_sink=lambda event: None
    )
    other = cast(ApplicationComposition, app.state.composition)
    try:
        with pytest.raises(ApiFailure, match="PRESENTATION_INVALID"):
            other.signer.verify_presentation(proof, now=runtime_clock.now())
    finally:
        other.close()
    actor = buyer(composition)
    created = session(composition, actor)
    runtime_clock.advance(1800)
    before = composition.store.path.read_bytes()
    rejected = private(
        composition,
        actor,
        "POST",
        "/api/v1/sessions/" + created["session_id"] + "/presentations",
        body={
            "client_action_id": str(uuid4()),
            "expected_revision": 0,
            "presentation": proof.model_dump(mode="json"),
        },
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "PRESENTATION_INVALID"
    assert composition.store.path.read_bytes() == before


def test_failed_inventory_admission_is_unavailable_not_empty(
    active_runtime: ApplicationComposition,
) -> None:
    composition = active_runtime
    composition.close()

    def corrupt(db: Session) -> None:
        db.execute(update(InventorySnapshotPayload).values(payload_sha256="f" * 64))

    composition.store.write(corrupt)
    app = create_runtime_app(
        composition.settings, clock=composition.clock, event_sink=lambda event: None
    )
    replacement = cast(ApplicationComposition, app.state.composition)
    try:
        health = call(app, composition.settings, "GET", "/api/v1/health")
        assert health.json()["data"]["inventory"]["state"] == "unavailable"
        assert health.json()["data"]["active_snapshot_id"] is None
        before = replacement.store.path.read_bytes()
        response = call(
            app,
            composition.settings,
            "POST",
            "/api/v1/inventory/search",
            body={"client_request_id": str(uuid4())},
        )
        assert response.status_code in {409, 503} and "data" not in response.json()
        assert replacement.store.path.read_bytes() == before
    finally:
        replacement.close()


def test_generation_change_invalidates_health_and_owned_actions(
    runtime_composition: ApplicationComposition,
    runtime_store: Store,
) -> None:
    composition = runtime_composition
    composition.admit_inventory()
    actor = buyer(composition)

    def replace_generation(db: Session) -> None:
        db.execute(update(StoreMetadata).values(store_generation=str(uuid4())))

    runtime_store.write(replace_generation)
    before = runtime_store.path.read_bytes()
    health = call(composition.app, composition.settings, "GET", "/api/v1/health")
    assert health.json()["data"]["store"]["state"] == "unavailable"
    assert health.json()["data"]["inventory"]["state"] == "unavailable"
    assert health.json()["data"]["active_snapshot_id"] is None
    denied = private(
        composition, actor, "POST", "/api/v1/sessions", body={"client_action_id": str(uuid4())}
    )
    assert denied.status_code in {409, 503}
    with pytest.raises(StoreError):
        composition.reader.read_refs(())
    assert runtime_store.path.read_bytes() == before


def test_readiness_observes_manual_reader_invalidation_without_cold_read(
    active_runtime: ApplicationComposition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composition = active_runtime

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("REQUEST_RAN_COLD_ADMISSION")

    monkeypatch.setattr(composition.reader, "refresh", forbidden)
    monkeypatch.setattr(composition.reader, "admit", forbidden)
    composition.reader.invalidate()
    health = call(composition.app, composition.settings, "GET", "/api/v1/health")
    assert health.json()["data"]["inventory"]["state"] == "unavailable"
    response = call(
        composition.app,
        composition.settings,
        "POST",
        "/api/v1/inventory/search",
        body={"client_request_id": str(uuid4())},
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "SNAPSHOT_STALE"
