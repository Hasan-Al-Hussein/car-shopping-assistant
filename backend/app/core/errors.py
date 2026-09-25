"""Closed public error messages; never serialize exception/input/provider details."""

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api.schemas.common import ApiError, ErrorCode, ErrorEnvelope
from app.database.store import StoreError


@dataclass(frozen=True)
class ErrorSpec:
    status: int
    message: str
    transient: bool = False


ERRORS: dict[str, ErrorSpec] = {
    "VALIDATION_ERROR": ErrorSpec(422, "Check the request fields and try again."),
    "INPUT_TOO_LARGE": ErrorSpec(413, "The request is too large."),
    "UNSUPPORTED_CONTENT_TYPE": ErrorSpec(415, "Use a supported JSON request."),
    "IDENTITY_REQUIRED": ErrorSpec(401, "A valid local identity is required."),
    "ORIGIN_DENIED": ErrorSpec(403, "This request origin is not allowed."),
    "CSRF_DENIED": ErrorSpec(403, "The request could not be verified."),
    "HOST_DENIED": ErrorSpec(400, "This request host is not allowed."),
    "NOT_FOUND": ErrorSpec(404, "The requested item is not available."),
    "REVISION_CONFLICT": ErrorSpec(409, "Read the current state before making another change."),
    "REVIEW_STALE": ErrorSpec(409, "Review the current details before confirming."),
    "IDEMPOTENCY_CONFLICT": ErrorSpec(
        409, "Recover the original action before making another change."
    ),
    "CAPACITY_UNAVAILABLE": ErrorSpec(409, "The requested simulated viewing is unavailable."),
    "ELIGIBILITY_UNAVAILABLE": ErrorSpec(409, "Simulated viewing eligibility is unavailable."),
    "RULES_UNAVAILABLE": ErrorSpec(409, "Simulated viewing rules are unavailable."),
    "UNSUPPORTED_STATE": ErrorSpec(409, "This action is not available in the current state."),
    "SNAPSHOT_STALE": ErrorSpec(409, "Read the current inventory before continuing."),
    "PRESENTATION_INVALID": ErrorSpec(409, "Refresh the current results before continuing."),
    "OPERATION_UNRESOLVED": ErrorSpec(
        409, "Check the original action; its outcome remains uncertain."
    ),
    "STORE_GENERATION_CHANGED": ErrorSpec(
        409, "Saved state changed; the original action needs reconciliation."
    ),
    "REPLAY_EXPIRED": ErrorSpec(409, "The original action can no longer be retried automatically."),
    "STORE_UNAVAILABLE": ErrorSpec(503, "Local saved state is temporarily unavailable.", True),
    "STORE_BUSY": ErrorSpec(503, "Local saved state is busy.", True),
    "PROVIDER_UNAVAILABLE": ErrorSpec(503, "Assistant support is temporarily unavailable.", True),
    "PROVIDER_TIMEOUT": ErrorSpec(504, "Assistant support did not respond in time.", True),
    "RATE_LIMITED": ErrorSpec(429, "This request is temporarily limited.", True),
    "INTERNAL_ERROR": ErrorSpec(500, "The request could not be completed."),
    "LEAD_EXISTS": ErrorSpec(409, "Read the existing local enquiry before making another change."),
    "LEAD_REVISION_CONFLICT": ErrorSpec(
        409, "Read the current local enquiry before making another change."
    ),
}


class ApiFailure(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code: ErrorCode = code if code in ERRORS else "INTERNAL_ERROR"
        super().__init__(self.code)


def error_response(
    code: ErrorCode,
    request_id: str,
    *,
    mutates: bool = False,
    status: int | None = None,
    uncertain: bool = False,
) -> JSONResponse:
    spec = ERRORS[code]
    unknown_write = mutates and (
        uncertain
        or code in {"STORE_UNAVAILABLE", "STORE_BUSY", "INTERNAL_ERROR", "STORE_GENERATION_CHANGED"}
    )
    error = ApiError(
        code=code,
        message=spec.message,
        request_id=request_id,
        retryable=spec.transient or (unknown_write and code != "STORE_GENERATION_CHANGED"),
        retry_action=(
            "none"
            if code == "STORE_GENERATION_CHANGED"
            else "same_operation_only"
            if unknown_write
            else "read"
            if spec.transient and not mutates
            else "none"
        ),
        outcome_state="unresolved" if unknown_write else None,
    )
    return JSONResponse(
        status_code=spec.status if status is None else status,
        content=ErrorEnvelope(error=error).model_dump(mode="json"),
        headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
    )


def install_error_handlers(application: FastAPI) -> None:
    def response(request: Request, code: ErrorCode) -> JSONResponse:
        request.state.safe_error_code = code
        return error_response(code, request.state.request_id, mutates=request.state.mutates)

    @application.exception_handler(ApiFailure)
    async def api_failure(request: Request, exc: ApiFailure) -> JSONResponse:
        return response(request, exc.code)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Even a validation location can contain a caller-selected key. Expose no raw issues.
        return response(request, "VALIDATION_ERROR")

    @application.exception_handler(ResponseValidationError)
    async def invalid_response(request: Request, exc: ResponseValidationError) -> JSONResponse:
        return response(request, "INTERNAL_ERROR")

    @application.exception_handler(StoreError)
    async def store_failure(request: Request, exc: StoreError) -> JSONResponse:
        code: ErrorCode = "STORE_UNAVAILABLE"
        if exc.args == ("STORE_BUSY",):
            code = "STORE_BUSY"
        elif exc.args == ("STORE_GENERATION_CHANGED",):
            code = "STORE_GENERATION_CHANGED"
        return response(request, code)

    @application.exception_handler(HTTPException)
    async def http_failure(request: Request, exc: HTTPException) -> JSONResponse:
        codes: dict[int, ErrorCode] = {
            400: "VALIDATION_ERROR",
            401: "IDENTITY_REQUIRED",
            403: "CSRF_DENIED",
            404: "NOT_FOUND",
            405: "NOT_FOUND",
            413: "INPUT_TOO_LARGE",
            415: "UNSUPPORTED_CONTENT_TYPE",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
        }
        return response(request, codes.get(exc.status_code, "INTERNAL_ERROR"))
