"""Safe public error translation; corruption is never an empty inventory result."""

from app.core.errors import ApiFailure

STALE_CODES = frozenset(
    {
        "INVENTORY_EXPECTED_SNAPSHOT_CHANGED",
        "INVENTORY_READ_IDENTITY_STALE",
        "INVENTORY_AUDIT_ADMISSION_REQUIRED",
        "INVENTORY_ADMISSION_INVALIDATED",
        "INVENTORY_BATCH_DEPENDENCY_LIMIT",
    }
)


def public_read_failure(error: ValueError) -> ApiFailure:
    return ApiFailure("SNAPSHOT_STALE" if str(error) in STALE_CODES else "STORE_UNAVAILABLE")
