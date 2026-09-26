"""Bounded fake-provider proof; no network, credentials, database or model quality claims."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from app.api.schemas.common import InventoryRef
from app.assistant.budget import BudgetExhausted, TurnBudget
from app.assistant.packet import (
    MAX_INPUT_TOKENS,
    REPAIR_INSTRUCTION,
    SYSTEM_INSTRUCTION,
    EvidenceClaim,
    EvidencePacket,
    PacketFact,
    minimize_text,
)
from app.assistant.provider import (
    GeminiAdapter,
    ProviderFault,
    TransportRequest,
    TransportResponse,
    UsageSummary,
)
from app.core.config import Settings, Timeouts
from app.core.readiness import DependencySnapshot, ReadinessRegistry

REQUEST_ID = "00000000-0000-0000-0000-000000000001"
EVIDENCE_ID = "00000000-0000-0000-0000-000000000002"
FAKE_KEY = "synthetic-not-a-real-credential"


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str


class FakeTransport:
    def __init__(
        self,
        steps: list[TransportResponse | ProviderFault | Callable[[], Awaitable[TransportResponse]]],
    ) -> None:
        self.steps = list(steps)
        self.requests: list[TransportRequest] = []

    async def generate(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        if not self.steps:
            raise AssertionError("UNSCRIPTED_CALL")
        step = self.steps.pop(0)
        if isinstance(step, ProviderFault):
            raise step
        return await step() if callable(step) else step


def configured() -> Settings:
    return Settings(gemini_api_key=SecretStr(FAKE_KEY))


def packet(**changes: Any) -> EvidencePacket:
    return EvidencePacket(message="Show cars", session_revision=1, **changes)


def budget(seconds: float = 30) -> TurnBudget:
    loop = asyncio.get_running_loop()
    return TurnBudget(Timeouts(), deadline_at=loop.time() + seconds)


def successful(text: str = "Grounded proposal") -> TransportResponse:
    return TransportResponse(
        json.dumps({"answer": text}),
        UsageSummary(
            input_tokens=100,
            output_tokens=10,
            total_tokens=110,
        ),
    )


def test_success_is_only_a_proposal_and_readiness_preserves_other_capabilities() -> None:
    async def exercise() -> None:
        registry = ReadinessRegistry(
            DependencySnapshot(
                inventory="ready", active_snapshot_id="a" * 64, viewing="ready", export="degraded"
            )
        )
        fake = FakeTransport([successful()])
        adapter = GeminiAdapter(
            configured(),
            fake,
            readiness=registry,
            utc_now=lambda: datetime(2026, 9, 24, tzinfo=UTC),
        )
        result = await adapter.generate(packet(), Answer, budget=budget(), request_id=REQUEST_ID)
        assert result.state == "available" and result.proposal == Answer(answer="Grounded proposal")
        assert result.diagnostic.attempts == 1
        assert result.diagnostic.usage.total_tokens == 110
        snapshot = registry.snapshot()
        assert snapshot.inventory == "ready" and snapshot.export == "degraded"
        assert snapshot.active_snapshot_id == "a" * 64 and snapshot.provider is not None
        assert snapshot.provider.state == "ready"
        assert len(fake.requests) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "settings,code",
    [
        (Settings(), "not_configured"),
        (Settings(assistant_enabled=False), "disabled"),
    ],
)
def test_missing_or_disabled_provider_never_invokes_transport(
    settings: Settings, code: str
) -> None:
    async def exercise() -> None:
        fake = FakeTransport([])
        result = await GeminiAdapter(settings, fake).generate(
            packet(), Answer, budget=budget(), request_id=REQUEST_ID
        )
        assert result.diagnostic.code == code and result.diagnostic.attempts == 0
        assert not fake.requests and result.proposal is None

    asyncio.run(exercise())


@pytest.mark.parametrize("code", ["auth", "quota", "model_missing", "timeout", "output_too_large"])
def test_terminal_provider_failures_never_retry(code: Any) -> None:
    async def exercise() -> None:
        fake = FakeTransport([ProviderFault(code), successful()])
        result = await GeminiAdapter(configured(), fake).generate(
            packet(), Answer, budget=budget(), request_id=REQUEST_ID
        )
        assert result.diagnostic.code == code and len(fake.requests) == 1
        assert result.proposal is None and result.diagnostic.usage.total_tokens is None

    asyncio.run(exercise())


def test_repair_has_no_raw_output_and_consumes_shared_attempt_ledger() -> None:
    async def exercise() -> None:
        fake = FakeTransport([TransportResponse("bad private output"), successful()])
        adapter = GeminiAdapter(configured(), fake)
        turn = budget()
        result = await adapter.generate(packet(), Answer, budget=turn, request_id=REQUEST_ID)
        assert result.state == "available" and turn.provider_attempts == 2
        assert [request.repair for request in fake.requests] == [False, True]
        assert "bad private output" not in fake.requests[1].contents
        again = await adapter.generate(packet(), Answer, budget=turn, request_id=REQUEST_ID)
        assert again.diagnostic.code == "attempt_limit" and len(fake.requests) == 2

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "text",
    [
        '{"answer": 3}',
        '{"answer":"ok","confirmed":true}',
        '{"answer":"a","answer":"b"}',
        '{"answer":',
    ],
)
def test_malformed_and_undeclared_output_cannot_become_a_proposal(text: str) -> None:
    async def exercise() -> None:
        fake = FakeTransport([TransportResponse(text), TransportResponse(text)])
        result = await GeminiAdapter(configured(), fake).generate(
            packet(), Answer, budget=budget(), request_id=REQUEST_ID
        )
        assert result.proposal is None and result.diagnostic.code == "malformed"
        assert len(fake.requests) == 2

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "response",
    [
        TransportResponse("x" * 8193),
        TransportResponse('{"answer":"ok"}', UsageSummary(output_tokens=2049)),
    ],
)
def test_output_bounds_stop_without_repair(response: TransportResponse) -> None:
    async def exercise() -> None:
        fake = FakeTransport([response])
        result = await GeminiAdapter(configured(), fake).generate(
            packet(), Answer, budget=budget(), request_id=REQUEST_ID
        )
        assert result.diagnostic.code == "output_too_large" and len(fake.requests) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonstandard_json_constants_are_rejected_even_if_output_model_allows_float(
    constant: str,
) -> None:
    class NumericProposal(BaseModel):
        model_config = ConfigDict(extra="forbid")
        amount: float

    async def exercise() -> None:
        text = '{"amount":' + constant + "}"
        fake = FakeTransport([TransportResponse(text), TransportResponse(text)])
        result = await GeminiAdapter(configured(), fake).generate(
            packet(), NumericProposal, budget=budget(), request_id=REQUEST_ID
        )
        assert result.proposal is None and result.diagnostic.code == "malformed"

    asyncio.run(exercise())


def test_deadline_includes_queue_and_schema_repair_without_reset() -> None:
    async def exercise() -> None:
        now = [10.0]
        turn = TurnBudget(Timeouts(), deadline_at=40.0, clock=lambda: now[0])
        now[0] = 20.0  # Earlier queue/coordinator work consumed ten seconds already.

        async def first() -> TransportResponse:
            now[0] += 9
            return TransportResponse("invalid")

        async def second() -> TransportResponse:
            now[0] += 11
            return successful()

        fake = FakeTransport([first, second])
        result = await GeminiAdapter(configured(), fake).generate(
            packet(), Answer, budget=turn, request_id=REQUEST_ID
        )
        assert result.diagnostic.code == "timeout" and result.proposal is None
        assert turn.deadline_at == 40.0 and turn.provider_attempts == 2
        assert [request.attempt_seconds for request in fake.requests] == [15, 11]

    asyncio.run(exercise())


def test_expired_turn_never_calls_provider() -> None:
    async def exercise() -> None:
        fake = FakeTransport([])
        result = await GeminiAdapter(configured(), fake).generate(
            packet(), Answer, budget=TurnBudget(Timeouts(), 0), request_id=REQUEST_ID
        )
        assert result.diagnostic.code == "timeout" and not fake.requests

    asyncio.run(exercise())


def test_cancelled_transport_is_quarantined_until_completion_and_late_result_ignored() -> None:
    async def exercise() -> None:
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def stubborn() -> TransportResponse:
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            finished.set()
            return successful("late result")

        fake = FakeTransport([stubborn])
        registry = ReadinessRegistry()
        adapter = GeminiAdapter(configured(), fake, readiness=registry)
        first = await adapter.generate(packet(), Answer, budget=budget(0.02), request_id=REQUEST_ID)
        assert entered.is_set() and first.diagnostic.code == "timeout"
        second = await adapter.generate(
            packet(), Answer, budget=budget(0.02), request_id=REQUEST_ID
        )
        assert second.diagnostic.code == "timeout" and len(fake.requests) == 1
        release.set()
        await asyncio.wait_for(finished.wait(), 0.5)
        await asyncio.sleep(0)
        observed = registry.snapshot().provider
        assert observed is not None and observed.state == "unavailable"

    asyncio.run(exercise())


def test_caller_cancellation_propagates_without_late_success_or_retry() -> None:
    async def exercise() -> None:
        entered, stopped = asyncio.Event(), asyncio.Event()

        async def waiting() -> TransportResponse:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
            return successful()

        fake = FakeTransport([waiting])
        registry = ReadinessRegistry()
        call = asyncio.create_task(
            GeminiAdapter(configured(), fake, readiness=registry).generate(
                packet(),
                Answer,
                budget=budget(),
                request_id=REQUEST_ID,
            )
        )
        await entered.wait()
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        await asyncio.wait_for(stopped.wait(), 0.5)
        assert len(fake.requests) == 1 and registry.snapshot().provider is None

    asyncio.run(exercise())


def test_minimization_covers_all_free_text_without_losing_exact_refs() -> None:
    async def exercise() -> None:
        ref = InventoryRef(namespace="synthetic", snapshot_id="a" * 64, source_id="12")
        source = EvidencePacket(
            message=f"Show Mazda 3. buyer@example.invalid +971 50 123 4567 {FAKE_KEY}",
            session_revision=2,
            selected_ref=ref,
            presented_refs=(ref,),
            facts=(
                PacketFact(
                    ref=ref,
                    attribute="warranty",
                    status="known",
                    claims=(
                        EvidenceClaim(
                            text="Seller note seller@example.invalid", evidence_ids=(EVIDENCE_ID,)
                        ),
                    ),
                ),
            ),
            preferences=("Use private-name-canary for contact",),
            history_summaries=("Passport document 1234 private document body",),
        )
        fake = FakeTransport([successful()])
        result = await GeminiAdapter(configured(), fake).generate(
            source,
            Answer,
            budget=budget(),
            request_id=REQUEST_ID,
            private_values=("private-name-canary",),
        )
        sent = fake.requests[0].contents
        for forbidden in [
            "buyer@example.invalid",
            "seller@example.invalid",
            "+971 50 123 4567",
            FAKE_KEY,
            "private-name-canary",
            "private document body",
        ]:
            assert forbidden not in sent and forbidden not in result.diagnostic.model_dump_json()
        parsed = json.loads(sent)
        assert parsed["selected_ref"] == ref.model_dump()
        assert parsed["facts"][0]["claims"][0]["evidence_ids"] == [EVIDENCE_ID]
        assert "Show Mazda 3" in parsed["message"]

    asyncio.run(exercise())


def test_packet_rejects_contact_fields_and_incoherent_fact_states() -> None:
    with pytest.raises(ValidationError):
        EvidencePacket.model_validate({"message": "x", "session_revision": 0, "email": "private"})
    ref = InventoryRef(namespace="synthetic", snapshot_id="b" * 64, source_id="1")
    with pytest.raises(ValidationError):
        PacketFact(ref=ref, attribute="year", status="known")


def test_minimization_preserves_year_range_but_removes_reformatted_contacts() -> None:
    assert minimize_text("Cars from 2019-2021 please") == "Cars from 2019-2021 please"
    assert minimize_text("View on 2026-09-24") == "View on 2026-09-24"
    assert minimize_text("Only AED 55000-65000") == "Only AED 55000-65000"
    assert minimize_text("10000000", normalized_numeric=True) == "10000000"
    assert "971501234567" not in minimize_text("AED 971501234567", ("+971501234567",))
    for number in ("+971.50.123.4567", "+971/50/123/4567", "+971 50 123 4567"):
        assert number not in minimize_text("Contact " + number, ("+971501234567",))


def test_packet_byte_budget_rejects_without_silent_truncation() -> None:
    async def exercise() -> None:
        large = EvidencePacket(
            message="🚙" * 4000, source_context="🚙" * 4000, session_revision=0
        )
        fake = FakeTransport([])
        result = await GeminiAdapter(configured(), fake).generate(
            large, Answer, budget=budget(), request_id=REQUEST_ID
        )
        assert result.diagnostic.code == "input_too_large" and not fake.requests

    asyncio.run(exercise())


def test_tool_budget_is_shared_and_cannot_expand_provider_attempts() -> None:
    turn = TurnBudget(Timeouts(), 30, clock=lambda: 0)
    for _ in range(4):
        turn.begin_tool()
    with pytest.raises(BudgetExhausted):
        turn.begin_tool()
    assert turn.tool_invocations == 4 and turn.provider_attempts == 0


def test_caller_cannot_enlarge_the_configured_attempt_policy() -> None:
    async def exercise() -> None:
        settings = Settings(
            gemini_api_key=SecretStr(FAKE_KEY), timeouts=Timeouts(provider_attempts=1)
        )
        fake = FakeTransport([])
        result = await GeminiAdapter(settings, fake).generate(
            packet(), Answer, budget=budget(), request_id=REQUEST_ID
        )
        assert result.diagnostic.code == "unavailable" and not fake.requests

    asyncio.run(exercise())


def test_schema_embedding_escapes_reject_before_any_attempt() -> None:
    class EscapedSchemaAnswer(Answer):
        model_config = ConfigDict(
            extra="forbid",
            strict=True,
            json_schema_extra={"description": "\\" * (MAX_INPUT_TOKENS // 4)},
        )

    async def exercise() -> None:
        source = packet()
        raw_schema_bytes = json.dumps(
            EscapedSchemaAnswer.model_json_schema(),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        old_raw_estimate = (
            len(source.minimized_json().encode("utf-8"))
            + len(raw_schema_bytes)
            + len(SYSTEM_INSTRUCTION.encode())
            + len(REPAIR_INSTRUCTION.encode())
            + 1024
        )
        assert old_raw_estimate < MAX_INPUT_TOKENS
        fake = FakeTransport([])
        turn_budget = budget()
        result = await GeminiAdapter(configured(), fake).generate(
            source,
            EscapedSchemaAnswer,
            budget=turn_budget,
            request_id=REQUEST_ID,
        )
        assert result.diagnostic.code == "input_too_large"
        assert result.diagnostic.failure_phase == "schema"
        assert result.diagnostic.attempts == turn_budget.provider_attempts == 0
        assert not fake.requests

    asyncio.run(exercise())
