"""Trusted HTTP-call integration for the bounded provider diagnostics slot."""

from collections.abc import MutableMapping
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.api.schemas.common import Id
from app.core.diagnostics import (
    ProviderMetric,
    ProviderMetricSlot,
    ProviderUsage,
    attach_provider_metric,
)

from .budget import TurnBudget
from .packet import EvidencePacket
from .provider import GeminiAdapter, ProviderDiagnostic, ProviderResult

_REQUEST_ID = TypeAdapter(Id)


def record_provider_diagnostic(
    request_state: MutableMapping[str, Any], diagnostic: ProviderDiagnostic
) -> bool:
    """Attach one completed invocation; unknown usage stays unknown.

    Only trusted application code passes the original HttpBoundary request state here.
    Explicit field construction keeps proposals, packets and future local fields out of
    logging. The core slot owns request matching, replacement and atomic final close.
    Invalid metadata or absent/closed/mismatched slots simply omit best-effort telemetry.
    """
    try:
        metric = ProviderMetric(
            request_id=diagnostic.request_id,
            model=diagnostic.model,
            sdk_version=diagnostic.sdk_version,
            adapter_version=diagnostic.adapter_version,
            configuration_version=diagnostic.configuration_version,
            state=diagnostic.state,
            code=diagnostic.code,
            attempts=diagnostic.attempts,
            failure_phase=diagnostic.failure_phase,
            http_status=diagnostic.http_status,
            elapsed_ms=diagnostic.elapsed_ms,
            usage=ProviderUsage(
                input_tokens=diagnostic.usage.input_tokens,
                output_tokens=diagnostic.usage.output_tokens,
                total_tokens=diagnostic.usage.total_tokens,
            ),
        )
        return attach_provider_metric(request_state, metric)
    except (ValidationError, AttributeError):
        # Do not log validation errors: their input values could contain private data.
        return False


async def generate_for_request[T: BaseModel](
    adapter: GeminiAdapter,
    packet: EvidencePacket,
    output_type: type[T],
    *,
    request_state: MutableMapping[str, Any],
    budget: TurnBudget,
    private_values: tuple[str, ...] = (),
) -> ProviderResult[T]:
    """Use HttpBoundary's original state and the coordinator's existing turn ledger.

    This is a provider-call interface, not a conversation/domain coordinator. The caller
    still owns supersession and action authority. No slot or deadline is constructed here.
    Cancellation propagates without attaching; a closed slot ignores late completion.
    The slot holds the last completed invocation, never inferred whole-turn totals.
    """
    try:
        request_id = _REQUEST_ID.validate_python(request_state.get("request_id"), strict=True)
    except ValidationError:
        raise ValueError("TRUSTED_REQUEST_CONTEXT_REQUIRED") from None
    if type(request_state.get("provider_metric_slot")) is not ProviderMetricSlot:
        raise ValueError("TRUSTED_REQUEST_CONTEXT_REQUIRED")
    result = await adapter.generate(
        packet,
        output_type,
        budget=budget,
        request_id=request_id,
        private_values=private_values,
    )
    record_provider_diagnostic(request_state, result.diagnostic)
    return result
