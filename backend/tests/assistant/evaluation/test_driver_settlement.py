"""Observe late service settlement without retrying an action or renewing its budget."""

import asyncio
from pathlib import Path
from threading import Event
from time import monotonic
from types import SimpleNamespace
from typing import cast

import pytest

from app.assistant.evaluation import driver as module
from app.assistant.evaluation.diagnostics import provider_metric_metadata, safe_exception
from app.assistant.evaluation.driver import ServiceDriver
from app.assistant.evaluation.schema import Corpus
from app.assistant.service_adapters import BoundedServiceWorker
from app.core.diagnostics import ProviderMetric, ProviderUsage
from app.core.errors import ApiFailure
from app.runtime_app import ApplicationComposition


def make_driver(worker: object) -> ServiceDriver:
    composition = cast(ApplicationComposition, SimpleNamespace(worker=worker))
    return ServiceDriver(composition, cast(Corpus, None), {}, None)


def test_late_action_is_observed_once_after_original_timeout() -> None:
    async def exercise() -> None:
        worker = BoundedServiceWorker()
        release = Event()
        actions: list[str] = []
        observations: list[str] = []

        def action() -> None:
            assert release.wait(2)
            actions.append("original")

        def observe() -> tuple[str, ...]:
            observations.append("read")
            return tuple(actions)

        try:
            with pytest.raises(ApiFailure) as failure:
                await worker.run(action, deadline_at=monotonic() + 0.05, persistence=True)
            assert failure.value.code == "OPERATION_UNRESOLVED"
            assert worker.pending and actions == []
            asyncio.get_running_loop().call_later(0.025, release.set)
            assert await make_driver(worker).read(observe) == ("original",)
            assert actions == ["original"] and observations == ["read"]
            assert failure.value.code == "OPERATION_UNRESOLVED"
        finally:
            release.set()
            limit = monotonic() + 2
            while worker.pending and monotonic() < limit:
                await asyncio.sleep(0.01)
            assert worker.close()

    asyncio.run(exercise())


def test_busy_observation_has_one_fixed_budget_and_never_submits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BusyWorker:
        pending = True

        async def run(self, *args: object, **kwargs: object) -> None:
            pytest.fail("Observation must not be submitted while the original call is busy")

    now = [100.0]
    sleeps: list[float] = []

    async def sleep(duration: float) -> None:
        assert 0 < duration <= 0.01
        sleeps.append(duration)
        now[0] += duration

    monkeypatch.setattr(module, "monotonic", lambda: now[0])
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    with pytest.raises(ApiFailure) as failure:
        asyncio.run(make_driver(BusyWorker()).read(lambda: pytest.fail("not submitted")))
    assert failure.value.code == "STORE_BUSY"
    assert now[0] == pytest.approx(105.0)
    assert sum(sleeps) == pytest.approx(5.0)


def test_safe_diagnostic_retains_only_allowlisted_api_code(tmp_path: Path) -> None:
    failure = ApiFailure("STORE_BUSY")
    failure.args = ("synthetic-private-value",)
    diagnostic = safe_exception(failure, tmp_path)
    assert diagnostic == {
        "exception_type": "ApiFailure",
        "repository_frames": [],
        "error_code": "STORE_BUSY",
    }
    failure.code = "synthetic-private-value"  # type: ignore[assignment]
    assert safe_exception(failure, tmp_path)["error_code"] == "INTERNAL_ERROR"


def test_provider_projection_distinguishes_absent_success_and_safe_failure() -> None:
    base = {
        "request_id": "10000000-0000-4000-8000-000000000001",
        "attempts": 1,
        "elapsed_ms": 100,
        "usage": ProviderUsage(),
    }
    success = ProviderMetric(**base, state="available", code=None)
    failure = ProviderMetric(
        **base, state="unavailable", code="unavailable",
        failure_phase="sdk_response", http_status=503,
    )
    assert provider_metric_metadata(None) is None
    assert provider_metric_metadata(success) == {
        "code": None, "failure_phase": None, "http_status": None,
    }
    assert provider_metric_metadata(failure) == {
        "code": "unavailable", "failure_phase": "sdk_response", "http_status": 503,
    }
