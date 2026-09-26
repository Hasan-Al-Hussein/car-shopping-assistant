"""Offline provider shutdown/diagnostic cases; no real credentials or transport."""

import asyncio

import pytest

from app.assistant.provider import GeminiAdapter, ProviderResult, TransportRequest, TransportResponse
from app.core.config import CONFIGURATION_VERSION, Settings
from app.core.readiness import DependencySnapshot, ReadinessRegistry

from .test_provider import Answer, FakeTransport, REQUEST_ID, budget, configured, packet, successful


@pytest.mark.parametrize("settings,code", [
    (Settings(), "not_configured"), (Settings(assistant_enabled=False), "disabled"),
])
def test_no_transport_diagnostic_uses_the_actual_configuration_version(
    settings: Settings, code: str,
) -> None:
    async def exercise() -> None:
        transport = FakeTransport([])
        adapter = GeminiAdapter(settings, transport)
        result = await adapter.generate(packet(), Answer, budget=budget(), request_id=REQUEST_ID)
        assert result.diagnostic.configuration_version == CONFIGURATION_VERSION
        assert result.diagnostic.code == code and result.diagnostic.attempts == 0
        assert transport.requests == [] and not adapter.pending
        assert await adapter.close(timeout_seconds=0)

    asyncio.run(exercise())


def test_stop_is_sticky_and_idle_close_is_truthful() -> None:
    async def exercise() -> None:
        transport = FakeTransport([])
        adapter = GeminiAdapter(configured(), transport)
        adapter.stop()
        assert await adapter.close(timeout_seconds=0)
        result = await adapter.generate(packet(), Answer, budget=budget(), request_id=REQUEST_ID)
        assert result.diagnostic.code == "disabled" and result.diagnostic.attempts == 0
        assert result.proposal is None and transport.requests == [] and not adapter.pending

    asyncio.run(exercise())


class ResistantTransport:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.release = asyncio.Event()
        self.requests: list[TransportRequest] = []
        self.cancellations = 0

    async def generate(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        self.started.set()
        while not self.release.is_set():
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancellations += 1
                self.cancelled.set()
        return successful("Late result must be discarded.")


def test_close_tracks_resistant_transport_and_queued_calls_without_replacement() -> None:
    async def exercise() -> None:
        transport = ResistantTransport()
        registry = ReadinessRegistry(DependencySnapshot())
        before = registry.snapshot()
        adapter = GeminiAdapter(configured(), transport, readiness=registry)
        first = asyncio.create_task(adapter.generate(packet(), Answer, budget=budget(), request_id=REQUEST_ID))
        calls = [first]
        try:
            await asyncio.wait_for(transport.started.wait(), timeout=1)
            calls.append(asyncio.create_task(adapter.generate(packet(), Answer, budget=budget(), request_id=REQUEST_ID)))
            await asyncio.sleep(0)
            assert not await adapter.close(timeout_seconds=0.001)
            assert adapter.pending and transport.cancelled.is_set()
            assert not await adapter.close(timeout_seconds=0)
            assert transport.cancellations == 1 and len(transport.requests) == 1
        finally:
            transport.release.set()
            results = await asyncio.wait_for(asyncio.gather(*calls, return_exceptions=True), timeout=1)
        assert all(isinstance(result, ProviderResult) and result.proposal is None and result.diagnostic.code == "disabled" for result in results)
        assert registry.snapshot() == before
        assert await adapter.close(timeout_seconds=1)
        assert not adapter.pending and len(transport.requests) == 1

    asyncio.run(exercise())


def test_cooperative_cancellation_settles_before_successful_close() -> None:
    async def exercise() -> None:
        started = asyncio.Event()

        async def wait_until_cancelled() -> TransportResponse:
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("Unreachable without cancellation")

        transport = FakeTransport([wait_until_cancelled])
        adapter = GeminiAdapter(configured(), transport)
        call = asyncio.create_task(adapter.generate(packet(), Answer, budget=budget(), request_id=REQUEST_ID))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            assert await adapter.close(timeout_seconds=1)
        finally:
            call.cancel()
            outcomes = await asyncio.gather(call, return_exceptions=True)
        assert isinstance(outcomes[0], asyncio.CancelledError)
        assert not adapter.pending and len(transport.requests) == 1

    asyncio.run(exercise())


def test_departed_caller_does_not_hide_retained_transport_work() -> None:
    async def exercise() -> None:
        transport = ResistantTransport()
        adapter = GeminiAdapter(configured(), transport)
        call = asyncio.create_task(adapter.generate(packet(), Answer, budget=budget(), request_id=REQUEST_ID))
        try:
            await asyncio.wait_for(transport.started.wait(), timeout=1)
            call.cancel()
            departed = await asyncio.gather(call, return_exceptions=True)
            assert isinstance(departed[0], asyncio.CancelledError)
            assert adapter.pending
            assert not await adapter.close(timeout_seconds=0.001)
            assert adapter.pending and transport.cancellations == 2
        finally:
            transport.release.set()
            await asyncio.gather(call, return_exceptions=True)
            assert await adapter.close(timeout_seconds=1)
        assert not adapter.pending and len(transport.requests) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("timeout", [-1.0, 31.0, float("inf"), float("nan")])
def test_close_rejects_unbounded_waits(timeout: float) -> None:
    async def exercise() -> None:
        adapter = GeminiAdapter(configured(), FakeTransport([]))
        with pytest.raises(ValueError, match="PROVIDER_CLOSE_TIMEOUT_INVALID"):
            await adapter.close(timeout_seconds=timeout)

    asyncio.run(exercise())
