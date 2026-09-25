"""Inert validated settings. No dotenv, credential-file access or runtime creation."""

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.api.schemas.capabilities import PublicConfig, PublicLimits
from app.database.paths import (
    RuntimeBoundary,
    boundary_from_environment,
    parse_runtime_path,
    validate_store_location,
)

CONTRACT_VERSION: Final = "1.0.0"
POLICY_VERSION: Final = "DEMO-POLICY-1"
CONFIGURATION_VERSION: Final = "F04-CONFIG-2"
VIEWING_VENUE: Final = "Simulated local viewing — no real venue or reservation."
DEFAULT_HOSTS = ("127.0.0.1:8000", "127.0.0.1:5173", "127.0.0.1:4173")


class ConfigurationError(ValueError):
    """Safe startup failure; the rejected input is never included in its message."""


class FrozenSettings(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        validate_default=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )


class DemoPolicy(FrozenSettings):
    """Adopted operating choices; changing them requires a new reviewed policy."""

    version: Literal["DEMO-POLICY-1"] = POLICY_VERSION
    booking_mode: Literal["simulated"] = "simulated"
    timezone: Literal["Asia/Dubai"] = "Asia/Dubai"
    open_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
    open_time: Literal["08:00"] = "08:00"
    close_time: Literal["20:00"] = "20:00"
    slot_minutes: Literal[30] = 30
    capacity: Literal[1] = 1
    minimum_lead_minutes: Literal[30] = 30
    horizon_days: Literal[30] = 30
    contact_required: Literal[False] = False
    owner_cookie_days: Literal[30] = 30
    session_retention_days: Literal[7] = 7
    preference_retention_days: Literal[30] = 30
    shortlist_retention_days: Literal[30] = 30
    draft_idle_minutes: Literal[30] = 30
    review_valid_minutes: Literal[5] = 5
    terminal_record_retention_days: Literal[90] = 90
    logs_retention_days: Literal[7] = 7
    backups_retention_days: Literal[7] = 7
    unresolved_operations_auto_delete: Literal[False] = False
    provider_spend_limit: Literal[0] = 0
    public_deployment: Literal[False] = False

    @model_validator(mode="after")
    def adopted_weekdays(self) -> Self:
        if self.open_weekdays != (0, 1, 2, 3, 4, 5):
            raise ValueError("POLICY_VERSION_CHANGE_REQUIRED")
        return self


class Timeouts(FrozenSettings):
    """Bounded initial tuning choices from technical-plan 14.2; not measured SLAs."""

    read_seconds: Annotated[int, Field(ge=1, le=5)] = 5
    operation_seconds: Annotated[int, Field(ge=1, le=30)] = 30
    confirmation_seconds: Annotated[int, Field(ge=1, le=8)] = 8
    provider_connect_seconds: Annotated[int, Field(ge=1, le=5)] = 5
    provider_attempt_seconds: Annotated[int, Field(ge=1, le=15)] = 15
    provider_attempts: Annotated[int, Field(ge=1, le=2)] = 2
    tool_invocations: Annotated[int, Field(ge=1, le=4)] = 4
    provider_observation_seconds: Annotated[int, Field(ge=1, le=60)] = 60

    @model_validator(mode="after")
    def nested_deadlines(self) -> Self:
        if not (
            self.provider_connect_seconds <= self.provider_attempt_seconds <= self.operation_seconds
            and self.confirmation_seconds <= self.operation_seconds
        ):
            raise ValueError("INCONSISTENT_DEADLINES")
        return self


class Settings(FrozenSettings):
    profile: Literal["local_http", "local_https"] = "local_http"
    bind_host: Literal["127.0.0.1"] = "127.0.0.1"
    bind_port: Annotated[int, Field(ge=1, le=65535)] = 8000
    allowed_hosts: Annotated[tuple[str, ...], Field(min_length=1, max_length=8)] = DEFAULT_HOSTS
    allowed_origins: Annotated[tuple[str, ...], Field(min_length=1, max_length=8)] = tuple(
        "http://" + host for host in DEFAULT_HOSTS
    )
    store_path: Path | None = Field(default=None, exclude=True, repr=False)
    runtime_boundary: RuntimeBoundary | None = Field(default=None, exclude=True, repr=False)
    gemini_api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    provider_model: Literal["gemini-3.5-flash-lite"] = "gemini-3.5-flash-lite"
    assistant_enabled: bool = True
    policy: DemoPolicy = DemoPolicy()
    timeouts: Timeouts = Timeouts()

    @property
    def scheme(self) -> Literal["http", "https"]:
        return "https" if self.profile == "local_https" else "http"

    @property
    def cookie_name(self) -> str:
        return "__Host-csa_owner" if self.profile == "local_https" else "csa_owner"

    @property
    def cookie_secure(self) -> bool:
        return self.profile == "local_https"

    @property
    def provider_configured(self) -> bool:
        return self.gemini_api_key is not None

    @model_validator(mode="after")
    def local_boundary(self) -> Self:
        if len(set(self.allowed_hosts)) != len(self.allowed_hosts):
            raise ValueError("DUPLICATE_HOST")
        for host in self.allowed_hosts:
            parts = host.split(":")
            if (
                len(parts) != 2
                or parts[0] != "127.0.0.1"
                or not parts[1].isascii()
                or not parts[1].isdigit()
                or str(int(parts[1])) != parts[1]
                or not 1 <= int(parts[1]) <= 65535
            ):
                raise ValueError("EXACT_LOOPBACK_HOST_REQUIRED")
        if f"{self.bind_host}:{self.bind_port}" not in self.allowed_hosts:
            raise ValueError("BIND_HOST_NOT_ALLOWED")
        if len(set(self.allowed_origins)) != len(self.allowed_origins):
            raise ValueError("DUPLICATE_ORIGIN")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != self.scheme
                or parsed.netloc not in self.allowed_hosts
                or origin != f"{self.scheme}://{parsed.netloc}"
            ):
                raise ValueError("EXACT_MATCHING_LOOPBACK_ORIGIN_REQUIRED")
        if self.store_path is not None:
            if self.runtime_boundary is None:
                raise ValueError("ADOPTED_STORE_LOCATION_REQUIRED")
            validate_store_location(self.store_path, boundary=self.runtime_boundary)
        if self.gemini_api_key is not None:
            secret = self.gemini_api_key.get_secret_value()
            if (
                not 1 <= len(secret) <= 4096
                or secret != secret.strip()
                or any(ord(character) < 33 or ord(character) > 126 for character in secret)
            ):
                raise ValueError("INVALID_SECRET_INPUT")
        return self

    def public_config(self) -> PublicConfig:
        # Construct the exact frozen DTO, never serialize the private settings object.
        return PublicConfig(limits=PublicLimits(), viewing_venue=VIEWING_VENUE)


def load_settings(environment: Mapping[str, str] | None = None) -> Settings:
    """Only the later launcher supplies a key in the backend child's environment."""
    values = os.environ if environment is None else environment
    allowed = {
        "CSA_PROFILE",
        "CSA_PORT",
        "CSA_ALLOWED_HOSTS",
        "CSA_ALLOWED_ORIGINS",
        "CSA_STORE_PATH",
        "CSA_RUNTIME_ROOT",
        "CSA_RUNTIME_PHYSICAL_ROOT",
        "CSA_TIMEOUTS_JSON",
        "CSA_ASSISTANT_ENABLED",
    }
    try:
        if any(key.startswith("CSA_") and key not in allowed for key in values):
            raise ValueError("UNKNOWN_SETTING")
        profile = values.get("CSA_PROFILE", "local_http")
        scheme = "https" if profile == "local_https" else "http"
        port_value = values.get("CSA_PORT", "8000")
        if not port_value.isascii() or not port_value.isdigit() or len(port_value) > 5:
            raise ValueError("INVALID_PORT")
        port = int(port_value)
        if str(port) != port_value:
            raise ValueError("NONCANONICAL_PORT")
        hosts_value = values.get("CSA_ALLOWED_HOSTS")
        origins_value = values.get("CSA_ALLOWED_ORIGINS")
        timeout_value = values.get("CSA_TIMEOUTS_JSON", "{}")
        if any(
            len(value) > 4096 for value in (hosts_value or "", origins_value or "", timeout_value)
        ):
            raise ValueError("CONFIGURATION_TOO_LARGE")
        parsed_hosts = json.loads(hosts_value) if hosts_value is not None else list(DEFAULT_HOSTS)
        parsed_origins = json.loads(origins_value) if origins_value is not None else None
        if not isinstance(parsed_hosts, list) or (
            parsed_origins is not None and not isinstance(parsed_origins, list)
        ):
            raise ValueError("CONFIGURATION_ARRAY_REQUIRED")
        hosts = tuple(parsed_hosts)
        origins = (
            tuple(parsed_origins)
            if parsed_origins is not None
            else tuple(f"{scheme}://{host}" for host in hosts)
        )
        enabled = values.get("CSA_ASSISTANT_ENABLED", "true")
        if enabled not in {"true", "false"}:
            raise ValueError("INVALID_BOOLEAN")
        secret = values.get("GEMINI_API_KEY")
        path = values.get("CSA_STORE_PATH")
        return Settings(
            profile=profile,  # type: ignore[arg-type]
            bind_port=port,
            allowed_hosts=hosts,
            allowed_origins=origins,
            store_path=parse_runtime_path(path) if path is not None else None,
            runtime_boundary=boundary_from_environment(values),
            gemini_api_key=SecretStr(secret) if secret else None,
            assistant_enabled=enabled == "true",
            timeouts=Timeouts.model_validate(json.loads(timeout_value)),
        )
    except (TypeError, ValueError, RecursionError):
        # No exception chaining: invalid inputs may contain secrets or operator paths.
        raise ConfigurationError("CONFIGURATION_INVALID") from None
