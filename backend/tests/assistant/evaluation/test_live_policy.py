"""Offline controls for live-run admission; no live provider or quality evidence."""

import asyncio
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from app.assistant.evaluation.runner import ReportWriter, evaluate, live_stop_reason
from app.assistant.evaluation.schema import Assertion, AssertionResult, Corpus, Step, StepResult
from app.assistant.evaluation.transports import LimitedLiveTransport
from app.assistant.provider import FailureCode, ProviderFault, TransportRequest, TransportResponse
from app.runtime_app import ApplicationComposition


class Clock:
    def __init__(self) -> None:
        self.value = 0.0
        self.waits: list[float] = []

    def now(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.value += seconds


class Delegate:
    def __init__(self, clock: Clock, fault: FailureCode | None = None) -> None:
        self.clock, self.fault = clock, fault
        self.calls: list[tuple[float, TransportRequest]] = []

    async def generate(self, request: TransportRequest) -> TransportResponse:
        self.calls.append((self.clock.now(), request))
        if self.fault is not None:
            raise ProviderFault(self.fault)
        return TransportResponse("synthetic")


def test_initial_and_repair_attempts_are_paced_inside_original_deadlines() -> None:
    async def exercise() -> None:
        clock = Clock()
        delegate = Delegate(clock)
        transport = LimitedLiveTransport(delegate, 3, clock=clock.now, sleep=clock.sleep)
        await transport.generate(TransportRequest(contents="synthetic", schema={}))
        await transport.generate(TransportRequest(contents="synthetic", schema={}, repair=True))
        await transport.generate(TransportRequest(
            contents="synthetic", schema={}, attempt_seconds=8, connect_seconds=5,
        ))
        assert [at for at, _ in delegate.calls] == [0, 6, 12]
        assert [request.attempt_seconds for _, request in delegate.calls] == [15, 9, 2]
        assert [request.connect_seconds for _, request in delegate.calls] == [5, 5, 2]
        assert delegate.calls[1][1].repair is True
        assert clock.waits == [6, 6]
        assert transport.calls == 3 and transport.refused == 0

    asyncio.run(exercise())


@pytest.mark.parametrize("fault", ["quota", "auth", "model_missing"])
def test_access_failure_latches_before_any_later_delegate(fault: FailureCode) -> None:
    async def exercise() -> None:
        clock = Clock()
        delegate = Delegate(clock, fault)
        transport = LimitedLiveTransport(delegate, 86, clock=clock.now, sleep=clock.sleep)
        with pytest.raises(ProviderFault) as first:
            await transport.generate(TransportRequest(contents="synthetic", schema={}))
        assert first.value.code == fault
        with pytest.raises(ProviderFault) as second:
            await transport.generate(TransportRequest(contents="synthetic", schema={}, repair=True))
        assert second.value.code == "attempt_limit"
        assert transport.stop_reason() == f"LIVE_PROVIDER_{fault.upper()}"
        assert transport.calls == len(delegate.calls) == 1 and transport.refused == 1
        assert clock.waits == []

    asyncio.run(exercise())


@pytest.mark.parametrize("remaining,reason", [
    (5, "LIVE_TIME_BUDGET_EXHAUSTED"),
    (1500, "LIVE_PACING_EXCEEDS_ATTEMPT_DEADLINE"),
])
def test_no_delegate_when_pacing_cannot_fit_existing_time_budget(
    remaining: int, reason: str,
) -> None:
    async def exercise() -> None:
        clock = Clock()
        delegate = Delegate(clock)
        transport = LimitedLiveTransport(
            delegate, 86, max_seconds=remaining, clock=clock.now, sleep=clock.sleep,
        )
        await transport.generate(TransportRequest(contents="synthetic", schema={}))
        with pytest.raises(ProviderFault):
            await transport.generate(TransportRequest(
                contents="synthetic", schema={}, attempt_seconds=5,
            ))
        assert transport.stop_reason() == reason
        assert transport.calls == len(delegate.calls) == 1 and transport.refused == 1
        assert clock.waits == []

    asyncio.run(exercise())


def test_time_exhaustion_stops_even_zero_provider_steps() -> None:
    clock = Clock()
    transport = LimitedLiveTransport(
        Delegate(clock), 86, max_seconds=1, clock=clock.now, sleep=clock.sleep,
    )
    step = Step(kind="new_session", prose_mode="no_result", assertions=[
        Assertion(name="new session control", path="new_session", expected=True),
    ])
    clock.value = 2
    assert live_stop_reason(transport, step) == "LIVE_TIME_BUDGET_EXHAUSTED"


@pytest.mark.parametrize("fault", ["quota", "auth", "model_missing"])
def test_evaluator_preserves_performed_failure_and_stops_later_cases(
    monkeypatch: pytest.MonkeyPatch, fault: FailureCode,
) -> None:
    project = Path(__file__).resolve().parents[4]
    path = project / "fixtures/assistant/evaluation/corpus-v1.json"
    corpus = Corpus.model_validate_json(path.read_bytes())
    clock = Clock()
    delegate = Delegate(clock, fault)
    transport = LimitedLiveTransport(delegate, 86, clock=clock.now, sleep=clock.sleep)
    performed: list[int] = []
    actors: list[object] = []

    class CompositionControl:
        async def shutdown(self) -> bool:
            return True

    class DriverControl:
        def __init__(self, *args: Any) -> None:
            pass

        async def actor(self) -> object:
            actor = object()
            actors.append(actor)
            return actor

        async def perform(self, actor: object, step: Step, index: int) -> StepResult:
            performed.append(index)
            with pytest.raises(ProviderFault):
                await transport.generate(TransportRequest(contents="synthetic", schema={}))
            return StepResult(
                index=index, kind=step.kind, synthetic_input="OFFLINE SCHEDULING CONTROL",
                verdict="FAIL", assertions=[AssertionResult(
                    name="actual unavailable control retained", path="state",
                    expected="answered", observed="provider_unavailable", verdict="FAIL",
                )],
            )

    monkeypatch.setattr("app.assistant.evaluation.runner.ServiceDriver", DriverControl)
    monkeypatch.setattr("app.assistant.evaluation.runner.identities", lambda *args: {
        "case_ids": [case.id for case in corpus.cases],
        "corpus_review_status": "SOURCE_REVIEWED",
        "fixture": "offline-scheduling-control-not-provider-quality",
    })
    writer = ReportWriter(project / "Records/build/BE-24/control-runs" / str(uuid4()))
    result = asyncio.run(evaluate(
        cast(ApplicationComposition, CompositionControl()), corpus, project=project,
        corpus_path=path, oracle={}, writer=writer, mode="live_synthetic", transport=transport,
        selected={"A11-001", "A11-002"}, access_evidence_sha256="a" * 64,
    ))
    first, second = result.cases[:2]
    assert first.verdict == first.steps[0].verdict == "FAIL"
    assert first.steps[0].assertions[0].observed == "provider_unavailable"
    assert second.verdict == "NOT_RUN" and second.reason == f"LIVE_PROVIDER_{fault.upper()}"
    assert len(actors) == 1 and performed == [0]
    assert result.identities["provider_delegate_calls"] == 1
    assert result.identities["provider_refused_admissions"] == 0
    assert result.identities["provider_stop_reason"] == second.reason
    assert result.gate == "FAIL" and result.live_quality == "HUMAN_REVIEW_REQUIRED"
    assert result.cleanup == "SETTLED" and len(result.cases) == 46
