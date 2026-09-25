"""Closed reply fragments; topic hints never authorize facts, reads or side effects.

The intent integration selects topics. This module is not a natural-language classifier
or an exhaustive competitor registry. Only an internally assembled answer carries facts.
"""

from dataclasses import replace

from .answer_assembly import GroundedAnswer
from .grounding import GroundingError

_REPLIES = {
    "greeting": (
        "Hello. I can help you browse the supplied cars and understand their listing evidence."
    ),
    "help": (
        "Tell me a make, model, model year, cash budget or mileage limit, or select a car "
        "to inspect its evidence. You can compare up to three listings."
    ),
    "cash_price": (
        "Cash asking price means the source-stated purchase price and currency. "
        "A monthly finance instalment is not the total cash price or a financing approval."
    ),
    "mileage": (
        "Odometer mileage describes the vehicle's stated distance travelled. "
        "A warranty mileage limit or service interval is a different claim."
    ),
    "evidence": (
        "Known means a supported source value, not an independently verified vehicle fact. "
        "Unknown means no supported value is available; conflicting means source claims disagree."
    ),
    "warranty": (
        "A seller's warranty statement can include time, mileage and other conditions. "
        "It does not independently establish current coverage or validity."
    ),
    "historical": (
        "A historical listing is a saved source record. It does not establish current stock, "
        "price or vehicle condition."
    ),
    "simulated_viewing": (
        "Viewings in this product are simulated. A discussion of a viewing is not a "
        "booking confirmation or a real dealer appointment."
    ),
    "competitor": (
        "I can't recommend or assess competing shopping services. "
        "I can help you compare the cars in the supplied inventory."
    ),
    "unrelated": (
        "I can help with this car-shopping task; "
        "I can't complete the unrelated part of the request."
    ),
    "unverified_vehicle_claim": (
        "The supplied evidence cannot establish that additional vehicle claim. "
        "I can explain the supported listing attributes and what remains unknown."
    ),
}


def compose_scope(
    answer: GroundedAnswer | None = None,
    *,
    topics: tuple[str, ...] = (),
) -> GroundedAnswer:
    """Append fixed scope/help text without erasing a supported part of a mixed request.

    Pass closed topic identifiers, never seller text or model-generated prose. An unknown
    identifier receives the generic scope boundary. No identifier can invoke an action.
    This interface deliberately cannot claim that any deferred action succeeded.
    """
    if len(topics) > 12:
        raise GroundingError("SCOPE_LIMIT")
    selected = tuple(dict.fromkeys(topic if topic in _REPLIES else "unrelated" for topic in topics))
    if answer is None and not selected:
        selected = ("help",)
    parts = [answer.text] if answer is not None else []
    parts.extend(_REPLIES[topic] for topic in selected)
    text = "\n".join(parts)
    if len(text) > 12000:
        raise GroundingError("ANSWER_LIMIT")
    return replace(answer, text=text) if answer is not None else GroundedAnswer(text, (), ())
