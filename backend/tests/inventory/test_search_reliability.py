"""Concurrent public-service reads using the real reviewed fixture and deadline."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, local
from time import monotonic
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.schemas.inventory import SearchRequest
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.database.store import Store, StoreError
from app.inventory import search_service
from app.inventory.compact_reader import CompactInventoryReader, SearchAnchor, _Certificate
from app.inventory.read_budget import check_deadline
from app.inventory.references import ImmutableInventoryRef
from app.inventory.search_service import InventorySearchService
from app.inventory.staging_plan import PreparedStage
from app.runtime_app import _Lifetime, _RuntimeReader
from tests.inventory.public_cases import NOW, public_harness
from tests.inventory.snapshot_cases import execute


def test_three_concurrent_searches_preserve_facts_within_service_deadline(
    inventory_store: Store, snapshot_plan: PreparedStage, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    barrier = Barrier(3)
    worker_state = local()
    original_check = check_deadline
    original_verified = CompactInventoryReader._verified

    def check(deadline: float) -> None:
        worker_state.events.append(
            {
                "stage": "deadline_check",
                "line": sys._getframe(1).f_lineno,
                "remaining_seconds": deadline - monotonic(),
            }
        )
        original_check(deadline)

    def verified(
        self: CompactInventoryReader, session: Session, refs: tuple[ImmutableInventoryRef, ...]
    ) -> tuple[InventoryObservation, tuple[_Certificate, ...], int]:
        started = monotonic()
        try:
            return original_verified(self, session, refs)
        finally:
            worker_state.events.append(
                {"stage": "fresh_fingerprint", "elapsed_seconds": monotonic() - started}
            )

    monkeypatch.setattr(search_service, "check_deadline", check)
    monkeypatch.setattr(CompactInventoryReader, "_verified", verified)

    def search(worker: int) -> dict[str, Any]:
        worker_state.events = []
        barrier.wait(timeout=10)
        started = monotonic()
        try:
            result = harness.search.search(
                SearchRequest(client_request_id=str(uuid4()), page_size=20)
            )
            assert result.supported_total == 100
            assert [item.ref.source_id for item in result.items] == sorted(
                str(index) for index in range(1, 101)
            )[:20]
            outcome = "returned"
        except ApiFailure as error:
            outcome = str(error)
        return {
            "worker": worker,
            "outcome": outcome,
            "elapsed_seconds": monotonic() - started,
            "events": worker_state.events,
        }

    with ThreadPoolExecutor(max_workers=3) as executor:
        outcomes = list(executor.map(search, range(3)))
    print("SEARCH_RELIABILITY_TRACE=" + json.dumps(outcomes, sort_keys=True))
    assert all(item["outcome"] == "returned" for item in outcomes), outcomes


@pytest.mark.parametrize("invalid", ["criteria", "snapshot"])
def test_invalid_search_metadata_preserves_admission_and_precedes_unrelated_corruption(
    inventory_store: Store, snapshot_plan: PreparedStage, invalid: str
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    first = harness.search.search(SearchRequest(client_request_id=str(uuid4())))
    request = (
        SearchRequest(client_request_id=str(uuid4()), cursor=first.next_cursor, query="toyota")
        if invalid == "criteria"
        else SearchRequest(client_request_id=str(uuid4()), snapshot_id="0" * 64)
    )
    expected = "VALIDATION_ERROR" if invalid == "criteria" else "SNAPSHOT_STALE"
    with pytest.raises(ApiFailure, match=expected):
        harness.search.search(request)
    valid = harness.search.search(SearchRequest(client_request_id=str(uuid4())))
    assert valid.supported_total == 100
    execute(
        inventory_store,
        "UPDATE listing_versions SET original_json='{}' WHERE source_id='99'",
    )
    # A rejected request carries no car facts; a valid request still verifies all rows.
    with pytest.raises(ApiFailure, match=expected):
        harness.search.search(request)
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        harness.search.search(SearchRequest(client_request_id=str(uuid4())))
    with pytest.raises(ValueError, match="AUDIT_ADMISSION_REQUIRED"):
        harness.reader.read_header()


@pytest.mark.parametrize("phase", ["search.before_index", "search.before_projection"])
@pytest.mark.parametrize("replacement", ["invalidate", "invalidate_and_readmit", "readmit"])
def test_search_rejects_admission_changes_at_both_checkpoints(
    inventory_store: Store, snapshot_plan: PreparedStage, phase: str, replacement: str
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    reached = False

    def checkpoint(current: str) -> None:
        nonlocal reached
        if current == phase:
            reached = True
            if replacement != "readmit":
                harness.reader.invalidate()
            if replacement != "invalidate":
                harness.reader.admit(snapshot_plan.index.snapshot_id)

    search = InventorySearchService(
        harness.reader, harness.signer, clock=lambda: NOW, _checkpoint=checkpoint
    )
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        search.search(SearchRequest(client_request_id=str(uuid4())))
    assert reached


@pytest.mark.parametrize("phase", ["search.before_index", "search.before_projection"])
def test_search_detects_unrequested_corruption_after_metadata_anchor(
    inventory_store: Store, snapshot_plan: PreparedStage, phase: str
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    reached = False

    def checkpoint(current: str) -> None:
        nonlocal reached
        if current == phase:
            reached = True
            execute(
                inventory_store,
                "UPDATE listing_versions SET original_json='{}' WHERE source_id='99'",
            )

    search = InventorySearchService(
        harness.reader, harness.signer, clock=lambda: NOW, _checkpoint=checkpoint
    )
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        search.search(SearchRequest(client_request_id=str(uuid4()), page_size=20))
    assert reached


@pytest.mark.parametrize("close_when", ["before", "after"])
def test_runtime_search_anchor_checks_lifetime_before_and_after_read(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
    close_when: str,
) -> None:
    public_harness(inventory_store, snapshot_plan)
    lifetime = _Lifetime(inventory_store)
    reader = _RuntimeReader(inventory_store, lifetime)
    try:
        reader.admit(snapshot_plan.index.snapshot_id)
        original = CompactInventoryReader.read_search_anchor
        reached = False

        def read(self: CompactInventoryReader) -> SearchAnchor:
            nonlocal reached
            reached = True
            assert close_when == "after", "closed lifetime reached a Store read"
            result = original(self)
            lifetime.close()
            return result

        monkeypatch.setattr(CompactInventoryReader, "read_search_anchor", read)
        pid = os.getpid()
        with monkeypatch.context() as foreign:
            foreign.setattr(os, "getpid", lambda: pid + 1)
            with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
                reader.read_search_anchor()
        assert reached is False
        if close_when == "before":
            lifetime.close()
        with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
            reader.read_search_anchor()
        assert reached == (close_when == "after")
    finally:
        lifetime.release()


def test_search_anchor_observation_must_match_authenticated_identity(
    inventory_store: Store, snapshot_plan: PreparedStage, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    original = harness.reader.read_search_anchor
    anchor = original()
    swapped = replace(
        anchor,
        observation=anchor.observation.model_copy(update={"active_revision": 999}),
    )
    monkeypatch.setattr(harness.reader, "read_search_anchor", lambda: swapped)
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        harness.search.search(SearchRequest(client_request_id=str(uuid4())))
    monkeypatch.setattr(harness.reader, "read_search_anchor", original)
    valid = harness.search.search(SearchRequest(client_request_id=str(uuid4())))
    assert valid.supported_total == 100
