"""Google GenAI 2.25.0 transport with one wire request and no model tools."""

import json
from collections.abc import Callable

import httpx
from google import genai
from google.genai import errors, types

from app.core.config import Settings
from app.core.diagnostics import ProviderFailurePhase, ProviderHttpStatus

from .packet import (
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_BYTES,
    MAX_OUTPUT_TOKENS,
    MAX_RESPONSE_BYTES,
    output_system_instruction,
)
from .provider import (
    FailureCode,
    ProviderBoundaryFailure,
    ProviderFault,
    TransportRequest,
    TransportResponse,
    UsageSummary,
)

OFFICIAL_BASE_URL = "https://generativelanguage.googleapis.com/"
MODEL_PATH = "/v1beta/models/gemini-3.5-flash-lite:generateContent"


def _http_failure_phase(
    error: httpx.HTTPError, *, response_started: bool = False,
) -> ProviderFailurePhase:
    if not response_started and isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)):
        return "http_connect"
    if isinstance(error, httpx.TimeoutException):
        return "http_timeout"
    return "http_transport"


def _reject_unknown_wire_part_fields(payload: object) -> None:
    """Check raw keys before the SDK can discard unrecognized Part fields."""
    if not isinstance(payload, dict):
        return
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
            continue
        for part in content["parts"]:
            if isinstance(part, dict) and set(part) - {"text", "thought", "thoughtSignature"}:
                raise ProviderFault("malformed")


class BoundedHttpTransport(httpx.AsyncBaseTransport):
    """Clamp SDK-overridden timeouts, forbid redirects/tools/endpoints, cap response bytes."""

    def __init__(
        self, delegate: httpx.AsyncBaseTransport, *, connect_seconds: float, attempt_seconds: float
    ) -> None:
        self._delegate = delegate
        self._connect_seconds = connect_seconds
        self._attempt_seconds = attempt_seconds
        self.calls = 0
        self.failure_phase: ProviderFailurePhase | None = None
        self.http_status: ProviderHttpStatus = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            self.calls != 0
            or request.method != "POST"
            or request.url.scheme != "https"
            or request.url.host != "generativelanguage.googleapis.com"
            or request.url.port not in {None, 443}
            or request.url.path != MODEL_PATH
            or request.url.query
            or request.url.username
            or request.url.password
        ):
            raise ProviderFault("unavailable", failure_phase="http_guard")
        # Actual serialized SDK body must also fit the conservative byte ceiling.
        # This covers SDK serialization, trusted instructions and request framing.
        if len(request.content) > MAX_INPUT_TOKENS:
            raise ProviderFault("input_too_large", failure_phase="http_guard")
        request.extensions["timeout"] = {
            "connect": self._connect_seconds,
            "read": self._attempt_seconds,
            "write": self._attempt_seconds,
            "pool": self._connect_seconds,
        }
        self.calls += 1
        self.failure_phase = "http_transport"
        try:
            response = await self._delegate.handle_async_request(request)
        except httpx.HTTPError as error:
            self.failure_phase = _http_failure_phase(error)
            raise
        # Only an actual observed response supplies status, never APIError.code or text.
        status = response.status_code
        self.http_status = status if type(status) is int and 100 <= status <= 599 else None
        self.failure_phase = "http_response"
        try:
            if 300 <= response.status_code < 400:
                raise ProviderFault(
                    "unavailable", failure_phase="http_response", http_status=self.http_status
                )
            length = response.headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > MAX_RESPONSE_BYTES):
                raise ProviderFault(
                    "output_too_large", failure_phase="http_response", http_status=self.http_status
                )
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise ProviderFault(
                        "output_too_large", failure_phase="http_response",
                        http_status=self.http_status,
                    )
                chunks.append(chunk)
            # aiter_bytes yields decoded bytes. Do not ask HTTPX to decode gzip again,
            # or retain the compressed content length when rebuilding the bounded body.
            headers = [
                (name, value)
                for name, value in response.headers.multi_items()
                if name.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
            ]
            bounded_response = httpx.Response(
                response.status_code,
                headers=headers,
                content=b"".join(chunks),
                request=request,
            )
            self.failure_phase = "sdk_response"
            if 200 <= response.status_code < 300:
                _reject_unknown_wire_part_fields(bounded_response.json())
            return bounded_response
        except httpx.HTTPError as error:
            self.failure_phase = _http_failure_phase(error, response_started=True)
            raise
        finally:
            try:
                await response.aclose()
            except Exception:
                self.failure_phase = "cleanup"
                raise

    async def aclose(self) -> None:
        await self._delegate.aclose()


def _usage(response: types.GenerateContentResponse) -> UsageSummary:
    usage = response.usage_metadata
    if usage is None:
        return UsageSummary()
    output = usage.candidates_token_count
    if usage.thoughts_token_count is not None and output is not None:
        output += usage.thoughts_token_count
    return UsageSummary(
        input_tokens=usage.prompt_token_count,
        output_tokens=output,
        total_tokens=usage.total_token_count,
    )


def _extract(response: types.GenerateContentResponse) -> TransportResponse:
    if response.prompt_feedback is not None and response.prompt_feedback.block_reason is not None:
        raise ProviderFault("unavailable")
    candidates = response.candidates or []
    if len(candidates) != 1:
        raise ProviderFault("malformed")
    candidate = candidates[0]
    if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
        raise ProviderFault("output_too_large")
    if candidate.finish_reason != types.FinishReason.STOP or candidate.content is None:
        raise ProviderFault("malformed")
    parts = candidate.content.parts or []
    if not parts:
        raise ProviderFault("malformed")
    texts: list[str] = []
    for part in parts:
        # Do not use response.text, which silently discards nontext/tool content.
        # A signature is opaque metadata, not thought text. This stateless
        # interpreter returns only visible text and never replays model parts.
        fields = part.model_dump(exclude_none=True)
        if (set(fields) - {"text", "thought", "thought_signature"}
                or part.thought or part.text is None):
            raise ProviderFault("malformed")
        texts.append(part.text)
    text = "".join(texts)
    if not text or len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ProviderFault("output_too_large" if text else "malformed")
    return TransportResponse(text=text, usage=_usage(response))


class GoogleGenAITransport:
    """Lazy client per attempt; constructor does not read files, decrypt keys or call Google.

    Optional transport factory is an internal offline-test seam, never request configuration.
    No injected client is left for the SDK to clean up: this layer owns its lifecycle.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None,
    ) -> None:
        self._settings = settings
        self._transport_factory = transport_factory

    async def generate(self, request: TransportRequest) -> TransportResponse:
        secret = self._settings.gemini_api_key
        if not self._settings.assistant_enabled:
            raise ProviderFault("disabled", failure_phase="admission")
        if secret is None:
            raise ProviderFault("not_configured", failure_phase="admission")
        if not 0 < request.connect_seconds <= request.attempt_seconds <= 15:
            raise ProviderFault("timeout", failure_phase="attempt")
        if request.connect_seconds > self._settings.timeouts.provider_connect_seconds:
            raise ProviderFault("timeout", failure_phase="attempt")
        phase: ProviderFailurePhase = "transport_setup"
        bounded: BoundedHttpTransport | None = None

        def fault(code: FailureCode, *, api_response: bool = False) -> ProviderFault:
            observed_phase = phase
            status = bounded.http_status if bounded is not None else None
            if phase == "sdk_request" and bounded is not None and bounded.failure_phase:
                observed_phase = bounded.failure_phase
            if api_response and status is not None:
                observed_phase = "http_response"
            return ProviderFault(code, failure_phase=observed_phase, http_status=status)

        try:
            delegate = (
                self._transport_factory()
                if self._transport_factory is not None
                else httpx.AsyncHTTPTransport(retries=0)
            )
            bounded = BoundedHttpTransport(
                delegate,
                connect_seconds=request.connect_seconds,
                attempt_seconds=request.attempt_seconds,
            )
            async with httpx.AsyncClient(
                transport=bounded,
                trust_env=False,
                follow_redirects=False,
                timeout=request.attempt_seconds,
            ) as http_client:
                # Supplying the HTTPX client also prevents the SDK's aiohttp-specific retry.
                client: genai.Client | None = None
                try:
                    phase = "sdk_setup"
                    client = genai.Client(
                        api_key=secret.get_secret_value(),
                        vertexai=False,
                        http_options=types.HttpOptions(
                            base_url=OFFICIAL_BASE_URL,
                            api_version="v1beta",
                            httpx_async_client=http_client,
                            client_args={"trust_env": False, "follow_redirects": False},
                            timeout=max(1, int(request.attempt_seconds * 1000)),
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    )
                    phase = "sdk_request"
                    response = await client.aio.models.generate_content(
                        model=self._settings.provider_model,
                        contents=request.contents,
                        config=types.GenerateContentConfig(
                            system_instruction=(
                                output_system_instruction(request.schema, repair=request.repair)
                            ),
                            max_output_tokens=MAX_OUTPUT_TOKENS,
                            candidate_count=1,
                            http_options=types.HttpOptions(
                                extra_body={
                                    "generationConfig": {
                                        "responseFormat": {
                                            "text": {
                                                "mimeType": "APPLICATION_JSON",
                                            }
                                        }
                                    }
                                }
                            ),
                            tools=[],
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                                disable=True
                            ),
                        ),
                    )
                    phase = "sdk_response"
                    return _extract(response)
                except ProviderFault as error:
                    if error.failure_phase is None:
                        raise fault(error.code) from None
                    raise
                except errors.APIError as error:
                    # Retain the existing code/retry mapping; log only observed wire status.
                    if error.code in {401, 403}:
                        raise fault("auth", api_response=True) from None
                    if error.code == 429:
                        raise fault("quota", api_response=True) from None
                    if error.code == 404:
                        raise fault("model_missing", api_response=True) from None
                    if error.code in {408, 504}:
                        raise fault("timeout", api_response=True) from None
                    raise fault("unavailable", api_response=True) from None
                except httpx.TimeoutException:
                    raise fault("timeout") from None
                except (ValueError, TypeError, json.JSONDecodeError):
                    raise fault("malformed") from None
                except Exception:
                    raise fault("unavailable") from None
                finally:
                    phase = "cleanup"
                    if client is not None:
                        # Preserve ownership/order: SDK sync client, then HTTPX context.
                        client.close()
        except ProviderFault:
            raise
        except Exception:
            # Setup/context/close errors formerly escaped to the adapter's generic
            # nonretry handler. Keep them out of the ProviderFault retry branch.
            raise ProviderBoundaryFailure(
                failure_phase=phase,
                http_status=bounded.http_status if bounded is not None else None,
            ) from None
