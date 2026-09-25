"""Actual retained DTO values, expiry and override language; no live-memory demonstration."""

from typing import Any
from uuid import uuid4

from app.api.schemas.inventory import SearchCriteria
from app.api.schemas.memory import PreferenceRecord
from app.assistant.recalled_values import format_recalled_preferences, is_recall_question


NOW = "2026-09-24T00:00:00Z"


def saved_record() -> PreferenceRecord:
    origin = str(uuid4())
    entries: list[dict[str, Any]] = []
    for preference in [
        {"key": "budget", "value": {"maximum": 6_000_000, "currency": "AED"}, "strength": "hard"},
        {"key": "makes", "value": ["Honda", "Toyota"], "strength": "soft"},
    ]:
        entries.append({
            "preference": preference, "source_session_id": origin,
            "source_action_id": str(uuid4()), "source_message_id": str(uuid4()),
            "confirmed_at": "2026-09-23T00:00:00Z", "expires_at": "2026-10-23T00:00:00Z",
            "applicability": "confirmed",
        })
    return PreferenceRecord.model_validate({
        "entries": entries, "revision": 2, "collection_mode": "explicit_save",
    })


def test_two_real_values_in_distinct_session_without_invented_chronology() -> None:
    record = saved_record()
    before = record.model_dump(mode="json")
    text = format_recalled_preferences(record, session_id=str(uuid4()), criteria=SearchCriteria(), now=NOW)
    assert "AED at most 60,000.00 total cash" in text
    assert '"Honda", "Toyota"' in text
    assert text.count("another session") == 2 and "earlier session" not in text
    assert "hard requirement" in text and "soft preference" in text
    assert "have not changed your current search" in text
    assert record.model_dump(mode="json") == before


def test_reconfirmation_and_explicit_override_stay_visible_together() -> None:
    record = saved_record()
    record.entries[0].applicability = "requires_reconfirmation"
    criteria = SearchCriteria.model_validate({"filters": {"budget": {"maximum": 8_000_000, "currency": "AED"}}})
    text = format_recalled_preferences(record, session_id=str(uuid4()), criteria=criteria, now=NOW)
    assert "60,000.00" in text and "80,000.00" not in text
    assert "needs your reconfirmation" in text and "current choice takes precedence" in text
    assert criteria.filters.budget is not None and criteria.filters.budget.maximum == 8_000_000


def test_expired_values_not_recalled_and_disabled_mode_is_honest() -> None:
    record = saved_record()
    for entry in record.entries:
        entry.expires_at = NOW
    record.collection_mode = "disabled"
    text = format_recalled_preferences(record, session_id=str(uuid4()), criteria=SearchCriteria(), now=NOW)
    assert "No current saved preferences" in text and "saving is paused" in text
    assert "Honda" not in text and "60,000" not in text


def test_non_aed_minor_units_and_long_lists_are_not_misrepresented() -> None:
    payload = saved_record().model_dump(mode="json")
    payload["entries"][0]["preference"]["value"] = {"maximum": 600_001, "currency": "JPY"}
    payload["entries"][1]["preference"]["value"] = ["Honda", "Toyota", "Mazda", "Nissan"]
    record = PreferenceRecord.model_validate(payload)
    text = format_recalled_preferences(record, session_id=str(uuid4()), criteria=SearchCriteria(), now=NOW)
    assert "JPY at most 600,001 minor units" in text and "display scale not established" in text
    assert "6,000.01" not in text and "1 additional saved values" in text
    assert "Nissan" not in text


def test_recall_question_is_complete_and_does_not_authorize_a_save() -> None:
    assert is_recall_question("What preferences do you remember?")
    assert not is_recall_question("Remember my preferences")
    assert not is_recall_question("What preferences do you remember and save my budget?")


def test_current_soft_preferences_do_not_override_saved_hard_requirements() -> None:
    payload = saved_record().model_dump(mode="json")
    payload["entries"] = [payload["entries"][1]]
    payload["entries"][0]["preference"] = {"key": "requirements", "value": ["seven seats"], "strength": "hard"}
    text = format_recalled_preferences(
        PreferenceRecord.model_validate(payload), session_id=str(uuid4()),
        criteria=SearchCriteria(soft_preferences=["compact"]), now=NOW,
    )
    assert "seven seats" in text and "hard requirement" in text
    assert "takes precedence" not in text
