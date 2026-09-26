"""One-field counterexamples for the F-02 cross-field contract invariants."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.api.schemas.inventory import (
    ConstraintCoverage,
    HandoffSummary,
    PresentationProof,
    SearchResult,
)
from app.api.schemas.memory import (
    PreferenceRecord,
    PreferencesUpdate,
    ShortlistItem,
    ShortlistResult,
)
from app.api.schemas.operations import OperationRejected, OperationSucceeded
from app.api.schemas.sessions import (
    ActionUnresolved,
    ClarificationIntent,
    MessageActionResults,
    MessageResult,
    SessionState,
    TranscriptPage,
)
from app.api.schemas.viewings import (
    BookingDraft,
    BookingReceipt,
    BookingReview,
    ConfirmRequest,
    ViewingOptions,
    ViewingSlot,
)

PROJECT = Path(__file__).resolve().parents[3]
FIXTURES = json.loads(
    (PROJECT / "contracts/fixtures/semantic_cases.json").read_text(encoding="utf-8")
)
MODELS: dict[str, Any] = {
    model.__name__: model
    for model in (
        ConstraintCoverage,
        HandoffSummary,
        PresentationProof,
        SearchResult,
        PreferenceRecord,
        PreferencesUpdate,
        ShortlistItem,
        ShortlistResult,
        OperationRejected,
        OperationSucceeded,
        ClarificationIntent,
        ActionUnresolved,
        MessageActionResults,
        MessageResult,
        SessionState,
        TranscriptPage,
        BookingDraft,
        BookingReceipt,
        BookingReview,
        ViewingOptions,
        ViewingSlot,
    )
}


@pytest.mark.parametrize("name", list(FIXTURES["baselines"]))
def test_valid_semantic_baseline(name: str) -> None:
    TypeAdapter(MODELS[name]).validate_json(json.dumps(FIXTURES["baselines"][name]))


@pytest.mark.parametrize("case", FIXTURES["mutations"], ids=lambda case: case["id"])
def test_rejects_specific_semantic_contradiction(case: dict[str, Any]) -> None:
    adapter = TypeAdapter(MODELS[case["model"]])
    payload = deepcopy(FIXTURES["baselines"][case["model"]])
    adapter.validate_json(json.dumps(payload))
    target = payload
    for component in case["path"][:-1]:
        target = target[component]
    target[case["path"][-1]] = case["value"]
    with pytest.raises(ValidationError) as raised:
        adapter.validate_json(json.dumps(payload))
    assert any(case["marker"] in error["msg"] for error in raised.value.errors()), (
        raised.value.errors()
    )


def test_preference_fields_retain_different_provenance_and_expiry() -> None:
    record = PreferenceRecord.model_validate(FIXTURES["baselines"]["PreferenceRecord"])
    budget, makes = record.entries
    assert budget.source_session_id != makes.source_session_id
    assert budget.confirmed_at != makes.confirmed_at
    assert budget.expires_at != makes.expires_at
    assert budget.preference.strength == "hard"
    assert makes.preference.strength == "soft"


def test_retained_soft_context_is_typed_and_transcript_is_historical() -> None:
    state = SessionState.model_validate(FIXTURES["baselines"]["SessionState"])
    assert state.criteria.soft_preferences == ["quiet cabin"]
    assert state.criteria.filters.budget is not None
    page = TranscriptPage.model_validate(FIXTURES["baselines"]["TranscriptPage"])
    assert page.items[0].historical is True
    assert page.items[0].assistant_result is not None
    assert page.items[0].assistant_result.pending_intent.kind == "clarification"


def test_saved_transcript_does_not_imply_saved_memory_or_enquiry() -> None:
    turn = MessageResult.model_validate(FIXTURES["baselines"]["MessageResult"])
    assert turn.persistence == "saved"
    assert turn.actions.preferences.state == "unresolved"
    assert turn.actions.shortlist.state == "not_requested"
    assert turn.actions.lead.state == "rejected"
    assert turn.comparison is not None
    assert len(turn.comparison.items) == 2


@pytest.mark.parametrize("state", ["expired", "invalidated"])
def test_old_review_remains_typed_history_without_replacement_payload(state: str) -> None:
    payload = deepcopy(FIXTURES["baselines"]["BookingReview"])
    payload["state"] = state
    review = BookingReview.model_validate(payload)
    confirmation = {
        "review_id": review.review_id,
        "expected_draft_revision": review.draft_revision,
        "operation_key": review.operation_key,
        "rules_version": review.rules_version,
        "store_generation": review.store_generation,
        "confirmation": "confirm_simulated_viewing",
    }
    original = ConfirmRequest.model_validate(confirmation)
    changed = ConfirmRequest.model_validate(
        {
            **confirmation,
            "review_id": "00000000-0000-4000-8000-000000000099",
        }
    )
    assert review.state != "valid"
    assert original.operation_key == changed.operation_key
    assert original.model_dump() != changed.model_dump()
