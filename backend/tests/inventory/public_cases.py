"""Real reviewed-source service fixtures; no alternative production search implementation."""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.database.store import Store
from app.inventory.compact_reader import CompactInventoryReader
from app.inventory.details_service import InventoryDetailsService
from app.inventory.search_service import InventorySearchService
from app.inventory.staging_plan import PreparedStage
from app.inventory_signing import HmacPublicInventorySigner
from tests.inventory.compact_cases import admitted

NOW = datetime(2026, 9, 24, 4, tzinfo=UTC)


@dataclass(frozen=True)
class PublicHarness:
    reader: CompactInventoryReader
    signer: HmacPublicInventorySigner
    search: InventorySearchService
    details: InventoryDetailsService


def public_harness(store: Store, plan: PreparedStage) -> PublicHarness:
    reader, _ = admitted(store, plan)
    signer = HmacPublicInventorySigner(store.generation)
    return PublicHarness(
        reader,
        signer,
        InventorySearchService(reader, signer, clock=lambda: NOW),
        InventoryDetailsService(reader),
    )
