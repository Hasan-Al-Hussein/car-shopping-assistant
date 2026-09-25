"""Short synchronous identity units using only accepted noncreating store access."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from pathlib import Path
from secrets import token_bytes
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.identity import (
    AnonymousIdentity,
    IdentityBootstrapRequest,
    IdentityResult,
    RecognizedIdentity,
)
from app.core.config import Settings
from app.core.errors import ApiFailure
from app.database.models import Owner, OwnerCredential
from app.database.paths import StorePathError
from app.database.store import Store, StoreError, open_store
from app.identity.credentials import (
    TOKEN_PATTERN,
    credential_digest,
    csrf_token,
    encode_token,
    new_material,
)


def utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("IDENTITY_CLOCK_REQUIRES_UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class IdentityObservation:
    identity: IdentityResult = field(repr=False)
    generation: str | None


@dataclass(frozen=True)
class BootstrapOutcome:
    identity: RecognizedIdentity = field(repr=False)
    generation: str
    cookie: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class EndOutcome:
    context_id: str
    generation: str


class IdentityService:
    def __init__(
        self,
        settings: Settings,
        *,
        store_opener: Callable[[Path], Store] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        entropy: Callable[[int], bytes] = token_bytes,
        new_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self.settings = settings
        boundary = settings.runtime_boundary

        def configured_opener(path: Path) -> Store:
            if boundary is None:
                raise StoreError("STORE_UNAVAILABLE")
            return open_store(path, boundary=boundary)

        self._open = configured_opener if store_opener is None else store_opener
        self._clock = clock
        self._entropy = entropy
        self._new_id = new_id

    def open_store(self) -> Store:
        if self.settings.store_path is None:
            raise StoreError("STORE_UNAVAILABLE")
        try:
            return self._open(self.settings.store_path)
        except (OSError, StorePathError):
            raise StoreError("STORE_UNAVAILABLE") from None

    def _lookup(
        self,
        session: Session,
        store: Store,
        material: bytes,
        now: str,
    ) -> tuple[OwnerCredential, Owner]:
        return self.lookup_digest(session, credential_digest(material, store.generation), now)

    def now_text(self) -> str:
        return utc_text(self._clock())

    @staticmethod
    def lookup_digest(session: Session, digest: str, now: str) -> tuple[OwnerCredential, Owner]:
        """Internal verified-cookie reuse; a caller-supplied digest is never authority."""
        row = session.execute(
            select(OwnerCredential, Owner)
            .join(Owner, Owner.id == OwnerCredential.owner_id)
            .where(OwnerCredential.token_digest == digest)
        ).one_or_none()
        if row is None:
            raise ApiFailure("IDENTITY_REQUIRED")
        credential, owner = row
        if (
            credential.revoked_at is not None
            or not credential.issued_at <= now < credential.expires_at
        ):
            raise ApiFailure("IDENTITY_REQUIRED")
        return credential, owner

    def authorize_in_unit(
        self,
        session: Session,
        store: Store,
        material: bytes | None,
        context_id: str,
        csrf: str | None = None,
    ) -> tuple[OwnerCredential, Owner]:
        if material is None:
            raise ApiFailure("IDENTITY_REQUIRED")
        credential, owner = self._lookup(session, store, material, self.now_text())
        if not compare_digest(credential.context_id.encode("utf-8"), context_id.encode("utf-8")):
            raise ApiFailure("IDENTITY_REQUIRED")
        if csrf is not None:
            recognized = self._recognized(credential, owner, material, store.generation)
            if TOKEN_PATTERN.fullmatch(csrf) is None or not compare_digest(
                recognized.csrf_token, csrf
            ):
                raise ApiFailure("CSRF_DENIED")
        return credential, owner

    @staticmethod
    def _recognized(
        credential: OwnerCredential, owner: Owner, material: bytes, generation: str
    ) -> RecognizedIdentity:
        try:
            csrf = csrf_token(material, generation, credential.context_id, credential.csrf_binding)
        except ValueError:
            raise StoreError("STORE_UNAVAILABLE") from None
        return RecognizedIdentity(
            state="recognized",
            context_id=credential.context_id,
            csrf_token=csrf,
            expires_at=credential.expires_at,
            display_name=owner.display_name,
        )

    def current(self, material: bytes | None) -> IdentityObservation:
        if material is None:
            return IdentityObservation(AnonymousIdentity(state="anonymous"), None)
        store = self.open_store()

        def read(session: Session) -> IdentityObservation:
            credential, owner = self._lookup(session, store, material, utc_text(self._clock()))
            return IdentityObservation(
                self._recognized(credential, owner, material, store.generation), store.generation
            )

        return store.read(read)

    def bootstrap(self, body: IdentityBootstrapRequest, material: bytes | None) -> BootstrapOutcome:
        if material is not None:
            observation = self.current(material)
            if (
                not isinstance(observation.identity, RecognizedIdentity)
                or observation.generation is None
            ):
                raise StoreError("STORE_UNAVAILABLE")
            return BootstrapOutcome(observation.identity, observation.generation)
        store = self.open_store()
        token = new_material(self._entropy)
        binding = encode_token(new_material(self._entropy))
        owner_id, credential_id, context_id = (str(self._new_id()) for _ in range(3))
        if len({owner_id, credential_id, context_id}) != 3:
            raise StoreError("IDENTITY_GENERATOR_INVALID")

        def create(session: Session) -> BootstrapOutcome:
            issued = self._clock()
            issued_at = utc_text(issued)
            expires_at = utc_text(issued + timedelta(days=self.settings.policy.owner_cookie_days))
            owner = Owner(
                id=owner_id,
                created_at=issued_at,
                display_name=body.display_name,
                shortlist_revision=0,
                preference_revision=0,
            )
            credential = OwnerCredential(
                id=credential_id,
                owner_id=owner_id,
                token_digest=credential_digest(token, store.generation),
                context_id=context_id,
                csrf_binding=binding,
                issued_at=issued_at,
                expires_at=expires_at,
                revoked_at=None,
            )
            session.add(owner)
            session.flush()  # Parent exists before its credential; no ORM cascade/relationship.
            session.add(credential)
            return BootstrapOutcome(
                self._recognized(credential, owner, token, store.generation),
                store.generation,
                encode_token(token),
            )

        return store.write(create)

    def end(self, material: bytes | None, context_id: str, csrf: str) -> EndOutcome:
        if material is None:
            raise ApiFailure("IDENTITY_REQUIRED")
        store = self.open_store()

        def revoke(session: Session) -> EndOutcome:
            now = utc_text(self._clock())
            credential, _ = self.authorize_in_unit(session, store, material, context_id, csrf)
            credential.revoked_at = now
            return EndOutcome(credential.context_id, store.generation)

        return store.write(revoke)
