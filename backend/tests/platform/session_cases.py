"""Synthetic owned-session fixture; its Inventory gateway is explicitly test-only."""

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.schemas.identity import IdentityBootstrapRequest, RecognizedIdentity
from app.api.schemas.inventory import PresentationProof
from app.api.schemas.sessions import MessageResult, SessionCreateRequest, SessionState
from app.core.config import Settings, load_settings
from app.core.errors import ApiFailure
from app.database.models import ActiveInventory, Base, ListingVersion
from app.database.store import Store, assert_outside_write_transaction, initialize_store
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext
from app.identity.credentials import decode_token, encode_token
from app.identity.service import IdentityService, utc_text
from app.inventory.references import ImmutableInventoryRef
from app.main import create_app
from app.sessions.inventory import InventoryAdmission
from app.sessions.service import SessionService, TurnAdmission
from app.sessions.state import canonical, fingerprint
from tests.platform.persistence_cases import seed_rows
from tests.platform.test_identity import ACK, Clock
from tests.support.harness import configured_runtime_boundary, runtime_environment

TEST_KEY = b"test-only-presentation-secret-key"
SNAPSHOT = "1" * 64


def ref(source_id: str = "12", snapshot_id: str = SNAPSHOT) -> ImmutableInventoryRef:
    return ImmutableInventoryRef(
        namespace="provided-cars-cleaned", snapshot_id=snapshot_id, source_id=source_id
    )


class TestInventory:
    __test__ = False

    def __init__(self, store: Store) -> None:
        self.store = store
        self.after_prepare: Callable[[], None] | None = None
        self.prepares = 0
        self.rechecks = 0

    @staticmethod
    def _identity(db: Session, refs: tuple[ImmutableInventoryRef, ...]) -> tuple[str, ...]:
        values = []
        for item in refs:
            row = db.get(ListingVersion, (item.namespace, item.snapshot_id, item.source_id))
            values.append(
                None
                if row is None
                else dict(
                    ref=item.model_dump(),
                    source_row=row.source_row,
                    original=row.original_json,
                    normalized=row.normalized_json,
                )
            )
        return (fingerprint(values),)

    def verify(self, proof: PresentationProof, *, now: datetime) -> None:
        assert_outside_write_transaction()
        unsigned = proof.model_dump(mode="json", exclude={"signature"})
        signature = encode_token(hmac.digest(TEST_KEY, canonical(unsigned), "sha256"))
        if not hmac.compare_digest(signature, proof.signature) or not (
            datetime.fromisoformat(proof.issued_at)
            <= now
            < datetime.fromisoformat(proof.expires_at)
        ):
            raise ApiFailure("PRESENTATION_INVALID")

    def prepare(
        self, refs: tuple[ImmutableInventoryRef, ...], *, snapshot_id: str
    ) -> InventoryAdmission:
        assert_outside_write_transaction()
        self.prepares += 1

        def read(db: Session) -> InventoryAdmission:
            active = db.get(ActiveInventory, 1)
            assert active is not None
            return InventoryAdmission(
                self.store.generation,
                snapshot_id,
                active.revision,
                active.index_version,
                refs,
                self._identity(db, refs),
            )

        prepared = self.store.read(read)
        if self.after_prepare is not None:
            self.after_prepare()
        return prepared

    def recheck(self, db: Session, prepared: InventoryAdmission) -> None:
        self.rechecks += 1
        assert db.connection().get_execution_options().get("store_write") is True
        if prepared.identity != self._identity(db, prepared.refs):
            raise ApiFailure("SNAPSHOT_STALE")


@dataclass
class Buyer:
    cookie: str
    identity: RecognizedIdentity


@dataclass
class SessionHarness:
    store: Store
    settings: Settings
    clock: Clock
    app: FastAPI
    auth: AuthorizationService
    service: SessionService
    inventory: TestInventory
    buyers: tuple[Buyer, Buyer]

    def context(self, who: int = 0, *, write: bool = True) -> AuthorizedOwnerContext:
        buyer = self.buyers[who]
        material = decode_token(buyer.cookie)
        if write:
            return self.auth.authorize_write(
                material, buyer.identity.context_id, buyer.identity.csrf_token
            )
        return self.auth.authorize_read(material, buyer.identity.context_id)

    def create(self, who: int = 0) -> SessionState:
        return self.service.create(
            self.context(who), SessionCreateRequest(client_action_id=str(uuid4()))
        )

    def proof(self, sources: tuple[str, ...] = ("12", "13")) -> PresentationProof:
        values: dict[str, Any] = dict(
            presentation_id=str(uuid4()),
            snapshot_id=SNAPSHOT,
            ordered_refs=[ref(source).model_dump() for source in sources],
            criteria_hash="a" * 64,
            issued_at=utc_text(self.clock.value),
            expires_at=utc_text(self.clock.value + timedelta(minutes=5)),
        )
        values["signature"] = encode_token(hmac.digest(TEST_KEY, canonical(values), "sha256"))
        return PresentationProof.model_validate(values)


def make_harness() -> SessionHarness:
    boundary = configured_runtime_boundary()
    path = boundary.logical_root / "test-stores" / ("be10-" + str(uuid4())) / "sessions.sqlite3"
    store = initialize_store(path, boundary=boundary)
    settings = load_settings({**runtime_environment(boundary), "CSA_STORE_PATH": str(path)})
    clock = Clock()
    identity = IdentityService(settings, clock=clock.now)
    buyers = []
    for _ in range(2):
        result = identity.bootstrap(IdentityBootstrapRequest.model_validate(ACK), None)
        assert result.cookie is not None
        buyers.append(Buyer(result.cookie, result.identity))

    def seed(db: Session) -> None:
        for table, values in seed_rows(store.generation):
            if table in {"inventory_snapshots", "listing_versions"}:
                db.execute(Base.metadata.tables[table].insert().values(**values))
                if table == "listing_versions":
                    db.execute(
                        Base.metadata.tables[table]
                        .insert()
                        .values(**{**values, "source_id": "13", "source_row": 14})
                    )
        db.add(ActiveInventory(id=1, snapshot_id=SNAPSHOT, index_version="test-1", revision=1))

    store.write(seed)
    inventory = TestInventory(store)
    app = create_app(
        settings, identity=identity, session_inventory=inventory, event_sink=lambda _: None
    )
    return SessionHarness(
        store,
        settings,
        clock,
        app,
        app.state.authorization,
        app.state.sessions,
        inventory,
        (buyers[0], buyers[1]),
    )


def answer(admission: TurnAdmission, text: str = "Synthetic answer") -> MessageResult:
    return MessageResult(
        client_message_id=admission.request.client_message_id,
        session_id=admission.session.session_id,
        turn_revision=admission.session.revision,
        current_revision=admission.session.revision,
        state="answered",
        text=text,
        pending_intent=admission.session.pending_intent,
        persistence="not_saved",
        provider_state="not_used",
    )
