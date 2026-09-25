"""Minimized projections plus independent comparison to the pinned reviewed fact ledger."""

import json
import re
from typing import Any

from pydantic import JsonValue

from app.api.schemas.inventory import ListingDetail, ListingSummary
from app.api.schemas.sessions import MessageResult, SessionState
from app.assistant.grounding import fact_for
from app.assistant.packet import minimize_text

from .effects import DomainSnapshot, project_effects
from .prose import prose_matches
from .schema import Step


def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            name in actual and _matches(value, actual[name]) for name, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(
            _matches(left, right) for left, right in zip(expected, actual, strict=True)
        )
    return expected == actual


def project(
    result: MessageResult | None, current: SessionState, *, before: DomainSnapshot,
    after: DomainSnapshot, oracle: dict[str, Any], namespace: str, snapshot: str, step: Step,
    error: str | None = None,
) -> dict[str, JsonValue]:
    observed: dict[str, JsonValue] = {
        "error_code": error, "selected_id": None if current.selected_ref is None else current.selected_ref.source_id,
        "selected_ref": None if current.selected_ref is None else current.selected_ref.model_dump(mode="json"),
        "pending_kind": current.pending_intent.kind,
        "pending_purpose": getattr(current.pending_intent, "purpose", None),
        "criteria": current.criteria.model_dump(mode="json"),
        "recalled": {entry.preference.key: entry.preference.model_dump(mode="json")["value"]
                     for entry in current.recalled_preferences.entries},
        "search_ids": [], "comparison_ids": [], "listing_refs": [],
        "evidence_refs": [], "fact_statuses": {},
        "grounding_matches": True, "reference_namespace_matches": True,
    }
    observed.update(project_effects(before, after))
    prose = prose_matches(result, step, oracle)
    if prose is not None:
        observed["prose_matches"] = prose
    if result is None:
        return observed
    observed.update({
        "state": result.state, "provider_state": result.provider_state,
        "text": minimize_text(result.text)[:12000], "persistence": result.persistence,
        "actions": {"preferences": result.actions.preferences.state,
                    "shortlist": result.actions.shortlist.state, "lead": result.actions.lead.state},
        "operation_state": None if result.operation is None else result.operation.state,
        "evidence_refs": [item.ref.model_dump(mode="json") for item in result.evidence],
    })
    items: list[ListingSummary | ListingDetail] = []
    if result.search is not None:
        items.extend(result.search.items)
        observed["search_ids"] = [item.ref.source_id for item in result.search.items]
        observed["search_total"] = result.search.supported_total
        observed["search_has_next"] = result.search.next_cursor is not None
    if result.comparison is not None:
        items.extend(item for item in result.comparison.items if isinstance(item, ListingDetail))
        observed["comparison_ids"] = [
            item.listing.ref.source_id if isinstance(item, ListingDetail) else item.ref.source_id
            for item in result.comparison.items
        ]
    if result.handoff_summary is not None and isinstance(result.handoff_summary.listing, ListingDetail):
        detail = result.handoff_summary.listing
        items.append(detail)
        observed["fact_statuses"] = {
            name: fact_for(detail, name).status for name in oracle[detail.listing.ref.source_id]["public_facts"]
        }
    exact = True
    observed["listing_refs"] = [
        (item.listing.ref if isinstance(item, ListingDetail) else item.ref).model_dump(mode="json")
        for item in items
    ]
    arabic_seen = False
    arabic_exact = True
    refs = [item.ref for item in result.evidence]
    if current.selected_ref is not None:
        refs.append(current.selected_ref)
    if result.actions.shortlist.state == "succeeded":
        refs.append(result.actions.shortlist.result.ref)
    if result.operation is not None and result.operation.state == "succeeded":
        refs.append(result.operation.booking.review.ref)
        observed["booking_ref"] = result.operation.booking.review.ref.model_dump(mode="json")
        observed["booking_start"] = result.operation.booking.review.local_start
    for item in items:
        ref = item.listing.ref if isinstance(item, ListingDetail) else item.ref
        refs.append(ref)
        expected = oracle.get(ref.source_id)
        if expected is None or expected["ref"] != ref.model_dump(mode="json"):
            exact = False
            continue
        families = expected["public_facts"]
        names = tuple(families) if isinstance(item, ListingDetail) else (
            "make", "model", "trim", "year", "cash_price", "mileage_km",
        )
        for name in names:
            actual = fact_for(item, name).model_dump(mode="json")
            same = _matches(families[name], actual)
            exact = exact and same
            if re.search(r"[\u0600-\u06ff]", json.dumps(families[name], ensure_ascii=False)):
                arabic_seen = True
                arabic_exact = arabic_exact and same
    observed["grounding_matches"] = exact
    observed["reference_namespace_matches"] = all(
        ref.namespace == namespace and ref.snapshot_id == snapshot and ref.source_id in oracle for ref in refs
    )
    observed["arabic_evidence_preserved"] = arabic_seen and arabic_exact
    return observed
