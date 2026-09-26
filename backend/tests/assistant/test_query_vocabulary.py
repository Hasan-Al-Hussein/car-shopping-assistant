"""The planner receives source vocabulary without treating it as result evidence."""

import asyncio
import json

from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import TextPatch, TurnIntent
from app.core.errors import ApiFailure

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    adapter,
    budget,
    request,
    state,
)


def test_source_vocabulary_is_sent_as_advisory_context_before_search():
    class Inventory(FakeInventory):
        async def catalog_vocabulary(self, *, deadline_at):
            return {"makes": ("mercedes-benz", "toyota"), "models": ("camry",)}

    async def check():
        text = "show Mercdes cars"
        model, transport = adapter(TurnIntent(operation="search", patches=[TextPatch(
            kind="text", field="makes", operation="replace", values=["mercedes-benz"],
            quote=text,
        )]))
        sessions, inventory = FakeSessions(), Inventory()
        result = await ReadCoordinator(sessions, model, inventory).run(
            CONTEXT, sessions.current.session_id, request(sessions.current, text),
            request_state=state(), budget=budget(),
        )
        packet = json.loads(transport.requests[0].contents)
        vocabulary = json.loads(packet["source_context"])["query_vocabulary"]
        assert vocabulary["makes"] == ["mercedes-benz", "toyota"]
        assert inventory.searches[0].filters.makes == ["mercedes-benz"]
        assert result.search.supported_total == len(inventory.items) == 1
        assert result.search.items[0].ref == inventory.items[0].listing.ref

    asyncio.run(check())


def test_unavailable_vocabulary_does_not_invent_filters_or_break_a_valid_read():
    class Inventory(FakeInventory):
        async def catalog_vocabulary(self, *, deadline_at):
            raise ApiFailure("STORE_UNAVAILABLE")

    async def check():
        model, transport = adapter(TurnIntent(operation="search"))
        sessions, inventory = FakeSessions(), Inventory()
        result = await ReadCoordinator(sessions, model, inventory).run(
            CONTEXT, sessions.current.session_id, request(sessions.current, "show cars"),
            request_state=state(), budget=budget(),
        )
        assert json.loads(transport.requests[0].contents)["source_context"] == ""
        assert inventory.searches[0].filters.makes == []
        assert result.state == "answered"

    asyncio.run(check())
