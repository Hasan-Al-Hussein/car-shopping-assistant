"""Public readiness exposes capability states, never secrets or operator paths."""

from typing import Annotated, Literal

from pydantic import Field

from app.api.schemas.common import DTO, Digest, ShortText


class Capability(DTO):
    state: Literal["ready", "unavailable", "unconfigured", "degraded"]
    reason: ShortText | None


class HealthResult(DTO):
    service: Literal["car-shopping-assistant"] = "car-shopping-assistant"
    inventory: Capability
    store: Capability
    viewing: Capability
    export: Capability
    assistant: Capability
    active_snapshot_id: Digest | None


class PublicLimits(DTO):
    message_codepoints: Literal[4000] = 4000
    search_codepoints: Literal[1000] = 1000
    page_size_default: Literal[20] = 20
    page_size_max: Literal[50] = 50
    comparison_max: Literal[3] = 3
    body_bytes_max: Literal[65536] = 65536
    filter_clauses_max: Literal[24] = 24


class PublicConfig(DTO):
    policy_version: Literal["DEMO-POLICY-1"] = "DEMO-POLICY-1"
    mode: Literal["local_simulated"] = "local_simulated"
    identity_mode: Literal["browser_local_explicit_save"] = "browser_local_explicit_save"
    notice_version: Literal["DEMO-POLICY-1"] = "DEMO-POLICY-1"
    language: Literal["en"] = "en"
    optional_features: Annotated[list[str], Field(max_length=0)] = []
    limits: PublicLimits
    timezone: Literal["Asia/Dubai"] = "Asia/Dubai"
    viewing_venue: Literal["Simulated local viewing — no real venue or reservation."]
