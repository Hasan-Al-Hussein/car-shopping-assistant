"""Unexecuted A6 composition of real I6/P12 services; provider JSON alone is scripted.

Reuses Inventory's reviewed workbook fixtures and existing approved disposable Store paths.
No live provider, alternative mapper, permissive signing gateway or production mount.
"""

import asyncio
from time import monotonic
from uuid import uuid4

import pytest

from app.api.schemas.common import InventoryRef
from app.api.schemas.identity import IdentityBootstrapRequest, RecognizedIdentity
from app.api.schemas.inventory import ComparisonRequest, ListingDetail
from app.api.schemas.sessions import SessionCreateRequest
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.assistant.service_adapters import (
    AssistantService,
    BoundedServiceWorker,
    InventoryServiceAdapter,
    SessionServiceAdapter,
)
from app.core.config import Settings
from app.core.errors import ApiFailure
from app.database.store import Store
from app.identity.authorization import AuthorizationService
from app.identity.credentials import decode_token
from app.identity.service import IdentityService
from app.inventory.staging_plan import PreparedStage
from app.inventory_gateways import CompactSessionInventory
from app.sessions.service import SessionService
from tests.inventory.conftest import inventory_store as inventory_store
from tests.inventory.conftest import inventory_store_path as inventory_store_path
from tests.inventory.conftest import snapshot_candidate as snapshot_candidate
from tests.inventory.conftest import snapshot_plan as snapshot_plan
from tests.inventory.public_cases import NOW, public_harness
from tests.platform.test_identity import ACK

from .conversation_fakes import adapter, budget, request, state
from .test_service_worker import until


def test_real_search_grounded_detail_original_batch_and_same_id_replay(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    public = public_harness(inventory_store, snapshot_plan)
    identity = IdentityService(
        Settings(store_path=inventory_store.path, runtime_boundary=inventory_store.boundary),
        clock=lambda: NOW,
    )
    bootstrap = identity.bootstrap(IdentityBootstrapRequest.model_validate(ACK), None)
    assert bootstrap.cookie is not None and isinstance(bootstrap.identity, RecognizedIdentity)
    authorization = AuthorizationService(identity)
    context = authorization.authorize_write(
        decode_token(bootstrap.cookie), bootstrap.identity.context_id, bootstrap.identity.csrf_token
    )
    sessions = SessionService(
        authorization, inventory=CompactSessionInventory(public.reader, public.signer)
    )
    current = sessions.create(context, SessionCreateRequest(client_action_id=str(uuid4())))
    model, transport = adapter(
        TurnIntent.model_validate(
            {
                "operation": "search",
                "patches": [
                    {
                        "kind": "text",
                        "field": "makes",
                        "operation": "add",
                        "values": ["Land Rover"],
                        "quote": "Land Rover",
                    }
                ],
            }
        ),
        TurnIntent(
            operation="detail", references=[ReferenceRequest(source="request", quote="this car")]
        ),
    )
    worker = BoundedServiceWorker()
    service = AssistantService(sessions, model, public.search, public.details, worker)

    async def exercise() -> None:
        value = request(current, "Show Land Rover cars")
        found = await service.run(
            context, current.session_id, value, request_state=state(), budget=budget()
        )
        assert found.search is not None and found.persistence == "saved"
        assert found.search.applied_criteria.filters.makes == ["land rover"]
        assert all(e.ref in found.search.presentation.ordered_refs for e in found.evidence)
        public.signer.verify_presentation(found.search.presentation, now=NOW)
        facade = SessionServiceAdapter(sessions, worker, budget())
        observed = await facade.get(context, current.session_id)
        assert observed.criteria.filters.makes == ["Land Rover"]
        assert observed.active_presentation_id is not None
        originals = await facade.original_refs(
            context, current.session_id, observed.active_presentation_id
        )
        assert list(originals) == found.search.presentation.ordered_refs
        reads = InventoryServiceAdapter(public.search, public.details, worker)
        batch = await reads.original_batch(originals, deadline_at=monotonic() + 2)
        assert [
            item.listing.ref if isinstance(item, ListingDetail) else item.ref for item in batch
        ] == list(originals)
        assert await reads.original_batch((), deadline_at=monotonic() + 2) == ()
        assert len(originals) >= 2
        compared = await reads.compare(
            ComparisonRequest(refs=[originals[1], originals[0]]), deadline_at=monotonic() + 2
        )
        assert [
            item.listing.ref if isinstance(item, ListingDetail) else item.ref
            for item in compared.items
        ] == [originals[1], originals[0]]
        selected = next(ref for ref in originals if ref.source_id == "3")
        detail_request = request(
            observed, "Show this car", selected_ref=selected.model_dump(mode="json")
        )
        result = await service.run(
            context, current.session_id, detail_request, request_state=state(), budget=budget()
        )
        assert (
            result.handoff_summary is not None and result.handoff_summary.selected_ref == selected
        )
        assert isinstance(result.handoff_summary.listing, ListingDetail)
        assert result.handoff_summary.listing.state == "current"
        assert "AED 119,750.00 cash" in result.text and "68,000 km" in result.text
        assert result.evidence[0].ref == selected
        assert result.handoff_summary.fit_reasons[0].criterion == "makes"
        assert all(fit.evidence_ids for fit in result.handoff_summary.fit_reasons)
        replay_budget = budget()
        replay = await service.run(
            context,
            current.session_id,
            detail_request,
            request_state=state(),
            budget=replay_budget,
        )
        assert replay == result and len(transport.requests) == 2
        assert replay_budget.provider_attempts == replay_budget.tool_invocations == 0
        assert not worker.pending

    try:
        asyncio.run(exercise())
    finally:
        # A failed latency assertion still retains ownership until actual worker settlement.
        asyncio.run(until(lambda: not worker.pending))
        assert worker.close()


def test_real_inventory_adapter_rejects_expired_deadline_without_empty_result(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    public = public_harness(inventory_store, snapshot_plan)
    worker = BoundedServiceWorker()
    reads = InventoryServiceAdapter(public.search, public.details, worker)
    ref = InventoryRef.model_validate(
        next(
            item.ref.model_dump(mode="json")
            for item in snapshot_plan.candidate.listings
            if item.ref.source_id == "3"
        )
    )

    async def exercise() -> None:
        with pytest.raises(ApiFailure, match="PROVIDER_TIMEOUT"):
            await reads.detail(ref, deadline_at=monotonic() - 1)
        assert not worker.pending

    try:
        asyncio.run(exercise())
    finally:
        assert worker.close()
