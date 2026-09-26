"""Narrow real-router boundaries; synthetic photo sources never alter the workbook."""

from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI

from app.core.config import Settings, load_settings
from app.database.store import Store
from app.inventory.extraction import ExtractedCandidate, extract_reviewed
from app.inventory.import_reader import WorkbookReadResult
from app.inventory.normalization import normalize_candidate
from app.inventory.router import inventory_router
from app.inventory.staging_plan import PreparedStage, prepare_stage
from app.main import create_app
from tests.inventory.public_cases import public_harness
from tests.platform.test_identity import call


def _app(store: Store, plan: PreparedStage) -> tuple[FastAPI, Settings]:
    harness = public_harness(store, plan)
    settings = load_settings()
    app = create_app(settings, event_sink=lambda event: None)
    app.include_router(inventory_router(harness.search, harness.details))
    return app, settings


@pytest.mark.parametrize("case", ["default-20", "page-51", "clauses-25", "query-1001"])
def test_public_search_request_boundaries(
    inventory_store: Store, snapshot_plan: PreparedStage, case: str
) -> None:
    app, settings = _app(inventory_store, snapshot_plan)
    body: dict[str, Any] = {"client_request_id": str(uuid4())}
    if case == "page-51":
        body["page_size"] = 51
    elif case == "clauses-25":
        # Each list is independently valid; only the combined clause limit fails.
        body["filters"] = {
            "makes": [f"make-{index}" for index in range(12)],
            "models": [f"model-{index}" for index in range(12)],
            "trims": ["trim"],
        }
    elif case == "query-1001":
        # One distinct short token isolates text length from lexical token limits.
        body["query"] = ("x " * 500) + "x"
    before = inventory_store.path.read_bytes()
    response = call(app, settings, "POST", "/api/v1/inventory/search", body=body)
    if case == "default-20":
        assert "page_size" not in body
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["state"] == "matches"
        assert len(data["items"]) == 20 and data["supported_total"] == 100
        assert data["next_cursor"] is not None
        assert data["client_request_id"] == body["client_request_id"]
        assert data["presentation"]["ordered_refs"] == [
            item["ref"] for item in data["items"]
        ]
    else:
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "set-cookie" not in response.headers
    assert inventory_store.path.read_bytes() == before


@pytest.mark.parametrize("segment", ["namespace", "snapshot_id", "source_id"])
def test_public_listing_rejects_malformed_ref(
    inventory_store: Store, snapshot_plan: PreparedStage, segment: str
) -> None:
    app, settings = _app(inventory_store, snapshot_plan)
    ref = snapshot_plan.candidate.manifest.reference("12").model_dump()
    ref[segment] = "INVALID!"
    path = "/api/v1/listings/" + "/".join(
        ref[name] for name in ("namespace", "snapshot_id", "source_id")
    )
    before = inventory_store.path.read_bytes()
    response = call(app, settings, "GET", path)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "set-cookie" not in response.headers
    assert inventory_store.path.read_bytes() == before


def _photo_variant(candidate: ExtractedCandidate) -> ExtractedCandidate:
    """Two explicit synthetic cells, through the existing normalization/extraction path."""
    original = candidate.normalized_source
    synthetic_hash = "c" * 64
    photos = {"12": "", "13": "https://example.invalid/synthetic-blocked-photo"}
    rows = tuple(
        replace(
            item.source,
            cells=tuple(
                replace(cell, value=photos[item.ref.source_id])
                if cell.field == "photo_url" and item.ref.source_id in photos
                else cell
                for cell in item.source.cells
            ),
        )
        for item in original.records
    )
    source = WorkbookReadResult(
        replace(original.source_manifest, workbook_sha256=synthetic_hash),
        replace(
            original.reader_report,
            workbook_sha256_before=synthetic_hash,
            workbook_sha256_after=synthetic_hash,
        ),
        rows,
        original.audit_records,
    )
    catalogue = candidate.catalogue.model_copy(update={"workbook_sha256": synthetic_hash})
    return extract_reviewed(normalize_candidate(source), catalogue)


def test_missing_and_blocked_photos_preserve_public_detail_and_comparison(
    inventory_store: Store, snapshot_candidate: ExtractedCandidate
) -> None:
    candidate = _photo_variant(snapshot_candidate)
    plan = prepare_stage(candidate, policy_version="DEMO-POLICY-1")
    app, settings = _app(inventory_store, plan)
    expected_states = {"12": "missing", "13": "blocked"}
    original_facts = {
        item.ref.source_id: tuple(field.text for field in item.fields)
        for item in snapshot_candidate.normalized_source.records
        if item.ref.source_id in expected_states
    }
    for item in candidate.normalized_source.records:
        if item.ref.source_id in expected_states:
            assert item.photo.state == expected_states[item.ref.source_id]
            assert item.photo.url is None
            assert tuple(field.text for field in item.fields) == original_facts[item.ref.source_id]
    assert len(candidate.records) == 100
    refs = [
        plan.candidate.manifest.reference(source_id).model_dump() for source_id in ("12", "13")
    ]
    before = inventory_store.path.read_bytes()
    details = []
    for ref in refs:
        path = "/api/v1/listings/" + "/".join(
            ref[name] for name in ("namespace", "snapshot_id", "source_id")
        )
        response = call(app, settings, "GET", path)
        assert response.status_code == 200
        detail = response.json()["data"]
        listing = detail["listing"]
        assert detail["state"] == "current" and listing["ref"] == ref
        assert listing["photo"]["state"] == expected_states[ref["source_id"]]
        assert listing["photo"]["url"] is None
        assert listing["make"]["status"] == listing["model"]["status"] == "known"
        assert listing["make"]["evidence"] and listing["model"]["evidence"]
        assert "set-cookie" not in response.headers
        details.append(detail)
    compared = call(app, settings, "POST", "/api/v1/comparisons", body={"refs": refs})
    assert compared.status_code == 200
    assert compared.json()["data"]["items"] == details
    assert "set-cookie" not in compared.headers
    assert inventory_store.path.read_bytes() == before
