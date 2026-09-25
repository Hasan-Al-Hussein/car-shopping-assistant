"""One bounded local read/persistence task at a time; late work cannot fan out."""

import asyncio
from collections.abc import Awaitable, Callable

from app.api.schemas.common import ErrorCode
from app.core.errors import ApiFailure

from .budget import BudgetExhausted, TurnBudget


class CallGate:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def run[T](
        self,
        call: Callable[[], Awaitable[T]],
        budget: TurnBudget,
        *,
        tool: bool = False,
        persistence: bool = False,
    ) -> T:
        """Admission/completion use time but are not model-requested domain tools.

        The trusted facade must enforce the same deadline in any worker it owns. Timeout
        does not mean a write rolled back. Keep the gate until cancelled work actually exits.
        """
        code: ErrorCode = "OPERATION_UNRESOLVED" if persistence else "PROVIDER_TIMEOUT"
        if budget.remaining() <= 0:
            raise ApiFailure(code)
        try:
            await asyncio.wait_for(self._lock.acquire(), budget.remaining())
        except TimeoutError:
            raise ApiFailure(code) from None
        try:
            if tool:
                budget.begin_tool()
            if budget.remaining() <= 0:
                raise BudgetExhausted

            async def invoke() -> T:
                return await call()

            task = asyncio.create_task(invoke())
        except BaseException:
            self._lock.release()
            raise

        def finished(completed: asyncio.Task[T]) -> None:
            self._lock.release()
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(finished)
        try:
            # Inventory facade also receives the caller's absolute deadline; this gate
            # independently caps latency and does not wait forever for cancellation.
            wait = min(budget.remaining(), 2 if tool else budget.timeouts.read_seconds)
            started = budget.clock()
            done, _ = await asyncio.wait({task}, timeout=wait)
            if not done:
                task.cancel()
                raise ApiFailure(code)
            if budget.remaining() <= 0 or budget.clock() - started >= wait:
                raise ApiFailure(code)
            return task.result()
        except asyncio.CancelledError:
            task.cancel()
            raise
