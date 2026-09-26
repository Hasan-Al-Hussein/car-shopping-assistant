import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr

from app.assistant.evaluation.runner import ReportWriter, evaluate, load_oracle
from app.assistant.evaluation.schema import Corpus, EvaluationRun
from app.assistant.evaluation.transports import ScriptedTransport
from app.core.config import Settings
from app.runtime_app import build_composition
from scripts.bootstrap_inventory import BootstrapInputs
from tests.inventory.conftest import inventory_store as inventory_store
from tests.inventory.conftest import inventory_store_path as inventory_store_path
from tests.inventory.test_viewing_adapter import Case
from tests.inventory.test_viewing_adapter import accepted_inputs as accepted_inputs
from tests.inventory.test_viewing_adapter import make_case as make_case

PROJECT = Path(__file__).resolve().parents[4]
CORPUS = PROJECT / "fixtures/assistant/evaluation/corpus-v1.json"


def test_corpus_preserves_categories_source_unicode_and_explicit_expectations() -> None:
    corpus = Corpus.model_validate_json(CORPUS.read_bytes())
    assert len(corpus.cases) >= 40
    assert all(case.scenarios and all(step.assertions for step in case.steps) for case in corpus.cases)
    assert all(not case.live_eligible for case in corpus.cases if any(step.fault for step in case.steps))
    assert len({case.id for case in corpus.cases}) == len(corpus.cases)


def test_executable_corpus_uses_actual_composition_and_preserves_each_result(
    make_case: Callable[..., Case], accepted_inputs: BootstrapInputs,
) -> None:
    corpus = Corpus.model_validate_json(CORPUS.read_bytes())
    fixture = make_case()
    transport = ScriptedTransport()
    composition = build_composition(Settings(
        store_path=fixture.store.path, runtime_boundary=fixture.store.boundary,
        policy=accepted_inputs.policy, gemini_api_key=SecretStr("synthetic-evaluation-never-live"),
    ), fixture.store, clock=lambda: datetime(2026, 9, 24, 4, tzinfo=UTC),
        provider_transport=transport, event_sink=lambda event: None)
    try:
        composition.admit_inventory()
        output = PROJECT / "Records/build/BE-24/check-runs" / str(uuid4())
        writer = ReportWriter(output)
        result = asyncio.run(evaluate(composition, corpus, project=PROJECT, corpus_path=CORPUS,
            oracle=load_oracle(PROJECT, corpus), writer=writer, mode="offline_scripted", transport=transport))
        saved = EvaluationRun.model_validate_json((output / "report.json").read_bytes())
        assert saved == result
        assert result.denominator == len(corpus.cases) and len(result.cases) == len(corpus.cases)
        assert all(case.verdict == "PASS" for case in result.cases), json.dumps(result.counts)
        assert result.critical_failures == [] and result.cleanup == "SETTLED"
        assert result.gate == ("PASS" if corpus.review_status == "SOURCE_REVIEWED" else "INCOMPLETE")
        assert all(step.elapsed_ms is not None for case in result.cases for step in case.steps)
    finally:
        assert composition.close()
        fixture.gateway.close()
