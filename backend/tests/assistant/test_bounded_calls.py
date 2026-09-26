"""Deadline/cancellation contract checks without network, database or threads."""

import asyncio

import pytest

from app.assistant.bounded_calls import CallGate
from app.assistant.budget import TurnBudget
from app.core.config import Settings
from app.core.errors import ApiFailure


def test_late_result_is_not_accepted_even_when_task_finishes() -> None:
    async def exercise() -> None:
        now = [0.0]
        ledger = TurnBudget(Settings().timeouts, 30.0, clock=lambda: now[0])

        async def late() -> str:
            now[0] = 3.0
            return "late-result"

        with pytest.raises(ApiFailure, match="PROVIDER_TIMEOUT"):
            await CallGate().run(late, ledger, tool=True)
        assert ledger.tool_invocations == 1

    asyncio.run(exercise())


def test_cancellation_resistant_work_retains_gate_and_cannot_fan_out() -> None:
    async def exercise() -> None:
        gate = CallGate()
        stopped, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        calls: list[str] = []

        async def stubborn() -> None:
            calls.append("first")
            try:
                await asyncio.Future[None]()
            except asyncio.CancelledError:
                stopped.set()
                await release.wait()
            finally:
                finished.set()

        async def forbidden() -> None:
            calls.append("second")

        def short() -> TurnBudget:
            return TurnBudget(Settings().timeouts, asyncio.get_running_loop().time() + 0.05)

        try:
            with pytest.raises(ApiFailure, match="PROVIDER_TIMEOUT"):
                await gate.run(stubborn, short(), tool=True)
            await asyncio.wait_for(stopped.wait(), 1)
            second = short()
            with pytest.raises(ApiFailure, match="PROVIDER_TIMEOUT"):
                await gate.run(forbidden, second, tool=True)
            assert calls == ["first"] and second.tool_invocations == 0
        finally:
            release.set()
            await asyncio.wait_for(finished.wait(), 1)
            await asyncio.sleep(0)  # Allow the done callback to release its retained gate.

    asyncio.run(exercise())


def test_expired_persistence_has_unknown_outcome_code_without_starting_work() -> None:
    async def exercise() -> None:
        invoked = False

        async def write() -> None:
            nonlocal invoked
            invoked = True

        expired = TurnBudget(Settings().timeouts, asyncio.get_running_loop().time() - 1)
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            await CallGate().run(write, expired, persistence=True)
        assert not invoked

    asyncio.run(exercise())
