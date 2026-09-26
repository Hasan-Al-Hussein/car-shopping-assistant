"""Narrow buyer-cited read correction after successful provider interpretation."""

import re

from app.api.schemas.sessions import MessageRequest, SessionState

from .intent import TextField, TextPatch, TurnIntent

_COMMAND = re.compile(
    r"[ ]*(?:show|find|list)[ ]+(?P<field>make|model|trim)[ ]+"
    r'(?:"(?P<double>[^"\r\n]{1,200})"|'
    r"'(?P<single>[^'\r\n]{1,200})'|(?P<number>[0-9]+(?:\.[0-9]+)?))[ ]*",
    re.IGNORECASE | re.ASCII,
)
_FIELDS: dict[str, TextField] = {"make": "makes", "model": "models", "trim": "trims"}


def explicit_field_read(
    intent: TurnIntent,
    request: MessageRequest,
    session: SessionState,
    *,
    collection_active: bool,
) -> TurnIntent:
    """Recover literal field references; decline every workflow ambiguity."""
    if (
        request.clarification_reply is not None
        or request.explicit_confirmation is not None
        or session.pending_intent.kind != "none"
        or session.current_draft_id is not None
        or collection_active
        or intent.scope != "session"
        or intent.operation not in {"search", "detail", "compare"}
        or intent.collection is not None
        or intent.deferred
        or intent.problem not in {None, "reference"}
        or len(request.text) > 400
        or any(
            ord(character) < 32 or ord(character) == 127 or character in "\x85\u2028\u2029"
            for character in request.text
        )
    ):
        return intent
    match = _COMMAND.fullmatch(request.text)
    if match is None:
        return intent
    value = match.group("double") or match.group("single") or match.group("number")
    if not value.strip() or len(value) > 200:
        return intent
    return TurnIntent(
        operation="search",
        patches=[TextPatch(
            kind="text", field=_FIELDS[match.group("field").casefold()], operation="replace",
            values=[value], quote=request.text,
        )],
    )
