"""Focused metadata comparisons; injected stat APIs, real bounded file reads."""

import stat
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.operations import restore_completion as observer
from tests.support.harness import PROJECT


@pytest.mark.parametrize(
    "case",
    [
        "windows_stable",
        "path_change",
        "descriptor_change",
        "inode_change",
        "birthtime_change",
        "posix_ctime_change",
        "between_observations",
    ],
)
def test_receipt_metadata_consistency(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    directory = PROJECT / "Records/build/platform/P16R/receipt-stat-tests" / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "receipt.json"
    data = b'{"retained":"synthetic-stat-comparison"}'
    path.write_bytes(data)
    named_before = (10, 20, len(data), 30, 40)
    named_after = (10, 20, len(data), 30, 41 if case == "path_change" else 40)
    named = iter((named_before, named_after, named_before, named_after))
    monkeypatch.setattr(observer, "_receipt_identity", lambda _: next(named))

    def info(*, changed: bool = False) -> SimpleNamespace:
        return SimpleNamespace(
            st_mode=stat.S_IFREG,
            st_nlink=1,
            st_file_attributes=0,
            st_dev=10,
            st_ino=21 if case == "inode_change" else 20,
            st_size=len(data),
            st_mtime_ns=30,
            st_ctime_ns=51 if changed else 50,
            st_birthtime_ns=41 if case == "birthtime_change" else 40,
        )

    descriptors = iter(
        (
            info(),
            info(changed=case == "descriptor_change"),
            info(changed=True),
            info(changed=True),
        )
    )
    monkeypatch.setattr(
        observer,
        "os",
        SimpleNamespace(
            name="posix" if case == "posix_ctime_change" else "nt",
            fstat=lambda _: next(descriptors),
        ),
    )
    if case in {"windows_stable", "between_observations"}:
        result = observer._read_receipt(path)
        assert result.data == data and result.identity == named_before
        if case == "between_observations":
            later = observer._read_receipt(path)
            assert later.data == result.data and later.identity == result.identity
            assert later.handle_identity != result.handle_identity
            assert later != result
    else:
        with pytest.raises(
            observer.RestoreCompletionError, match="^RESTORE_COMPLETION_RECEIPT_CHANGED$"
        ):
            observer._read_receipt(path)
