"""Canonical 256-bit cookie material and domain-separated digest/CSRF derivation."""

import base64
import hashlib
import hmac
import re
from collections.abc import Callable
from secrets import token_bytes

TOKEN_BYTES = 32
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
CREDENTIAL_DOMAIN = b"car-shopping-owner-v1\x00"
CSRF_DOMAIN = b"car-shopping-csrf-v1\x00"


def encode_token(value: bytes) -> str:
    if not isinstance(value, bytes) or len(value) != TOKEN_BYTES:
        raise ValueError("INVALID_CREDENTIAL_MATERIAL")
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def decode_token(value: str) -> bytes:
    if not isinstance(value, str) or TOKEN_PATTERN.fullmatch(value) is None:
        raise ValueError("INVALID_CREDENTIAL_MATERIAL")
    decoded = base64.urlsafe_b64decode(value + "=")
    if encode_token(decoded) != value:
        raise ValueError("INVALID_CREDENTIAL_MATERIAL")
    return decoded


def new_material(entropy: Callable[[int], bytes] = token_bytes) -> bytes:
    material = entropy(TOKEN_BYTES)
    encode_token(material)  # Fail closed if an injected source violates the entropy-size contract.
    return material


def credential_digest(material: bytes, generation: str) -> str:
    return hashlib.sha256(
        CREDENTIAL_DOMAIN + generation.encode("ascii") + b"\x00" + material
    ).hexdigest()


def csrf_token(material: bytes, generation: str, context_id: str, binding: str) -> str:
    # Binding is an independent persisted salt, not the credential or plaintext CSRF token.
    salt = decode_token(binding)
    payload = (
        CSRF_DOMAIN
        + generation.encode("ascii")
        + b"\x00"
        + context_id.encode("ascii")
        + b"\x00"
        + salt
    )
    return encode_token(hmac.digest(material, payload, "sha256"))
