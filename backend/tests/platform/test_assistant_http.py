"""P16 actual HTTP/Assistant/Session/Store/CSV integration sources, NOT_RUN.

Scripted transport is the sole provider dependency. No live key, remote service,
permissive domain gateway or replacement worker is involved.
"""

import asyncio
from threading import Event

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.schemas.sessions import MessageRequest
from app.assistant.intent import TurnIntent
from app.core.config import Timeouts
from app.database.models import Lead
from app.database.store import Store
from app.identity.credentials import decode_token
from app.leads.projection import ProjectionRun
from app.leads.projection_files import CSV_NAME
from tests.assistant.conversation_fakes import ScriptedTransport, response
from tests.platform.assistant_http_cases import (
    collection_transport,
    composition_for,
    message,
    ready_to_save,
    request,
    submit,
    until,
)
from tests.platform.runtime_cases import runtime_clock as runtime_clock
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import runtime_store as runtime_store
from tests.platform.test_identity import ACK, snapshot
from tests.platform.test_runtime_integration import buyer, private, session
from tests.support.harness import FrozenClock
from tests.transactions.lead_fixtures import buyer_values, save_request


def test_keyless_message_is_saved_and_original_receipt_replays(
    runtime_store: Store,
    runtime_clock: FrozenClock,
) -> None:
    transport = ScriptedTransport()
    composition = composition_for(runtime_store, runtime_clock, transport, key=False)
    actor = buyer(composition)
    current = session(composition, actor)
    command = message(current, "Hello")

    async def exercise() -> None:
        first = await submit(composition, actor, current["session_id"], command)
        assert first.status_code == 200
        data = first.json()["data"]
        assert data["state"] == "provider_unavailable" and data["persistence"] == "saved"
        assert data["provider_state"] == "unavailable"
        before = await asyncio.to_thread(snapshot, runtime_store)
        replay = await submit(composition, actor, current["session_id"], command)
        assert replay.status_code == 200 and replay.json()["data"] == data
        assert (
            await asyncio.to_thread(snapshot, runtime_store) == before and transport.requests == []
        )
        transcript = await request(
            composition, actor, "GET", f"/sessions/{current['session_id']}/messages"
        )
        assert transcript.json()["data"]["items"][0]["assistant_result"] == data
        assert first.json()["meta"]["entity_revision"] == data["current_revision"]

    try:
        asyncio.run(exercise())
    finally:
        assert composition.close()


@pytest.mark.parametrize("text", [str(ACK["display_name"]), "form-only@example.test"])
def test_owned_private_values_stay_local_and_expired_lead_does_not_gate_chat(
    runtime_store: Store,
    runtime_clock: FrozenClock,
    text: str,
) -> None:
    transport = ScriptedTransport(response(TurnIntent(operation="smalltalk")))
    composition = composition_for(runtime_store, runtime_clock, transport)
    actor = buyer(composition)
    current = session(composition, actor)
    supplied = buyer_values().model_dump(mode="json")
    supplied["email"] = {"state": "provided", "value": "form-only@example.test"}
    command = save_request(current["session_id"], buyer_values()).model_dump(mode="json")
    command["values"] = supplied
    saved = private(composition, actor, "POST", "/api/v1/leads", body=command)
    assert saved.status_code == 201

    def expire(db: Session) -> None:
        db.execute(update(Lead).values(expires_at="2029-01-01T00:00:00.000000Z")).close()

    runtime_store.write(expire)

    async def exercise() -> None:
        local = await submit(composition, actor, current["session_id"], message(current, text))
        assert local.status_code == 200
        data = local.json()["data"]
        assert data["provider_state"] == "not_used" and data["persistence"] == "saved"
        assert "local enquiry form" in data["text"] and transport.requests == []
        ordinary = await submit(composition, actor, current["session_id"], message(data, "Hello"))
        assert (
            ordinary.status_code == 200 and ordinary.json()["data"]["provider_state"] == "available"
        )
        assert len(transport.requests) == 1
        assert text not in transport.requests[0].contents
        observed = await request(composition, actor, "GET", f"/sessions/{current['session_id']}")
        assert "collection" not in observed.json()["data"]

    try:
        asyncio.run(exercise())
    finally:
        assert composition.close()


def test_pending_original_message_requires_read_and_private_denials_precede_provider(
    runtime_store: Store,
    runtime_clock: FrozenClock,
) -> None:
    transport = ScriptedTransport()
    composition = composition_for(runtime_store, runtime_clock, transport)
    actor, foreign = buyer(composition), buyer(composition)
    current = session(composition, actor)
    command = message(current, "Hello")
    context = composition.authorization.authorize_write(
        decode_token(actor.cookie), actor.context, actor.csrf
    )
    admitted = composition.sessions.begin(
        context, current["session_id"], MessageRequest.model_validate(command)
    )
    assert admitted.status == "accepted"
    before = snapshot(runtime_store)

    async def exercise() -> None:
        unresolved = await submit(composition, actor, current["session_id"], command)
        error = unresolved.json()["error"]
        assert unresolved.status_code == 409 and error["code"] == "OPERATION_UNRESOLVED"
        assert error["retry_action"] == "read" and error["outcome_state"] == "unresolved"
        assert error["operation_key"] is None
        hidden = await submit(composition, foreign, current["session_id"], command)
        denied = await request(
            composition,
            actor,
            "POST",
            f"/sessions/{current['session_id']}/messages",
            body=command,
            overrides={"X-CSRF-Token": "x" * 43},
        )
        assert hidden.status_code == 404 and denied.status_code == 403
        assert (
            transport.requests == [] and await asyncio.to_thread(snapshot, runtime_store) == before
        )

    try:
        asyncio.run(exercise())
    finally:
        assert composition.close()


@pytest.mark.parametrize("stall", [False, True])
def test_real_conversation_save_preserves_receipt_across_csv_and_repair_timeout(
    runtime_store: Store,
    runtime_clock: FrozenClock,
    monkeypatch: pytest.MonkeyPatch,
    stall: bool,
) -> None:
    transport = collection_transport()
    timeouts = Timeouts(
        operation_seconds=2,
        confirmation_seconds=1,
        provider_connect_seconds=1,
        provider_attempt_seconds=1,
        read_seconds=1,
    )
    composition = composition_for(runtime_store, runtime_clock, transport, timeouts=timeouts)
    actor = buyer(composition)
    current = session(composition, actor)
    entered, release = Event(), Event()
    actual_repair = composition.projector.repair_once

    def stalled_repair() -> ProjectionRun:
        entered.set()
        if not release.wait(8):
            raise AssertionError("TEST_DID_NOT_RELEASE_PROJECTOR")
        return actual_repair()

    async def exercise() -> None:
        command = await ready_to_save(composition, actor, current)
        if stall:
            monkeypatch.setattr(composition.projector, "repair_once", stalled_repair)
        try:
            saved = await submit(composition, actor, current["session_id"], command)
            assert saved.status_code == 200, saved.text
            data = saved.json()["data"]
            assert (
                data["persistence"] == "saved" and data["actions"]["lead"]["state"] == "succeeded"
            )
            original_lead = data["actions"]["lead"]["result"]["lead"]
            assert original_lead["csv"]["state"] == "pending"
            assert original_lead["values"]["budget"]["value"]["maximum"] == 4500000
            if stall:
                assert entered.is_set() and composition.worker.pending
            transcript = await request(
                composition, actor, "GET", f"/sessions/{current['session_id']}/messages"
            )
            stored = next(
                item
                for item in transcript.json()["data"]["items"]
                if item["client_message_id"] == command["client_message_id"]
            )
            assert stored["assistant_result"] == data
        finally:
            release.set()
            await until(lambda: not composition.worker.pending)
            monkeypatch.setattr(composition.projector, "repair_once", actual_repair)
        observed = await request(composition, actor, "GET", "/leads/current")
        assert observed.status_code == 200 and observed.json()["data"]["csv"]["state"] == "current"
        csv_path = runtime_store.boundary.physical_root / "exports" / CSV_NAME
        assert csv_path.is_file() and "quiet cabin" in csv_path.read_text(encoding="utf-8-sig")
        replay = await submit(composition, actor, current["session_id"], command)
        assert replay.status_code == 200 and replay.json()["data"] == data
        assert len(transport.requests) == 3
        capability = await asyncio.to_thread(composition.projector.capability)
        assert capability.state == "ready"

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        assert composition.close()
