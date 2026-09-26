"""Default tests are offline. Real integration grants must explicitly override this fixture."""

import httpx
import pytest

from tests.support.harness import FrozenClock, OwnerSpec, new_clock, owner_specs


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("LIVE_NETWORK_DISABLED_IN_UNIT_TESTS")

    async def async_denied(*args: object, **kwargs: object) -> None:
        denied(*args, **kwargs)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", denied)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_denied)


@pytest.fixture
def clock() -> FrozenClock:
    return new_clock()


@pytest.fixture
def owners() -> tuple[OwnerSpec, OwnerSpec]:
    return owner_specs()
