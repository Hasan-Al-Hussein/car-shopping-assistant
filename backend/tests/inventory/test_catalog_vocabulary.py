"""Source-owned advisory vocabulary, bounded independently of factual search results."""

import asyncio
import json
from time import monotonic
from typing import cast

import pytest

from app.assistant.service_adapters import BoundedServiceWorker, InventoryServiceAdapter
from app.core.errors import ApiFailure
from app.database.store import Store, StoreError
from app.inventory.details_service import InventoryDetailsService
from app.inventory.search_service import (
    CATALOG_VOCABULARY_CHARS,
    InventorySearchService,
    _compact_vocabulary,
)
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage
from tests.inventory.public_cases import NOW, public_harness


def test_active_vocabulary_uses_actual_exact_names_without_alias_dictionary(
    inventory_store: Store, snapshot_plan: PreparedStage,
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    before = inventory_store.path.read_bytes()
    vocabulary = harness.search.catalog_vocabulary()
    assert "mercedes-benz" in vocabulary["makes"]
    assert "toyota" in vocabulary["makes"]
    assert "mercedes" not in vocabulary["makes"]
    assert "camry" in vocabulary["models"]
    assert set(vocabulary) <= {
        "makes", "models", "trims", "body_types", "fuel_types", "transmissions",
    }
    assert len(json.dumps(vocabulary, ensure_ascii=True, separators=(",", ":"))) <= 8000
    assert all(len(values) == len(set(values)) for values in vocabulary.values())
    assert inventory_store.path.read_bytes() == before


def test_vocabulary_bounds_include_json_escaping_without_truncating_labels() -> None:
    rows = [("make", "Alpha"), ("make", "Alpha"), ("model", "Model One")]
    rows.extend(("trim", str(index) + "界" * 190) for index in range(100))
    rows.extend([("private", "hidden"), ("make", ""), ("make", "z" * 201)])
    result = _compact_vocabulary(rows)
    assert result["makes"] == ("Alpha",)
    assert result["models"] == ("Model One",)
    assert len(json.dumps(result, ensure_ascii=True, separators=(",", ":"))) <= (
        CATALOG_VOCABULARY_CHARS
    )
    assert all(("trim", value) in rows for value in result["trims"])
    assert "private" not in result


def test_activation_between_anchor_and_selection_cannot_mix_catalogues(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage,
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    repository = InventoryRepository(inventory_store)
    repository.stage(second_plan)
    harness.reader.admit(snapshot_plan.index.snapshot_id)
    harness.reader.admit(second_plan.index.snapshot_id)

    def checkpoint(phase: str) -> None:
        if phase == "catalog.before_index":
            repository.activate(second_plan.index.snapshot_id, expected_revision=1)

    raced = InventorySearchService(
        harness.reader, harness.signer, clock=lambda: NOW, _checkpoint=checkpoint,
    )
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        raced.catalog_vocabulary()


def test_expired_vocabulary_deadline_is_checked_before_inventory_read(
    inventory_store: Store, snapshot_plan: PreparedStage,
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        harness.search.catalog_vocabulary(deadline_at=monotonic() - 1)


@pytest.mark.parametrize("failure", [ApiFailure("SNAPSHOT_STALE"), StoreError("STORE_BUSY")])
def test_advisory_adapter_returns_empty_if_source_is_unavailable(failure: Exception) -> None:
    class FailingSearch:
        def catalog_vocabulary(self, *, deadline_at: float) -> dict[str, tuple[str, ...]]:
            raise failure

    worker = BoundedServiceWorker()
    adapter = InventoryServiceAdapter(
        cast(InventorySearchService, FailingSearch()), cast(InventoryDetailsService, None), worker,
    )
    try:
        assert asyncio.run(adapter.catalog_vocabulary(deadline_at=monotonic() + 2)) == {}
    finally:
        assert worker.close()
