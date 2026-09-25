"""Small whole-request policies; opaque source labels never become tool destinations."""

import re

from app.api.schemas.sessions import MessageRequest, SessionState

from .intent import TurnIntent

# This is a closed English command grammar, not a marketplace/name classifier.
# Uncovered language stays with the normal guarded interpretation path.
_EXTERNAL_SEARCH = re.compile(
    r"[ ]*(?:show|find|list|search[ ]+for)[ ]+"
    r"(?P<qualifiers>(?:[a-z0-9]{1,40}[ ]+){0,4})"
    r"(?:cars|vehicles|listings)[ ]+(?:on|via)[ ]+"
    r"(?P<source_cue>(?:the[ ]+)?(?:external[ ]+|other[ ]+|another[ ]+)?"
    r"(?:site|website|marketplace|platform)[ ]+)?"
    r"(?P<destination>[a-z][a-z0-9_-]{0,63})[.!?]?[ ]*",
    re.IGNORECASE | re.ASCII,
)
# Reviewed routing vocabulary, not a verified platform registry. Our app's branding
# (dubizzle) is deliberately excluded. Unknown bare labels keep existing handling.
_BARE_EXTERNAL_SOURCES = frozenset({"dubicars", "yallamotor", "autotrader", "cars24"})
_INTERNAL_OR_UNNAMED_SOURCES = frozenset({
    "dubizzle", "local", "inventory", "here", "this", "that", "our",
    "site", "website", "marketplace", "platform",
})
_NON_SEARCH_QUALIFIERS = frozenset({
    "not", "no", "never", "without", "except", "and", "or", "then", "if", "unless",
    "imagine", "hypothetical", "save", "book", "prepare", "arrange", "contact", "send",
    "enquire", "inquiry", "first", "second", "third", "last", "selected", "only", "instead",
    "remember", "recall", "return", "remove", "clear", "reset", "delete",
})


def request_routing_eligible(
    intent: TurnIntent, request: MessageRequest, session: SessionState, *, collection_active: bool,
) -> bool:
    """Never let a request policy replace workflow, private-input or scope authority."""
    return (
        intent.scope == "session"
        and not intent.deferred
        and intent.collection is None
        and request.clarification_reply is None
        and request.explicit_confirmation is None
        and session.pending_intent.kind == "none"
        and session.current_draft_id is None
        and not collection_active
        and len(request.text) <= 400
        and not any(
            ord(char) < 32 or ord(char) == 127 or char in "\x85\u2028\u2029"
            for char in request.text
        )
    )


def external_source_search(
    intent: TurnIntent, request: MessageRequest, session: SessionState, *, collection_active: bool,
) -> bool:
    """Recognize a bounded source-directed search before proposed local patches apply.

    Explicit source cues permit an opaque label; bare labels require reviewed routing
    vocabulary. We never accept the destination as inventory authority. Compound,
    quoted or unknown bare destinations stay outside this narrow policy.
    """
    if not request_routing_eligible(intent, request, session, collection_active=collection_active):
        return False
    match = _EXTERNAL_SEARCH.fullmatch(request.text)
    if match is None:
        return False
    destination = match.group("destination").casefold()
    return (
        destination not in _INTERNAL_OR_UNNAMED_SOURCES
        and (match.group("source_cue") is not None or destination in _BARE_EXTERNAL_SOURCES)
        and not _NON_SEARCH_QUALIFIERS.intersection(match.group("qualifiers").casefold().split())
    )
