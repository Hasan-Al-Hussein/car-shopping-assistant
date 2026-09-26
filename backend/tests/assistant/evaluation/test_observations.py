"""Projection canaries mutate actual DTO text and row identity/content snapshots."""

from copy import deepcopy
from typing import Any

import pytest

from app.api.schemas.inventory import ListingDetail, SearchCriteria
from app.api.schemas.sessions import MessageResult, SessionState
from app.assistant.answer_assembly import assemble_handoff
from app.assistant.evaluation.effects import MODELS, DomainSnapshot, project_effects
from app.assistant.evaluation.judging import judge
from app.assistant.evaluation.observations import project
from app.assistant.evaluation.schema import Assertion, Step
from tests.assistant.a4_cases import CLIENT_ID, detail, fixture_data, handoff


def empty() -> DomainSnapshot:
    return DomainSnapshot({name: {} for name in MODELS}, {name: {} for name in MODELS})


def sample(item: ListingDetail) -> tuple[MessageResult, SessionState, Step]:
    answer = assemble_handoff(
        handoff(item), expected_ref=item.listing.ref, criteria=SearchCriteria()
    )
    session = SessionState.model_validate({
        "session_id": CLIENT_ID, "journey_id": CLIENT_ID, "revision": 1,
        "criteria": {}, "selected_ref": item.listing.ref.model_dump(),
        "active_presentation_id": None, "current_draft_id": None,
        "pending_intent": {"kind": "none"},
        "recalled_preferences": {"entries": [], "revision": 0, "collection_mode": "explicit_save"},
    })
    result = MessageResult(
        client_message_id=CLIENT_ID, session_id=CLIENT_ID, turn_revision=1, current_revision=1,
        state="answered", text=answer.text, pending_intent=session.pending_intent,
        evidence=list(answer.evidence), handoff_summary=answer.handoff_summary,
        persistence="saved", provider_state="available",
    )
    step = Step.model_validate({
        "kind": "message", "text": "Show this car", "intent": {"operation": "detail"},
        "prose_mode": "grounded", "assertions": [{
            "name": "final prose", "path": "prose_matches", "expected": True,
            "critical": "invented_fact",
        }],
    })
    return result, session, step


def observe(
    result: MessageResult, session: SessionState, step: Step, oracle: dict[str, Any]
) -> dict[str, Any]:
    ref = detail().listing.ref
    return project(result, session, before=empty(), after=empty(), oracle=oracle,
                   namespace=ref.namespace, snapshot=ref.snapshot_id, step=step)


@pytest.mark.parametrize("source_id,corruption", [
    ("3", "This car costs AED 1 and has a full warranty."),
    ("22", "The cash asking price is AED 1."),
    ("52", "The year is definitely 2014; all conflicts are resolved."),
])
def test_final_prose_mutants_fail_even_when_all_attached_fact_dtos_match(
    source_id: str, corruption: str,
) -> None:
    oracle = {row["ref"]["source_id"]: row for row in fixture_data()["records"]}
    result, session, step = sample(detail(source_id))
    baseline = observe(result, session, step, oracle)
    assert baseline["grounding_matches"] is True and baseline["prose_matches"] is True
    if source_id == "22":
        assert "not stated" in result.text
    if source_id == "52":
        assert "conflicting listing values" in result.text and "No value is resolved" in result.text
    corrupted = observe(result.model_copy(update={"text": corruption}), session, step, oracle)
    assert corrupted["grounding_matches"] is True
    checked = judge(step.assertions[0], corrupted)
    assert checked.verdict == "FAIL" and checked.critical == "invented_fact"


def test_removed_qualifier_and_added_claim_cannot_pass_the_final_body_gate() -> None:
    oracle = deepcopy({row["ref"]["source_id"]: row for row in fixture_data()["records"]})
    # Explicit synthetic detector input, not a correction to accepted workbook facts.
    oracle["3"]["public_facts"]["mileage_km"]["qualifier"] = "approximate"
    value = detail().model_dump(mode="json")
    value["listing"]["mileage_km"]["qualifier"] = "approximate"
    result, session, step = sample(ListingDetail.model_validate(value))
    assert "approximately 68,000 km" in result.text
    assert observe(result, session, step, oracle)["prose_matches"] is True
    for text in (
        result.text.replace("approximately ", ""), result.text + " This car is accident-free."
    ):
        mutated = observe(result.model_copy(update={"text": text}), session, step, oracle)
        assert judge(step.assertions[0], mutated).verdict == "FAIL"


@pytest.mark.parametrize("domain", [
    "preferences", "leads", "drafts", "bookings", "shortlist",
    "preference_settings", "owner_revisions",
])
def test_same_count_mutation_and_identity_replacement_are_visible(domain: str) -> None:
    before = empty()
    before.owned[domain]["original-row-identity"] = "original-content-fingerprint"
    expected = project_effects(before, deepcopy(before))["mutations"]
    for replace_identity in (False, True):
        after = deepcopy(before)
        if replace_identity:
            after.owned[domain] = {"replacement-row-identity": "original-content-fingerprint"}
        else:
            after.owned[domain]["original-row-identity"] = "corrupted-content-fingerprint"
        observed = project_effects(before, after)
        assert all(value == 0 for value in observed["effects"].values())
        for critical in ("unauthorized_action", "duplicate_commit"):
            assertion = Assertion.model_validate({
                "name": "exact domain stability", "path": "mutations", "expected": expected,
                "critical": critical,
            })
            assert judge(assertion, observed).verdict == "FAIL"


def test_cross_owner_row_change_fails_the_foreign_domain_gate() -> None:
    before, after = empty(), empty()
    before.foreign["leads"]["other-owner-row"] = "original"
    after.foreign["leads"]["other-owner-row"] = "changed"
    assert project_effects(before, after)["foreign_domains_unchanged"] is False
