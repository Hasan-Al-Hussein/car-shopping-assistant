import asyncio
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.assistant.evaluation.transports import LimitedLiveTransport, LivePermission
from app.assistant.evaluation.effects import DomainSnapshot, MODELS, project_effects
from app.assistant.evaluation.runner import ReportWriter, budget_exhausted, evaluate
from app.assistant.evaluation.schema import Corpus, Step, StepResult
from app.assistant.evaluation.judging import judge
from app.assistant.provider import ProviderFault, TransportRequest, TransportResponse
from app.core.config import Settings
from app.runtime_app import ApplicationComposition


class OfflineDelegate:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: TransportRequest) -> TransportResponse:
        self.calls += 1
        return TransportResponse("synthetic")


def test_live_permission_defaults_disabled_and_requires_every_condition() -> None:
    permission = LivePermission(access_evidence_sha256="a" * 64)
    settings = Settings(gemini_api_key=SecretStr("synthetic-never-live"))
    with pytest.raises(ValueError, match="LIVE_EVALUATION_NOT_AUTHORIZED"):
        permission.require(settings)
    for changes in ({"enabled": True}, {"approved_free_only": True}):
        with pytest.raises(ValueError, match="LIVE_EVALUATION_NOT_AUTHORIZED"):
            permission.model_copy(update=changes).require(settings)
    approved = permission.model_copy(update={"enabled": True, "approved_free_only": True})
    with pytest.raises(ValueError, match="LIVE_EVALUATION_NOT_AUTHORIZED"):
        approved.require(Settings())
    approved.require(settings)


def test_call_cap_counts_actual_attempts_including_repair_without_fallback() -> None:
    async def exercise() -> None:
        delegate = OfflineDelegate()
        transport = LimitedLiveTransport(delegate, 1)
        await transport.generate(TransportRequest(contents="synthetic", schema={}))
        with pytest.raises(ProviderFault) as error:
            await transport.generate(TransportRequest(contents="synthetic", schema={}, repair=True))
        assert error.value.code == "attempt_limit"
        assert delegate.calls == transport.calls == 1
        assert transport.refused == 1

    asyncio.run(exercise())


def test_budget_boundary_preserves_zero_provider_actions() -> None:
    transport = LimitedLiveTransport(OfflineDelegate(), 1, calls=1)
    corpus = Corpus.model_validate_json((Path(__file__).resolve().parents[4]
        / "fixtures/assistant/evaluation/corpus-v1.json").read_bytes())
    message = corpus.cases[0].steps[0]
    assert budget_exhausted(transport, message)
    for kind in ("replay", "new_session", "confirm", "foreign_owner"):
        assert not budget_exhausted(transport, message.model_copy(update={"kind": kind}))


@pytest.mark.parametrize("case_id,refuse_repair,unsafe_change", [
    ("A11-008", False, False), ("A11-035", True, False), ("A11-035", True, True),
])
def test_live_budget_exhaustion_retains_unrun_expectations_and_checks_actual_safety(
    monkeypatch: pytest.MonkeyPatch, case_id: str, refuse_repair: bool, unsafe_change: bool,
) -> None:
    project = Path(__file__).resolve().parents[4]
    path = project / "fixtures/assistant/evaluation/corpus-v1.json"
    corpus = Corpus.model_validate_json(path.read_bytes())
    delegate = OfflineDelegate()
    transport = LimitedLiveTransport(delegate, 1)
    performed: list[int] = []

    class OrchestrationControl:
        # This synthetic control tests runner scheduling only, never corpus/domain quality.
        async def shutdown(self) -> bool:
            return True

    class DriverControl:
        def __init__(self, *args: Any) -> None:
            pass

        async def actor(self) -> object:
            return object()

        async def perform(self, actor: object, step: Step, index: int) -> StepResult:
            performed.append(index)
            await transport.generate(TransportRequest(contents="synthetic", schema={}))
            if refuse_repair:
                with pytest.raises(ProviderFault):
                    await transport.generate(TransportRequest(contents="synthetic", schema={}, repair=True))
                before = DomainSnapshot({name: {} for name in MODELS}, {name: {} for name in MODELS})
                after = DomainSnapshot({name: {} for name in MODELS}, {name: {} for name in MODELS})
                if unsafe_change:
                    after.owned["preferences"]["unexpected-identity"] = "unexpected-row"
                observed = project_effects(before, after)
                return StepResult(index=index, kind=step.kind, synthetic_input="REFUSAL CONTROL",
                    verdict="FAIL", observed=observed,
                    assertions=[judge(item, observed) for item in step.assertions])
            return StepResult(index=index, kind=step.kind, synthetic_input="SCHEDULING CONTROL",
                verdict="PASS", assertions=[judge(item, {"value": item.expected})
                    for original in step.assertions
                    for item in [original.model_copy(update={"path": "value"})]])

    monkeypatch.setattr("app.assistant.evaluation.runner.ServiceDriver", DriverControl)
    monkeypatch.setattr("app.assistant.evaluation.runner.identities", lambda *args: {
        "case_ids": [case.id for case in corpus.cases], "corpus_review_status": "SOURCE_REVIEWED",
        "fixture": "scheduling-unit-control-not-model-or-domain-evidence",
    })
    writer = ReportWriter(project / "Records/build/BE-24/control-runs" / str(uuid4()))
    result = asyncio.run(evaluate(cast(ApplicationComposition, OrchestrationControl()), corpus,
        project=project, corpus_path=path, oracle={}, writer=writer, mode="live_synthetic",
        transport=transport, selected={case_id}, access_evidence_sha256="a" * 64))
    case = next(item for item in result.cases if item.case_id == case_id)
    assert performed == [0] and transport.calls == delegate.calls == 1
    assert transport.refused == int(refuse_repair)
    if not refuse_repair:
        assert case.steps[0].verdict == "PASS" and case.steps[1].verdict == "NOT_RUN"
        assert case.reason == case.steps[1].safe_error == "LIVE_CALL_BUDGET_EXHAUSTED"
        assert case.steps[1].elapsed_ms is None
    else:
        assert case.steps[0].safe_error == "LIVE_CALL_BUDGET_EXHAUSTED"
        assert case.steps[0].verdict == ("FAIL" if unsafe_change else "NOT_RUN")
        successful_insert_expectation = next(item for item in case.steps[0].assertions if item.path == "effects")
        assert successful_insert_expectation.verdict == "NOT_RUN"
        assert isinstance(successful_insert_expectation.expected, dict)
        assert successful_insert_expectation.expected["preferences"] == 1
    assert result.gate == ("FAIL" if unsafe_change else "INCOMPLETE")
    assert bool(result.critical_failures) == unsafe_change
    assert result.live_quality == "HUMAN_REVIEW_REQUIRED"
