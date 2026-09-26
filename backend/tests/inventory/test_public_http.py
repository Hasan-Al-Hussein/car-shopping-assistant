"""Owned routers in an explicit test app; production main remains untouched."""

from uuid import uuid4

from app.core.config import load_settings
from app.database.store import Store
from app.inventory.router import inventory_router
from app.inventory.staging_plan import PreparedStage
from app.main import create_app
from tests.inventory.public_cases import public_harness
from tests.platform.test_identity import call


def test_real_public_http_has_no_owner_side_effects_and_exact_contract(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    settings = load_settings()
    app = create_app(settings, event_sink=lambda event: None)
    app.include_router(inventory_router(harness.search, harness.details))
    before = inventory_store.path.read_bytes()
    found = call(
        app,
        settings,
        "POST",
        "/api/v1/inventory/search",
        body={
            "client_request_id": str(uuid4()),
            "filters": {"models": ["3"]},
        },
    )
    assert found.status_code == 200
    data = found.json()["data"]
    assert [item["ref"]["source_id"] for item in data["items"]] == ["12"]
    ref = data["items"][0]["ref"]
    path = "/api/v1/listings/" + "/".join(
        ref[name] for name in ("namespace", "snapshot_id", "source_id")
    )
    detail = call(app, settings, "GET", path)
    assert detail.status_code == 200 and detail.json()["data"]["state"] == "current"
    assert detail.json()["data"]["listing"] == data["items"][0]
    bad = call(app, settings, "POST", "/api/v1/comparisons", body={"refs": [ref] * 4})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"
    missing = call(app, settings, "GET", path.rsplit("/", 1)[0] + "/missing")
    assert missing.status_code == 200 and missing.json()["data"]["state"] == "missing"
    assert inventory_store.path.read_bytes() == before
    for operation in (found, detail, bad, missing):
        assert "set-cookie" not in operation.headers
