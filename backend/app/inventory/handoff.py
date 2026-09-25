"""Core read-only factual handoff. No inferred winner, saved need or action."""

from typing import Any

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    FitReason,
    HandoffSummary,
    ListingDetail,
    SearchCriteria,
    UnresolvedQuestion,
)
from app.inventory.details_service import InventoryDetailsService
from app.inventory.search_policy import normalize_criteria
from app.inventory.search_sql import filter_terms, term_matches


def handoff(
    service: InventoryDetailsService, selected_ref: InventoryRef, expressed_criteria: SearchCriteria
) -> HandoffSummary:
    expressed = SearchCriteria.model_validate(expressed_criteria.model_dump())
    criteria = normalize_criteria(expressed)
    selected = service.lookup(selected_ref)
    reasons: list[FitReason] = []
    questions: list[UnresolvedQuestion] = []
    if isinstance(selected, ListingDetail):
        detail = selected.model_dump(mode="json")
        facts: dict[str, Any] = {**detail, **detail["listing"]}
        for term in filter_terms(criteria.criteria.filters):
            fact = facts[term.attribute]
            if fact["status"] == "known" and fact["qualifier"] == "exact":
                value = fact["value"]
                currency = value["currency"] if term.attribute == "cash_price" else None
                scalar = value["minor_units"] if term.attribute == "cash_price" else value
                ids = list(dict.fromkeys(item["evidence_id"] for item in fact["evidence"]))
                if term_matches(term, scalar, currency) and len(ids) <= 12:
                    reasons.append(
                        FitReason(
                            criterion=term.attribute,
                            attribute=term.attribute,
                            evidence_ids=ids,
                            text=(
                                "The supplied source supports the requested "
                                f"{term.attribute.replace('_', ' ')} filter."
                            ),
                        )
                    )
                    continue
                reason = "unmet" if not term_matches(term, scalar, currency) else "unverified"
            else:
                reason = (
                    fact["status"] if fact["status"] in {"unknown", "conflicting"} else "unverified"
                )
            questions.append(
                UnresolvedQuestion.model_validate(
                    {
                        "criterion": term.attribute,
                        "attribute": term.attribute,
                        "reason": reason,
                        "question": (
                            f"Confirm the {term.attribute.replace('_', ' ')} "
                            "against your stated requirement."
                        ),
                    }
                )
            )
        if selected.state == "historical":
            questions.append(
                UnresolvedQuestion(
                    criterion="selected listing",
                    attribute="listing",
                    reason="unverified",
                    question=(
                        "This is a historical version; check a current exact listing "
                        "before arranging a viewing."
                    ),
                )
            )
    else:
        questions.append(
            UnresolvedQuestion(
                criterion="selected listing",
                attribute="listing",
                reason="unknown",
                question="Read the selected listing successfully before judging its fit.",
            )
        )
    if expressed.query:
        questions.append(
            UnresolvedQuestion(
                criterion="search text",
                attribute="query",
                reason="unverified",
                question=(
                    "Confirm how this listing meets your search text; "
                    "literal matching is not verification."
                ),
            )
        )
    if expressed.soft_preferences:
        questions.append(
            UnresolvedQuestion(
                criterion="stated preferences",
                attribute="preferences",
                reason="unverified",
                question=(
                    "Discuss your stated preferences; "
                    "lexical relevance does not verify suitability."
                ),
            )
        )
    # Revalidate detached values at the public boundary: immutable internal refs
    # and base wire refs identify the same listing but have different model classes.
    return HandoffSummary.model_validate(
        {
            "selected_ref": selected_ref.model_dump(mode="json"),
            "listing": selected.model_dump(mode="json"),
            "expressed_criteria": expressed.model_dump(mode="json"),
            "fit_reasons": [reason.model_dump(mode="json") for reason in reasons],
            "unresolved_questions": [question.model_dump(mode="json") for question in questions],
        }
    )
