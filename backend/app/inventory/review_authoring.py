"""Concise constructors for the explicitly reviewed source catalogue, not parsers."""

import hashlib
import json

from app.inventory.review_catalogue import (
    ClaimAnnotation,
    ClaimCondition,
    Disposition,
    Family,
    FamilyHold,
    Qualifier,
    RecordReview,
    SourceField,
)


def claim(
    family: Family,
    quote: str,
    value: str | int | None = None,
    *,
    field: SourceField = "description",
    role: str | None = None,
    unit: str | None = None,
    currency: str | None = None,
    basis: str | None = None,
    disposition: Disposition = "accepted",
    qualifier: Qualifier = "exact",
    subject: str = "vehicle",
    polarity: str = "positive",
    reason: str | None = None,
    occurrence: int | None = None,
    conditions: tuple[ClaimCondition, ...] = (),
) -> ClaimAnnotation:
    data = {
        "family": family,
        "source": {"source_field": field, "quote": quote, "occurrence": occurrence},
        "value": {
            "value": quote if value is None else value,
            "unit": unit,
            "currency": currency,
            "basis": basis,
        },
        "role": role or family,
        "qualifier": qualifier,
        "disposition": disposition,
        "subject": subject,
        "polarity": polarity,
        "conditions": [item.model_dump() for item in conditions],
        "reason": reason
        or (
            "Explicit source claim reviewed against this listing's complete context; not "
            "independent vehicle verification."
        ),
    }
    key_hash = hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]
    return ClaimAnnotation.model_validate({"key": f"{family}-{key_hash}", **data})


def term(
    kind: str,
    quote: str,
    value: str | int,
    *,
    unit: str | None = None,
    field: SourceField = "description",
) -> ClaimCondition:
    return ClaimCondition.model_validate(
        {
            "kind": kind,
            "source": {"source_field": field, "quote": quote},
            "value": {"value": value, "unit": unit},
        }
    )


def cash(quote: str, minor_units: int, *, field: SourceField = "description") -> ClaimAnnotation:
    return claim(
        "cash_price",
        quote,
        minor_units,
        field=field,
        role="cash_price",
        unit="minor_units",
        currency="AED",
        basis="cash",
    )


def finance(
    quote: str,
    minor_units: int,
    *,
    down: int | None = None,
    years: int | None = None,
    field: SourceField = "description",
    qualifier: Qualifier = "exact",
    flexible: bool = False,
) -> ClaimAnnotation:
    terms = []
    if down is not None:
        terms.append(term("down_payment", quote, down, unit="percent", field=field))
    if years is not None:
        terms.append(term("finance_term", quote, years, unit="years", field=field))
    if flexible:
        terms.append(
            term("other", quote, "flexible offer; scope/eligibility unspecified", field=field)
        )
    return claim(
        "money",
        quote,
        minor_units,
        field=field,
        role="finance_instalment",
        unit="minor_units",
        currency="AED",
        basis="monthly_finance",
        qualifier=qualifier,
        conditions=tuple(terms),
    )


def mileage(
    quote: str, km: int, *, field: SourceField = "description", qualifier: Qualifier = "exact"
) -> ClaimAnnotation:
    return claim(
        "mileage_km", quote, km, field=field, role="vehicle_mileage", unit="km", qualifier=qualifier
    )


def record(
    source_id: str,
    row: int,
    note: str,
    *claims: ClaimAnnotation,
    holds: tuple[FamilyHold, ...] = (),
) -> RecordReview:
    return RecordReview(
        source_id=source_id,
        source_row=row,
        review_complete=True,
        note=note,
        claims=claims,
        holds=holds,
    )
