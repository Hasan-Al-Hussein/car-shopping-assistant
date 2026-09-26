"""Harness behavior only: these synthetic checks do not accept product services."""

import asyncio
import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from tests.support.harness import (
    PROJECT,
    FrozenClock,
    HttpStep,
    OwnerSpec,
    ProviderFault,
    ProviderStep,
    ScriptedHttpTransport,
    ScriptedProvider,
    new_clock,
    read_seed,
    run_bounded,
    unopened_store_plan,
)


def test_clock_and_same_name_owner_specs_are_independent(
    clock: FrozenClock,
    owners: tuple[OwnerSpec, OwnerSpec],
) -> None:
    other_clock = new_clock()
    before = other_clock.now()
    clock.advance(300)
    assert clock.now() == before + timedelta(minutes=5)
    assert other_clock.now() == before
    assert owners[0].display_name == owners[1].display_name
    assert owners[0].owner_id != owners[1].owner_id
    assert owners[0].context_id != owners[1].context_id


def test_provider_scripts_are_finite_and_do_not_share_mutable_results() -> None:
    script = [ProviderStep("success", {"text": "Synthetic answer", "facts": []})]
    first, second = ScriptedProvider(script), ScriptedProvider(script)
    answer = first.complete("Synthetic bounded prompt")
    assert isinstance(answer, dict)
    answer["facts"].append("changed only in this test")
    assert second.complete("Synthetic bounded prompt") == {"text": "Synthetic answer", "facts": []}
    with pytest.raises(AssertionError, match="UNSCRIPTED_PROVIDER_CALL"):
        first.complete("No hidden live fallback")


@pytest.mark.parametrize("kind", ["timeout", "quota", "unavailable"])
def test_provider_fault_is_explicit_and_repeatable(kind: str) -> None:
    # Fixture data is deliberately selected from the three supported fault modes.
    step = ProviderStep(kind)  # type: ignore[arg-type]
    provider = ScriptedProvider([step])
    with pytest.raises(ProviderFault, match=kind):
        provider.complete("Synthetic prompt")
    assert provider.calls == 1


def test_malformed_provider_payload_is_not_silently_repaired() -> None:
    provider = ScriptedProvider([ProviderStep("malformed", "{not valid JSON")])
    assert provider.complete("Synthetic prompt") == "{not valid JSON"


def test_delayed_reply_can_arrive_after_newer_reply_without_sleeping() -> None:
    async def exercise() -> None:
        old_gate, accepted = asyncio.Event(), asyncio.Event()
        transport = ScriptedHttpTransport(
            [
                HttpStep(
                    "GET", "/state", payload={"revision": 1}, gate=old_gate, on_accept=accepted.set
                ),
                HttpStep("GET", "/state", payload={"revision": 2}),
            ]
        )
        async with httpx.AsyncClient(
            transport=transport, base_url="http://fixture.invalid"
        ) as client:
            old_request = asyncio.create_task(client.get("/state"))
            await accepted.wait()
            fresh = await client.get("/state")
            assert fresh.json()["revision"] == 2
            assert not old_request.done()
            old_gate.set()
            stale = await old_request
            assert stale.json()["revision"] == 1

    run_bounded(exercise())


def test_response_loss_does_not_erase_simulated_acceptance() -> None:
    async def exercise() -> None:
        accepted: list[str] = []
        transport = ScriptedHttpTransport(
            [
                HttpStep(
                    "POST",
                    "/action",
                    on_accept=lambda: accepted.append("original-action"),
                    lose_response=True,
                ),
                HttpStep(
                    "GET", "/action", payload={"state": "succeeded", "key": "original-action"}
                ),
                HttpStep("POST", "/storage", status=503, payload={"code": "STORE_UNAVAILABLE"}),
                HttpStep("GET", "/projection", payload={"state": "failed", "canonical_version": 2}),
            ]
        )
        async with httpx.AsyncClient(
            transport=transport, base_url="http://fixture.invalid"
        ) as client:
            with pytest.raises(httpx.ReadError, match="SYNTHETIC_RESPONSE_LOST_AFTER_ACCEPT"):
                await client.post("/action")
            assert accepted == ["original-action"]
            assert (await client.get("/action")).json()["state"] == "succeeded"
            assert (await client.post("/storage")).status_code == 503
            assert (await client.get("/projection")).json()["state"] == "failed"

    run_bounded(exercise())


def test_default_network_and_unscripted_transport_are_blocked() -> None:
    with httpx.Client() as client, pytest.raises(AssertionError, match="LIVE_NETWORK_DISABLED"):
        client.get("https://example.invalid")

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=ScriptedHttpTransport([])) as client:
            with pytest.raises(AssertionError, match="UNSCRIPTED_HTTP_CALL"):
                await client.get("https://example.invalid")

    run_bounded(exercise())


def test_unreleased_async_gate_fails_with_a_bounded_deadline() -> None:
    async def waiting() -> None:
        await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        run_bounded(waiting(), timeout_seconds=0)


def test_store_plan_is_unopened_scoped_and_generation_aware() -> None:
    seed = read_seed()
    run_id = "40000000-0000-4000-8000-000000000001"
    original = unopened_store_plan(
        run_id=run_id, case_id="case-recovery", generation=seed["synthetic_generations"][0]
    )
    restored = unopened_store_plan(
        run_id=run_id,
        case_id="case-recovery",
        generation=seed["synthetic_generations"][1],
        schema_state="old_revision",
        fault="response_lost",
    )
    assert original.state == restored.state == "unopened"
    assert original.path == restored.path
    assert original.store_generation != restored.store_generation
    assert original.requires_resolved_path_check is True
    assert not Path(str(original.path)).exists()
    with pytest.raises(ValueError, match="path input is not allowed"):
        unopened_store_plan(
            run_id=run_id, case_id="../original", generation=seed["synthetic_generations"][0]
        )


def test_audited_source_fixtures_preserve_numeric_labels_placeholder_and_unicode() -> None:
    packet = json.loads((PROJECT / "fixtures/shared/source-facts.json").read_text(encoding="utf-8"))
    by_cell = {case["cell"]: case for case in packet["cases"]}
    assert by_cell["D13"]["raw_value"] == 3
    assert by_cell["E23"]["raw_value"] == 707
    assert by_cell["G36"]["raw_value"] == "."
    assert by_cell["F36"]["raw_value"] == "ميني كوبر 2017 S"
    assert all(case["sheet"] == "cleaned dataset" for case in packet["cases"])
