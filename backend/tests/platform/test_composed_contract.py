"""Missing BE-25 composition proof sources. No executed result is implied."""

import copy
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.api.schemas.routes import ROUTES, RouteContract, create_contract_app
from app.database.store import Store
from app.runtime_app import build_composition
from tests.platform.composed_contract_cases import assert_wire_contract, operations, same_json, schema_shape
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import settings_for
from tests.platform.test_identity import call
from tests.support.harness import PROJECT, configured_runtime_boundary


def frozen_contract() -> dict[str, Any]:
    value = json.loads((PROJECT / "contracts/v1/openapi.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def descriptor(path: Path) -> Store:
    return Store(path, str(uuid4()), schema_version="0002", inventory_mode="fts5",
                 boundary=configured_runtime_boundary())


def test_current_catalog_matches_frozen_wire_contract() -> None:
    assert_wire_contract(create_contract_app().openapi(), frozen_contract())


def test_actual_composed_openapi_matches_frozen_wire_contract(runtime_path: Path) -> None:
    composition = build_composition(settings_for(runtime_path), descriptor(runtime_path),
                                    event_sink=lambda event: None)
    try:
        actual = composition.app.openapi()
        assert all(route.get("x-implementation") != "contract-only" for route in operations(actual).values())
        assert_wire_contract(actual, frozen_contract())
        assert not runtime_path.parent.exists()
    finally:
        assert composition.close()


@pytest.mark.parametrize("damage", ["response_status", "required_header", "property_constraint"])
def test_comparison_canary_rejects_material_contract_drift(damage: str) -> None:
    expected = frozen_contract()
    candidate = copy.deepcopy(expected)
    if damage == "response_status":
        del candidate["paths"]["/api/v1/health"]["get"]["responses"]["503"]
    elif damage == "required_header":
        candidate["paths"]["/api/v1/sessions"]["post"]["parameters"] = []
    else:
        candidate["components"]["schemas"]["MessageRequest"]["properties"]["text"]["maxLength"] = 1
    with pytest.raises(AssertionError):
        assert_wire_contract(candidate, expected)


def test_schema_annotation_normalization_never_drops_a_property_named_title() -> None:
    original = {"type": "object", "title": "Display annotation", "properties": {
        "title": {"type": "string", "maxLength": 80, "description": "Display annotation"},
    }}
    assert schema_shape(original) == {"type": "object", "properties": {
        "title": {"type": "string", "maxLength": 80},
    }}


@pytest.mark.parametrize("keyword", ["const", "enum", "default"])
def test_schema_comparison_preserves_literal_annotation_names(keyword: str) -> None:
    left: Any = {"title": "left", "description": "literal", "examples": [1]}
    right: Any = {"title": "right", "description": "literal", "examples": [1]}
    if keyword == "enum":
        left, right = [left], [right]
    assert schema_shape({keyword: left}) != schema_shape({keyword: right})


def test_public_security_equivalence_never_ignores_inherited_authorization() -> None:
    expected = frozen_contract()
    candidate = copy.deepcopy(expected)
    candidate["paths"]["/api/v1/health"]["get"].pop("security", None)
    assert_wire_contract(candidate, expected)
    candidate["security"] = [{"OwnerCookie": []}]
    with pytest.raises(AssertionError):
        assert_wire_contract(candidate, expected)


def test_json_equality_preserves_boolean_and_numeric_types() -> None:
    assert not same_json({"const": False}, {"const": 0})


def concrete_path(contract: RouteContract) -> str:
    path = "/api/v1" + contract.path
    for part in contract.path.split("/"):
        if part.startswith("{"):
            name = part[1:-1]
            replacement = {"namespace": "synthetic", "snapshot_id": "a" * 64,
                           "source_id": "12", "operation_key": "b" * 32}.get(name, str(uuid4()))
            path = path.replace(part, replacement)
    return path


@pytest.mark.parametrize("contract", ROUTES, ids=[item.operation_id for item in ROUTES])
def test_every_composed_route_rejects_bad_host_before_any_store_unit(
    runtime_path: Path, monkeypatch: pytest.MonkeyPatch, contract: RouteContract,
) -> None:
    composition = build_composition(settings_for(runtime_path), descriptor(runtime_path),
                                    event_sink=lambda event: None)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("BAD_HOST_REACHED_STORE_UNIT")

    try:
        monkeypatch.setattr(Store, "read", forbidden)
        monkeypatch.setattr(Store, "write", forbidden)
        response = call(composition.app, composition.settings, contract.method,
                        concrete_path(contract), overrides={"Host": "untrusted.example"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "HOST_DENIED"
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"
        assert not runtime_path.parent.exists()
    finally:
        assert composition.close()


@pytest.mark.parametrize("contract", [item for item in ROUTES if item.mutates],
                         ids=[item.operation_id for item in ROUTES if item.mutates])
def test_every_composed_mutation_rejects_bad_origin_before_any_store_unit(
    runtime_path: Path, monkeypatch: pytest.MonkeyPatch, contract: RouteContract,
) -> None:
    composition = build_composition(settings_for(runtime_path), descriptor(runtime_path),
                                    event_sink=lambda event: None)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("BAD_ORIGIN_REACHED_STORE_UNIT")

    try:
        monkeypatch.setattr(Store, "read", forbidden)
        monkeypatch.setattr(Store, "write", forbidden)
        response = call(composition.app, composition.settings, contract.method,
                        concrete_path(contract), overrides={"Origin": "https://untrusted.example"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ORIGIN_DENIED"
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"
        assert not runtime_path.parent.exists()
    finally:
        assert composition.close()
