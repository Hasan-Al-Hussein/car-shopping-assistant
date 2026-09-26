"""Provider metadata survives actual service evaluation and saved report serialization."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr
from scripts.bootstrap_inventory import BootstrapInputs

from app.assistant.evaluation.runner import ReportWriter, evaluate, load_oracle
from app.assistant.evaluation.schema import Corpus, EvaluationRun
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
OUTPUT = PROJECT / "Records/build/quality-review/feedback-explicit-command-20260925/offline-runs"


def test_saved_service_result_distinguishes_failed_successful_and_absent_provider_metadata(
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
        output = OUTPUT / str(uuid4())
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
                selected={"A11-031", "A11-039"},
            )
        )
        saved = EvaluationRun.model_validate_json((output / "report.json").read_bytes())
        assert saved == result
        cases = {case.case_id: case for case in saved.cases}
        assert cases["A11-031"].verdict == cases["A11-039"].verdict == "PASS"
        assert cases["A11-031"].steps[0].observed["provider_diagnostic"] == {
            "code": "quota",
            "failure_phase": None,
            "http_status": None,
        }
        assert cases["A11-039"].steps[0].observed["provider_diagnostic"] == {
            "code": None,
            "failure_phase": None,
            "http_status": None,
        }
        assert cases["A11-039"].steps[1].observed["provider_diagnostic"] is None
        assert transport.calls == 2
        assert saved.cleanup == "SETTLED"
    finally:
        assert composition.close()
        fixture.gateway.close()
