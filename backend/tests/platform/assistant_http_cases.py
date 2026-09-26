"""Real runtime/HTTP helpers; only external provider responses are synthetic.

Source-only P16 packet: no fixture has been imported or executed for this grant.
"""

import asyncio
from collections.abc import Callable
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx
from pydantic import SecretStr

from app.assistant.intent import TurnIntent
from app.core.config import Settings, Timeouts
from app.database.store import Store
from app.runtime_app import ApplicationComposition, build_composition
from tests.assistant.conversation_fakes import ScriptedTransport, response
from tests.platform.test_runtime_integration import Buyer
from tests.support.harness import FrozenClock


def composition_for(
    store: Store,
    clock: FrozenClock,
    transport: ScriptedTransport,
    *,
    key: bool = True,
    timeouts: Timeouts | None = None,
) -> ApplicationComposition:
    return build_composition(
        Settings(
            store_path=store.path,
            runtime_boundary=store.boundary,
            gemini_api_key=SecretStr("synthetic-never-live") if key else None,
            timeouts=timeouts or Timeouts(),
        ),
        store,
        clock=clock.now,
        provider_transport=transport,
        event_sink=lambda event: None,
    )


def collection_transport() -> ScriptedTransport:
    return ScriptedTransport(
        *(
            response(
                TurnIntent.model_validate(
                    {
                        "operation": "smalltalk",
                        "deferred": ["lead"],
                        "collection": {"command": command, "fields": fields},
                    }
                )
            )
            for command, fields in (
                (
                    "start_enquiry",
                    [
                        {"field": "budget", "quote": "My cash budget is AED 45000"},
                        {"field": "requirements", "quote": 'My requirements are "quiet cabin"'},
                    ],
                ),
                ("review_enquiry", []),
                ("save_enquiry", []),
            )
        )
    )


async def request(
    composition: ApplicationComposition,
    actor: Buyer,
    method: str,
    path: str,
    *,
    body: Any = None,
    overrides: dict[str, str] | None = None,
) -> httpx.Response:
    headers = {
        **actor.headers(),
        "Cookie": composition.settings.cookie_name + "=" + actor.cookie,
        **(overrides or {}),
    }
    transport = httpx.ASGITransport(app=composition.app, client=("127.0.0.1", 45000))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        return await client.request(method, "/api/v1" + path, json=body, headers=headers)


def message(current: dict[str, Any], text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "client_message_id": str(uuid4()),
        "expected_revision": current.get("current_revision", current.get("revision")),
        "text": text,
    }
    pending = current["pending_intent"]
    if pending["kind"] == "clarification":
        result["clarification_reply"] = {
            "intent_id": pending["intent_id"],
            "created_revision": pending["created_revision"],
        }
    return result


async def submit(
    composition: ApplicationComposition,
    actor: Buyer,
    session_id: str,
    command: dict[str, Any],
) -> httpx.Response:
    return await request(
        composition, actor, "POST", f"/sessions/{session_id}/messages", body=command
    )


async def ready_to_save(
    composition: ApplicationComposition,
    actor: Buyer,
    current: dict[str, Any],
) -> dict[str, Any]:
    for text in (
        'Prepare a local enquiry; My cash budget is AED 45000; My requirements are "quiet cabin"',
        "Review my local enquiry",
    ):
        response_value = await submit(
            composition, actor, current["session_id"], message(current, text)
        )
        assert response_value.status_code == 200, response_value.text
        current = response_value.json()["data"]
        assert current["persistence"] == "saved"
    assert current["pending_intent"]["purpose"] == "action_intent"
    return message(current, "Save this local enquiry")


async def until(predicate: Callable[[], bool], *, seconds: float = 3) -> None:
    deadline = monotonic() + seconds
    while not predicate():
        if monotonic() >= deadline:
            raise AssertionError("OWNED_WORK_DID_NOT_SETTLE")
        await asyncio.sleep(0.005)
