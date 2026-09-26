"""Expected-ID searches through real persisted rows, index, CompactReader and signer."""

import json
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

import pytest
from app.api.schemas.inventory import SearchCriteria, SearchFilters, SearchRequest
from app.core.errors import ApiFailure
from app.database.store import Store, StoreError, initialize_store
from app.inventory.extraction import ExtractedCandidate, extract_reviewed
from app.inventory.review_catalogue import ReviewCatalogue
from app.inventory.search_policy import normalize_criteria
from app.inventory.search_service import InventorySearchService
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage, prepare_stage
from tests.inventory.public_cases import NOW, public_harness
from tests.inventory.snapshot_cases import execute
from tests.support.harness import PROJECT, configured_runtime_boundary

CORPUS = json.loads(
    (PROJECT / "fixtures/inventory/search-expected.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["name"])
def test_reviewed_expected_ids(
    inventory_store: Store, snapshot_plan: PreparedStage, case: dict[str, Any]
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    before = inventory_store.path.read_bytes()
    request = SearchRequest.model_validate(
        {
            "client_request_id": str(uuid4()),
            "page_size": 50,
            **{key: case[key] for key in ("query", "filters", "soft_preferences") if key in case},
        }
    )
    result = harness.search.search(request)
    assert [item.ref.source_id for item in result.items] == case["ids"]
    assert result.supported_total == len(case["ids"])
    assert result.unsupported_constraints == case.get("unsupported", [])
    assert result.state == ("matches" if case["ids"] else "no_supported_matches")
    assert result.next_cursor is None and result.constraints_relaxed is False
    assert result.presentation.ordered_refs == [item.ref for item in result.items]
    harness.signer.verify_presentation(result.presentation, now=NOW)
    assert all(coverage.source_total == 100 for coverage in result.evidence_coverage)
    assert inventory_store.path.read_bytes() == before


def test_paging_is_exact_and_page_size_changes_do_not_renew_cursor(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    first = harness.search.search(SearchRequest(client_request_id=str(uuid4()), page_size=20))
    assert first.next_cursor is not None
    original = harness.signer.decode_search_cursor(first.next_cursor, now=NOW)
    second = harness.search.search(
        SearchRequest(
            client_request_id=str(uuid4()),
            cursor=first.next_cursor,
            page_size=50,
        )
    )
    assert second.next_cursor is not None
    continuation = harness.signer.decode_search_cursor(second.next_cursor, now=NOW)
    assert continuation.issued_at == original.issued_at
    assert continuation.expires_at == original.expires_at
    last = harness.search.search(
        SearchRequest(
            client_request_id=str(uuid4()),
            cursor=second.next_cursor,
            page_size=50,
        )
    )
    ordered = first.items + second.items + last.items
    assert [item.ref.source_id for item in ordered] == sorted(str(i) for i in range(1, 101))
    assert len({item.ref.source_id for item in ordered}) == 100
    assert last.next_cursor is None
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        harness.search.search(
            SearchRequest(
                client_request_id=str(uuid4()),
                cursor=first.next_cursor,
                query="toyota",
            )
        )
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        harness.search.search(
            SearchRequest(
                client_request_id=str(uuid4()),
                cursor=first.next_cursor + "x",
            )
        )


@pytest.mark.parametrize("phase", ["search.before_index", "search.before_projection"])
def test_activation_race_never_mixes_index_projection_or_cursor(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage, phase: str
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    repo = InventoryRepository(inventory_store)
    repo.stage(second_plan)
    # Admission must see the final retained FTS set; this is explicit operator setup.
    harness.reader.admit(snapshot_plan.index.snapshot_id)
    harness.reader.admit(second_plan.index.snapshot_id)
    first = harness.search.search(SearchRequest(client_request_id=str(uuid4()), page_size=20))
    changed = False

    def checkpoint(current: str) -> None:
        nonlocal changed
        if current == phase and not changed:
            repo.activate(second_plan.index.snapshot_id, expected_revision=1)
            changed = True

    raced = InventorySearchService(
        harness.reader, harness.signer, clock=lambda: NOW, _checkpoint=checkpoint
    )
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        raced.search(SearchRequest(client_request_id=str(uuid4())))
    assert changed
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        harness.search.search(
            SearchRequest(client_request_id=str(uuid4()), cursor=first.next_cursor)
        )


def test_coverage_is_disjoint_and_price_currency_is_explicit(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    result = harness.search.search(
        SearchRequest.model_validate(
            {
                "client_request_id": str(uuid4()),
                "filters": {"budget": {"currency": "USD", "maximum": 10**12}},
            }
        )
    )
    coverage = result.evidence_coverage[0]
    assert (
        coverage.source_total,
        coverage.supported,
        coverage.excluded_unknown,
        coverage.excluded_conflicting,
        coverage.excluded_unsupported_qualifier,
    ) == (100, 0, 87, 0, 13)


@pytest.mark.parametrize("qualifier", ["approximate", "at_least", "at_most"])
def test_synthetic_nonexact_mileage_never_qualifies_a_hard_range(
    inventory_store: Store, snapshot_candidate: ExtractedCandidate, qualifier: str
) -> None:
    # Deliberately synthetic review policy, not a claim that the real listing is approximate.
    catalogue = snapshot_candidate.catalogue.model_dump(mode="json")
    record = next(item for item in catalogue["records"] if item["source_id"] == "10")
    claim = next(item for item in record["claims"] if item["family"] == "mileage_km")
    claim["qualifier"] = qualifier
    candidate = extract_reviewed(
        snapshot_candidate.normalized_source, ReviewCatalogue.model_validate(catalogue)
    )
    plan = prepare_stage(candidate, policy_version="DEMO-POLICY-1")
    harness = public_harness(inventory_store, plan)
    result = harness.search.search(
        SearchRequest.model_validate(
            {
                "client_request_id": str(uuid4()),
                "filters": {
                    "makes": ["rolls-royce"],
                    "mileage_km": {"minimum": 42000, "maximum": 42000},
                },
            }
        )
    )
    assert result.items == []
    mileage = next(item for item in result.evidence_coverage if item.attribute == "mileage_km")
    assert mileage.excluded_unsupported_qualifier == 1


def test_adopted_bounded_lexical_storage_uses_the_same_expected_search(
    inventory_store_path: Path,
    snapshot_candidate: ExtractedCandidate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.database.store.detect_fts5", lambda: False)
    monkeypatch.setattr("app.database.store.fts5_registered", lambda _: False)
    store = initialize_store(inventory_store_path, boundary=configured_runtime_boundary())
    plan = prepare_stage(
        snapshot_candidate, policy_version="DEMO-POLICY-1", capability_probe=lambda: False
    )
    harness = public_harness(store, plan)
    result = harness.search.search(
        SearchRequest(client_request_id=str(uuid4()), query="rolls royce")
    )
    assert [item.ref.source_id for item in result.items] == [
        "10",
        "15",
        "30",
        "42",
        "73",
        "74",
        "82",
    ]


@pytest.mark.parametrize(
    "query",
    [
        "-petrol",
        "!petrol",
        "−petrol",
        "(-petrol)",
        "[!petrol]",
        "{−petrol}",
        "year ≥ 2020",
        "year ≤ 2020",
        "make ≠ toyota",
    ],
)
def test_operator_intent_is_not_positive_lexical_search(query: str) -> None:
    assert normalize_criteria(SearchCriteria(query=query)).unsupported
    assert not normalize_criteria(SearchCriteria(query="mercedes-benz")).unsupported


@pytest.mark.parametrize("preference", ["(!petrol)", "[-petrol]", "{−petrol}"])
def test_grouped_exclusion_preference_is_explicitly_rejected(preference: str) -> None:
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        normalize_criteria(SearchCriteria(soft_preferences=[preference]))


@pytest.mark.parametrize(
    "criteria",
    [
        SearchCriteria(filters=SearchFilters(makes=["ß" * 101])),
        SearchCriteria(query="ß " * 500),
    ],
)
def test_wire_valid_casefold_expansion_returns_safe_validation_failure(
    criteria: SearchCriteria,
) -> None:
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        normalize_criteria(criteria)


def test_unsupported_soft_preference_and_expired_deadline_fail_explicitly(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        normalize_criteria(SearchCriteria(soft_preferences=["not petrol"]))
    harness = public_harness(inventory_store, snapshot_plan)
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        harness.search.search(
            SearchRequest(client_request_id=str(uuid4())), deadline_at=monotonic() - 1
        )


def test_corruption_is_retrieval_failure_not_zero_matches(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    execute(
        inventory_store,
        "UPDATE inventory_search_documents SET document_text='corrupt' WHERE source_id='12'",
    )
    with pytest.raises((ApiFailure, StoreError)):
        harness.search.search(
            SearchRequest(client_request_id=str(uuid4()), filters=SearchFilters(makes=["absent"]))
        )
    # Shared Store may reject before the fingerprint, but neither path returns a zero result.
