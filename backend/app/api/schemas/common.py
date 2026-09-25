"""Shared, bounded wire primitives. These are not persistence models."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StringConstraints

Id = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
]
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
OpaqueKey = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_-]{43}$")]
Revision = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]
ShortText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
SafeText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2000)]


def require_utc(value: str) -> str:
    if not value.endswith("Z"):
        raise ValueError("Use an explicit UTC timestamp ending in Z.")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


UtcInstant = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"),
    AfterValidator(require_utc),
]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_default=True)


class InventoryRef(DTO):
    namespace: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-z0-9_-]{1,64}$")]
    snapshot_id: Digest
    source_id: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9._-]{1,128}$")]


class ResponseMeta(DTO):
    request_id: Id
    contract_version: Literal["1.0.0"] = "1.0.0"
    policy_version: Literal["DEMO-POLICY-1"] = "DEMO-POLICY-1"
    inventory_snapshot_id: Digest | None = None
    store_generation: Id | None = None
    entity_revision: Revision | None = None
    identity_context_id: Id | None = None


class Envelope[T](DTO):
    data: T
    meta: ResponseMeta


ErrorCode = Literal[
    "VALIDATION_ERROR",
    "INPUT_TOO_LARGE",
    "UNSUPPORTED_CONTENT_TYPE",
    "IDENTITY_REQUIRED",
    "ORIGIN_DENIED",
    "CSRF_DENIED",
    "HOST_DENIED",
    "NOT_FOUND",
    "REVISION_CONFLICT",
    "REVIEW_STALE",
    "IDEMPOTENCY_CONFLICT",
    "CAPACITY_UNAVAILABLE",
    "ELIGIBILITY_UNAVAILABLE",
    "RULES_UNAVAILABLE",
    "UNSUPPORTED_STATE",
    "SNAPSHOT_STALE",
    "PRESENTATION_INVALID",
    "OPERATION_UNRESOLVED",
    "STORE_GENERATION_CHANGED",
    "REPLAY_EXPIRED",
    "STORE_UNAVAILABLE",
    "STORE_BUSY",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_TIMEOUT",
    "RATE_LIMITED",
    "INTERNAL_ERROR",
    "LEAD_EXISTS",
    "LEAD_REVISION_CONFLICT",
]


class FieldIssue(DTO):
    path: Annotated[list[ShortText], Field(max_length=8)]
    code: ShortText


class ApiError(DTO):
    code: ErrorCode
    message: SafeText
    request_id: Id
    retryable: StrictBool
    retry_action: Literal["none", "read", "same_operation_only"]
    fields: Annotated[list[FieldIssue], Field(max_length=24)] = []
    operation_key: OpaqueKey | None = None
    outcome_state: Literal["unresolved", "rejected", "succeeded"] | None = None


class ErrorEnvelope(DTO):
    error: ApiError


class EmptyResult(DTO):
    state: Literal["ended"]
