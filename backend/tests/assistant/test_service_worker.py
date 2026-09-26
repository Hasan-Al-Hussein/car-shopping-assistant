"""Real bounded-thread lifetime checks; no Store/provider/network in these cases."""

import asyncio
from collections.abc import Callable
from threading import Event
from time import monotonic

import pytest

from app.assistant.service_adapters import BoundedServiceWorker
from app.core.errors import ApiFailure


async def until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.005)


@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("late_error", [False, True])
def test_abandoned_caller_keeps_shared_capacity_until_real_settlement(
    cancel: bool, late_error: bool
) -> None:
    worker, started, release = BoundedServiceWorker(), Event(), Event()
    calls: list[str] = []

    def blocked() -> str:
        calls.append("original")
        started.set()
        assert release.wait(5)
        if late_error:
            raise ValueError("SYNTHETIC_LATE_ERROR")
        return "late result"

    async def exercise() -> None:
        task = asyncio.create_task(worker.run(blocked, deadline_at=monotonic() + 0.1))
        try:
            await until(started.is_set)
            if cancel:
                task.cancel()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                with pytest.raises(ApiFailure, match="PROVIDER_TIMEOUT"):
                    await task
            assert worker.pending and calls == ["original"]
            for _ in range(3):
                with pytest.raises(ApiFailure, match="STORE_BUSY"):
                    await worker.run(lambda: calls.append("forbidden"), deadline_at=monotonic() + 1)
            assert calls == ["original"]
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            await until(lambda: not worker.pending)
        assert await worker.run(lambda: "next", deadline_at=monotonic() + 1) == "next"

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        assert worker.close()


def test_close_during_work_prevents_replacement_and_reports_pending() -> None:
    worker, started, release = BoundedServiceWorker(), Event(), Event()

    def blocked() -> None:
        started.set()
        assert release.wait(5)

    async def exercise() -> None:
        task = asyncio.create_task(worker.run(blocked, deadline_at=monotonic() + 2))
        try:
            await until(started.is_set)
            assert worker.close() is False and worker.pending
            with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
                await worker.run(lambda: None, deadline_at=monotonic() + 1)
        finally:
            release.set()
            await task
            await until(lambda: not worker.pending)
        assert worker.close() is True

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        asyncio.run(until(lambda: not worker.pending))
        assert worker.close()


def test_expired_closed_and_submission_failure_never_leave_reserved_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = BoundedServiceWorker()
    calls: list[str] = []

    def rejected(*args: object, **kwargs: object) -> None:
        raise RuntimeError("SYNTHETIC_SUBMISSION_FAILURE")

    async def exercise() -> None:
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            await worker.run(
                lambda: calls.append("expired"), deadline_at=monotonic() - 1, persistence=True
            )
        with monkeypatch.context() as patch:
            patch.setattr(worker._executor, "submit", rejected)
            with pytest.raises(RuntimeError, match="SYNTHETIC_SUBMISSION_FAILURE"):
                await worker.run(lambda: None, deadline_at=monotonic() + 1)
        assert not worker.pending and calls == []
        # Fast completion exercises callback registration when a Future may already be done.
        for _ in range(10):
            assert await worker.run(lambda: 7, deadline_at=monotonic() + 1) == 7
        assert worker.close()
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            await worker.run(
                lambda: calls.append("closed"), deadline_at=monotonic() + 1, persistence=True
            )
        assert calls == []

    try:
        asyncio.run(exercise())
    finally:
        assert worker.close()


def test_settlement_does_not_require_the_abandoned_event_loop() -> None:
    worker, started, release, finished = BoundedServiceWorker(), Event(), Event(), Event()

    def blocked() -> None:
        started.set()
        assert release.wait(5)
        finished.set()
        raise ValueError("LATE_AFTER_LOOP_CLOSED")

    async def abandon() -> None:
        task = asyncio.create_task(worker.run(blocked, deadline_at=monotonic() + 2))
        await until(started.is_set)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert worker.pending

    try:
        asyncio.run(abandon())
    finally:
        release.set()
        assert finished.wait(5)
        asyncio.run(until(lambda: not worker.pending))
        assert worker.close()
