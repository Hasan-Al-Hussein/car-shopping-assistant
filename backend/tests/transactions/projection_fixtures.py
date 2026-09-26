"""Disposable real canonical Store/lead saves; no real inventory or provider calls.

Requires the coordinated portable Store/harness patch. Each fixture has its own
physical exports directory under the explicitly configured test-stores boundary.
No project-wide exports file is touched and fixture evidence is retained.
"""

import csv
import ctypes
import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.leads import LeadRecord, LeadValues
from app.database.models import Booking, CommandReceipt, ExportIntent, ExportState, Lead
from app.database.paths import RuntimeBoundary, initialize_runtime_root
from app.database.store import Store
from app.leads.projection import CsvProjector
from app.leads.projection_files import CSV_NAME, MANIFEST_NAME, ProjectionFiles
from tests.support.harness import configured_runtime_boundary, runtime_environment
from tests.transactions.lead_fixtures import (
    LeadHarness,
    buyer_values,
    correction,
    make_lead_harness,
    save_request,
)


@dataclass
class ProjectionHarness:
    leads: LeadHarness
    projector: CsvProjector
    files: ProjectionFiles

    @property
    def store(self) -> Store:
        return self.leads.sessions.store

    def save(self, who: int = 0, *, email: str | None = None) -> LeadRecord:
        values = buyer_values().model_dump(mode="json")
        if email is not None:
            values["email"] = {"state": "provided", "value": email}
        return self.leads.service.save(
            self.leads.sessions.context(who),
            save_request(self.leads.session_ids[who], LeadValues.model_validate(values)),
        ).lead

    def revise(self, who: int = 0, *, text: str = "Revised requirements") -> LeadRecord:
        current = self.leads.service.get(self.leads.sessions.context(who, write=False))
        assert isinstance(current, LeadRecord)
        values = current.values.model_dump(mode="json")
        values["requirements"] = [text]
        return self.leads.service.update(
            self.leads.sessions.context(who),
            current.lead_id,
            correction(
                self.leads.session_ids[who], current.revision, LeadValues.model_validate(values)
            ),
        ).lead

    def rows(self) -> list[dict[str, str]]:
        data = self.files.path(CSV_NAME).read_bytes()
        assert data.startswith(b"\xef\xbb\xbf")
        return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))

    def publication(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(self.files.path(MANIFEST_NAME).read_bytes())
        return value

    def metadata(self) -> tuple[str, int, int | None, tuple[tuple[int, str], ...]]:
        def read(db: Session) -> tuple[str, int, int | None, tuple[tuple[int, str], ...]]:
            state = db.get(ExportState, 1)
            assert state is not None
            intents = tuple(
                (row.projection_version, row.state)
                for row in db.scalars(
                    select(ExportIntent).order_by(ExportIntent.projection_version)
                )
            )
            return state.state, state.canonical_version, state.exported_version, intents

        return self.store.read(read)

    def canonical_facts(self) -> tuple[tuple[dict[str, Any], ...], ...]:
        def read(db: Session) -> tuple[tuple[dict[str, Any], ...], ...]:
            return tuple(
                tuple(dict(row) for row in db.execute(select(model.__table__)).mappings())
                for model in (Lead, Booking, CommandReceipt)
            )

        return self.store.read(read)


def make_projection_harness(
    monkeypatch: pytest.MonkeyPatch,
    *,
    boundary: RuntimeBoundary | None = None,
) -> ProjectionHarness:
    if boundary is None:
        configured = configured_runtime_boundary()
        root = configured.physical_root / "test-stores" / ("be19-" + str(uuid4())) / "runtime"
        boundary = RuntimeBoundary(root, root)
    initialize_runtime_root(boundary)
    for key, value in runtime_environment(boundary).items():
        monkeypatch.setenv(key, value)
    leads = make_lead_harness()
    projector = CsvProjector(leads.sessions.store, clock=leads.sessions.clock.now)
    return ProjectionHarness(leads, projector, ProjectionFiles(leads.sessions.store))


@contextmanager
def deny_replacement(path: Path) -> Iterator[None]:
    """Real Windows open handle without FILE_SHARE_DELETE; always close it."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create.restype = ctypes.c_void_p
    close = kernel.CloseHandle
    close.argtypes, close.restype = [ctypes.c_void_p], ctypes.c_int
    handle = create(str(path), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        if not close(handle):
            raise ctypes.WinError(ctypes.get_last_error())
