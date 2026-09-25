"""Criteria transition regressions, synthetic language proposals, no runtime services."""

from typing import Any

import pytest

from app.api.schemas.inventory import SearchCriteria
from app.assistant.intent import TurnIntent, apply_intent


def intent(*patches: dict[str, Any], **changes: Any) -> TurnIntent:
    return TurnIntent.model_validate({"operation": "search", "patches": list(patches), **changes})


def accepted() -> SearchCriteria:
    return SearchCriteria.model_validate(
        {
            "filters": {
                "makes": ["Honda"],
                "years": {"minimum": 2018, "maximum": 2024},
                "budget": {"currency": "AED", "minimum": 2_000_000, "maximum": 6_000_000},
            },
            "soft_preferences": ["family trips"],
        }
    )


@pytest.mark.parametrize("text", [
    "Help me find a car within my budget 20k dirhams",
    "Help me find a car within my budget20k dirhams",
    "Find a car up to dirhams 20k",
    "Find a car up to Dhs 20k", "Find cars within 20k dirham",
    "My car budget 20k DHS", "My budget 20k AED", "Find cars up to UAE dirhams 20k",
])
@pytest.mark.parametrize("problem", [None, "basis", "currency"])
def test_natural_purchase_budget_keeps_quote_and_sets_aed(text: str, problem: str | None) -> None:
    value = intent({
        "kind": "range", "field": "budget", "operation": "refine",
        "maximum": {"text": "20k"}, "quote": text,
    }, problem=problem, problem_target="budget")
    before = value.model_dump(mode="json")
    result = apply_intent(SearchCriteria(), value, text)
    assert result.clarification is None
    assert result.retained.filters.budget is not None
    assert result.retained.filters.budget.model_dump() == {
        "minimum": None, "maximum": 2_000_000, "currency": "AED", "basis": "cash",
    }
    assert value.model_dump(mode="json") == before


@pytest.mark.parametrize("text", [
    "My budget 20k dirhams monthly", "My budget 20k Dhs downpayment",
    "My budget 20k Dhs instalment", "My payment up to AED 20k",
    "My finance budget 20k Dhs", "My budget 20k Moroccan dirhams",
    "My budget 20k dirhams USD", "My budget 20k dirhamster",
    "Do not change my budget 20k Dhs", "My budget 20k MAD",
])
def test_natural_budget_does_not_invent_basis_currency_or_permission(text: str) -> None:
    value = intent({
        "kind": "range", "field": "budget", "operation": "refine",
        "maximum": {"text": "20k"}, "currency": "AED", "basis": "cash", "quote": text,
    })
    result = apply_intent(SearchCriteria(), value, text)
    assert result.clarification is not None and result.retained.filters.budget is None


@pytest.mark.parametrize("prefix", ["In Morocco, ", "My monthly payment: ", "In USD, "])
def test_short_quote_cannot_hide_currency_or_payment_context(prefix: str) -> None:
    quote = "my budget 20k dirhams"
    value = intent({
        "kind": "range", "field": "budget", "operation": "refine",
        "maximum": {"text": "20k"}, "quote": quote,
    })
    result = apply_intent(accepted(), value, prefix + quote)
    assert result.clarification is not None and result.retained == accepted()


def test_foreign_existing_range_is_not_reinterpreted_as_dirhams() -> None:
    current = SearchCriteria.model_validate({
        "filters": {"budget": {"currency": "USD", "minimum": 100_000, "maximum": 3_000_000}},
    })
    text = "Actually my budget 20k dirhams"
    value = intent({
        "kind": "range", "field": "budget", "operation": "correct",
        "maximum": {"text": "20k"}, "quote": text,
    })
    result = apply_intent(current, value, text)
    assert result.clarification is not None and result.retained == current


def test_natural_budget_range_preserves_minimum_and_exclusive_bounds() -> None:
    text = "Find cars within my budget 10k to 20k dirhams"
    value = intent({
        "kind": "range", "field": "budget", "operation": "refine",
        "minimum": {"text": "10k"}, "maximum": {"text": "20k"}, "quote": text,
    })
    result = apply_intent(SearchCriteria(), value, text)
    assert result.clarification is None and result.retained.filters.budget is not None
    assert result.retained.filters.budget.minimum == 1_000_000
    assert result.retained.filters.budget.maximum == 2_000_000
    text = "Find a car under Dhs 20k"
    value = intent({
        "kind": "range", "field": "budget", "operation": "refine",
        "maximum": {"text": "20k", "inclusive": False}, "quote": text,
    })
    result = apply_intent(SearchCriteria(), value, text)
    assert result.clarification is None and result.retained.filters.budget is not None
    assert result.retained.filters.budget.maximum == 1_999_999


def test_complete_request_preserves_hard_types_and_minor_units() -> None:
    text = "Honda sedan, 2018 or newer, cash up to AED 60k, under 80k km; family trips"
    value = intent(
        {
            "kind": "text",
            "field": "makes",
            "operation": "add",
            "values": ["Honda"],
            "quote": "Honda",
        },
        {
            "kind": "text",
            "field": "body_types",
            "operation": "add",
            "values": ["sedan"],
            "quote": "sedan",
        },
        {
            "kind": "range",
            "field": "years",
            "operation": "refine",
            "minimum": {"text": "2018"},
            "quote": "2018 or newer",
        },
        {
            "kind": "range",
            "field": "budget",
            "operation": "refine",
            "maximum": {"text": "60k"},
            "currency": "AED",
            "basis": "cash",
            "quote": "cash up to AED 60k",
        },
        {
            "kind": "range",
            "field": "mileage_km",
            "operation": "refine",
            "maximum": {"text": "80k", "inclusive": False},
            "quote": "under 80k km",
        },
        {
            "kind": "text",
            "field": "soft_preferences",
            "operation": "add",
            "values": ["family trips"],
            "quote": "family trips",
        },
    )
    result = apply_intent(SearchCriteria(), value, text)
    assert result.clarification is None
    assert result.retained.filters.budget is not None
    assert result.retained.filters.budget.maximum == 6_000_000
    assert result.retained.filters.mileage_km is not None
    assert result.retained.filters.mileage_km.maximum == 79_999
    assert result.retained.filters.makes == ["Honda"]
    assert result.retained.filters.body_types == ["sedan"]


def test_correction_and_explicit_removal_keep_unrelated_constraints() -> None:
    result = apply_intent(
        accepted(),
        intent(
            {
                "kind": "text",
                "field": "makes",
                "operation": "replace",
                "values": ["Toyota"],
                "quote": "Actually Toyota instead",
            },
            {
                "kind": "range",
                "field": "budget",
                "operation": "correct",
                "maximum": {"text": "70k"},
                "quote": "raise budget to at most 70k",
            },
        ),
        "Actually Toyota instead; raise budget to at most 70k",
    )
    assert result.clarification is None
    assert result.retained.filters.makes == ["Toyota"]
    assert result.retained.filters.budget is not None
    assert (result.retained.filters.budget.minimum, result.retained.filters.budget.maximum) == (
        2_000_000,
        7_000_000,
    )
    assert result.retained.filters.years == accepted().filters.years
    removed = apply_intent(
        result.retained,
        intent(
            {
                "kind": "range",
                "field": "budget",
                "operation": "clear",
                "quote": "remove the budget",
            }
        ),
        "remove the budget",
    )
    assert removed.clarification is None and removed.retained.filters.budget is None
    assert removed.retained.soft_preferences == ["family trips"]


@pytest.mark.parametrize(
    "patch,text",
    [
        ({"kind": "reset", "quote": "Do not reset the search"}, "Do not reset the search"),
        (
            {
                "kind": "text",
                "field": "makes",
                "operation": "clear",
                "quote": "Do not remove Honda",
            },
            "Do not remove Honda",
        ),
        (
            {
                "kind": "range",
                "field": "budget",
                "operation": "refine",
                "maximum": {"text": "70k"},
                "quote": "at most 70k",
            },
            "at most 70k",
        ),
        (
            {
                "kind": "range",
                "field": "years",
                "operation": "refine",
                "maximum": {"text": "2020"},
                "quote": "at least 2020",
            },
            "at least 2020",
        ),
        (
            {
                "kind": "range",
                "field": "years",
                "operation": "refine",
                "maximum": {"text": "2020"},
                "quote": "before 2020",
            },
            "before 2020",
        ),
        (
            {
                "kind": "text",
                "field": "makes",
                "operation": "replace",
                "values": ["BMW"],
                "quote": "Actually Toyota",
            },
            "Actually Toyota",
        ),
        (
            {
                "kind": "text",
                "field": "makes",
                "operation": "replace",
                "values": ["Toyota"],
                "quote": "Toyota",
            },
            "Toyota",
        ),
        (
            {
                "kind": "text",
                "field": "soft_preferences",
                "operation": "add",
                "values": ["accident-free"],
                "quote": "only accident-free",
            },
            "only accident-free",
        ),
    ],
)
def test_uncertain_or_malicious_changes_cannot_erase_accepted_conditions(
    patch: dict[str, Any], text: str
) -> None:
    result = apply_intent(accepted(), intent(patch), text)
    assert result.clarification is not None
    assert result.retained == accepted()


@pytest.mark.parametrize(
    "patch",
    [
        {"maximum": {"text": "60k"}, "quote": "up to 60k", "basis": "cash"},
        {"maximum": {"text": "60k"}, "quote": "up to AED 60k", "currency": "AED"},
        {
            "maximum": {"text": "2k"},
            "quote": "up to AED 2k monthly",
            "currency": "AED",
            "basis": "monthly_finance",
        },
    ],
)
def test_unestablished_currency_or_cash_basis_requires_clarification(patch: dict[str, Any]) -> None:
    value = {"kind": "range", "field": "budget", "operation": "refine", **patch}
    result = apply_intent(SearchCriteria(), intent(value), str(patch["quote"]))
    assert result.clarification is not None and result.clarification.target == "budget"
    assert result.retained.filters.budget is None


def test_duplicate_conflicting_field_keeps_old_value_but_accepts_unrelated_soft_delta() -> None:
    result = apply_intent(
        accepted(),
        intent(
            {
                "kind": "text",
                "field": "makes",
                "operation": "replace",
                "values": ["Toyota"],
                "quote": "Actually Toyota",
            },
            {
                "kind": "text",
                "field": "makes",
                "operation": "replace",
                "values": ["Mazda"],
                "quote": "instead Mazda",
            },
            {
                "kind": "text",
                "field": "soft_preferences",
                "operation": "add",
                "values": ["commuting"],
                "quote": "commuting",
            },
        ),
        "Actually Toyota, instead Mazda; commuting",
    )
    assert result.clarification is not None
    assert result.retained.filters == accepted().filters
    assert result.retained.soft_preferences == ["family trips", "commuting"]


def test_hypothetical_correction_is_effective_only_for_that_read() -> None:
    quote = "What if I raise budget to at most 70k"
    patch = {
        "kind": "range",
        "field": "budget",
        "operation": "correct",
        "maximum": {"text": "70k"},
        "quote": quote,
    }
    result = apply_intent(accepted(), intent(patch, scope="hypothetical"), quote)
    assert result.clarification is None and result.retained == accepted()
    assert result.effective.filters.budget is not None
    assert result.effective.filters.budget.maximum == 7_000_000
    wrong_scope = apply_intent(accepted(), intent(patch), quote)
    assert wrong_scope.clarification is not None and wrong_scope.retained == accepted()


def test_uncaptured_hard_or_durable_intent_cannot_become_a_broad_session_search() -> None:
    for text in ("Only accident-free cars", "remember my Honda preference"):
        result = apply_intent(accepted(), intent(), text)
        assert result.clarification is not None and result.retained == accepted()


def test_durable_request_does_not_commit_session_criteria_or_claim_preference_save() -> None:
    result = apply_intent(
        accepted(),
        intent(
            {
                "kind": "text",
                "field": "makes",
                "operation": "replace",
                "values": ["Toyota"],
                "quote": "Remember Toyota instead",
            },
            scope="durable",
        ),
        "Remember Toyota instead",
    )
    assert result.clarification is not None and result.clarification.target == "preference_scope"
    assert result.retained == accepted()


def test_currency_change_cannot_reinterpret_an_unrestated_opposite_bound() -> None:
    result = apply_intent(
        accepted(),
        intent(
            {
                "kind": "range",
                "field": "budget",
                "operation": "correct",
                "currency": "USD",
                "maximum": {"text": "20k"},
                "quote": "Actually up to USD 20k",
            }
        ),
        "Actually up to USD 20k",
    )
    assert result.clarification is not None and result.retained == accepted()


def test_shortened_quote_cannot_strip_whole_message_negation() -> None:
    result = apply_intent(
        accepted(),
        intent(
            {
                "kind": "reset",
                "quote": "reset the search",
            }
        ),
        "Do not reset the search",
    )
    assert result.clarification is not None and result.retained == accepted()


def test_compound_upper_bound_cannot_be_read_as_exclusive_lower_bound() -> None:
    result = apply_intent(
        accepted(),
        intent(
            {
                "kind": "range",
                "field": "years",
                "operation": "refine",
                "minimum": {"text": "2020", "inclusive": False},
                "quote": "no more than 2020",
            }
        ),
        "no more than 2020",
    )
    assert result.clarification is not None and result.retained == accepted()


def test_wide_make_quote_cannot_cover_an_omitted_price_bound() -> None:
    text = "Only Honda, under AED 60k cash"
    result = apply_intent(
        SearchCriteria(),
        intent(
            {
                "kind": "text",
                "field": "makes",
                "operation": "add",
                "values": ["Honda"],
                "quote": text,
            }
        ),
        text,
    )
    assert result.clarification is not None and result.retained.filters.budget is None
