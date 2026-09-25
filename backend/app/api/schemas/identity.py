"""Credential-derived identity only: no wire request may select an owner."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StringConstraints, model_validator

from app.api.schemas.common import DTO, Id, OpaqueKey, UtcInstant


class IdentityBootstrapRequest(DTO):
    notice_version: Literal["DEMO-POLICY-1"]
    notice_acknowledged: StrictBool
    display_name: (
        Annotated[str, StringConstraints(strict=True, min_length=1, max_length=100)] | None
    ) = None

    @model_validator(mode="after")
    def explicit_notice(self) -> "IdentityBootstrapRequest":
        if not self.notice_acknowledged:
            raise ValueError("Local continuity notice must be acknowledged explicitly.")
        return self


class AnonymousIdentity(DTO):
    state: Literal["anonymous"]
    notice_version: Literal["DEMO-POLICY-1"] = "DEMO-POLICY-1"


class RecognizedIdentity(DTO):
    state: Literal["recognized"]
    context_id: Id
    csrf_token: OpaqueKey
    expires_at: UtcInstant
    display_name: Annotated[str, StringConstraints(strict=True, max_length=100)] | None
    continuity: Literal["this_browser_only"] = "this_browser_only"


IdentityResult = Annotated[AnonymousIdentity | RecognizedIdentity, Field(discriminator="state")]


class IdentityEndRequest(DTO):
    acknowledge_loss_of_access: StrictBool

    @model_validator(mode="after")
    def explicit_end(self) -> "IdentityEndRequest":
        if not self.acknowledge_loss_of_access:
            raise ValueError("Ending this local identity loses access to its private history.")
        return self
