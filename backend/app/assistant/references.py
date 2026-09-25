"""Exact reference roles and original-order ordinals; never a fresh search substitute."""

import re

from pydantic import TypeAdapter

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import ListingDetail, ListingResult
from app.api.schemas.sessions import MessageRequest, SessionState
from app.identity.authorization import AuthorizedOwnerContext

from .bounded_calls import CallGate
from .budget import TurnBudget
from .intent import ReferenceRequest
from .read_ports import InventoryReadPort, SessionPort


class AmbiguousReference(Exception):
    pass


def ref_key(ref: InventoryRef) -> tuple[str, str, str]:
    return ref.namespace, ref.snapshot_id, ref.source_id


def listing_ref(result: ListingResult) -> InventoryRef:
    return result.listing.ref if isinstance(result, ListingDetail) else result.ref


_ORDINALS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
)
_LISTING: TypeAdapter[ListingResult] = TypeAdapter(ListingResult)
_SHOWN_CONTEXT = r"\s+you\s+(?:just\s+)?showed\s+me"
_SHOWN_SUFFIX = re.compile(_SHOWN_CONTEXT + r"\s*$", re.I)
_SHOWN_AFTER_QUOTE = re.compile(
    r"(?:\s+(?:car|cars|listing|listings|one|result|results))?" + _SHOWN_CONTEXT + r"\b",
    re.I,
)


def _cited_position(position: int, quote: str) -> bool:
    positions = {
        index
        for index, word in enumerate(_ORDINALS)
        if re.search(r"\b" + word + r"\b", quote, re.I)
    }
    positions.update(
        int(match.group(1)) - 1 for match in re.finditer(r"\b(\d+)(?:st|nd|rd|th)\b", quote, re.I)
    )
    bare = re.fullmatch(r"(?:number\s+|#)?(\d+)", quote.strip(), re.I)
    if bare is None and re.search(r"\b\d+\b", quote):
        # A standalone numeric citation is supported; a second bare number
        # within an ordinal phrase could be a model or listing qualifier.
        return False
    if bare:
        positions.add(int(bare.group(1)) - 1)
    return positions == {position}


def _has_ordinal(quote: str) -> bool:
    return bool(re.search(r"\b(?:" + "|".join(_ORDINALS) + r"|\d+(?:st|nd|rd|th))\b", quote, re.I))


def _unqualified(quote: str) -> bool:
    # Only this closed vocabulary permits an ordinal without a make qualifier.
    words = re.findall(r"\w+", quote.casefold())
    allowed = set(_ORDINALS) | {
        "the",
        "car",
        "cars",
        "listing",
        "listings",
        "one",
        "result",
        "results",
        "number",
    }
    allowed |= {str(n) for n in range(1, 51)} | {
        f"{n}{suffix}" for n in range(1, 51) for suffix in ("st", "nd", "rd", "th")
    }
    return all(word in allowed for word in words)


def _covered_references(message: str, references: list[ReferenceRequest]) -> bool:
    remaining = message
    for reference in sorted(references, key=lambda item: len(item.quote), reverse=True):
        start = remaining.find(reference.quote)
        if start < 0:
            continue
        end = start + len(reference.quote)
        if reference.source == "ordinal" and _SHOWN_SUFFIX.search(reference.quote) is None:
            # A short model quote may omit this exact adjacent contextual suffix.
            # Never discard other qualifiers or allow its words independently.
            context = _SHOWN_AFTER_QUOTE.match(remaining, end)
            if context is not None:
                end = context.end()
        remaining = remaining[:start] + " " + remaining[end:]
    # A finite surrounding-command vocabulary cannot hide an omitted make, numeral,
    # colour or non-English qualifier outside a model's short quote.
    allowed = {
        "show",
        "me",
        "the",
        "a",
        "an",
        "and",
        "or",
        "with",
        "vs",
        "versus",
        "compare",
        "tell",
        "about",
        "please",
        "details",
        "detail",
        "of",
        "for",
        "car",
        "cars",
        "listing",
        "listings",
        "is",
        "are",
        "there",
        "on",
        "does",
        "do",
        "one",
        "how",
        "much",
        "what",
        "which",
        "price",
        "mileage",
        "year",
        "warranty",
        "cheaper",
        "than",
        "has",
        "have",
        "arrange",
        "book",
        "viewing",
        "enquiry",
        "enquire",
        "lead",
        "save",
        "shortlist",
        "then",
    }
    return all(word in allowed for word in re.findall(r"\w+", remaining.casefold()))


class ReferenceResolver:
    def __init__(
        self,
        sessions: SessionPort,
        inventory: InventoryReadPort,
        gate: CallGate,
        context: AuthorizedOwnerContext,
        session: SessionState,
        request: MessageRequest,
        budget: TurnBudget,
        references: list[ReferenceRequest],
    ) -> None:
        self.sessions, self.inventory, self.gate = sessions, inventory, gate
        self.context, self.session, self.request, self.budget = context, session, request, budget
        self._covered = _covered_references(request.text, references)
        self._originals: dict[str, tuple[InventoryRef, ...]] = {}
        self._facts: dict[str, tuple[ListingResult, ...]] = {}

    async def original(self, presentation_id: str) -> tuple[InventoryRef, ...]:
        if presentation_id not in self._originals:
            refs = await self.gate.run(
                lambda: self.sessions.original_refs(
                    self.context, self.session.session_id, presentation_id
                ),
                self.budget,
                tool=True,
            )
            refs = tuple(InventoryRef.model_validate(ref.model_dump(mode="json")) for ref in refs)
            if (
                len(refs) > 50
                or len({ref_key(ref) for ref in refs}) != len(refs)
                or len({ref.snapshot_id for ref in refs}) > 1
            ):
                raise AmbiguousReference
            self._originals[presentation_id] = refs
        return self._originals[presentation_id]

    async def resolve(self, reference: ReferenceRequest) -> InventoryRef:
        if not self._covered or reference.quote not in self.request.text:
            raise AmbiguousReference
        if reference.source != "ordinal":
            if reference.position is not None or reference.make is not None:
                raise AmbiguousReference
            if _has_ordinal(reference.quote):
                raise AmbiguousReference
            role = (
                r"(?:(?:the )?selected(?: car|one|listing)?|"
                r"(?:this|that) (?:car|one|listing)|it|its)"
            )
            if reference.source == "request":
                role = rf"(?:{role}|details?)"
            if not re.fullmatch(role, reference.quote.strip(), re.I):
                raise AmbiguousReference
            ref = (
                self.request.selected_ref
                if reference.source == "request"
                else self.session.selected_ref
            )
            if ref is None:
                raise AmbiguousReference
            if reference.source == "selected" and self.session.active_presentation_id is not None:
                original = await self.original(self.session.active_presentation_id)
                if ref_key(ref) not in {ref_key(item) for item in original}:
                    raise AmbiguousReference
            return ref
        presentation_id = (
            self.request.presentation_id
            if reference.page == "request"
            else self.session.active_presentation_id
        )
        # A full quote may include the same suffix. Only validation uses the
        # shortened quote; the original request and presentation binding stay intact.
        quote = _SHOWN_SUFFIX.sub("", reference.quote)
        if (
            presentation_id is None
            or reference.position is None
            or not _cited_position(reference.position, quote)
        ):
            raise AmbiguousReference
        position = reference.position
        if reference.make is None:
            if not _unqualified(quote):
                raise AmbiguousReference
            return await self.gate.run(
                lambda: self.sessions.ordinal(
                    self.context, self.session.session_id, presentation_id, position
                ),
                self.budget,
                tool=True,
            )
        if not re.search(r"(?<!\w)" + re.escape(reference.make) + r"(?!\w)", quote, re.I):
            raise AmbiguousReference
        if not _unqualified(
            re.sub(
                r"(?<!\w)" + re.escape(reference.make) + r"(?!\w)", "", quote, flags=re.I
            )
        ):
            raise AmbiguousReference
        if re.search(r"\d", re.sub(r"\b\d+(?:st|nd|rd|th)\b", "", quote, flags=re.I)):
            raise AmbiguousReference
        refs = await self.original(presentation_id)
        if not refs:
            raise AmbiguousReference
        if presentation_id not in self._facts:
            batch = await self.gate.run(
                lambda: self.inventory.original_batch(
                    refs, deadline_at=min(self.budget.deadline_at, self.budget.clock() + 2)
                ),
                self.budget,
                tool=True,
            )
            batch = tuple(_LISTING.validate_python(item.model_dump(mode="json")) for item in batch)
            if [ref_key(listing_ref(item)) for item in batch] != [ref_key(item) for item in refs]:
                raise AmbiguousReference
            self._facts[presentation_id] = batch
        matched = 0
        for result in self._facts[presentation_id]:
            if (
                not isinstance(result, ListingDetail)
                or result.listing.make.status != "known"
                or result.listing.make.qualifier != "exact"
            ):
                # Unknown earlier make could change which item the buyer means by first.
                raise AmbiguousReference
            if result.listing.make.value.casefold().strip() == reference.make.casefold().strip():
                if matched == reference.position:
                    return result.listing.ref
                matched += 1
        raise AmbiguousReference
