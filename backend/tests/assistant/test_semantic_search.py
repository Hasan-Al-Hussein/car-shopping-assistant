"""Semantic shopping edits retain facts and state without requiring magic phrases."""

import pytest

from app.api.schemas.inventory import SearchCriteria
from app.assistant.intent import TurnIntent
from app.assistant.semantic_search import apply_search_intent


def proposal(*patches, **fields):
    return TurnIntent.model_validate({"operation": "search", "patches": list(patches), **fields})


def text_patch(quote, *, operation="replace", field="makes", values=None):
    return {
        "kind": "text", "field": field, "operation": operation,
        "values": ["Toyota"] if values is None else values, "quote": quote,
    }


def budget_patch(quote, *, operation="correct", maximum="40k", **fields):
    return {
        "kind": "range", "field": "budget", "operation": operation,
        "maximum": {"text": maximum}, "quote": quote, **fields,
    }


def accepted():
    return SearchCriteria.model_validate({
        "filters": {
            "makes": ["Toyata"], "models": ["Camry"],
            "years": {"minimum": 2018, "maximum": 2024},
            "budget": {"currency": "AED", "minimum": 1_000_000, "maximum": 5_000_000},
            "mileage_km": {"maximum": 150_000},
        },
        "soft_preferences": ["family trips"],
    })


@pytest.mark.parametrize("message", [
    "i meant toyota", "Toyota is the one I intended", "Let's go with Toyota",
    "The brand should be Toyota", "Toyota", "what toyata cars do u offer?",
])
def test_model_text_correction_preserves_every_unrelated_condition(message):
    current = accepted()
    result = apply_search_intent(current, proposal(text_patch(message)), message)
    expected = current.model_dump(mode="json")
    expected["filters"]["makes"] = ["Toyota"]
    assert result.clarification is None
    assert result.retained.model_dump(mode="json") == expected
    assert current == accepted()


@pytest.mark.parametrize("operation,values,expected", [
    ("replace", [" Toyota ", "toyota", "TOYOTA"], ["Toyota"]),
    ("add", ["Toyota", "toyota"], ["Toyata", "Toyota"]),
    ("remove", ["toyata"], []),
    ("clear", [], []),
])
def test_model_operation_not_verb_dictionary_controls_text_delta(operation, values, expected):
    message = "My brand preference is different."
    result = apply_search_intent(
        accepted(), proposal(text_patch(message, operation=operation, values=values)), message,
    )
    assert result.clarification is None
    assert result.retained.filters.makes == expected
    assert result.retained.filters.budget == accepted().filters.budget


def test_unknown_make_is_preserved_instead_of_being_changed_to_a_known_make():
    message = "Show me Acme Automobiles"
    result = apply_search_intent(
        SearchCriteria(), proposal(text_patch(message, values=["Acme Automobiles"])), message,
    )
    assert result.retained.filters.makes == ["Acme Automobiles"]


@pytest.mark.parametrize("message", [
    "Don't change my Toyota preference", "I wonder whether Toyota is reliable",
    "My brother drives a Toyota", "Toyota? Never mind, keep the choices I already made",
])
def test_model_non_change_intent_cannot_erase_or_add_conditions(message):
    result = apply_search_intent(accepted(), proposal(), message)
    assert result.clarification is None
    assert result.retained == accepted()


@pytest.mark.parametrize("operation", ["search", "question", "analyze"])
def test_hypothetical_filters_only_apply_to_this_read(operation):
    message = "Toyota could work for comparison"
    result = apply_search_intent(
        accepted(),
        proposal(text_patch(message), operation=operation, scope="hypothetical"),
        message,
    )
    assert result.clarification is None
    assert result.effective.filters.makes == ["Toyota"]
    assert result.retained == accepted()


@pytest.mark.parametrize("fields", [
    {"problem": "conflict", "problem_target": "makes"},
    {"scope": "durable"}, {"scope": "unclear"}, {"deferred": ["preferences"]},
    {"collection": {"command": "start_enquiry"}}, {"operation": "unsupported"},
])
def test_ambiguity_and_business_actions_cannot_use_semantic_read_authority(fields):
    message = "Toyota"
    result = apply_search_intent(accepted(), proposal(text_patch(message), **fields), message)
    assert result.clarification is not None
    assert result.effective == result.retained == accepted()


@pytest.mark.parametrize("bad_patch", [
    text_patch("not in the buyer input"),
    text_patch("Toyota", operation="clear", values=["Toyota"]),
    text_patch("Toyota", values=[" "]),
    text_patch("Toyota", operation="remove", values=["Mazda"]),
    budget_patch("Toyota", maximum="99k"),
    {"kind": "range", "field": "budget", "operation": "clear", "quote": "Toyota",
     "maximum": {"text": "50k"}},
])
def test_invalid_patch_rejects_entire_transition_without_partial_changes(bad_patch):
    message = "Toyota"
    good_patch = text_patch(message, field="models", values=["Corolla"])
    result = apply_search_intent(accepted(), proposal(good_patch, bad_patch), message)
    assert result.clarification is not None
    assert result.effective == result.retained == accepted()


def test_duplicate_fields_reject_atomically_even_if_values_match():
    message = "Toyota"
    patch = text_patch(message)
    result = apply_search_intent(accepted(), proposal(patch, patch), message)
    assert result.clarification is not None
    assert result.retained == accepted()


def test_model_reset_does_not_need_one_of_a_few_literal_reset_phrases():
    message = "Begin with a clean slate and look at Toyota"
    result = apply_search_intent(accepted(), proposal(
        text_patch(message), {"kind": "reset", "quote": message},
    ), message)
    assert result.clarification is None
    assert result.retained == SearchCriteria.model_validate({"filters": {"makes": ["Toyota"]}})


@pytest.mark.parametrize("operation,token,expected", [
    ("correct", "40k", 4_000_000), ("correct", "70k", 7_000_000),
    ("refine", "40k", 4_000_000), ("refine", "70k", 5_000_000),
])
def test_numeric_meaning_is_model_supplied_and_arithmetic_is_local(operation, token, expected):
    message = f"I can spend {token}."
    result = apply_search_intent(
        accepted(), proposal(budget_patch(message, operation=operation, maximum=token)), message,
    )
    assert result.clarification is None
    assert result.retained.filters.budget.maximum == expected
    assert result.retained.filters.budget.minimum == 1_000_000
    assert result.retained.filters.years == accepted().filters.years


def test_lower_and_exclusive_upper_bounds_use_exact_integer_units():
    message = "20k through 40k"
    patch = budget_patch(message)
    patch["minimum"] = {"text": "20k", "inclusive": False}
    patch["maximum"]["inclusive"] = False
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is None
    assert result.retained.filters.budget.minimum == 2_000_001
    assert result.retained.filters.budget.maximum == 3_999_999


@pytest.mark.parametrize("message,fields", [
    ("I can spend 40k", {"currency": "USD"}),
    ("I can spend 40k", {"basis": "monthly_finance"}),
    ("I can spend 40k monthly", {"basis": "monthly_finance"}),
    ("I can spend USD 40k", {"currency": "USD"}),
])
def test_currency_and_payment_guards_preserve_existing_purchase_budget(message, fields):
    result = apply_search_intent(accepted(), proposal(budget_patch(message, **fields)), message)
    assert result.clarification is not None
    assert result.retained == accepted()


@pytest.mark.parametrize("message", [
    "No finance please, my cash budget is AED 40k",
    "My cash budget is AED 40k, not USD",
    "I don't want monthly payments; 40k dirhams is my purchase budget",
])
def test_model_cash_meaning_is_not_overridden_by_incidental_payment_or_currency_words(message):
    patch = budget_patch(message, currency="AED", basis="cash")
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is None
    assert result.retained.filters.budget.maximum == 4_000_000
    assert result.retained.filters.budget.currency == "AED"


def test_model_currency_alias_is_allowed_when_canonical_code_is_not_literal():
    message = "My full purchase budget is 40k dirhams"
    result = apply_search_intent(SearchCriteria(), proposal(
        budget_patch(message, currency="AED", basis="cash"),
    ), message)
    assert result.clarification is None
    assert result.retained.filters.budget.maximum == 4_000_000


@pytest.mark.parametrize("fields", [
    {"currency": "AED", "basis": "unknown"}, {"currency": None, "basis": "cash"},
    {"currency": None, "basis": "unknown"},
])
def test_omitted_purchase_metadata_uses_uae_defaults(fields):
    message = "I can spend 40k"
    result = apply_search_intent(
        SearchCriteria(), proposal(budget_patch(message, **fields)), message,
    )
    assert result.clarification is None
    assert result.retained.filters.budget.currency == "AED"
    assert result.retained.filters.budget.basis == "cash"
    assert result.retained.filters.budget.maximum == 4_000_000


@pytest.mark.parametrize("problem", ["currency", "basis"])
def test_explicit_uncertainty_is_not_overridden_by_purchase_defaults(problem):
    message = "I can spend 40k"
    result = apply_search_intent(
        SearchCriteria(),
        proposal(budget_patch(message), problem=problem, problem_target="budget"),
        message,
    )
    assert result.clarification is not None
    assert result.retained == SearchCriteria()


def test_omitted_metadata_preserves_established_foreign_currency():
    current = SearchCriteria.model_validate({
        "filters": {"budget": {"currency": "USD", "maximum": 5_000_000}},
    })
    message = "I can spend 40k"
    result = apply_search_intent(current, proposal(budget_patch(message)), message)
    assert result.clarification is None
    assert result.retained.filters.budget.currency == "USD"
    assert result.retained.filters.budget.maximum == 4_000_000


def test_restate_all_bounds_to_change_currency_without_conversion():
    message = "My purchase budget is USD 10k to 40k"
    patch = budget_patch(message, currency="USD", basis="cash")
    patch["minimum"] = {"text": "10k"}
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is None
    assert result.retained.filters.budget.currency == "USD"
    assert result.retained.filters.budget.minimum == 1_000_000
    assert result.retained.filters.budget.maximum == 4_000_000


def test_currency_only_clarification_keeps_exact_prior_amount():
    prior = "I can spend 50k"
    message = "Dirhams, for the full purchase"
    patch = budget_patch(message, maximum="50k", currency="AED", basis="cash")
    result = apply_search_intent(
        SearchCriteria(), proposal(patch), message,
        clarification_targets=("budget",), prior_request=prior,
    )
    assert result.clarification is None
    assert result.retained.filters.budget.maximum == 5_000_000


def test_currency_only_reply_cannot_reinterpret_a_monthly_payment_as_cash():
    message = "Dirhams"
    patch = budget_patch(message, maximum="2k", currency="AED", basis="monthly_finance")
    result = apply_search_intent(
        SearchCriteria(), proposal(patch), message,
        clarification_targets=("budget",), prior_request="I can pay 2k monthly",
    )
    assert result.clarification is not None
    assert result.retained == SearchCriteria()


def test_current_clarification_amount_cannot_be_replaced_by_stale_prior_amount():
    message = "AED 40k for the full purchase"
    patch = budget_patch(message, maximum="50k", currency="AED", basis="cash")
    result = apply_search_intent(
        accepted(), proposal(patch), message,
        clarification_targets=("budget",), prior_request="I can spend 50k",
    )
    assert result.clarification is not None
    assert result.retained == accepted()


def test_prior_quote_is_accepted_only_for_a_matching_clarification():
    prior = "Toyota"
    message = "That's the brand I want"
    for targets, expected in [((), False), (("models",), False), (("makes",), True)]:
        result = apply_search_intent(
            accepted(), proposal(text_patch(prior)), message,
            clarification_targets=targets, prior_request=prior,
        )
        assert (result.clarification is None) == expected


@pytest.mark.parametrize("field,token,quote,extra", [
    ("years", "24", "model year 24", {}),
    ("years", "2020", "model year 2020", {"currency": "AED"}),
    ("mileage_km", "40k", "40k miles", {}),
    ("mileage_km", "40k", "40k", {}),
    ("budget", "40.001", "AED 40.001 cash", {"currency": "AED", "basis": "cash"}),
])
def test_invalid_year_unit_or_precision_cannot_be_reinterpreted(field, token, quote, extra):
    patch = {"kind": "range", "field": field, "operation": "refine",
             "maximum": {"text": token}, "quote": quote, **extra}
    result = apply_search_intent(SearchCriteria(), proposal(patch), quote)
    assert result.clarification is not None
    assert result.retained == SearchCriteria()


def test_range_correction_can_replace_an_interval_with_an_open_ended_maximum():
    original = accepted().model_dump(mode="json")
    original["filters"]["budget"].update(minimum=5_000_000, maximum=10_000_000)
    current = SearchCriteria.model_validate(original)
    message = "Just show cars up to 40k instead of that interval"
    patch = budget_patch(message, clear_minimum=True)
    result = apply_search_intent(current, proposal(patch), message)
    assert result.clarification is None
    assert result.retained.filters.budget.minimum is None
    assert result.retained.filters.budget.maximum == 4_000_000
    expected = current.model_dump(mode="json")
    expected["filters"]["budget"].update(minimum=None, maximum=4_000_000)
    assert result.retained.model_dump(mode="json") == expected


@pytest.mark.parametrize("clear_field,kept_field", [
    ("minimum", "maximum"), ("maximum", "minimum"),
])
def test_clearing_one_endpoint_keeps_the_other_numeric_value(clear_field, kept_field):
    message = "I no longer need that side of the price range"
    patch = {
        "kind": "range", "field": "budget", "operation": "correct",
        "quote": message, f"clear_{clear_field}": True,
    }
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is None
    assert getattr(result.retained.filters.budget, clear_field) is None
    assert getattr(result.retained.filters.budget, kept_field) == getattr(
        accepted().filters.budget, kept_field,
    )
    assert result.retained.filters.years == accepted().filters.years


@pytest.mark.parametrize("operation", ["refine", "clear"])
@pytest.mark.parametrize("clear_field", ["minimum", "maximum"])
def test_endpoint_flags_require_a_correction_operation(operation, clear_field):
    message = "Change that budget"
    patch = {
        "kind": "range", "field": "budget", "operation": operation,
        "quote": message, f"clear_{clear_field}": True,
    }
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is not None
    assert result.effective == result.retained == accepted()


@pytest.mark.parametrize("endpoint", ["minimum", "maximum"])
def test_clearing_and_setting_the_same_endpoint_is_rejected_atomically(endpoint):
    message = "40k Toyota"
    patch = {
        "kind": "range", "field": "budget", "operation": "correct",
        "quote": message, f"clear_{endpoint}": True, endpoint: {"text": "40k"},
    }
    result = apply_search_intent(accepted(), proposal(text_patch(message), patch), message)
    assert result.clarification is not None
    assert result.effective == result.retained == accepted()


def test_clearing_both_endpoints_requires_whole_range_clear_operation():
    message = "No price limits"
    patch = {
        "kind": "range", "field": "budget", "operation": "correct",
        "quote": message, "clear_minimum": True, "clear_maximum": True,
    }
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is not None
    assert result.effective == result.retained == accepted()


def test_currency_change_may_explicitly_remove_one_bound_and_restate_the_other():
    message = "My total budget is USD 40k with no minimum price"
    patch = budget_patch(message, currency="USD", basis="cash", clear_minimum=True)
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is None
    assert result.retained.filters.budget.currency == "USD"
    assert result.retained.filters.budget.minimum is None
    assert result.retained.filters.budget.maximum == 4_000_000


def test_clearing_one_bound_cannot_silently_reinterpret_the_remaining_currency_amount():
    message = "Remove the minimum and make the currency USD"
    patch = {
        "kind": "range", "field": "budget", "operation": "correct", "quote": message,
        "currency": "USD", "clear_minimum": True,
    }
    result = apply_search_intent(accepted(), proposal(patch), message)
    assert result.clarification is not None
    assert result.effective == result.retained == accepted()


def test_missing_endpoint_clear_flag_does_not_silently_discard_a_lower_bound():
    original = accepted().model_dump(mode="json")
    original["filters"]["budget"].update(minimum=5_000_000, maximum=10_000_000)
    current = SearchCriteria.model_validate(original)
    message = "My maximum is 40k"
    result = apply_search_intent(current, proposal(budget_patch(message)), message)
    assert result.clarification is not None
    assert result.effective == result.retained == current


@pytest.mark.parametrize("quote,token", [
    ("AED 20,000 cash", "20"),
    ("AED 20,000 cash", "000"),
    ("AED 40.001 cash", "40"),
    ("AED 40.001 cash", "001"),
    ("AED 20k cash", "20"),
])
def test_numeric_token_must_match_a_complete_cited_lexeme(quote, token):
    patch = budget_patch(quote, maximum=token, currency="AED", basis="cash")
    result = apply_search_intent(accepted(), proposal(patch), quote)
    assert result.clarification is not None
    assert result.effective == result.retained == accepted()


@pytest.mark.parametrize("quote,token,expected", [
    ("AED 20,000 cash", "20,000", 2_000_000),
    ("AED 40.01 cash", "40.01", 4001),
    ("AED 20k cash", "20k", 2_000_000),
    ("AED 20K cash", "20k", 2_000_000),
    ("budget20k dirhams", "20k", 2_000_000),
])
def test_complete_comma_decimal_and_compact_budget_tokens_remain_supported(quote, token, expected):
    patch = budget_patch(quote, maximum=token, currency="AED", basis="cash")
    result = apply_search_intent(SearchCriteria(), proposal(patch), quote)
    assert result.clarification is None
    assert result.retained.filters.budget.maximum == expected


def test_partial_token_cannot_bypass_matched_clarification_provenance():
    message = "Dirhams for the full purchase"
    patch = budget_patch(message, maximum="20", currency="AED", basis="cash")
    result = apply_search_intent(
        SearchCriteria(), proposal(patch), message,
        clarification_targets=("budget",), prior_request="I can spend 20,000",
    )
    assert result.clarification is not None
    assert result.retained == SearchCriteria()
