"""Bounded real Windows contenders; explicit fixture calls only, never import I/O."""

import multiprocessing
import os
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Literal, cast

from app.database.maintenance import MaintenanceBusy, MaintenanceError, exclusive_store_lease, shared_store_lease
from app.database.paths import RuntimeBoundary


def _contender(path: Path, boundary: RuntimeBoundary, exclusive: bool, pipe: Connection) -> None:
    try:
        scope = exclusive_store_lease if exclusive else shared_store_lease
        with scope(path, boundary=boundary):
            pipe.send("held")
            if not pipe.poll(10):
                raise AssertionError("CONTENDER_NOT_RELEASED")
            action = pipe.recv()
            if action == "crash":
                os._exit(0)  # Deliberate abrupt exit of this test-owned child only.
            if action != "release":
                raise AssertionError("CONTENDER_UNKNOWN_COMMAND")
        pipe.send("released")
    except MaintenanceBusy:
        pipe.send("busy")
    except MaintenanceError:
        pipe.send("unavailable")
    finally:
        pipe.close()


def receive(pipe: Connection) -> Literal["held", "released", "busy", "unavailable"]:
    assert pipe.poll(8), "CONTENDER_NO_RESPONSE"
    result = pipe.recv()
    assert result in {"held", "released", "busy", "unavailable"}
    return cast(Literal["held", "released", "busy", "unavailable"], result)


@contextmanager
def contender(
    path: Path, boundary: RuntimeBoundary, *, exclusive: bool,
) -> Iterator[tuple[multiprocessing.Process, Connection, str]]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_contender, args=(path, boundary, exclusive, child))
    process.start()
    child.close()
    try:
        state = receive(parent)
        yield process, parent, state
        if state == "held" and process.is_alive():
            parent.send("release")
            assert receive(parent) == "released"
        process.join(3)
        assert not process.is_alive()
        assert process.exitcode == 0
    finally:
        # Only this test-owned child may be stopped; no global process cleanup.
        if process.is_alive():
            process.terminate()
            process.join(3)
        parent.close()
        process.close()


def exclusion_state(path: Path, boundary: RuntimeBoundary, *, exclusive: bool = True) -> str:
    with contender(path, boundary, exclusive=exclusive) as (_, _, state):
        return state
