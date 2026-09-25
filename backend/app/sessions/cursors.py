"""Purpose-separated transcript cursors; the key remains inside the private unit."""

import base64
import binascii
import hmac
import json
from typing import Literal

from pydantic import ValidationError

from app.api.schemas.common import Id, Revision
from app.core.errors import ApiFailure
from app.sessions.state import StoredPayload, canonical

PURPOSE = b"csa-transcript-cursor-1\0"


class TranscriptCursor(StoredPayload):
    version: Literal["transcript-cursor-1"] = "transcript-cursor-1"
    owner_id: Id
    context_id: Id
    session_id: Id
    generation: Id
    observed_revision: Revision
    after_revision: Revision


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("NONCANONICAL_CURSOR")
    return decoded


def encode_cursor(cursor: TranscriptCursor, binding: str) -> str:
    body = canonical(cursor.model_dump(mode="json"))
    signature = hmac.digest(binding.encode("ascii"), PURPOSE + body, "sha256")
    return _encode(body) + "." + _encode(signature)


def decode_cursor(value: str, binding: str) -> TranscriptCursor:
    try:
        if not isinstance(value, str) or not 1 <= len(value) <= 2048:
            raise ValueError("INVALID_CURSOR")
        body_text, signature_text = value.split(".")
        body, signature = _decode(body_text), _decode(signature_text)
        expected = hmac.digest(binding.encode("ascii"), PURPOSE + body, "sha256")
        if not hmac.compare_digest(signature, expected):
            raise ValueError("INVALID_CURSOR")
        parsed = TranscriptCursor.model_validate(json.loads(body))
        if canonical(parsed.model_dump(mode="json")) != body:
            raise ValueError("NONCANONICAL_CURSOR")
        if parsed.after_revision > parsed.observed_revision:
            raise ValueError("INVALID_CURSOR_BOUNDARY")
        return parsed
    except (ValueError, TypeError, UnicodeError, binascii.Error, ValidationError):
        raise ApiFailure("VALIDATION_ERROR") from None
