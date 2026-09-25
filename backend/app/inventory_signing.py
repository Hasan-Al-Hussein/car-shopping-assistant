"""Ephemeral public Inventory signatures, explicitly composed per store generation."""

import base64
import binascii
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import TypeAdapter

from app.api.schemas.common import Id, InventoryRef
from app.api.schemas.inventory import PresentationProof
from app.core.errors import ApiFailure
from app.inventory.references import ImmutableInventoryRef
from app.inventory.search_contracts import SearchCursorClaims, SearchCursorPosition

CURSOR_PURPOSE = b"csa-public-search-cursor-1\x00"
MAX_TOKEN_LENGTH = 2048
MAX_LIFETIME_SECONDS = 1800


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("PUBLIC_SIGNATURE_ENCODING_INVALID")
    return decoded


def _instant(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("PUBLIC_SIGNATURE_CLOCK_INVALID")
    return now.astimezone(UTC)


def _text(now: datetime) -> str:
    return now.isoformat().replace("+00:00", "Z")


def _check_time(issued: str, expires: str, now: datetime, lifetime: int) -> None:
    start, end = datetime.fromisoformat(issued), datetime.fromisoformat(expires)
    if not start <= now < end or not timedelta(0) < end - start <= timedelta(seconds=lifetime):
        raise ValueError("PUBLIC_SIGNATURE_INTERVAL_INVALID")


def _context(position: SearchCursorPosition) -> bytes:
    return _canonical(position.model_dump(mode="json", exclude={"sort_key", "position"}))


class HmacPublicInventorySigner:
    """One explicit instance shared by Inventory issuance and Session verification.

    Construct a new instance on process/store-generation change. Keys have no
    persistence or serialization API. Already owned presentations and receipt replay
    do not depend on these public, short-lived signatures.
    """

    __slots__ = ("_generation", "_proof_key", "_cursor_key", "_proof_ttl", "_cursor_ttl")

    def __init__(
        self,
        generation: str,
        *,
        proof_lifetime_seconds: int = MAX_LIFETIME_SECONDS,
        cursor_lifetime_seconds: int = MAX_LIFETIME_SECONDS,
    ) -> None:
        self._generation = TypeAdapter(Id).validate_python(generation, strict=True)
        for lifetime in (proof_lifetime_seconds, cursor_lifetime_seconds):
            if type(lifetime) is not int or not 1 <= lifetime <= MAX_LIFETIME_SECONDS:
                raise ValueError("PUBLIC_SIGNATURE_LIFETIME_INVALID")
        self._proof_ttl = proof_lifetime_seconds
        self._cursor_ttl = cursor_lifetime_seconds
        self._proof_key = secrets.token_bytes(32)
        self._cursor_key = secrets.token_bytes(32)

    @property
    def generation(self) -> str:
        return self._generation

    def sign_presentation(
        self,
        *,
        snapshot_id: str,
        ordered_refs: tuple[ImmutableInventoryRef, ...],
        criteria_hash: str,
        now: datetime,
    ) -> PresentationProof:
        try:
            current = _instant(now)
            if type(ordered_refs) is not tuple or len(ordered_refs) > 50:
                raise ValueError("PUBLIC_PRESENTATION_REFERENCES_INVALID")
            refs = [
                InventoryRef.model_validate(ref.model_dump(mode="python"), strict=True)
                for ref in ordered_refs
            ]
            proof = PresentationProof(
                presentation_id=str(uuid4()),
                snapshot_id=snapshot_id,
                ordered_refs=refs,
                criteria_hash=criteria_hash,
                issued_at=_text(current),
                expires_at=_text(current + timedelta(seconds=self._proof_ttl)),
                signature="A" * 43,
            )
            body = _canonical(proof.model_dump(mode="json", exclude={"signature"}))
            proof.signature = _encode(hmac.digest(self._proof_key, body, "sha256"))
            return proof
        except (ValueError, TypeError, AttributeError, OverflowError):
            raise ApiFailure("PRESENTATION_INVALID") from None

    def verify_presentation(self, proof: PresentationProof, *, now: datetime) -> None:
        try:
            current = _instant(now)
            if (
                type(proof) is not PresentationProof
                or type(proof.ordered_refs) is not list
                or len(proof.ordered_refs) > 50
            ):
                raise ValueError("PUBLIC_PRESENTATION_REFERENCES_INVALID")
            # Detached strict validation rejects model_construct/model_copy bypasses,
            # including integer/boolean aliasing and mutated nested reference objects.
            checked = PresentationProof.model_validate(proof.model_dump(mode="python"), strict=True)
            body = _canonical(checked.model_dump(mode="json", exclude={"signature"}))
            signature = _decode(checked.signature)
            if len(signature) != 32 or not hmac.compare_digest(
                signature, hmac.digest(self._proof_key, body, "sha256")
            ):
                raise ValueError("PUBLIC_PRESENTATION_SIGNATURE_INVALID")
            _check_time(checked.issued_at, checked.expires_at, current, self._proof_ttl)
        except (ValueError, TypeError, AttributeError, OverflowError, binascii.Error):
            raise ApiFailure("PRESENTATION_INVALID") from None

    def encode_search_cursor(
        self,
        position: SearchCursorPosition,
        *,
        now: datetime,
        continuation: str | None = None,
    ) -> str:
        try:
            current = _instant(now)
            position = SearchCursorPosition.model_validate(
                position.model_dump(mode="python"), strict=True
            )
            if position.generation != self._generation:
                raise ValueError("PUBLIC_CURSOR_GENERATION_INVALID")
            issued_at = _text(current)
            expires_at = _text(current + timedelta(seconds=self._cursor_ttl))
            if continuation is not None:
                previous = self.decode_search_cursor(continuation, now=current)
                before, after = previous.position.sort_key, position.sort_key
                if (
                    _context(previous.position) != _context(position)
                    or position.position <= previous.position.position
                    or (-after.preference_score, after.source_id)
                    <= (-before.preference_score, before.source_id)
                ):
                    raise ValueError("PUBLIC_CURSOR_CONTINUATION_INVALID")
                issued_at, expires_at = previous.issued_at, previous.expires_at
            claims = SearchCursorClaims(
                position=position, issued_at=issued_at, expires_at=expires_at
            )
            body = _canonical(claims.model_dump(mode="json"))
            signature = hmac.digest(self._cursor_key, CURSOR_PURPOSE + body, "sha256")
            token = _encode(body) + "." + _encode(signature)
            if len(token) > MAX_TOKEN_LENGTH:
                raise ValueError("PUBLIC_CURSOR_SIZE_INVALID")
            return token
        except (ValueError, TypeError, AttributeError, OverflowError):
            raise ApiFailure("VALIDATION_ERROR") from None

    def decode_search_cursor(self, token: str, *, now: datetime) -> SearchCursorClaims:
        try:
            current = _instant(now)
            if type(token) is not str or not 1 <= len(token) <= MAX_TOKEN_LENGTH:
                raise ValueError("PUBLIC_CURSOR_SIZE_INVALID")
            body_text, signature_text = token.split(".")
            if len(signature_text) != 43:
                raise ValueError("PUBLIC_CURSOR_SIGNATURE_INVALID")
            body, signature = _decode(body_text), _decode(signature_text)
            if len(signature) != 32 or not hmac.compare_digest(
                signature, hmac.digest(self._cursor_key, CURSOR_PURPOSE + body, "sha256")
            ):
                raise ValueError("PUBLIC_CURSOR_SIGNATURE_INVALID")
            claims = SearchCursorClaims.model_validate_json(body, strict=True)
            if _canonical(claims.model_dump(mode="json")) != body:
                raise ValueError("PUBLIC_CURSOR_CANONICAL_INVALID")
            if claims.position.generation != self._generation:
                raise ValueError("PUBLIC_CURSOR_GENERATION_INVALID")
            _check_time(claims.issued_at, claims.expires_at, current, self._cursor_ttl)
            return claims
        except (ValueError, TypeError, AttributeError, OverflowError, binascii.Error):
            raise ApiFailure("VALIDATION_ERROR") from None
