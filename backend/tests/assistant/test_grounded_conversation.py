"""Synthetic evidence and fake-provider checks; no live credentials or user data."""

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest

from app.api.schemas.inventory import ListingDetail, ListingSummary, SearchCriteria
from app.assistant.grounded_conversation import (
    GroundedConversationDraft,
    _packet_fits,
    build_grounded_corpus,
    compose_grounded_answer,
    validate_grounded_draft,
)
from app.assistant.grounding import GroundingError
from app.assistant.packet import EvidencePacket
from app.assistant.provider import TransportResponse

from .conversation_fakes import (
    ScriptedTransport,
    budget,
    listing,
    provider,
    request,
    session,
    state,
)


def car(
    index: int,
    *,
    price: int | None = None,
    year: int = 2020,
    make: str = "Nissan",
    model: str | None = None,
    description: str = "",
) -> ListingDetail:
    value = listing(str(index), make).model_dump(mode="json")
    summary = value["listing"]
    template = summary["make"]
    for field, field_value in (
        ("model", model if model is not None else f"Model {index}"),
        ("year", year),
        (
            "cash_price",
            None if price is None else {"minor_units": price, "currency": "AED", "basis": "cash"},
        ),
    ):
        if field_value is None:
            continue
        fact = json.loads(json.dumps(template))
        fact["value"] = field_value
        evidence = fact["evidence"][0]
        evidence.update(
            evidence_id=str(uuid4()),
            raw_text=str(field_value),
            span_start=0,
            span_end=len(str(field_value)),
            cell=f"{field}{index}",
        )
        if field == "cash_price":
            evidence.update(semantic_role="cash_price", original_unit="AED")
        summary[field] = fact
    value["description"] = description
    return ListingDetail.model_validate(value)


def corpus(*rows: ListingSummary | ListingDetail, **changes: Any):
    return build_grounded_corpus(
        tuple(rows), scope="inventory", complete=True, total=len(rows), **changes
    )


def draft(text: str, *citations: tuple[str, str], **changes: Any) -> GroundedConversationDraft:
    return GroundedConversationDraft.model_validate_json(
        json.dumps(
            {
                "status": "answered",
                "paragraphs": [
                    {
                        "text": text,
                        "citations": [
                            {"source_id": source_id, "quote": quote}
                            for source_id, quote in citations
                        ],
                    }
                ],
                **changes,
            }
        )
    )


def test_all_rows_and_exact_stats_are_kept_without_a_question_specific_route() -> None:
    source = corpus(car(1, price=3_500_000), car(2), car(3, price=5_000_000, make="Mazda"))
    value = json.loads(source.context)
    assert len(value["rows"]) == 3
    assert value["statistics"]["stats.cash_price"]["exact"] == 2
    assert value["statistics"]["stats.cash_price"]["unknown"] == 1
    assert value["statistics"]["stats.cash_price"]["currencies"]["AED"]["minimum"] == "35,000.00"
    assert value["statistics"]["stats.make"]["distribution"] == {"mazda": 1, "nissan": 2}
    nissan = next(group for group in value["groups"].values() if group["value"] == "nissan")
    assert nissan["count"] == 2 and nissan["cash_price"]["exact"] == 1


def test_every_published_row_column_has_a_citation_binding() -> None:
    source = corpus(car(95, year=2023), car(61, year=2018))
    value = json.loads(source.context)
    for row in value["rows"]:
        for field in value["columns"]:
            assert f"{row[0]}.{field}" in source.sources
    answer = validate_grounded_draft(
        draft("Listing 95 has model year 2023.",
              ("car1.listing_id", "95"), ("car1.year", "2023")), source,
    )
    assert answer is not None
    assert {claim.attribute for claim in answer.claims} == {"year"}


@pytest.mark.parametrize("citation", [
    ("car1.listing_id", "61"), ("car2.listing_id", "95"),
    ("car3.listing_id", "95"), ("car1.invented_id", "95"),
    ("car1.listing_id", "5"),
])
def test_identity_citations_cannot_borrow_other_rows_or_invent_fields(citation) -> None:
    source = corpus(car(95, year=2023), car(61, year=2018))
    assert validate_grounded_draft(draft("This is listing 95.", citation), source) is None


@pytest.mark.parametrize("text", [
    "The cash price is AED 95.", "The model year is 95.", "The mileage is 95 km.",
    "Listing 95 costs AED 95.", "This is listing 95,000.",
])
def test_identity_digits_cannot_support_vehicle_facts(text) -> None:
    assert validate_grounded_draft(
        draft(text, ("car1.listing_id", "95")), corpus(car(95, year=2023)),
    ) is None


def test_hundred_full_rows_fit_existing_input_budget() -> None:
    source = corpus(*(car(index, price=3_500_000 + index * 1000) for index in range(1, 101)))
    packet = EvidencePacket(
        message="How many have a stated cash price?",
        session_revision=1,
        source_context=source.context,
    )
    assert len(json.loads(source.context)["rows"]) == 100
    assert _packet_fits(packet, ())


def test_arithmetic_excludes_qualified_and_conflicting_claims() -> None:
    approximate = car(1, price=3_500_000).model_dump(mode="json")
    approximate["listing"]["cash_price"]["qualifier"] = "approximate"
    conflict = car(2, year=2024).model_dump(mode="json")
    first = conflict["listing"]["year"].copy()
    first.pop("status")
    second = json.loads(json.dumps(first))
    second["value"] = 2022
    second["evidence"][0]["evidence_id"] = str(uuid4())
    conflict["listing"]["year"] = {"status": "conflicting", "claims": [first, second]}
    source = corpus(
        ListingDetail.model_validate(approximate), ListingDetail.model_validate(conflict)
    )
    value = json.loads(source.context)
    assert value["statistics"]["stats.cash_price"]["exact"] == 0
    assert value["statistics"]["stats.cash_price"]["qualified"] == 1
    assert value["statistics"]["stats.year"]["maximum"] == 2020
    assert value["statistics"]["stats.year"]["conflicting"] == 1
    assert (
        validate_grounded_draft(draft("The model year is 2024.", ("car2.year", "2024")), source)
        is None
    )
    assert validate_grounded_draft(
        draft("The year conflicts: 2024 versus 2022.", ("car2.year", "2024")), source
    )


def test_description_questions_have_bounded_selected_source_excerpts() -> None:
    description = "Exterior paint is silver. " * 60 + "The listing mentions heated leather seats."
    source = corpus(
        car(1, description=description), question="Which seats have heating?", description_limit=180
    )
    assert "heated leather seats" in source.sources["car1.description"].text
    assert len(source.sources["car1.description"].text) <= 180
    answer = validate_grounded_draft(
        draft(
            "The listing mentions heated leather seats.",
            ("car1.description", "heated leather seats"),
        ),
        source,
    )
    assert answer is not None and answer.evidence[0].attributes == ["description"]
    assert json.loads(source.context)["scope"]["description_coverage"] == "excerpts only"


def test_known_private_values_and_contact_details_are_not_uploaded() -> None:
    source = corpus(
        car(
            1,
            description=(
                "Leather seats. Contact buyer@example.com or +971 50 123 4567. secret-owner-note"
            ),
        ),
        private_values=("secret-owner-note",),
    )
    assert "buyer@example.com" not in source.context
    assert "123 4567" not in source.context
    assert "secret-owner-note" not in source.context


def test_natural_answer_can_combine_facts_without_a_fixed_template() -> None:
    source = corpus(car(1, year=2024, price=3_500_000))
    answer = validate_grounded_draft(
        draft(
            "This 2024 Nissan is listed at AED 35,000 cash. "
            "It fits the newer-model option you asked about.",
            ("car1.year", "2024"),
            ("car1.make", "Nissan"),
            ("car1.cash_price", "35,000.00"),
        ),
        source,
    )
    assert answer is not None
    assert answer.text.startswith("This 2024 Nissan")
    assert answer.evidence[0].attributes == ["year", "make", "cash_price"]


@pytest.mark.parametrize(
    ("text", "citation"),
    [
        ("The year is 2025.", ("car1.year", "2024")),
        ("The year is 2024.", ("car9.year", "2024")),
        ("The year is 2024.", ("car1.year", "2025")),
        ("I have booked this Nissan.", ("car1.make", "Nissan")),
        ("See https://example.com for this Nissan.", ("car1.make", "Nissan")),
    ],
)
def test_rejects_invalid_support_invented_numbers_links_and_action_receipts(text, citation) -> None:
    assert validate_grounded_draft(draft(text, citation), corpus(car(1, year=2024))) is None


def test_missing_facts_can_be_answered_honestly_without_a_questionnaire() -> None:
    answer = validate_grounded_draft(
        draft(
            "The cash price is not stated, so I cannot establish affordability from this listing.",
            ("car1.cash_price", "not stated"),
            status="unanswerable",
            missing_facts=["cash price"],
        ),
        corpus(car(1)),
    )
    assert answer is not None
    assert "make or model" not in answer.text


@pytest.mark.parametrize(
    "metadata",
    [
        {"status": "partial"},
        {"status": "unanswerable"},
        {"status": "answered", "missing_facts": ["warranty"]},
    ],
)
def test_coverage_metadata_does_not_reject_supported_prose_or_bypass_fact_guards(metadata) -> None:
    source = corpus(car(1))
    assert (
        validate_grounded_draft(
            draft(
                "The listing does not mention a warranty.", ("car1.warranty", "null"), **metadata
            ),
            source,
        )
        is not None
    )
    for text in ("It comes with a warranty.", "A 3-year warranty is not stated."):
        assert (
            validate_grounded_draft(
                draft(text, ("car1.warranty", "null"), **metadata),
                source,
            )
            is None
        )


def test_aggregate_quote_supports_its_total_and_stated_count() -> None:
    source = corpus(car(1, price=3_500_000), car(2), car(3))
    answer = validate_grounded_draft(
        draft("Of the 3 listings, 1 has a stated cash price.", ("stats.cash_price", '"exact":1')),
        source,
    )
    assert answer is not None


def test_recorded_inventory_answer_accepts_real_scope_member_and_complete_statistics() -> None:
    prices = [2_150_000, *([2_500_000] * 11), 134_999_900]
    source = corpus(
        *(car(index + 1, price=prices[index] if index < 13 else None) for index in range(100))
    )
    text = (
        "Across all 100 listings in the inventory, exactly 13 listings feature a clearly "
        "stated cash price in AED, ranging from a minimum of AED 21,500.00 to a maximum "
        "of AED 1,349,999.00."
    )
    answer = validate_grounded_draft(
        draft(
            text,
            ("scope.rows", "100"),
            ("stats.cash_price", source.sources["stats.cash_price"].text),
        ),
        source,
    )
    assert answer is not None and answer.text == text
    assert len(answer.evidence) == 10 and len(answer.claims) == 100


def test_nested_json_member_citation_inherits_provenance_but_only_supports_its_value() -> None:
    source = corpus(car(1, price=3_500_000), car(2))
    answer = validate_grounded_draft(
        draft(
            "The lowest stated cash price is AED 35,000.00.",
            ("stats.cash_price.currencies.AED.minimum", "35,000.00"),
        ),
        source,
    )
    assert answer is not None
    assert all(item.attributes == ["cash_price"] for item in answer.evidence)
    assert {claim.ref for claim in answer.claims} == {
        (ref.namespace, ref.snapshot_id, ref.source_id)
        for ref in source.sources["stats.cash_price"].refs
    }
    assert (
        validate_grounded_draft(
            draft("There are 2 listings and 1 stated price.", ("stats.cash_price.exact", "1")),
            source,
        )
        is None
    )


@pytest.mark.parametrize(
    "source_id,quote",
    [
        ("scope.invented", "2"),
        ("scope.rows.value", "2"),
        ("scope.rows", "100"),
        ("stats.cash_price.currencies.USD.minimum", "35,000.00"),
        ("stats.cash_price.currencies.AED.minimum", "99,000.00"),
        ("stats.made_up.exact", "1"),
        ("car1.warranty.null", "null"),
    ],
)
def test_json_member_citations_reject_absent_keys_scalar_paths_and_false_quotes(
    source_id, quote
) -> None:
    assert (
        validate_grounded_draft(
            draft("The supplied value is not available.", (source_id, quote)),
            corpus(car(1, price=3_500_000), car(2)),
        )
        is None
    )


def test_unique_row_quote_resolves_field_and_hides_internal_markers() -> None:
    source = corpus(car(1, description="The seller mentions a factory sunroof."))
    answer = validate_grounded_draft(
        draft(
            "The seller mentions a factory sunroof [car1.description].", ("car1", "factory sunroof")
        ),
        source,
    )
    assert answer is not None
    assert answer.text == "The seller mentions a factory sunroof."
    assert answer.evidence[0].attributes == ["description"]
    assert (
        validate_grounded_draft(
            draft("The year is 2020.", ("car2", "2020")),
            source,
        )
        is None
    )


def test_missing_field_cannot_be_used_to_claim_a_positive_fact() -> None:
    source = corpus(car(1))
    assert (
        validate_grounded_draft(
            draft("It comes with a warranty.", ("car1.warranty", "not stated")), source
        )
        is None
    )


@pytest.mark.parametrize(
    "label",
    ["2022 Nissan Patrol Safari", "Nissan Patrol Safari 2022", "Nissan Patrol Safari (2022)"],
)
def test_missing_fact_answer_binds_a_complete_same_row_vehicle_identity(label: str) -> None:
    source = corpus(car(1, year=2022, model="Patrol Safari"))
    text = f"Regarding the {label}, the inventory listing does not mention a warranty."
    answer = validate_grounded_draft(draft(text, ("car1.warranty", "null")), source)
    assert answer is not None and answer.text == text
    assert answer.evidence[0].attributes == ["warranty", "year", "make", "model"]
    claims = {claim.attribute: claim for claim in answer.claims}
    for field in ("year", "make", "model"):
        assert claims[field].evidence_ids == source.sources[f"car1.{field}"].evidence_ids


@pytest.mark.parametrize(
    "text",
    [
        "The 2023 Nissan Patrol Safari has no stated warranty.",
        "The 2022 Mazda CX-5 has no stated warranty.",
        "The 2021 Nissan Xterra has no stated warranty.",
        "The 2022 Nissan Patrol Safari has no stated warranty and costs AED 35,000.",
        "The 2022 Nissan Patrol Safari has no stated warranty and has 2022 km mileage.",
        "The 2022 Nissan Patrol Safari comes with a warranty.",
    ],
)
def test_identity_support_does_not_admit_other_years_cars_or_unrelated_numbers(text: str) -> None:
    source = corpus(
        car(1, year=2022, model="Patrol Safari", price=3_500_000),
        car(2, year=2022, make="Mazda", model="CX-5"),
        car(3, year=2021, model="Xterra"),
    )
    assert validate_grounded_draft(draft(text, ("car1.warranty", "null")), source) is None


def test_qualified_vehicle_identity_is_not_promoted_to_an_exact_label() -> None:
    approximate = car(1, year=2022, model="Patrol Safari").model_dump(mode="json")
    approximate["listing"]["year"]["qualifier"] = "approximate"
    source = corpus(ListingDetail.model_validate(approximate))
    assert (
        validate_grounded_draft(
            draft(
                "The 2022 Nissan Patrol Safari has no stated warranty.", ("car1.warranty", "null")
            ),
            source,
        )
        is None
    )


def test_summary_only_row_does_not_claim_unretrieved_detail_is_missing() -> None:
    source = corpus(car(1), car(2).listing)
    value = json.loads(source.context)
    column = value["columns"].index("warranty")
    assert value["rows"][1][column] == {"not_retrieved": True}
    assert value["statistics"]["stats.warranty"]["not_retrieved"] == 1
    assert value["statistics"]["stats.warranty"]["unknown"] == 1


def test_corpus_coverage_is_not_silently_upgraded() -> None:
    row = car(1)
    source = build_grounded_corpus((row,), scope="matching", complete=False, total=15)
    coverage = json.loads(source.context)["scope"]
    assert coverage["rows"] == 1 and coverage["total"] == 15 and not coverage["complete"]
    with pytest.raises(GroundingError, match="INVALID_CORPUS_COVERAGE"):
        build_grounded_corpus((row,), scope="inventory", complete=True, total=15)
    with pytest.raises(GroundingError, match="INVALID_CORPUS_IDENTITIES"):
        corpus(row, row)


def test_aggregate_evidence_stays_inside_public_maximum() -> None:
    source = corpus(*(car(index) for index in range(1, 21)))
    answer = validate_grounded_draft(
        draft("There are 20 Nissan listings.", ("stats.make", '"nissan":20')), source
    )
    assert answer is not None and len(answer.evidence) == 10
    assert len(answer.claims) == 20


def test_competitor_names_in_generated_text_are_suppressed() -> None:
    answer = validate_grounded_draft(
        draft("Nissan listings on DubiCars.", ("car1.make", "Nissan")), corpus(car(1))
    )
    assert answer is not None and "DubiCars" not in answer.text


def test_fake_provider_roundtrip_uses_synthesis_schema_and_owned_scope() -> None:
    async def check() -> None:
        current = session()
        output = draft("There is 1 Nissan listing.", ("stats.make", '"nissan":1'))
        transport = ScriptedTransport(TransportResponse(output.model_dump_json()))
        answer = await compose_grounded_answer(
            provider(transport),
            request(current, "What have you got from Nissan?"),
            current,
            (),
            (car(1),),
            scope="matching",
            complete=True,
            total=1,
            request_state=state(),
            budget=budget(),
        )
        assert answer is not None and answer.text == "There is 1 Nissan listing."
        assert transport.requests[0].schema["title"] == "GroundedConversationDraft"
        packet = json.loads(transport.requests[0].contents)
        assert json.loads(packet["source_context"])["scope"]["scope"] == "matching"

    asyncio.run(check())


@pytest.mark.parametrize("quote", ["36,999 AED", "AED 36999", "36999.00 AED cash"])
def test_cash_quote_accepts_exact_currency_amount_format_equivalence(quote) -> None:
    source = corpus(car(1, price=3_699_900))
    assert (
        validate_grounded_draft(
            draft("Its stated cash price is AED 36,999.", ("car1.cash_price", quote)),
            source,
        )
        is not None
    )


@pytest.mark.parametrize(
    "quote", ["36,998 AED", "36,999 USD", "about 36,999 AED", "36,999 AED monthly"]
)
def test_cash_quote_does_not_change_amount_currency_or_qualifier(quote) -> None:
    assert (
        validate_grounded_draft(
            draft("Its stated cash price is AED 36,999.", ("car1.cash_price", quote)),
            corpus(car(1, price=3_699_900)),
        )
        is None
    )


def test_qualified_cash_source_does_not_gain_exact_equivalence() -> None:
    row = car(1, price=3_699_900).model_dump(mode="json")
    row["listing"]["cash_price"]["qualifier"] = "approximate"
    assert (
        validate_grounded_draft(
            draft("Its approximate price is AED 36,999.", ("car1.cash_price", "36,999 AED")),
            corpus(ListingDetail.model_validate(row)),
        )
        is None
    )


def test_buyer_budget_source_never_supports_listing_mileage_warranty_or_price() -> None:
    criteria = SearchCriteria(filters={"budget": {"maximum": 5_000_000, "currency": "AED"}})
    source = corpus(car(1), accepted_criteria=criteria)
    citation = ("buyer.criteria.filters.budget.maximum", "AED 50,000.00 cash")
    assert (
        validate_grounded_draft(draft("Your budget is AED 50,000.", citation), source) is not None
    )
    for text in (
        "The car costs AED 50,000.",
        "The mileage is 50,000 km.",
        "The warranty is for 50,000 km.",
        "Your budget is AED 60,000.",
        "Your budget is USD 50,000.",
        "Your budget is AED 50,000 and the car has 50,000 km mileage.",
    ):
        assert validate_grounded_draft(draft(text, citation), source) is None
    assert source.sources["buyer.criteria"].refs == ()
    assert criteria.filters.budget.maximum == 5_000_000


def test_buyer_source_minimizes_text_without_corrupting_json() -> None:
    criteria = SearchCriteria(
        query="passport number private-example", soft_preferences=["buyer@example.com"]
    )
    source = corpus(car(1), accepted_criteria=criteria, private_values=("private-example",))
    value = json.loads(source.context)["buyer.criteria"]
    assert "passport" not in value["query"] and "private-example" not in source.context
    assert "buyer@example.com" not in source.context


def test_buyer_free_text_redacts_phone_numbers_while_preserving_a_typed_budget() -> None:
    criteria = SearchCriteria(
        query="contact 0501234567",
        soft_preferences=["call 0507654321"],
        filters={"budget": {"maximum": 5_000_000, "currency": "AED"}},
    )
    source = corpus(car(1), accepted_criteria=criteria)
    assert "0501234567" not in source.context and "0507654321" not in source.context
    value = json.loads(source.context)["buyer.criteria"]
    assert value["filters"]["budget"]["maximum"] == "AED 50,000.00 cash"
    assert (
        validate_grounded_draft(
            draft(
                "Your budget is AED 50,000.",
                ("buyer.criteria.filters.budget.maximum", "AED 50,000.00 cash"),
            ),
            source,
        )
        is not None
    )


def recorded_budget_cars() -> list[ListingDetail]:
    specifications = [
        ("Mazda", "3", 2019, 3_500_000, "s grade", None, None),
        ("Ford", "Mustang", 2014, 2_150_000, "v6", 164000, "convertible"),
        ("Volkswagen", "Beetle", 2019, 3_200_000, "s", 36000, None),
        ("Toyota", "Camry", 2018, 3_699_900, "le", 169859, None),
    ]
    rows = []
    for index, (make, model, year, price, trim, mileage, body_type) in enumerate(specifications, 1):
        row = car(index, make=make, model=model, year=year, price=price).model_dump(mode="json")
        for field, value in (("trim", trim), ("mileage_km", mileage), ("body_type", body_type)):
            if value is None:
                continue
            fact = json.loads(json.dumps(row["listing"]["make"]))
            fact["value"] = value
            fact["evidence"][0].update(
                evidence_id=str(uuid4()),
                raw_text=str(value),
                span_start=0,
                span_end=len(str(value)),
                cell=f"{field}{index}",
            )
            if field == "mileage_km":
                fact["evidence"][0]["semantic_role"] = "vehicle_mileage"
            (row if field == "body_type" else row["listing"])[field] = fact
        rows.append(ListingDetail.model_validate(row))
    return rows


def test_complete_recorded_budget_followup_uses_price_equivalence_and_typed_buyer_budget() -> None:
    rows = recorded_budget_cars()
    criteria = SearchCriteria(filters={"budget": {"maximum": 5_000_000, "currency": "AED"}})
    source = corpus(*rows, accepted_criteria=criteria)
    text = (
        "Within your budget of AED 50,000, all four available cars fall under the limit with "
        "cash prices ranging from AED 21,500.00 to AED 36,999.00. The options include a 2019 "
        "Mazda 3 s grade priced at AED 35,000.00 cash, a 2014 Ford Mustang v6 convertible "
        "priced at AED 21,500.00 cash with 164,000 km, a 2019 Volkswagen Beetle s priced at "
        "AED 32,000.00 cash with 36,000 km, and a 2018 Toyota Camry le priced at "
        "AED 36,999.00 cash with 169,859 km."
    )
    citations = (
        ("car1.cash_price", "AED 35,000.00 cash"),
        ("car2.cash_price", "AED 21,500.00 cash"),
        ("car3.cash_price", "AED 32,000.00 cash"),
        ("car4.cash_price", "36,999 AED"),
        ("car1.year", "2019"),
        ("car1.trim", "s grade"),
        ("car2.year", "2014"),
        ("car2.trim", "v6"),
        ("car2.body_type", "convertible"),
        ("car2.mileage_km", "164000"),
        ("car3.year", "2019"),
        ("car3.trim", "s"),
        ("car3.mileage_km", "36000"),
        ("car4.year", "2018"),
        ("car4.trim", "le"),
        ("car4.mileage_km", "169859"),
    )
    answer = validate_grounded_draft(draft(text, *citations), source)
    assert answer is not None and answer.text == text
    assert len(answer.evidence) == 4
    assert all("budget" not in item.attributes for item in answer.evidence)
    assert validate_grounded_draft(draft(text, *citations), corpus(*rows)) is None


@pytest.mark.parametrize(
    "quote",
    [
        '{"AED":{"count":1,"minimum":"35,000.00"}}',
        '{ "minimum": "35,000.00", "count": 1 }',
        '{"currencies": {"AED": {"minimum": "35,000.00"}}}',
    ],
)
def test_structural_citation_matches_real_nested_projection_with_order_and_spacing_changes(
    quote,
) -> None:
    source = corpus(car(1, price=3_500_000), car(2))
    answer = validate_grounded_draft(
        draft("The minimum cash price is AED 35,000.", ("stats.cash_price", quote)),
        source,
    )
    assert answer is not None
    assert all(item.attributes == ["cash_price"] for item in answer.evidence)
    assert (
        validate_grounded_draft(
            draft("There are 2 listings.", ("stats.cash_price", quote)),
            source,
        )
        is None
    )


@pytest.mark.parametrize(
    "quote",
    [
        "{}",
        '{"AED":{}}',
        '{"USD":{"count":1}}',
        '{"AED":{"count":9}}',
        '{"AED":{"count":true}}',
        '{"AED":{"count":1.0}}',
        '{"AED":{"count":"1"}}',
        '{"AED":{"minimum":"36,000.00"}}',
        '{"invented":null}',
        '{"AED":{"count":9,"count":1}}',
    ],
)
def test_structural_citation_rejects_empty_invented_wrong_currency_value_or_scalar_type(
    quote,
) -> None:
    assert (
        validate_grounded_draft(
            draft("A stated cash price is present.", ("stats.cash_price", quote)),
            corpus(car(1, price=3_500_000), car(2)),
        )
        is None
    )


def test_structural_citation_cannot_borrow_a_json_object_from_another_registered_source() -> None:
    source = corpus(car(1, price=3_500_000), car(2))
    assert (
        validate_grounded_draft(
            draft("There is 1 priced car.", ("stats.year", '{"AED":{"count":1}}')),
            source,
        )
        is None
    )


def test_exact_make_model_label_does_not_admit_other_identity_or_year() -> None:
    source = corpus(car(1, make="Mazda", model="3", year=2019))
    answer = validate_grounded_draft(
        draft("The Mazda 3 has no stated warranty.", ("car1.warranty", "null")),
        source,
    )
    assert answer is not None
    assert answer.evidence[0].attributes == ["warranty", "make", "model"]
    for label in ("Honda 3", "Mazda 30", "2025 Mazda 3"):
        assert (
            validate_grounded_draft(
                draft(f"The {label} has no stated warranty.", ("car1.warranty", "null")),
                source,
            )
            is None
        )


def test_complete_live06_budget_paragraph_accepts_structural_stats_and_repeated_numeric_model() -> (
    None
):
    criteria = SearchCriteria(filters={"budget": {"maximum": 5_000_000, "currency": "AED"}})
    source = corpus(*recorded_budget_cars(), accepted_criteria=criteria)
    text = (
        "Within your budget of AED 50,000 cash, there are 4 matching vehicles available, and all "
        "of them fall under your price limit with cash prices ranging from AED 21,500.00 to "
        "AED 36,999.00. The options include a 2019 Mazda 3 s grade priced at AED 35,000.00 cash, "
        "a 2014 Ford Mustang v6 priced at AED 21,500.00 cash with 164,000 km mileage, a 2019 "
        "Volkswagen Beetle s priced at AED 32,000.00 cash with 36,000 km mileage, and a 2018 "
        "Toyota Camry le priced at AED 36,999.00 cash with 169,859 km mileage. Note that the "
        "mileage for the Mazda 3 is not stated."
    )
    citations = (
        ("stats.cash_price", '{"AED":{"count":4,"minimum":"21,500.00","maximum":"36,999.00"}}'),
        ("car1.cash_price", "AED 35,000.00 cash"),
        ("car1.year", "2019"),
        ("car1.trim", "s grade"),
        ("car2.cash_price", "AED 21,500.00 cash"),
        ("car2.year", "2014"),
        ("car2.trim", "v6"),
        ("car2.mileage_km", "164000"),
        ("car3.cash_price", "AED 32,000.00 cash"),
        ("car3.year", "2019"),
        ("car3.trim", "s"),
        ("car3.mileage_km", "36000"),
        ("car4.cash_price", "AED 36,999.00 cash"),
        ("car4.year", "2018"),
        ("car4.trim", "le"),
        ("car4.mileage_km", "169859"),
    )
    answer = validate_grounded_draft(
        draft(text, *citations, missing_facts=["Mazda 3 mileage is not stated"]),
        source,
    )
    assert answer is not None and answer.text == text
    assert len(answer.evidence) == 4


def recorded_live07_budget_answer() -> GroundedConversationDraft:
    return GroundedConversationDraft.model_validate(
        {
            "status": "answered",
            "paragraphs": [
                {
                    "text": (
                        "Within your budget of 50,000 Dirhams total cash purchase price, there "
                        "are four matching vehicles available, all priced below your maximum "
                        "limit. The options include a 2019 Mazda 3 S grade priced at AED "
                        "35,000.00 cash, a 2014 Ford Mustang V6 priced at AED 21,500.00 cash "
                        "with 164,000 km mileage, a 2019 Volkswagen Beetle S priced at AED "
                        "32,000.00 cash with 36,000 km mileage, and a 2018 Toyota Camry LE priced "
                        "at AED 36,999.00 cash with 169,859 km mileage. Note that the mileage "
                        "for the Mazda 3 is not stated in the listing."
                    ),
                    "citations": [
                        {"source_id": "car1.cash_price", "quote": "AED 35,000.00 cash"},
                        {"source_id": "car1.year", "quote": "2019"},
                        {"source_id": "car1.trim", "quote": "s grade"},
                        {"source_id": "car2.cash_price", "quote": "AED 21,500.00 cash"},
                        {"source_id": "car2.mileage_km", "quote": "164000"},
                        {"source_id": "car3.cash_price", "quote": "AED 32,000.00 cash"},
                        {"source_id": "car3.mileage_km", "quote": "36000"},
                        {"source_id": "car4.cash_price", "quote": "AED 36,999.00 cash"},
                        {"source_id": "car4.mileage_km", "quote": "169859"},
                        {"source_id": "car1.mileage_km", "quote": "null"},
                    ],
                }
            ],
            "missing_facts": [],
        }
    )


def test_complete_live07_dirhams_budget_answer() -> None:
    criteria = SearchCriteria(filters={"budget": {"maximum": 5_000_000, "currency": "AED"}})
    source = corpus(*recorded_budget_cars(), accepted_criteria=criteria)
    answer = recorded_live07_budget_answer()
    actual = validate_grounded_draft(answer, source)
    assert actual is not None and actual.text == answer.paragraphs[0].text


@pytest.mark.parametrize(
    "amount",
    [
        "50,000 Dirhams",
        "50k dirham",
        "UAE dirhams 50,000",
        "50 k UAE Dirhams",
        "Dhs 50k",
        "50k Dh",
        "AED 50,000",
        "50k AED total cash purchase price",
    ],
)
def test_buyer_budget_accepts_equivalent_aed_names_and_thousands_notation(amount) -> None:
    source = corpus(
        car(1),
        accepted_criteria=SearchCriteria(
            filters={"budget": {"maximum": 5_000_000, "currency": "AED"}},
        ),
    )
    citation = ("buyer.criteria.filters.budget.maximum", "AED 50,000.00 cash")
    assert (
        validate_grounded_draft(draft(f"Within your budget of {amount}.", citation), source)
        is not None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Your budget of 40k Dirhams.",
        "Your budget of 50k USD.",
        "Your budget of 50k Dirhams per month.",
        "Your budget of 50k Dirhams monthly.",
        "Your budget of 50k Dirhams in monthly payments.",
        "The car costs 50k Dirhams.",
        "The car has 50,000 km mileage.",
        "Within your budget of 50k Dirhams, the car costs 50,000 Dirhams.",
    ],
)
def test_aed_aliases_never_change_budget_value_currency_basis_or_support_vehicle_facts(
    text,
) -> None:
    source = corpus(
        car(1),
        accepted_criteria=SearchCriteria(
            filters={"budget": {"maximum": 5_000_000, "currency": "AED"}},
        ),
    )
    assert (
        validate_grounded_draft(draft(text, ("buyer.criteria", '"currency":"AED"')), source) is None
    )


def test_cash_quote_and_buyer_budget_share_money_token_interpretation() -> None:
    source = corpus(car(1, price=3_500_000))
    assert (
        validate_grounded_draft(
            draft("The listed cash price is AED 35,000.", ("car1.cash_price", "35k UAE Dirhams")),
            source,
        )
        is not None
    )
    assert (
        validate_grounded_draft(
            draft(
                "The listed cash price is AED 35,000.", ("car1.cash_price", "35k Dirhams monthly")
            ),
            source,
        )
        is None
    )


def recorded_live08_budget_answer() -> GroundedConversationDraft:
    return GroundedConversationDraft.model_validate(
        {
            "status": "answered",
            "paragraphs": [
                {
                    "text": (
                        "Within your budget of 50,000 Dirhams total cash purchase price, "
                        "there are four matching vehicles available, all priced below your "
                        "maximum limit. The options include a 2019 Mazda 3 s grade priced at "
                        "AED 35,000.00 cash, a 2014 Ford Mustang V6 listed at AED 21,500.00 "
                        "cash with 164,000 km, a 2019 Volkswagen Beetle S for AED 32,000.00 "
                        "cash with 36,000 km, and a 2018 Toyota Camry LE available at AED "
                        "36,999.00 cash with 169,859 km. Note that mileage is not stated "
                        "for the Mazda 3."
                    ),
                    "citations": [
                        {"source_id": "car1.cash_price", "quote": "AED 35,000.00 cash"},
                        {"source_id": "car1.year", "quote": "2019"},
                        {"source_id": "car1.model", "quote": "3"},
                        {"source_id": "car1.trim", "quote": "s grade"},
                        {"source_id": "car2.cash_price", "quote": "AED 21,500.00 cash"},
                        {"source_id": "car2.year", "quote": "2014"},
                        {"source_id": "car2.model", "quote": "mustang"},
                        {"source_id": "car2.trim", "quote": "v6"},
                        {"source_id": "car2.mileage_km", "quote": "164000"},
                        {"source_id": "car3.cash_price", "quote": "AED 32,000.00 cash"},
                        {"source_id": "car3.year", "quote": "2019"},
                        {"source_id": "car3.model", "quote": "beetle"},
                        {"source_id": "car3.trim", "quote": "s"},
                        {"source_id": "car3.mileage_km", "quote": "36000"},
                        {"source_id": "car4.cash_price", "quote": "AED 36,999.00 cash"},
                        {"source_id": "car4.year", "quote": "2018"},
                    ],
                }
            ],
            "missing_facts": ["Mazda 3 mileage is not stated."],
        }
    )


def test_complete_live08_answer_requires_its_seventeenth_source_citation() -> None:
    rows = []
    for row in recorded_budget_cars():
        value = row.model_dump(mode="json")
        fact = value["listing"]["model"]
        fact["value"] = fact["value"].lower()
        fact["evidence"][0]["raw_text"] = fact["evidence"][0]["raw_text"].lower()
        rows.append(ListingDetail.model_validate(value))
    source = corpus(
        *rows,
        accepted_criteria=SearchCriteria(
            filters={"budget": {"maximum": 5_000_000, "currency": "AED"}},
        ),
    )
    incomplete = recorded_live08_budget_answer()
    assert len(incomplete.paragraphs[0].citations) == 16
    assert validate_grounded_draft(incomplete, source) is None
    payload = incomplete.model_dump(mode="json")
    payload["paragraphs"][0]["citations"].append(
        {"source_id": "car4.mileage_km", "quote": "169859"}
    )
    completed = GroundedConversationDraft.model_validate(payload)
    assert len(completed.paragraphs[0].citations) == 17
    answer = validate_grounded_draft(completed, source)
    assert answer is not None and answer.text == incomplete.paragraphs[0].text
    assert "mileage_km" in answer.evidence[-1].attributes


def test_citation_limit_stays_local_without_expanding_native_schema_complexity() -> None:
    from app.assistant.transport import native_json_schema

    canonical = GroundedConversationDraft.model_json_schema()
    native = native_json_schema(canonical)
    citations = canonical["$defs"]["GroundedParagraph"]["properties"]["citations"]
    assert citations["maxItems"] == 32 and citations["minItems"] == 1
    native_citations = native["$defs"]["GroundedParagraph"]["properties"]["citations"]
    assert "maxItems" not in native_citations
    assert native_citations["minItems"] == 1
    assert (
        "every numeric claim"
        in canonical["$defs"]["GroundedParagraph"]["properties"]["citations"]["description"]
    )
