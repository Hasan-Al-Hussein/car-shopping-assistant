"""Public signer contract tests; synthetic keys only, no Store or live composition."""

import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import cast
from uuid import UUID

import pytest

from app.api.schemas.inventory import PresentationProof
from app.core.errors import ApiFailure
from app.inventory.references import ImmutableInventoryRef
from app.inventory.search_contracts import SearchCursorPosition, SearchSortKey
from app.inventory_signing import HmacPublicInventorySigner

NOW = datetime(2026, 9, 24, 2, 30, 0, 123456, tzinfo=UTC)
GENERATION = "00000000-0000-4000-8000-000000000001"
OTHER_GENERATION = "00000000-0000-4000-8000-000000000002"
SNAPSHOT = "a" * 64
PROOF_KEY = b"P" * 32
CURSOR_KEY = b"C" * 32
CURSOR_PURPOSE = b"csa-public-search-cursor-1\x00"


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def authenticated_cursor(
    payload: bytes, *, key: bytes = CURSOR_KEY, purpose: bytes = CURSOR_PURPOSE
) -> str:
    return encoded(payload) + "." + encoded(hmac.digest(key, purpose + payload, "sha256"))


def ref(source_id: str = "020") -> ImmutableInventoryRef:
    return ImmutableInventoryRef(
        namespace="provided-cars-cleaned", snapshot_id=SNAPSHOT, source_id=source_id
    )


def position(*, count: int = 20, score: int = 5, source_id: str = "020") -> SearchCursorPosition:
    return SearchCursorPosition(
        namespace="provided-cars-cleaned",
        snapshot_id=SNAPSHOT,
        index_version="b" * 64,
        ranking_version="literal-terms-soft-count-source-id-1",
        criteria_hash="c" * 64,
        sort_key=SearchSortKey(preference_score=score, source_id=source_id),
        position=count,
        generation=GENERATION,
        active_revision=1,
    )


def proof(signer: HmacPublicInventorySigner) -> PresentationProof:
    return signer.sign_presentation(
        snapshot_id=SNAPSHOT,
        ordered_refs=(ref("020"), ref("010")),
        criteria_hash="c" * 64,
        now=NOW,
    )


@pytest.fixture
def signer(monkeypatch: pytest.MonkeyPatch) -> HmacPublicInventorySigner:
    keys = iter((PROOF_KEY, CURSOR_KEY))
    sizes: list[int] = []

    def key_bytes(size: int) -> bytes:
        sizes.append(size)
        assert size == 32
        value = next(keys)
        assert len(value) == 32
        return value

    monkeypatch.setattr("app.inventory_signing.secrets.token_bytes", key_bytes)
    result = HmacPublicInventorySigner(GENERATION)
    assert sizes == [32, 32]
    return result


def test_proof_mac_matches_frozen_preimage_and_retains_order(
    signer: HmacPublicInventorySigner,
) -> None:
    issued = proof(signer)
    payload = canonical(issued.model_dump(mode="json", exclude={"signature"}))
    assert issued.signature == encoded(hmac.new(PROOF_KEY, payload, hashlib.sha256).digest())
    assert [item.source_id for item in issued.ordered_refs] == ["020", "010"]
    assert UUID(issued.presentation_id).version == 4
    assert issued.presentation_id != proof(signer).presentation_id
    assert len(issued.signature) == 43 and "=" not in issued.signature
    assert datetime.fromisoformat(issued.issued_at) == NOW
    assert datetime.fromisoformat(issued.expires_at) == NOW + timedelta(seconds=1800)
    returned = cast(Callable[..., object], signer.verify_presentation)(issued, now=NOW)
    assert returned is None
    assert PROOF_KEY.decode() not in repr(signer) and CURSOR_KEY.decode() not in repr(signer)


@pytest.mark.parametrize("count", [0, 50])
def test_proof_accepts_empty_and_maximum_exact_order(
    signer: HmacPublicInventorySigner, count: int
) -> None:
    refs = tuple(ref(f"{number:03d}" + "x" * 125) for number in range(count))
    issued = signer.sign_presentation(
        snapshot_id=SNAPSHOT, ordered_refs=refs, criteria_hash="c" * 64, now=NOW
    )
    assert [item.model_dump() for item in issued.ordered_refs] == [
        item.model_dump() for item in refs
    ]
    signer.verify_presentation(issued, now=NOW)


@pytest.mark.parametrize("variant", ["duplicate", "wrong_snapshot", "too_many", "bool_ref"])
def test_signing_rejects_inconsistent_or_bypassed_refs(
    signer: HmacPublicInventorySigner, variant: str
) -> None:
    refs: tuple[ImmutableInventoryRef, ...] = (ref(), ref())
    if variant == "wrong_snapshot":
        refs = (ref().model_copy(update={"snapshot_id": "d" * 64}),)
    elif variant == "too_many":
        refs = tuple(ref(str(number)) for number in range(51))
    elif variant == "bool_ref":
        refs = (ref().model_copy(update={"source_id": True}),)
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        signer.sign_presentation(
            snapshot_id=SNAPSHOT, ordered_refs=refs, criteria_hash="c" * 64, now=NOW
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("presentation_id", OTHER_GENERATION),
        ("snapshot_id", "d" * 64),
        ("ordered_refs", [ref("010"), ref("020")]),
        ("criteria_hash", "d" * 64),
        ("issued_at", "2026-09-24T02:29:00Z"),
        ("expires_at", "2026-09-24T03:01:00Z"),
        ("signature", "A" * 43),
    ],
)
def test_every_proof_field_is_authenticated(
    signer: HmacPublicInventorySigner, field: str, value: object
) -> None:
    altered = proof(signer).model_copy(update={field: value})
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        signer.verify_presentation(altered, now=NOW)


def test_proof_rejects_noncanonical_signature_with_same_decoded_mac(
    signer: HmacPublicInventorySigner,
) -> None:
    issued = proof(signer)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    changed = issued.signature[:-1] + alphabet[alphabet.index(issued.signature[-1]) + 1]
    assert base64.urlsafe_b64decode(changed + "=") == base64.urlsafe_b64decode(
        issued.signature + "="
    )
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        signer.verify_presentation(issued.model_copy(update={"signature": changed}), now=NOW)


@pytest.mark.parametrize("variant", ["zero", "negative", "overlong", "boolean_ref"])
@pytest.mark.parametrize("bypass", ["copy", "construct"])
def test_authenticated_proof_cannot_bypass_shape_or_lifetime(
    signer: HmacPublicInventorySigner, variant: str, bypass: str
) -> None:
    original = proof(signer)
    material = original.model_dump(mode="json", exclude={"signature"})
    if variant == "zero":
        material["expires_at"] = material["issued_at"]
    elif variant == "negative":
        material["expires_at"] = "2026-09-24T02:29:00Z"
    elif variant == "overlong":
        material["expires_at"] = "2026-09-24T03:00:01Z"
    else:
        material["ordered_refs"][0]["source_id"] = True
    material["signature"] = encoded(hmac.digest(PROOF_KEY, canonical(material), "sha256"))
    forged = (
        original.model_copy(update=material)
        if bypass == "copy"
        else PresentationProof.model_construct(**material)
    )
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        signer.verify_presentation(forged, now=NOW)


@pytest.mark.parametrize("delta", [timedelta(microseconds=-1), timedelta(seconds=1800)])
def test_proof_and_cursor_reject_future_issue_or_expiry_boundary(
    signer: HmacPublicInventorySigner, delta: timedelta
) -> None:
    issued, token = proof(signer), signer.encode_search_cursor(position(), now=NOW)
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        signer.verify_presentation(issued, now=NOW + delta)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.decode_search_cursor(token, now=NOW + delta)


def test_last_microsecond_and_equivalent_aware_clock_are_valid(
    signer: HmacPublicInventorySigner,
) -> None:
    local_now = NOW.astimezone(timezone(timedelta(hours=4)))
    issued = signer.sign_presentation(
        snapshot_id=SNAPSHOT, ordered_refs=(), criteria_hash="c" * 64, now=local_now
    )
    token = signer.encode_search_cursor(position(), now=local_now)
    claims = signer.decode_search_cursor(token, now=NOW)
    assert datetime.fromisoformat(issued.issued_at) == NOW
    assert datetime.fromisoformat(claims.issued_at) == NOW
    assert issued.issued_at.endswith("Z") and claims.issued_at.endswith("Z")
    last = NOW + timedelta(seconds=1800, microseconds=-1)
    signer.verify_presentation(issued, now=last)
    assert signer.decode_search_cursor(token, now=last) == claims


def test_all_methods_reject_naive_clock(signer: HmacPublicInventorySigner) -> None:
    naive, issued = NOW.replace(tzinfo=None), proof(signer)
    token = signer.encode_search_cursor(position(), now=NOW)
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        signer.sign_presentation(
            snapshot_id=SNAPSHOT, ordered_refs=(), criteria_hash="c" * 64, now=naive
        )
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        signer.verify_presentation(issued, now=naive)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.encode_search_cursor(position(), now=naive)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.decode_search_cursor(token, now=naive)


def test_cursor_mac_purpose_and_closed_public_payload(signer: HmacPublicInventorySigner) -> None:
    token = signer.encode_search_cursor(position(), now=NOW)
    claims = signer.decode_search_cursor(token, now=NOW)
    payload = canonical(claims.model_dump(mode="json"))
    assert token == authenticated_cursor(payload)
    assert claims.position == position()
    assert len(token) <= 2048 and "=" not in token
    assert set(claims.model_dump()) == {"version", "position", "issued_at", "expires_at"}
    assert set(claims.position.model_dump()) == {
        "namespace",
        "snapshot_id",
        "index_version",
        "ranking_version",
        "criteria_hash",
        "sort_key",
        "position",
        "generation",
        "active_revision",
    }


def test_cursor_supports_maximum_typed_fields_within_wire_cap(
    signer: HmacPublicInventorySigner,
) -> None:
    maximum = position(count=2_147_483_647, score=24, source_id="z" * 128).model_copy(
        update={
            "namespace": "n" * 64,
            "ranking_version": "r" * 64,
            "active_revision": 2_147_483_647,
        }
    )
    token = signer.encode_search_cursor(maximum, now=NOW)
    assert len(token) <= 2048
    assert signer.decode_search_cursor(token, now=NOW).position == maximum


def test_continuation_advances_order_without_renewing_initial_lifetime(
    signer: HmacPublicInventorySigner,
) -> None:
    first = signer.encode_search_cursor(position(), now=NOW)
    original = signer.decode_search_cursor(first, now=NOW)
    second_position = position(count=35, score=5, source_id="021")
    second = signer.encode_search_cursor(
        second_position, now=NOW + timedelta(minutes=10), continuation=first
    )
    third_position = position(count=36, score=4, source_id="001")
    third = signer.encode_search_cursor(
        third_position, now=NOW + timedelta(minutes=20), continuation=second
    )
    for token, expected in ((second, second_position), (third, third_position)):
        claims = signer.decode_search_cursor(token, now=NOW + timedelta(minutes=20))
        assert claims.position == expected
        assert (claims.issued_at, claims.expires_at) == (original.issued_at, original.expires_at)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.encode_search_cursor(
            position(count=37, score=3), now=NOW + timedelta(minutes=30), continuation=third
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("namespace", "another"),
        ("snapshot_id", "d" * 64),
        ("index_version", "d" * 64),
        ("ranking_version", "new-ranking-2"),
        ("criteria_hash", "d" * 64),
        ("generation", OTHER_GENERATION),
        ("active_revision", 2),
    ],
)
def test_continuation_cannot_change_its_context(
    signer: HmacPublicInventorySigner, field: str, value: object
) -> None:
    token = signer.encode_search_cursor(position(), now=NOW)
    changed = position(count=21, score=4).model_copy(update={field: value})
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.encode_search_cursor(changed, now=NOW, continuation=token)


@pytest.mark.parametrize(
    ("count", "score", "source_id"),
    [(20, 4, "030"), (19, 4, "030"), (21, 6, "030"), (21, 5, "020"), (21, 5, "019")],
)
def test_continuation_requires_both_count_and_sort_key_to_advance(
    signer: HmacPublicInventorySigner, count: int, score: int, source_id: str
) -> None:
    token = signer.encode_search_cursor(position(), now=NOW)
    changed = position(count=count, score=score, source_id=source_id)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.encode_search_cursor(changed, now=NOW, continuation=token)


@pytest.mark.parametrize("field", ["position", "active_revision", "sort_key"])
@pytest.mark.parametrize("bypass", ["copy", "construct"])
def test_cursor_revalidates_detached_boolean_bypasses(
    signer: HmacPublicInventorySigner, field: str, bypass: str
) -> None:
    valid = position()
    value: object = True
    if field == "sort_key":
        value = valid.sort_key.model_copy(update={"preference_score": True})
    invalid = (
        valid.model_copy(update={field: value})
        if bypass == "copy"
        else SearchCursorPosition.model_construct(
            **{**valid.model_dump(), "sort_key": valid.sort_key, field: value}
        )
    )
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.encode_search_cursor(invalid, now=NOW)


@pytest.mark.parametrize(
    "variant",
    [
        "whitespace",
        "extra",
        "missing_version",
        "duplicate_key",
        "bool",
        "float",
        "nan",
        "overscore",
        "long_source",
        "wrong_generation",
        "future",
        "expired",
        "long_lifetime",
    ],
)
def test_authenticated_but_invalid_cursor_payloads_are_rejected(
    signer: HmacPublicInventorySigner, variant: str
) -> None:
    good = signer.encode_search_cursor(position(), now=NOW)
    claims = signer.decode_search_cursor(good, now=NOW).model_dump(mode="json")
    location = cast(dict[str, object], claims["position"])
    sort_key = cast(dict[str, object], location["sort_key"])
    if variant == "extra":
        claims["owner_id"] = "SYNTHETIC_OWNER_MUST_NOT_BECOME_PUBLIC"
    elif variant == "missing_version":
        del claims["version"]
    elif variant in {"bool", "float", "nan"}:
        location["position"] = {"bool": True, "float": 20.0, "nan": float("nan")}[variant]
    elif variant == "overscore":
        sort_key["preference_score"] = 25
    elif variant == "long_source":
        sort_key["source_id"] = "x" * 129
    elif variant == "wrong_generation":
        location["generation"] = OTHER_GENERATION
    elif variant == "future":
        claims["issued_at"], claims["expires_at"] = "2026-09-24T02:31:00Z", "2026-09-24T03:00:00Z"
    elif variant == "expired":
        claims["issued_at"], claims["expires_at"] = "2026-09-24T02:00:00Z", "2026-09-24T02:30:00Z"
    elif variant == "long_lifetime":
        claims["expires_at"] = "2026-09-24T03:00:01Z"
    raw = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if variant == "whitespace":
        raw = b" " + raw
    elif variant == "duplicate_key":
        raw = b'{"version":"inventory-search-cursor-1",' + raw[1:]
    forged = authenticated_cursor(raw)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.decode_search_cursor(forged, now=NOW)


@pytest.mark.parametrize(
    "variant", ["empty", "oversize", "body_padding", "mac_padding", "short_mac", "tamper", "dots"]
)
def test_malformed_cursor_encoding_fails_closed(
    signer: HmacPublicInventorySigner, variant: str
) -> None:
    token = signer.encode_search_cursor(position(), now=NOW)
    body, mac = token.split(".")
    invalid = {
        "empty": "",
        "oversize": "x" * 2049,
        "body_padding": body + "=." + mac,
        "mac_padding": token + "=",
        "short_mac": body + "." + mac[:-1],
        "tamper": ("A" if body[0] != "A" else "B") + token[1:],
        "dots": token + ".extra",
    }[variant]
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.decode_search_cursor(invalid, now=NOW)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.encode_search_cursor(position(count=21, score=4), now=NOW, continuation=invalid)


def test_keys_and_purposes_cannot_be_cross_used(signer: HmacPublicInventorySigner) -> None:
    issued = proof(signer)
    proof_payload = canonical(issued.model_dump(mode="json", exclude={"signature"}))
    for key, prefix in ((CURSOR_KEY, b""), (PROOF_KEY, CURSOR_PURPOSE)):
        changed = issued.model_copy(
            update={"signature": encoded(hmac.digest(key, prefix + proof_payload, "sha256"))}
        )
        with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
            signer.verify_presentation(changed, now=NOW)
    token = signer.encode_search_cursor(position(), now=NOW)
    payload = canonical(signer.decode_search_cursor(token, now=NOW).model_dump(mode="json"))
    for key, purpose in ((PROOF_KEY, CURSOR_PURPOSE), (CURSOR_KEY, b"")):
        with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
            signer.decode_search_cursor(
                authenticated_cursor(payload, key=key, purpose=purpose), now=NOW
            )


def test_new_instance_keys_invalidate_unregistered_tokens(
    signer: HmacPublicInventorySigner, monkeypatch: pytest.MonkeyPatch
) -> None:
    issued, token = proof(signer), signer.encode_search_cursor(position(), now=NOW)
    keys = iter((b"R" * 32, b"S" * 32))
    monkeypatch.setattr("app.inventory_signing.secrets.token_bytes", lambda _: next(keys))
    replacement = HmacPublicInventorySigner(GENERATION)
    with pytest.raises(ApiFailure, match="^PRESENTATION_INVALID$"):
        replacement.verify_presentation(issued, now=NOW)
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        replacement.decode_search_cursor(token, now=NOW)
    assert signer.generation == GENERATION
    with pytest.raises((AttributeError, TypeError)):
        signer.generation = OTHER_GENERATION  # type: ignore[misc]  # Exercise readonly API.
    with pytest.raises(ApiFailure, match="^VALIDATION_ERROR$"):
        signer.encode_search_cursor(
            position().model_copy(update={"generation": OTHER_GENERATION}), now=NOW
        )


@pytest.mark.parametrize("field", ["proof_lifetime_seconds", "cursor_lifetime_seconds"])
@pytest.mark.parametrize("invalid", [0, -1, 1801, True, 1.0, "30", None])
def test_constructor_rejects_invalid_lifetime(field: str, invalid: object) -> None:
    arguments = {field: cast(int, invalid)}
    with pytest.raises((ValueError, ApiFailure)):
        HmacPublicInventorySigner(GENERATION, **arguments)


@pytest.mark.parametrize("invalid", [True, None, "", "not-a-generation", "A" * 36])
def test_constructor_requires_strict_generation_id(invalid: object) -> None:
    with pytest.raises((ValueError, ApiFailure)):
        HmacPublicInventorySigner(cast(str, invalid))


@pytest.mark.parametrize("lifetime", [1, 1800])
def test_configured_lifetime_applies_to_both_envelopes(lifetime: int) -> None:
    configured = HmacPublicInventorySigner(
        GENERATION, proof_lifetime_seconds=lifetime, cursor_lifetime_seconds=lifetime
    )
    issued = proof(configured)
    token = configured.encode_search_cursor(position(), now=NOW)
    claims = configured.decode_search_cursor(token, now=NOW)
    for envelope in (issued, claims):
        assert datetime.fromisoformat(envelope.expires_at) - datetime.fromisoformat(
            envelope.issued_at
        ) == timedelta(seconds=lifetime)
