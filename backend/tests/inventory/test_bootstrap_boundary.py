"""CLI admission keeps raw path text until validation, before any bootstrap work."""

import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType

import pytest

from app.database.paths import RuntimeBoundary
from tests.support.harness import PROJECT, runtime_environment


@pytest.fixture
def bootstrap_cli(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(PROJECT))
    module = import_module("scripts.bootstrap_inventory")
    boundary = RuntimeBoundary(Path(r"C:\bootstrap-inert"), Path(r"C:\bootstrap-inert"))
    for name, value in runtime_environment(boundary).items():
        monkeypatch.setenv(name, value)
    return module


@pytest.mark.parametrize(
    "suffix",
    [
        r"stores\.\instance.sqlite3",
        r"stores\..\stores\instance.sqlite3",
        r"stores.\instance.sqlite3",
        "stores \\instance.sqlite3",
        r"stores\instance.sqlite3:stream",
    ],
    ids=["dot", "parent", "trailing-dot", "trailing-space", "stream"],
)
def test_raw_cli_path_rejected_before_bootstrap(
    bootstrap_cli: ModuleType, monkeypatch: pytest.MonkeyPatch, suffix: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("REJECTED_RAW_PATH_REACHED_BOOTSTRAP")

    monkeypatch.setattr(bootstrap_cli, "bootstrap_inventory", forbidden)
    monkeypatch.setattr(bootstrap_cli, "initialize_runtime_root", forbidden)
    monkeypatch.setattr(bootstrap_cli, "_evidence_destination", forbidden)
    monkeypatch.setattr(bootstrap_cli, "initialize_store", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(sys, "argv", [
        "bootstrap_inventory", "--destination", "C:\\bootstrap-inert\\" + suffix,
        "--evidence-directory", str(PROJECT / "Records/build/BE-05/I7/runs/inert-cli"),
        "--initialize-runtime-root",
    ])
    assert bootstrap_cli.main() == 1
    assert '"status": "BOOTSTRAP_FAILED"' in capsys.readouterr().out


@pytest.mark.parametrize("initialize", [False, True])
def test_cli_passes_captured_boundary_and_explicit_flag(
    bootstrap_cli: ModuleType, monkeypatch: pytest.MonkeyPatch, initialize: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: list[tuple[Path, RuntimeBoundary, bool]] = []

    def intercept(
        destination: Path, *, boundary: RuntimeBoundary, evidence_directory: Path,
        disposable_fixture: bool, initialize_runtime: bool,
    ) -> None:
        captured.append((destination, boundary, initialize_runtime))
        assert not disposable_fixture
        raise RuntimeError("STOP_BEFORE_BOOTSTRAP_IO")

    monkeypatch.setattr(bootstrap_cli, "bootstrap_inventory", intercept)
    raw = r"C:\bootstrap-inert\stores\instance.sqlite3"
    arguments = [
        "bootstrap_inventory", "--destination", raw, "--evidence-directory",
        str(PROJECT / "Records/build/BE-05/I7/runs/inert-cli"),
    ]
    if initialize:
        arguments.append("--initialize-runtime-root")
    monkeypatch.setattr(sys, "argv", arguments)
    assert bootstrap_cli.main() == 1
    assert captured == [(
        Path(raw), RuntimeBoundary(Path(r"C:\bootstrap-inert"), Path(r"C:\bootstrap-inert")),
        initialize,
    )]
    assert '"status": "BOOTSTRAP_FAILED"' in capsys.readouterr().out
