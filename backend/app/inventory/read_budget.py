"""Monotonic caller budget, checked at integrity-safe boundaries."""

import math
from time import monotonic

from app.core.errors import ApiFailure


def read_deadline(deadline_at: float | None, *, seconds: float) -> float:
    if deadline_at is not None and (
        type(deadline_at) not in {int, float} or not math.isfinite(deadline_at)
    ):
        raise ApiFailure("VALIDATION_ERROR")
    local = monotonic() + seconds
    return local if deadline_at is None else min(local, deadline_at)


def check_deadline(deadline: float) -> None:
    if monotonic() >= deadline:
        raise ApiFailure("STORE_UNAVAILABLE")
