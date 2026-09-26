"""Natural synthesis over bounded, owned inventory evidence; no mutation authority.

The model chooses the explanation, not the facts or arithmetic. Compact source IDs
are resolved locally to the original listings. Citation/numeric checks are useful
guards, not a proof that arbitrary natural language is logically entailed.
"""

import json
import re
from collections import Counter
from collections.abc import MutableMapping
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import Field

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    CashMoney,
    ConflictingFact,
    KnownFact,
    ListingDetail,
    ListingSummary,
    SearchCriteria,
    UnknownFact,
)
from app.api.schemas.sessions import AnswerEvidence, MessageRequest, SessionState, TranscriptTurn
from app.core.config import FrozenSettings

from .answer_assembly import GroundedAnswer
from .budget import TurnBudget
from .grounding import (
    LABELS,
    EvidenceBindings,
    FactualClaimReference,
    GroundingError,
    fact_for,
    key,
)
from .output_policy import safe_assistant_text
from .packet import (
    MAX_INPUT_TOKENS,
    MAX_SOURCE_CONTEXT_CHARS,
    ConversationMessage,
    EvidencePacket,
    minimize_text,
    output_system_instruction,
)
from .provider import GeminiAdapter
from .request_diagnostics import generate_for_request

Row = ListingSummary | ListingDetail
_SUMMARY_FIELDS = ("make", "model", "trim", "year", "cash_price", "mileage_km")
_NUMBER = re.compile(r"(?<![\w])\d+(?:,\d{3})*(?:\.\d+)?(?:k\b)?", re.IGNORECASE)
_WORDS = re.compile(r"\b[\w'-]{3,}\b", re.UNICODE)
_MONEY_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?(?:\s*[kK])?"
_CURRENCY = r"(?:(?:UAE\s+)?dirhams?|dhs?|[A-Z]{3})"
_CASH_SUFFIX = r"(?:\s+(?:total\s+)?cash(?:\s+(?:purchase\s+)?price)?)?"
_MONEY_EXPRESSION = (
    rf"(?:{_CURRENCY}\s*{_MONEY_AMOUNT}|{_MONEY_AMOUNT}\s*{_CURRENCY}){_CASH_SUFFIX}"
)
_CASH_QUOTE = re.compile(
    rf"(?:({_CURRENCY})\s*({_MONEY_AMOUNT})|({_MONEY_AMOUNT})\s*({_CURRENCY})){_CASH_SUFFIX}",
    re.IGNORECASE,
)
_PERIODIC_BASIS = re.compile(
    r"^\s*(?:per\s+month|a\s+month|monthly|/\s*(?:month|mo)|"
    r"in\s+(?:monthly\s+)?(?:payments|instalments|installments))\b",
    re.IGNORECASE,
)
_LINK = re.compile(r"https?://|www\.|mailto:|<[^>]+>", re.IGNORECASE)
_RECEIPT = re.compile(
    r"\b(?:I(?:'ve| have)?|we(?:'ve| have)?)\s+(?:successfully\s+)?"
    r"(?:booked|reserved|saved|submitted|sent|approved|confirmed)\b|"
    r"\b(?:booking|reservation|application|loan)\s+(?:is|has been)\s+"
    r"(?:confirmed|approved|completed)\b",
    re.IGNORECASE,
)
_STATE_WARNING = re.compile(
    r"conflict|disagree|unclear|unknown|uncertain|missing|unavailable|unverified|"
    r"undisclosed|unspecified|unstated|\b(?:not|no|cannot|can't|couldn't|doesn't|lack|lacks)\b",
    re.IGNORECASE,
)


class SourceCitation(FrozenSettings):
    source_id: Annotated[str, Field(min_length=1, max_length=80)] = Field(
        description="Exact source key, including field: car1.year, car2.description, "
        "stats.cash_price, group.make1, scope or application. Never a bare car1 row ID.",
    )
    quote: Annotated[str, Field(min_length=1, max_length=500)] = Field(
        description="Short exact substring of the cited value/source, e.g. 2022 for car1.year. "
        "For an aggregate cite its JSON value; do not paraphrase the quote.",
    )


class GroundedParagraph(FrozenSettings):
    text: Annotated[str, Field(min_length=1, max_length=1600)] = Field(
        description="Readable user-facing prose. Keep all source keys in citations only; "
        "never print raw source IDs or bracketed citation markers in this text.",
    )
    citations: Annotated[
        list[SourceCitation],
        Field(
            min_length=1,
            max_length=32,
            description="Cite every numeric claim and the facts stated for each car. "
            "Do not omit later cars' mileage or prices to save citations. Split a long "
            "comparison into readable paragraphs when helpful, each with its own citations.",
        ),
    ]


class GroundedConversationDraft(FrozenSettings):
    """Answer each part naturally; cite exact source IDs and short verbatim quotes.

    Answer the actual question concisely. Acknowledge retained preferences without
    relisting unchanged cars unless asked. Focus on that car when asked about one
    car. When listing cars, cite every numeric claim and the facts for each car.
    Cell IDs are row_id.field, statistics IDs are stats.field or group IDs, and
    scope/application are available for coverage and app behavior. Use statistics
    for counts/extrema. Every paragraph needs support, including limitations.
    Say what is missing rather than asking for irrelevant search criteria.
    """

    status: Literal["answered", "partial", "unanswerable"]
    paragraphs: Annotated[list[GroundedParagraph], Field(min_length=1, max_length=6)]
    missing_facts: Annotated[list[Annotated[str, Field(max_length=160)]], Field(max_length=6)] = (
        Field(default_factory=list)
    )


@dataclass(frozen=True)
class SourceSupport:
    text: str
    refs: tuple[InventoryRef, ...] = ()
    attribute: str | None = None
    state: str = "known"
    evidence_ids: tuple[str, ...] = ()
    qualifier: str | None = None
    buyer_owned: bool = False
    identity_kind: Literal["row", "listing"] | None = None


@dataclass(frozen=True)
class GroundedCorpus:
    context: str
    sources: dict[str, SourceSupport]
    description_excerpts: bool
    accepted_criteria: SearchCriteria | None = None


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _value(value: object, private_values: tuple[str, ...]) -> str | int:
    if isinstance(value, CashMoney):
        amount = Decimal(value.minor_units) / 100
        return f"{value.currency} {amount:,.2f} cash"
    if type(value) is int:
        return value
    if isinstance(value, str):
        return minimize_text(safe_assistant_text(value), private_values)[:500]
    raise GroundingError("UNSUPPORTED_FACT_VALUE")


def _cell(
    row: Row, field: str, bindings: EvidenceBindings, private_values: tuple[str, ...]
) -> tuple[object, SourceSupport]:
    if isinstance(row, ListingSummary) and field not in _SUMMARY_FIELDS:
        return {"not_retrieved": True}, SourceSupport(
            f"{LABELS[field]}: not retrieved", (row.ref,), field, "unknown"
        )
    fact = fact_for(row, field)
    ref = row.listing.ref if isinstance(row, ListingDetail) else row.ref
    ids = bindings.bind(ref, field, fact)
    if isinstance(fact, UnknownFact):
        value: object = None
        text = f"null; {LABELS[field]}: {fact.reason.replace('_', ' ')}"
    elif isinstance(fact, ConflictingFact):
        value = {
            "conflicting": [
                {claim.qualifier: _value(claim.value, private_values)} for claim in fact.claims
            ]
        }
        text = _json(value)
    else:
        converted = _value(fact.value, private_values)
        value = converted if fact.qualifier == "exact" else {fact.qualifier: converted}
        text = _json(value) if isinstance(value, dict) else str(value)
    return value, SourceSupport(
        text,
        (ref,),
        field,
        fact.status,
        ids,
        fact.qualifier if isinstance(fact, KnownFact) else None,
    )


def _excerpt(description: str, question: str, limit: int, private_values: tuple[str, ...]) -> str:
    clean = minimize_text(safe_assistant_text(description), private_values)
    if len(clean) <= limit:
        return clean
    terms = {word.casefold() for word in _WORDS.findall(question)}
    parts = re.split(r"(?<=[.!?])\s+|[\r\n]+", clean)
    ranked = sorted(
        enumerate(parts),
        key=lambda pair: (
            -len(terms.intersection(word.casefold() for word in _WORDS.findall(pair[1]))),
            pair[0],
        ),
    )
    chosen: list[tuple[int, str]] = []
    remaining = limit
    for index, part in ranked:
        if not part.strip() or remaining < 30:
            continue
        snippet = part[:remaining]
        chosen.append((index, snippet))
        remaining -= len(snippet) + 3
    return " … ".join(text for _, text in sorted(chosen))[:limit]


def _statistics(
    rows: tuple[Row, ...], fields: tuple[str, ...], private_values: tuple[str, ...]
) -> dict[str, object]:
    result: dict[str, object] = {}
    for field in fields:
        fetched = [
            row for row in rows if isinstance(row, ListingDetail) or field in _SUMMARY_FIELDS
        ]
        facts = [fact_for(row, field) for row in fetched]
        exact = [
            fact for fact in facts if isinstance(fact, KnownFact) and fact.qualifier == "exact"
        ]
        data: dict[str, object] = {
            "total": len(rows),
            "exact": len(exact),
            "unknown": sum(isinstance(fact, UnknownFact) for fact in facts),
            "conflicting": sum(isinstance(fact, ConflictingFact) for fact in facts),
            "qualified": sum(
                isinstance(fact, KnownFact) and fact.qualifier != "exact" for fact in facts
            ),
            "not_retrieved": len(rows) - len(fetched),
        }
        if field in {"year", "mileage_km"} and exact:
            numbers = [fact.value for fact in exact if type(fact.value) is int]
            if numbers:
                data.update(minimum=min(numbers), maximum=max(numbers))
        elif field == "cash_price":
            currencies: dict[str, list[int]] = {}
            for fact in exact:
                if isinstance(fact.value, CashMoney):
                    currencies.setdefault(fact.value.currency, []).append(fact.value.minor_units)
            data["currencies"] = {
                currency: {
                    "count": len(values),
                    "minimum": f"{Decimal(min(values)) / 100:,.2f}",
                    "maximum": f"{Decimal(max(values)) / 100:,.2f}",
                }
                for currency, values in sorted(currencies.items())
            }
        elif field in {"make", "model", "body_type", "fuel_type", "transmission", "location"}:
            counts = Counter(str(_value(fact.value, private_values)).casefold() for fact in exact)
            data["distribution"] = dict(sorted(counts.items()))
        result[field] = data
    return result


def build_grounded_corpus(
    rows: tuple[Row, ...],
    *,
    scope: str,
    complete: bool,
    total: int | None,
    question: str = "",
    context_note: str = "",
    private_values: tuple[str, ...] = (),
    description_limit: int = 600,
    accepted_criteria: SearchCriteria | None = None,
) -> GroundedCorpus:
    """Keep every row and fact state; derive arithmetic before asking the model."""
    refs = tuple(row.listing.ref if isinstance(row, ListingDetail) else row.ref for row in rows)
    if len(refs) > 200 or len({key(ref) for ref in refs}) != len(refs):
        raise GroundingError("INVALID_CORPUS_IDENTITIES")
    if len({(ref.namespace, ref.snapshot_id) for ref in refs}) > 1:
        raise GroundingError("MIXED_CORPUS_SNAPSHOTS")
    if total is not None and (total < len(rows) or (complete and total != len(rows))):
        raise GroundingError("INVALID_CORPUS_COVERAGE")
    fields = (
        tuple(LABELS) if any(isinstance(row, ListingDetail) for row in rows) else _SUMMARY_FIELDS
    )
    bindings = EvidenceBindings()
    sources: dict[str, SourceSupport] = {}
    compact_rows: list[list[object]] = []
    descriptions: dict[str, str] = {}
    for index, row in enumerate(rows, 1):
        row_id = f"car{index}"
        values: list[object] = [row_id, refs[index - 1].source_id]
        # Every published column has a citation binding. Identity metadata refers
        # to this exact listing; it does not manufacture a vehicle-attribute claim.
        sources[f"{row_id}.id"] = SourceSupport(
            row_id, (refs[index - 1],), identity_kind="row"
        )
        sources[f"{row_id}.listing_id"] = SourceSupport(
            refs[index - 1].source_id, (refs[index - 1],), identity_kind="listing"
        )
        for field in fields:
            value, support = _cell(row, field, bindings, private_values)
            values.append(value)
            sources[f"{row_id}.{field}"] = support
        compact_rows.append(values)
        if isinstance(row, ListingDetail) and row.description.strip() and description_limit:
            excerpt = _excerpt(row.description, question, description_limit, private_values)
            if excerpt:
                descriptions[f"{row_id}.description"] = excerpt
                sources[f"{row_id}.description"] = SourceSupport(
                    excerpt,
                    (row.listing.ref,),
                    "description",
                )
    stats = _statistics(rows, fields, private_values)
    for field, data in stats.items():
        sources[f"stats.{field}"] = SourceSupport(_json(data), refs, field)
    # Cross-field group arithmetic is computed locally, preserving unknowns.
    groups: dict[str, object] = {}
    for field in ("make", "model"):
        grouped: dict[str, list[Row]] = {}
        for row in rows:
            fact = fact_for(row, field)
            if isinstance(fact, KnownFact) and fact.qualifier == "exact":
                grouped.setdefault(str(_value(fact.value, private_values)).casefold(), []).append(
                    row
                )
        for number, (name, members) in enumerate(sorted(grouped.items()), 1):
            # A unique model already has a complete row; only repeated models need
            # additional cross-field arithmetic. Make counts remain exhaustive.
            if field == "model" and len(members) == 1:
                continue
            group_id = f"group.{field}{number}"
            subset = tuple(members)
            group_data = {
                "field": field,
                "value": name,
                "count": len(subset),
                "cash_price": _statistics(subset, ("cash_price",), private_values)["cash_price"],
            }
            groups[group_id] = group_data
            member_refs = tuple(
                row.listing.ref if isinstance(row, ListingDetail) else row.ref for row in subset
            )
            sources[group_id] = SourceSupport(_json(group_data), member_refs, "cash_price")
    coverage = {
        "scope": scope,
        "rows": len(rows),
        "total": total,
        "complete": complete,
        "description_coverage": "excerpts only" if descriptions else "not retrieved",
        "all_values_are": "listing claims; live stock and condition not verified",
    }
    sources["scope"] = SourceSupport(_json(coverage))
    note = minimize_text(safe_assistant_text(context_note), private_values)[:2000]
    if note:
        sources["application"] = SourceSupport(note)
    buyer_criteria: object = None
    if accepted_criteria is not None:
        buyer_criteria = accepted_criteria.model_dump(mode="json")
        buyer_budget = buyer_criteria["filters"]["budget"]
        if buyer_budget is not None:
            for bound in ("minimum", "maximum"):
                if buyer_budget[bound] is not None:
                    amount = Decimal(buyer_budget[bound]) / 100
                    buyer_budget[bound] = f"{buyer_budget['currency']} {amount:,.2f} cash"

        def minimized(value: Any) -> Any:
            if isinstance(value, str):
                return minimize_text(safe_assistant_text(value), private_values)
            if isinstance(value, dict):
                return {key: minimized(item) for key, item in value.items()}
            if isinstance(value, list):
                return [minimized(item) for item in value]
            return value

        buyer_criteria = minimized(buyer_criteria)
        buyer_text = _json(buyer_criteria)
        sources["buyer.criteria"] = SourceSupport(buyer_text, buyer_owned=True)
    corpus = {
        "legend": (
            "Rows follow columns. Cite carN.field with an exact quote. null means not stated/"
            "unsupported; not_retrieved means the field was not fetched. Conflicting values "
            "remain unresolved. Stats count exact values only. Description excerpts cannot "
            "establish absence. Group counts apply only to retrieved scope. "
            "buyer.criteria contains accepted buyer preferences, never vehicle facts."
        ),
        "scope": coverage,
        "columns": ["id", "listing_id", *fields],
        "rows": compact_rows,
        "statistics": {f"stats.{field}": value for field, value in stats.items()},
        "groups": groups,
        "descriptions": descriptions,
        "application": note,
        "buyer.criteria": buyer_criteria,
    }
    return GroundedCorpus(
        _json(corpus),
        sources,
        bool(descriptions),
        accepted_criteria.model_copy(deep=True) if accepted_criteria is not None else None,
    )


def _numbers(text: str) -> set[Decimal]:
    values = set()
    for match in _NUMBER.finditer(text):
        token = match.group().lower().replace(",", "")
        try:
            values.add(Decimal(token.rstrip("k")) * (1000 if token.endswith("k") else 1))
        except InvalidOperation:
            continue
    return values


def _identity_mentions(
    text: str, row_ids: set[str], corpus: GroundedCorpus
) -> tuple[str, list[SourceSupport]]:
    """Bind complete vehicle labels only to the rows explicitly cited here.

    Remove matched identity spans from numeric checking, not their numbers from
    the whole paragraph. A year in a verified label cannot support a separate
    claim about price, warranty duration, or another vehicle.
    """
    remaining = text
    supports: list[SourceSupport] = []
    for row_id in sorted(row_ids):
        for fields in (("year", "make", "model"), ("make", "model")):
            identity = [corpus.sources.get(f"{row_id}.{field}") for field in fields]
            if any(
                source is None or source.state != "known" or source.qualifier != "exact"
                for source in identity
            ):
                continue
            exact = [source for source in identity if source is not None]
            tokens = [
                r"\s+".join(re.escape(word) for word in source.text.split()) for source in exact
            ]
            if len(tokens) == 3:
                year, make, model = tokens
                pattern = rf"(?:{year}\s+{make}\s+{model}|{make}\s+{model}\s+(?:{year}|\({year}\)))"
            else:
                pattern = rf"{tokens[0]}\s+{tokens[1]}"
            remaining, count = re.subn(
                rf"(?<!\w){pattern}(?!\w)", "", remaining, flags=re.IGNORECASE
            )
            if count:
                supports.extend(exact)
    return remaining, supports


def _resolve_source(source_id: str, corpus: GroundedCorpus) -> SourceSupport | None:
    """Resolve a real JSON member under the longest registered source prefix."""
    if source_id in corpus.sources:
        return corpus.sources[source_id]
    prefix = source_id
    while "." in prefix:
        prefix = prefix.rsplit(".", 1)[0]
        parent = corpus.sources.get(prefix)
        if parent is None:
            continue
        try:
            value = json.loads(parent.text)
        except (ValueError, TypeError):
            return None
        for member in source_id[len(prefix) + 1 :].split("."):
            if not isinstance(value, dict) or member not in value:
                return None
            value = value[member]
        return replace(parent, text=_json(value))
    return None


def _cash_expression(text: str) -> tuple[str, Decimal] | None:
    matched = _CASH_QUOTE.fullmatch(text.strip())
    if matched is None:
        return None
    currency = matched.group(1) or matched.group(4)
    amount = matched.group(2) or matched.group(3)
    normalized_currency = (
        "AED" if re.fullmatch(r"(?:UAE\s+)?dirhams?|dhs?", currency, re.I) else currency.upper()
    )
    token = re.sub(r"[\s,]", "", amount).lower()
    return normalized_currency, Decimal(token.rstrip("k")) * (1000 if token.endswith("k") else 1)


def _quote_matches(quote: str, source: SourceSupport) -> bool:
    if source.identity_kind is not None:
        return quote.strip() == source.text
    if " ".join(quote.split()) in " ".join(source.text.split()):
        return True
    if source.attribute != "cash_price" or source.state != "known" or source.qualifier != "exact":
        return False
    quoted = _cash_expression(quote)
    return quoted is not None and quoted == _cash_expression(source.text)


def _structural_quote_support(quote: str, source: SourceSupport) -> SourceSupport | None:
    """Match a nonempty JSON projection only inside this cited source's own tree."""

    def unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("DUPLICATE_CITATION_MEMBER")
            result[name] = value
        return result

    def matches(projection: Any, actual: Any) -> bool:
        if type(projection) is not type(actual):
            return False
        if isinstance(projection, dict):
            return bool(projection) and all(
                name in actual and matches(value, actual[name])
                for name, value in projection.items()
            )
        if isinstance(projection, list):
            return len(projection) == len(actual) and all(
                matches(value, item) for value, item in zip(projection, actual, strict=True)
            )
        return projection == actual

    def contained(projection: dict[str, Any], actual: Any) -> bool:
        if isinstance(actual, dict):
            return matches(projection, actual) or any(
                contained(projection, value) for value in actual.values()
            )
        if isinstance(actual, list):
            return any(contained(projection, value) for value in actual)
        return False

    try:
        projection = json.loads(quote, object_pairs_hook=unique_members)
        actual = json.loads(source.text)
    except (ValueError, TypeError):
        return None
    if not isinstance(projection, dict) or not projection or not contained(projection, actual):
        return None
    # Retain provenance but do not make sibling/parent numbers available to prose.
    return replace(source, text=_json(projection))


def _buyer_budget_mentions(text: str, corpus: GroundedCorpus) -> str:
    """Bind only explicit buyer-budget spans, never general inventory numbers."""
    budget = corpus.accepted_criteria.filters.budget if corpus.accepted_criteria else None
    if budget is None or budget.maximum is None:
        return text
    patterns = (
        rf"\byour\s+(?:(?:cash|car|purchase|total)\s+)?budget"
        rf"(?:\s+(?:of|is|at|up to))?\s+(?P<money>{_MONEY_EXPRESSION})(?!\w)",
        rf"\byour\s+(?P<money>{_MONEY_EXPRESSION})\s+(?:cash\s+)?budget\b",
    )
    expected = budget.currency, Decimal(budget.maximum) / 100
    for pattern in patterns:
        text = re.sub(
            pattern,
            lambda match, current=text: (
                ""
                if _cash_expression(match.group("money")) == expected
                and not _PERIODIC_BASIS.match(current[match.end() :])
                else match.group()
            ),
            text,
            flags=re.IGNORECASE,
        )
    return text


def validate_grounded_draft(
    draft: GroundedConversationDraft, corpus: GroundedCorpus
) -> GroundedAnswer | None:
    """Reject invented citations/numbers, invalid quote bindings and action receipts."""
    lines: list[str] = []
    evidence: dict[tuple[str, str, str], tuple[InventoryRef, list[str]]] = {}
    claims: list[FactualClaimReference] = []
    for paragraph in draft.paragraphs:
        text = safe_assistant_text(paragraph.text.strip())
        text = re.sub(r"\s*\[(?:car\d+\.[\w_]+|stats\.[\w_]+|group\.[\w_]+)\]", "", text)
        if _LINK.search(text) or _RECEIPT.search(text):
            return None
        supports: list[SourceSupport] = []
        cited_rows: set[str] = set()
        for citation in paragraph.citations:
            source = _resolve_source(citation.source_id, corpus)
            if source is None and re.fullmatch(r"car\d+", citation.source_id):
                # Resolve an abbreviated row citation only when its exact quote
                # uniquely identifies a field in that same row. Never infer facts.
                matching = [
                    candidate
                    for source_id, candidate in corpus.sources.items()
                    if source_id.startswith(citation.source_id + ".")
                    and " ".join(citation.quote.split()) in " ".join(candidate.text.split())
                ]
                if len(matching) == 1:
                    source = matching[0]
            if source is not None:
                if citation.quote.lstrip().startswith("{"):
                    source = _structural_quote_support(citation.quote, source)
                elif not _quote_matches(citation.quote, source):
                    source = None
            if source is None:
                return None
            supports.append(source)
            row_id = citation.source_id.split(".", 1)[0]
            if re.fullmatch(r"car\d+", row_id):
                cited_rows.add(row_id)
        supported_numbers = set().union(
            *(_numbers(source.text) for source in supports
              if not source.buyer_owned and source.identity_kind is None)
        )
        # Numbered Markdown list markers describe presentation rather than source facts.
        factual_text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
        # Identifiers can support an explicit reference, never a price, year or
        # mileage value with coincidentally equal digits.
        for source in supports:
            if source.identity_kind is None:
                continue
            prefix = r"listing(?:\s+(?:id|number))?\s*#?\s*" if (
                source.identity_kind == "listing"
            ) else ""
            factual_text = re.sub(
                rf"(?<!\w){prefix}{re.escape(source.text)}(?!\w|[.,]\d)",
                "", factual_text, flags=re.IGNORECASE,
            )
        factual_text, identity_supports = _identity_mentions(factual_text, cited_rows, corpus)
        factual_text = _buyer_budget_mentions(factual_text, corpus)
        if not _numbers(factual_text).issubset(supported_numbers):
            return None
        supports.extend(source for source in identity_supports if source not in supports)
        if any(
            source.state in {"conflicting", "unknown"} for source in supports
        ) and not _STATE_WARNING.search(text):
            return None
        for source in supports:
            for ref in source.refs:
                if source.attribute is None:
                    continue
                _, attributes = evidence.setdefault(key(ref), (ref, []))
                if source.attribute not in attributes:
                    attributes.append(source.attribute)
                claims.append(
                    FactualClaimReference(
                        key(ref),
                        source.attribute,
                        source.evidence_ids,
                        "conflicting"
                        if source.state == "conflicting"
                        else "unknown"
                        if source.state == "unknown"
                        else "known",
                        text,
                    )
                )
        lines.append(text)
    return GroundedAnswer(
        text="\n\n".join(lines),
        evidence=tuple(
            AnswerEvidence(ref=ref, attributes=attributes)
            for ref, attributes in list(evidence.values())[:10]
        ),
        claims=tuple(claims),
    )


def _conversation(turns: tuple[TranscriptTurn, ...]) -> tuple[ConversationMessage, ...]:
    values: list[ConversationMessage] = []
    for turn in turns[-6:]:
        values.append(ConversationMessage(role="user", text=turn.user_text[:700]))
        answer = turn.assistant_result
        if answer is not None:
            text = answer.text[:2000]
            if answer.search is not None:
                # Keep displayed order separate from prose, which may summarize only
                # the first few cars. A later ordinal must still resolve after chitchat.
                rows = []
                for index, car in enumerate(answer.search.items, 1):
                    label = " ".join(
                        str(fact.value)
                        for fact in (car.make, car.model, car.year)
                        if isinstance(fact, KnownFact)
                    )
                    rows.append(f"{index}. [{car.ref.source_id}] {label}")
                text = (
                    f"Displayed {len(rows)} of {answer.search.supported_total} matches "
                    "in this exact order (brackets are source IDs):\n" + "\n".join(rows)
                )
                if len(text) > 2000:
                    text = text[:1930] + "\n[Remaining displayed order omitted; do not guess it.]"
            values.append(ConversationMessage(role="assistant", text=text or "No answer."))
    while len(values) > 2 and sum(len(value.text) for value in values) > 6000:
        del values[:2]
    return tuple(values)


def _packet_fits(packet: EvidencePacket, private_values: tuple[str, ...]) -> bool:
    contents = packet.minimized_json(private_values)
    instruction = output_system_instruction(
        GroundedConversationDraft.model_json_schema(), repair=True
    )
    return (
        len(json.dumps(contents, ensure_ascii=True).encode())
        + len(json.dumps(instruction, ensure_ascii=True).encode())
        + 1024
        <= MAX_INPUT_TOKENS
    )


async def compose_grounded_answer(
    adapter: GeminiAdapter,
    request: MessageRequest,
    session: SessionState,
    recent_turns: tuple[TranscriptTurn, ...],
    rows: tuple[Row, ...],
    *,
    scope: str,
    complete: bool,
    total: int | None,
    context_note: str = "",
    request_state: MutableMapping[str, Any],
    budget: TurnBudget,
    private_values: tuple[str, ...] = (),
) -> GroundedAnswer | None:
    """One bounded synthesis call after the coordinator's authorized retrieval."""
    if budget.remaining() <= 0 or budget.provider_attempts >= budget.timeouts.provider_attempts:
        return None
    history = _conversation(recent_turns)
    for description_limit in (600, 220, 80, 0):
        corpus = build_grounded_corpus(
            rows,
            scope=scope,
            complete=complete,
            total=total,
            question=request.text,
            context_note=context_note,
            private_values=private_values,
            description_limit=description_limit,
            accepted_criteria=session.criteria,
        )
        if len(corpus.context) > MAX_SOURCE_CONTEXT_CHARS:
            continue
        packet = EvidencePacket(
            message=request.text,
            session_revision=session.revision,
            selected_ref=session.selected_ref,
            conversation=history,
            accepted_criteria=session.criteria.model_dump_json(),
            source_context=corpus.context,
        )
        if _packet_fits(packet, private_values):
            break
    else:
        return None
    result = await generate_for_request(
        adapter,
        packet,
        GroundedConversationDraft,
        request_state=request_state,
        budget=budget,
        private_values=private_values,
    )
    if result.state != "available" or result.proposal is None:
        return None
    return validate_grounded_draft(result.proposal, corpus)
