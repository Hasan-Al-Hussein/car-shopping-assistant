"""Bounded parameterized predicates over audited persisted resolutions and index."""

import sqlite3
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas.inventory import ConstraintCoverage, SearchFilters
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.inventory.search_policy import MAX_SEARCH_RECORDS, TOKEN, SearchPolicy, fold

MAX_DOCUMENT_BYTES = 256 * 1024
TEXT_FILTERS = (
    ("makes", "make"),
    ("models", "model"),
    ("trims", "trim"),
    ("body_types", "body_type"),
    ("fuel_types", "fuel_type"),
    ("transmissions", "transmission"),
)
RANGE_FILTERS = (("years", "year"), ("budget", "cash_price"), ("mileage_km", "mileage_km"))


@dataclass(frozen=True, slots=True)
class FilterTerm:
    attribute: str
    values: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    currency: str | None = None


def filter_terms(filters: SearchFilters) -> tuple[FilterTerm, ...]:
    terms = []
    for name, attribute in TEXT_FILTERS:
        values = tuple(getattr(filters, name))
        if values:
            terms.append(FilterTerm(attribute, values))
    for name, attribute in RANGE_FILTERS:
        value = getattr(filters, name)
        if value is not None:
            terms.append(
                FilterTerm(
                    attribute,
                    minimum=value.minimum,
                    maximum=value.maximum,
                    currency=value.currency if name == "budget" else None,
                )
            )
    return tuple(terms)


def term_matches(term: FilterTerm, value: str | int, currency: str | None = None) -> bool:
    if term.values:
        return isinstance(value, str) and fold(value) in term.values
    return (
        type(value) is int
        and (term.currency is None or currency == term.currency)
        and (term.minimum is None or value >= term.minimum)
        and (term.maximum is None or value <= term.maximum)
    )


@dataclass(frozen=True, slots=True)
class RankedRef:
    source_id: str
    preference_score: int


@dataclass(frozen=True, slots=True)
class SearchSelection:
    namespace: str
    source_total: int
    ranked: tuple[RankedRef, ...]
    coverage: tuple[ConstraintCoverage, ...]


def _coverage(
    session: Session, namespace: str, snapshot: str, total: int, terms: tuple[FilterTerm, ...]
) -> tuple[ConstraintCoverage, ...]:
    output = []
    for term in terms:
        counts = {
            "supported": 0,
            "excluded_unknown": 0,
            "excluded_conflicting": 0,
            "excluded_unsupported_qualifier": 0,
        }
        rows = session.execute(
            text(
                "SELECT json_extract(r.value,'$.status'), "
                "json_extract(r.value,'$.strict_match_eligible'), "
                "json_extract(r.value,'$.groups[0].qualifier'), "
                "json_extract(r.value,'$.groups[0].value.currency'), count(*) "
                "FROM listing_versions l, json_each(l.normalized_json,'$.resolutions') r "
                "WHERE l.namespace=:namespace AND l.snapshot_id=:snapshot "
                "AND json_extract(r.value,'$.family')=:family GROUP BY 1,2,3,4"
            ),
            {"namespace": namespace, "snapshot": snapshot, "family": term.attribute},
        )
        for status, strict, qualifier, currency, amount in rows:
            category = (
                "excluded_unknown"
                if status == "unknown"
                else "excluded_conflicting"
                if status == "conflicting"
                else "supported"
                if status == "known"
                and strict == 1
                and qualifier == "exact"
                and (term.currency is None or currency == term.currency)
                else "excluded_unsupported_qualifier"
            )
            counts[category] += amount
        output.append(
            ConstraintCoverage.model_validate(
                {"attribute": term.attribute, "source_total": total, **counts}
            )
        )
    return tuple(output)


def _predicate(terms: tuple[FilterTerm, ...]) -> tuple[str, dict[str, Any]]:
    predicates = []
    parameters: dict[str, Any] = {}
    for ordinal, term in enumerate(terms):
        prefix = f"filter_{ordinal}"
        parameters[prefix + "_family"] = term.attribute
        clauses = [
            f"json_extract(r.value,'$.family')=:{prefix}_family",
            "json_extract(r.value,'$.status')='known'",
            "json_extract(r.value,'$.strict_match_eligible')=1",
            "json_extract(r.value,'$.groups[0].qualifier')='exact'",
        ]
        value_sql = "json_extract(r.value,'$.groups[0].value.value')"
        if term.values:
            names = []
            for index, value in enumerate(term.values):
                name = f"{prefix}_value_{index}"
                parameters[name] = value
                names.append(":" + name)
            clauses.append("json_type(r.value,'$.groups[0].value.value')='text'")
            clauses.append(f"inventory_search_fold({value_sql}) IN ({','.join(names)})")
        else:
            clauses.append("json_type(r.value,'$.groups[0].value.value')='integer'")
            for name, operator, boundary in (
                ("minimum", ">=", term.minimum),
                ("maximum", "<=", term.maximum),
            ):
                if boundary is not None:
                    parameters[f"{prefix}_{name}"] = boundary
                    clauses.append(f"{value_sql}{operator}:{prefix}_{name}")
            if term.currency is not None:
                parameters[prefix + "_currency"] = term.currency
                clauses.extend(
                    (
                        f"json_extract(r.value,'$.groups[0].value.currency')=:{prefix}_currency",
                        "json_extract(r.value,'$.groups[0].value.unit')='minor_units'",
                        "json_extract(r.value,'$.groups[0].value.basis')='cash'",
                    )
                )
        predicates.append(
            "EXISTS(SELECT 1 FROM json_each(l.normalized_json,'$.resolutions') r WHERE "
            + " AND ".join(clauses)
            + ")"
        )
    return " AND ".join(predicates) or "1=1", parameters


def select_matches(
    session: Session, observation: InventoryObservation, policy: SearchPolicy
) -> SearchSelection:
    """Caller must recheck the compact header identity in THIS Store.read unit first."""
    metadata = (
        session.connection()
        .exec_driver_sql(
            "SELECT namespace,index_version,accepted_count FROM inventory_snapshots "
            "WHERE snapshot_id=?",
            (observation.snapshot_id,),
        )
        .first()
    )
    if metadata is None or metadata[1] != observation.index_version:
        raise ApiFailure("SNAPSHOT_STALE")
    namespace, _, total = metadata
    if type(total) is not int or not 0 <= total <= MAX_SEARCH_RECORDS:
        raise ApiFailure("UNSUPPORTED_STATE")
    snapshot = observation.snapshot_id
    assert snapshot is not None
    terms = filter_terms(policy.criteria.filters)
    coverage = _coverage(session, namespace, snapshot, total, terms)
    if policy.unsupported:
        return SearchSelection(namespace, total, (), coverage)
    connection = cast(sqlite3.Connection, session.connection().connection.driver_connection)
    connection.create_function("inventory_search_fold", 1, fold, deterministic=True)
    try:
        predicate, parameters = _predicate(terms)
        parameters.update(namespace=namespace, snapshot=snapshot, limit=MAX_SEARCH_RECORDS + 1)
        eligible = set(
            session.execute(
                text(
                    "SELECT l.source_id FROM listing_versions l "
                    "WHERE l.namespace=:namespace AND l.snapshot_id=:snapshot AND "
                    + predicate
                    + " ORDER BY l.source_id COLLATE BINARY LIMIT :limit"
                ),
                parameters,
            ).scalars()
        )
    finally:
        connection.create_function("inventory_search_fold", 1, None)
    if len(eligible) > total:
        raise ValueError("INVENTORY_SEARCH_POPULATION_MISMATCH")
    rows = (
        session.connection()
        .exec_driver_sql(
            "SELECT source_id,CASE WHEN length(CAST(document_text AS BLOB))<=? "
            "THEN document_text ELSE NULL END FROM inventory_search_documents "
            "WHERE namespace=? AND snapshot_id=? AND index_version=? "
            "ORDER BY source_id COLLATE BINARY LIMIT ?",
            (
                MAX_DOCUMENT_BYTES,
                namespace,
                snapshot,
                observation.index_version,
                MAX_SEARCH_RECORDS + 1,
            ),
        )
        .all()
    )
    if len(rows) != total or any(type(document) is not str for _, document in rows):
        raise ValueError("INVENTORY_SEARCH_INDEX_INVALID")
    documents = {source_id: document for source_id, document in rows}
    if not eligible <= documents.keys():
        raise ValueError("INVENTORY_SEARCH_INDEX_INVALID")
    if policy.terms and observation.mode == "fts5":
        # Only internally tokenized quoted terms enter FTS grammar. No raw user expression.
        expression = " AND ".join('"' + term + '"' for term in policy.terms)
        postings = set(
            session.execute(
                text(
                    "SELECT source_id FROM inventory_search_fts "
                    "WHERE inventory_search_fts MATCH :terms "
                    "AND namespace=:namespace AND snapshot_id=:snapshot AND index_version=:version "
                    "ORDER BY source_id COLLATE BINARY LIMIT :limit"
                ),
                {
                    "terms": expression,
                    "namespace": namespace,
                    "snapshot": snapshot,
                    "version": observation.index_version,
                    "limit": MAX_SEARCH_RECORDS + 1,
                },
            ).scalars()
        )
        eligible &= postings
    ranked = []
    for source_id in eligible:
        # Full document vocabulary is bounded by source material, not the query-token limit.
        tokens = {token.casefold() for token in TOKEN.findall(documents[source_id])}
        if not set(policy.terms) <= tokens:
            continue
        score = sum(term in tokens for term in policy.preferences)
        ranked.append(RankedRef(source_id, score))
    ranked.sort(key=lambda item: (-item.preference_score, item.source_id))
    return SearchSelection(namespace, total, tuple(ranked), coverage)
