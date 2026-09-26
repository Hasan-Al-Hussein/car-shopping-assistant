"""Fresh offline fixture for the observed Q06 reset failure; no provider network."""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr
from scripts.bootstrap_inventory import BootstrapInputs

from app.assistant.evaluation.diagnostics import safe_exception
from app.assistant.evaluation.runner import ReportWriter, evaluate, load_oracle
from app.assistant.evaluation.schema import Corpus
from app.assistant.evaluation.transports import ScriptedTransport
from app.core.config import Settings
from app.runtime_app import build_composition
from tests.inventory.conftest import inventory_store as inventory_store
from tests.inventory.conftest import inventory_store_path as inventory_store_path
from tests.inventory.test_viewing_adapter import Case
from tests.inventory.test_viewing_adapter import accepted_inputs as accepted_inputs
from tests.inventory.test_viewing_adapter import make_case as make_case

PROJECT = Path(__file__).resolve().parents[4]
CORPUS = PROJECT / "fixtures/assistant/evaluation/corpus-v1.json"
OUTPUT = PROJECT / "Records/build/quality-review/feedback-reset-diagnosis-20260925"


def test_safe_exception_omits_payload_and_absolute_paths() -> None:
    secret = "synthetic-private-marker-do-not-serialize"
    try:
        raise ValueError(secret)
    except ValueError as error:
        diagnostic = safe_exception(error, PROJECT)
    rendered = json.dumps(diagnostic)
    assert secret not in rendered and str(PROJECT) not in rendered
    assert diagnostic["exception_type"] == "ValueError"
    assert (
        diagnostic["repository_frames"][-1]["function"]
        == "test_safe_exception_omits_payload_and_absolute_paths"
    )
    assert all(
        set(frame) == {"file", "function", "line"} for frame in diagnostic["repository_frames"]
    )
    unknown = safe_exception(type(secret, (Exception,), {})(secret), PROJECT)
    assert unknown["exception_type"] == "OtherException"


def test_case008_reset_using_original_script_and_fresh_store(
    make_case: Callable[..., Case],
    accepted_inputs: BootstrapInputs,
) -> None:
    corpus = Corpus.model_validate_json(CORPUS.read_bytes())
    fixture = make_case()
    transport = ScriptedTransport()
    composition = build_composition(
        Settings(
            store_path=fixture.store.path,
            runtime_boundary=fixture.store.boundary,
            policy=accepted_inputs.policy,
            gemini_api_key=SecretStr("synthetic-evaluation-never-live"),
        ),
        fixture.store,
        clock=lambda: datetime(2026, 9, 24, 4, tzinfo=UTC),
        provider_transport=transport,
        event_sink=lambda event: None,
    )
    try:
        composition.admit_inventory()
        output = OUTPUT / "offline-runs" / str(uuid4())
        result = asyncio.run(
            evaluate(
                composition,
                corpus,
                project=PROJECT,
                corpus_path=CORPUS,
                oracle=load_oracle(PROJECT, corpus),
                writer=ReportWriter(output),
                mode="offline_scripted",
                transport=transport,
                selected={"A11-008"},
            )
        )
        case = next(case for case in result.cases if case.case_id == "A11-008")
        assert case.verdict == "PASS"
        assert result.cleanup == "SETTLED"
    finally:
        assert composition.close()
        fixture.gateway.close()
