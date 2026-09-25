"""Exact final-body checks against pinned facts and explicitly reviewed corpus copy.

The real deterministic renderer is reused over the independent BE04 fact oracle.
Corpus reference/state assertions separately bind the returned cars and criteria.
This is a finite regression oracle, not a general factuality judge for arbitrary prose.
"""

from typing import Any

from app.api.schemas.inventory import (
    ComparisonRequest, ListingDetail, ListingSummary, SearchRequest,
)
from app.api.schemas.sessions import MessageResult
from app.assistant.answer_assembly import (
    GroundedAnswer, assemble_comparison, assemble_handoff, assemble_search,
)
from app.assistant.scope import compose_scope

from .schema import Step


def reviewed[T: ListingSummary | ListingDetail](item: T, oracle: dict[str, Any]) -> T:
    detail = isinstance(item, ListingDetail)
    ref = item.listing.ref if isinstance(item, ListingDetail) else item.ref
    facts = oracle[ref.source_id]["public_facts"]
    value = item.model_dump(mode="json")
    summary = value["listing"] if detail else value
    summary.update({name: facts[name] for name in (
        "make", "model", "trim", "year", "cash_price", "mileage_km",
    )})
    if detail:
        value.update({name: facts[name] for name in (
            "fuel_type", "body_type", "transmission", "location", "warranty", "service_history",
        )})
    return type(item).model_validate(value)


def expected_answer(result: MessageResult, step: Step, oracle: dict[str, Any]) -> GroundedAnswer | None:
    if step.prose_mode == "fixed":
        assert step.expected_text is not None
        return GroundedAnswer(step.expected_text, (), ())
    if step.prose_mode != "grounded":
        return None
    if result.search is not None:
        source = result.search.model_copy(update={
            "items": [reviewed(item, oracle) for item in result.search.items],
        })
        request = SearchRequest(
            **source.applied_criteria.model_dump(mode="json"),
            client_request_id=source.client_request_id,
        )
        answer = assemble_search(source, request=request)
    elif result.comparison is not None:
        source_comparison = result.comparison.model_copy(update={
            "items": [reviewed(item, oracle) if isinstance(item, ListingDetail) else item
                      for item in result.comparison.items],
        })
        refs = [item.listing.ref if isinstance(item, ListingDetail) else item.ref
                for item in source_comparison.items]
        answer = assemble_comparison(source_comparison, request=ComparisonRequest(refs=refs))
    elif result.handoff_summary is not None:
        handoff = result.handoff_summary
        source_handoff = handoff.model_copy(update={
            "listing": reviewed(handoff.listing, oracle)
            if isinstance(handoff.listing, ListingDetail) else handoff.listing,
        })
        answer = assemble_handoff(source_handoff, expected_ref=source_handoff.selected_ref,
                                  criteria=source_handoff.expressed_criteria)
    else:
        return None
    return compose_scope(answer, topics=tuple(step.scope_topics))


def prose_matches(result: MessageResult | None, step: Step, oracle: dict[str, Any]) -> bool | None:
    if result is None:
        return step.prose_mode == "no_result"
    expected = expected_answer(result, step, oracle)
    return None if expected is None else (
        result.text == expected.text and result.evidence == list(expected.evidence)
    )
