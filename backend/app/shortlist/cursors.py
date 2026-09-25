"""Owner/revision/order and expiry-bound shortlist cursors; never renew on read."""

import base64
import binascii
import hmac
import json
from typing import Literal

from app.api.schemas.common import Id, InventoryRef, Revision, UtcInstant
from app.core.errors import ApiFailure
from app.sessions.state import StoredPayload, canonical

PURPOSE = b"csa-shortlist-cursor-1\0"


class ShortlistCursor(StoredPayload):
    version: Literal["shortlist-cursor-1"] = "shortlist-cursor-1"
    owner_id: Id
    context_id: Id
    generation: Id
    revision: Revision
    observed_at: UtcInstant
    earliest_expiry: UtcInstant
    after_added_at: UtcInstant
    after_ref: InventoryRef


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("NONCANONICAL_CURSOR")
    return decoded


def encode_cursor(cursor: ShortlistCursor, binding: str) -> str:
    body = canonical(cursor.model_dump(mode="json"))
    return (
        _encode(body)
        + "."
        + _encode(hmac.digest(binding.encode("ascii"), PURPOSE + body, "sha256"))
    )


def decode_cursor(value: str, binding: str) -> ShortlistCursor:
    try:
        if not isinstance(value, str) or not 1 <= len(value) <= 2048:
            raise ValueError("INVALID_CURSOR")
        body_text, signature_text = value.split(".")
        body, signature = _decode(body_text), _decode(signature_text)
        if not hmac.compare_digest(
            signature, hmac.digest(binding.encode("ascii"), PURPOSE + body, "sha256")
        ):
            raise ValueError("INVALID_CURSOR")
        parsed = ShortlistCursor.model_validate(json.loads(body))
        if canonical(parsed.model_dump(mode="json")) != body:
            raise ValueError("NONCANONICAL_CURSOR")
        if not parsed.after_added_at <= parsed.observed_at < parsed.earliest_expiry:
            raise ValueError("INVALID_CURSOR_BOUNDARY")
        return parsed
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise ApiFailure("VALIDATION_ERROR") from None
