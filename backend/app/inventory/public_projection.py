"""Pure public projection of an already audited exact ListingRow; never extraction."""

import json
from dataclasses import dataclass
from typing import Any, Literal

from app.api.schemas.inventory import ListingDetail, ListingSummary, SourceLocator
from app.inventory.compact_reader import MAX_PROJECTION_BYTES, CompactReference
from app.inventory.review_catalogue import PUBLIC_FAMILIES
from app.inventory.snapshot_codec import ListingRow


@dataclass(frozen=True, slots=True)
class ListingEligibility:
    state: Literal["simulated_eligible", "unavailable", "configuration_missing"]
    reason: str


def _material(row: ListingRow) -> dict[str, Any]:
    if len(row.normalized_json.encode("utf-8")) > MAX_PROJECTION_BYTES:
        raise ValueError("INVENTORY_PUBLIC_PROJECTION_INVALID")
    data: dict[str, Any] = json.loads(row.normalized_json)
    if data["ref"] != row.ref.model_dump() or data["source_row"] != row.source_row:
        raise ValueError("INVENTORY_PUBLIC_REFERENCE_MISMATCH")
    claims = data["claims"]
    if len({claim["annotation"]["key"] for claim in claims}) != len(claims):
        raise ValueError("INVENTORY_PUBLIC_CLAIM_COLLISION")
    sources = {
        value["provenance"]["source"]["coordinate"]: value["provenance"]
        for value in data["fields"].values()
    }
    for claim in claims:
        if claim["ref"] != data["ref"]:
            raise ValueError("INVENTORY_PUBLIC_EVIDENCE_ASSOCIATION")
        for value in claim["evidence"]:
            locator = SourceLocator.model_validate(value)
            provenance = sources[locator.cell]
            source = provenance["source"]
            original = (
                source["value"]["value"]
                if source["value"]["type"] == "str"
                else source["storage"]["value"]
            )
            if (
                locator.workbook_sha256 != provenance["workbook_sha256"]
                or locator.sheet != provenance["sheet"]
                or type(original) is not str
                or original[locator.span_start : locator.span_end] != locator.raw_text
            ):
                raise ValueError("INVENTORY_PUBLIC_EVIDENCE_ASSOCIATION")
    return data


def public_facts(data: dict[str, Any]) -> dict[str, Any]:
    """Use frozen resolution decisions and every group locator without truncation."""
    claims = {claim["annotation"]["key"]: claim for claim in data["claims"]}
    result: dict[str, Any] = {}
    for resolution in data["resolutions"]:
        family = resolution["family"]
        if family not in PUBLIC_FAMILIES:
            continue
        if family in result:
            raise ValueError("INVENTORY_PUBLIC_FAMILY_COLLISION")
        if resolution["status"] == "unknown":
            result[family] = {"status": "unknown", "reason": resolution["reason"]}
            continue
        groups = []
        for group in resolution["groups"]:
            value = group["value"]["value"]
            if family == "cash_price":
                value = {
                    "minor_units": value,
                    "currency": group["value"]["currency"],
                    "basis": "cash",
                }
            evidence = []
            for key in group["claim_keys"]:
                claim = claims[key]
                if claim["annotation"]["family"] != family:
                    raise ValueError("INVENTORY_PUBLIC_EVIDENCE_ASSOCIATION")
                evidence.extend(claim["evidence"])
            groups.append({"value": value, "qualifier": group["qualifier"], "evidence": evidence})
        if resolution["status"] == "known":
            if len(groups) != 1:
                raise ValueError("INVENTORY_PUBLIC_RESOLUTION_INVALID")
            result[family] = {"status": "known", **groups[0]}
        elif resolution["status"] == "conflicting":
            result[family] = {"status": "conflicting", "claims": groups}
        else:
            raise ValueError("INVENTORY_PUBLIC_RESOLUTION_INVALID")
    if set(result) != set(PUBLIC_FAMILIES):
        raise ValueError("INVENTORY_PUBLIC_FAMILY_MISSING")
    return result


def _summary(row: ListingRow, data: dict[str, Any], facts: dict[str, Any]) -> ListingSummary:
    warnings = ["Listing claims have not been independently verified."]
    if any(fact["status"] == "conflicting" for fact in facts.values()):
        warnings.append("Some source claims conflict; check the attributed alternatives.")
    if any(item["partial_coverage"] for item in data["resolutions"]):
        warnings.append("Some source information cannot be represented as a confirmed fact.")
    if any(claim["annotation"]["family"] == "money" for claim in data["claims"]):
        warnings.append("Finance offers, fees and service costs are not the cash price.")
    if any(
        data["fields"][name]["text"]["state"] in {"withheld", "unsupported"}
        for name in ("title", "description")
    ):
        warnings.append("Some source text could not be displayed safely or interpreted reliably.")
    title = data["fields"]["title"]["text"]["display"]
    return ListingSummary.model_validate(
        {
            "ref": row.ref.model_dump(),
            "title": title or f"Listing {row.ref.source_id}",
            **{
                name: facts[name]
                for name in ("make", "model", "trim", "year", "cash_price", "mileage_km")
            },
            "photo": data["photo"],
            "evidence_warnings": warnings,
        }
    )


def map_listing_summary(row: ListingRow) -> ListingSummary:
    """Trusted input must come from CompactReader or an accepted staged audit."""
    data = _material(row)
    return _summary(row, data, public_facts(data))


def map_listing_detail(
    item: CompactReference, *, eligibility: ListingEligibility | None = None
) -> ListingDetail:
    if item.state not in {"current", "historical"} or item.listing is None:
        raise ValueError("INVENTORY_PUBLIC_DETAIL_REQUIRES_LISTING")
    if item.ref != item.listing.ref:
        raise ValueError("INVENTORY_PUBLIC_REFERENCE_MISMATCH")
    data = _material(item.listing)
    facts = public_facts(data)
    if item.state == "historical":
        eligibility = ListingEligibility("unavailable", "This is a historical listing version.")
    elif eligibility is None:
        eligibility = ListingEligibility(
            "configuration_missing", "Viewing eligibility has not been configured."
        )
    return ListingDetail.model_validate(
        {
            "state": item.state,
            "listing": _summary(item.listing, data, facts).model_dump(mode="json"),
            "description": data["fields"]["description"]["text"]["display"] or "",
            **{
                name: facts[name]
                for name in (
                    "fuel_type",
                    "body_type",
                    "transmission",
                    "location",
                    "warranty",
                    "service_history",
                )
            },
            "eligibility": eligibility.state,
            "eligibility_reason": eligibility.reason,
        }
    )
