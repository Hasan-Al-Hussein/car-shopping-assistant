"""Schema-only F-02 proof. These checks do not exercise identity or commits."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.api.schemas.identity import IdentityBootstrapRequest
from app.api.schemas.inventory import BudgetRange, ComparisonRequest, SearchRequest
from app.api.schemas.leads import ContactValue, ExportCurrent
from app.api.schemas.memory import MembershipRequest, PreferencesUpdate
from app.api.schemas.operations import OperationStatus
from app.api.schemas.routes import ROUTES, create_contract_app
from app.api.schemas.sessions import MessageRequest
from app.api.schemas.viewings import ConfirmRequest

PROJECT = Path(__file__).resolve().parents[3]
CASES = json.loads((PROJECT / "contracts/fixtures/cases.json").read_text(encoding="utf-8"))
MODELS: dict[str, Any] = {
    "IdentityBootstrapRequest": IdentityBootstrapRequest,
    "BudgetRange": BudgetRange,
    "SearchRequest": SearchRequest,
    "PreferencesUpdate": PreferencesUpdate,
    "MembershipRequest": MembershipRequest,
    "ConfirmRequest": ConfirmRequest,
    "OperationStatus": OperationStatus,
    "ExportCurrent": ExportCurrent,
    "ContactValue": ContactValue,
}


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_contract_fixture(case: dict[str, Any]) -> None:
    adapter = TypeAdapter(MODELS[case["model"]])
    payload = json.dumps(case["payload"])
    if case["valid"]:
        adapter.validate_json(payload)
    else:
        with pytest.raises(ValidationError) as raised:
            adapter.validate_json(payload)
        expected = case["expected_error"]
        assert any(
            list(error["loc"]) == expected["loc"] and error["type"] == expected["type"]
            for error in raised.value.errors()
        ), raised.value.errors()


def test_message_codepoint_boundary_and_excess() -> None:
    request = {
        "client_message_id": "00000000-0000-4000-8000-000000000001",
        "expected_revision": 0,
        "text": "🚗" * 4000,
    }
    MessageRequest.model_validate(request)
    with pytest.raises(ValidationError):
        MessageRequest.model_validate({**request, "text": "🚗" * 4001})


def test_comparison_rejects_duplicate_ref_and_fourth_car() -> None:
    refs = [
        {"namespace": "synthetic", "snapshot_id": "a" * 64, "source_id": str(index)}
        for index in range(4)
    ]
    ComparisonRequest(refs=refs[:3])
    for invalid in (refs, [refs[0], refs[0]]):
        with pytest.raises(ValidationError):
            ComparisonRequest(refs=invalid)


def test_route_catalog_has_unique_names_and_no_get_mutations() -> None:
    assert len({route.operation_id for route in ROUTES}) == len(ROUTES)
    assert not any(route.mutates for route in ROUTES if route.method == "GET")
    assert not next(route for route in ROUTES if route.operation_id == "search_inventory").mutates
    assert not next(route for route in ROUTES if route.operation_id == "compare_listings").mutates


def test_private_routes_document_cookie_context_and_mutation_csrf() -> None:
    schema = create_contract_app().openapi()
    for route in ROUTES:
        operation = schema["paths"]["/api/v1" + route.path][route.method.lower()]
        headers = {
            item["name"] for item in operation.get("parameters", []) if item["in"] == "header"
        }
        if route.private:
            assert operation["security"] == [{"OwnerCookie": []}]
            assert "X-Identity-Context" in headers
        if route.private and route.mutates:
            assert "X-CSRF-Token" in headers
        if route.mutates:
            assert "Origin" in headers
