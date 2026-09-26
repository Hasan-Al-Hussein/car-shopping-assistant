"""One read-only reviewed candidate shared by the BE05 tests in an approved run."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.database.store import Store, initialize_store
from app.inventory.extraction import ExtractedCandidate, extract_reviewed
from app.inventory.import_reader import SourceSpec, read_workbook
from app.inventory.normalization import normalize_candidate
from app.inventory.snapshot_codec import PreparedCandidate, prepare_candidate
from app.inventory.source_catalogue import provided_source_catalogue
from app.inventory.staging_plan import PreparedStage, prepare_stage
from tests.inventory.snapshot_cases import variant_candidate
from tests.support.harness import PROJECT, configured_runtime_boundary, unopened_store_plan

RUN_ID = str(uuid4())


@pytest.fixture(scope="session")
def snapshot_candidate() -> ExtractedCandidate:
    facts = json.loads((PROJECT / "fixtures/shared/source-facts.json").read_text(encoding="utf-8"))
    source = read_workbook(
        PROJECT / facts["source_relative_path"],
        SourceSpec(expected_sha256=facts["workbook_sha256"]),
    )
    return extract_reviewed(normalize_candidate(source), provided_source_catalogue())


@pytest.fixture(scope="session")
def prepared_snapshot(snapshot_candidate: ExtractedCandidate) -> PreparedCandidate:
    return prepare_candidate(snapshot_candidate)


@pytest.fixture(scope="session")
def snapshot_plan(snapshot_candidate: ExtractedCandidate) -> PreparedStage:
    return prepare_stage(snapshot_candidate, policy_version="DEMO-POLICY-1")


@pytest.fixture(scope="session")
def second_candidate(snapshot_candidate: ExtractedCandidate) -> ExtractedCandidate:
    return variant_candidate(snapshot_candidate)


@pytest.fixture(scope="session")
def second_plan(second_candidate: ExtractedCandidate) -> PreparedStage:
    return prepare_stage(second_candidate, policy_version="DEMO-POLICY-1")


@pytest.fixture
def inventory_store_path(request: pytest.FixtureRequest) -> Path:
    case = "case-" + hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16]
    return Path(
        unopened_store_plan(
            run_id=RUN_ID,
            case_id=case,
            generation=str(uuid4()),
        ).path
    )


@pytest.fixture
def inventory_store(inventory_store_path: Path) -> Store:
    return initialize_store(inventory_store_path, boundary=configured_runtime_boundary())
