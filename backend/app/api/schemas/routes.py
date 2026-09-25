"""Versioned route catalogue for generated contracts, not runtime stub handlers.

Domain routers must implement these signatures. The spec-only app is never mounted
by app.main; BE-25 checks the actual application's OpenAPI against this catalogue.
"""

import inspect
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import FastAPI, Header, Path, Query

from app.api.schemas.capabilities import HealthResult, PublicConfig
from app.api.schemas.common import EmptyResult, Envelope, ErrorEnvelope, Id, OpaqueKey
from app.api.schemas.identity import (
    IdentityBootstrapRequest,
    IdentityEndRequest,
    IdentityResult,
    RecognizedIdentity,
)
from app.api.schemas.inventory import (
    ComparisonRequest,
    ComparisonResult,
    ListingResult,
    SearchRequest,
    SearchResult,
)
from app.api.schemas.leads import (
    LeadRecord,
    LeadSaveRequest,
    LeadSaveResult,
    LeadUpdateRequest,
    NoLead,
)
from app.api.schemas.memory import (
    MembershipRequest,
    MembershipResult,
    PreferenceCommand,
    PreferenceRecord,
    ShortlistResult,
)
from app.api.schemas.openapi_security import install_owner_cookie_schema
from app.api.schemas.operations import OperationRejected, OperationStatus
from app.api.schemas.sessions import (
    MessageRequest,
    MessageResult,
    PresentationRegisterRequest,
    SessionCreateRequest,
    SessionSelectionRequest,
    SessionState,
    TranscriptPage,
)
from app.api.schemas.viewings import (
    BookingDraft,
    BookingDraftCreate,
    BookingDraftUpdate,
    BookingReceipt,
    ConfirmRequest,
    ViewingOptions,
    ViewingOptionsRequest,
)


@dataclass(frozen=True)
class RouteContract:
    method: str
    path: str
    operation_id: str
    response: Any
    request: Any = None
    private: bool = False
    mutates: bool = False
    owner: str = "platform"
    status: int = 200


REF_PATH = "/{namespace}/{snapshot_id}/{source_id}"
REF_PATH_PATTERNS = {
    "namespace": r"^[a-z0-9_-]{1,64}$",
    "snapshot_id": r"^[0-9a-f]{64}$",
    "source_id": r"^[A-Za-z0-9._-]{1,128}$",
}
ROUTES = (
    RouteContract("GET", "/health", "get_health", HealthResult),
    RouteContract("GET", "/config", "get_config", PublicConfig),
    RouteContract("GET", "/identity", "get_identity", IdentityResult),
    RouteContract(
        "POST",
        "/identity/bootstrap",
        "bootstrap_identity",
        RecognizedIdentity,
        IdentityBootstrapRequest,
        mutates=True,
        status=201,
    ),
    RouteContract(
        "POST", "/identity/end", "end_identity", EmptyResult, IdentityEndRequest, True, True
    ),
    RouteContract(
        "POST",
        "/sessions",
        "create_session",
        SessionState,
        SessionCreateRequest,
        True,
        True,
        status=201,
    ),
    RouteContract("GET", "/sessions/{session_id}", "get_session", SessionState, private=True),
    RouteContract(
        "GET",
        "/sessions/{session_id}/messages",
        "get_session_messages",
        TranscriptPage,
        private=True,
    ),
    RouteContract(
        "POST",
        "/sessions/{session_id}/presentations",
        "register_presentation",
        SessionState,
        PresentationRegisterRequest,
        True,
        True,
    ),
    RouteContract(
        "PATCH",
        "/sessions/{session_id}/selection",
        "select_session_listing",
        SessionState,
        SessionSelectionRequest,
        True,
        True,
    ),
    RouteContract(
        "POST",
        "/sessions/{session_id}/messages",
        "submit_message",
        MessageResult,
        MessageRequest,
        True,
        True,
        "assistant",
    ),
    RouteContract(
        "POST",
        "/inventory/search",
        "search_inventory",
        SearchResult,
        SearchRequest,
        owner="inventory",
    ),
    RouteContract("GET", "/listings" + REF_PATH, "get_listing", ListingResult, owner="inventory"),
    RouteContract(
        "POST",
        "/comparisons",
        "compare_listings",
        ComparisonResult,
        ComparisonRequest,
        owner="inventory",
    ),
    RouteContract("GET", "/preferences", "get_preferences", PreferenceRecord, private=True),
    RouteContract(
        "PATCH",
        "/preferences",
        "update_preferences",
        PreferenceRecord,
        PreferenceCommand,
        True,
        True,
    ),
    RouteContract("GET", "/shortlist", "get_shortlist", ShortlistResult, private=True),
    RouteContract(
        "PUT",
        "/shortlist" + REF_PATH,
        "add_shortlist_membership",
        MembershipResult,
        MembershipRequest,
        True,
        True,
    ),
    RouteContract(
        "DELETE",
        "/shortlist" + REF_PATH,
        "remove_shortlist_membership",
        MembershipResult,
        private=True,
        mutates=True,
    ),
    RouteContract(
        "POST",
        "/viewing-options",
        "get_viewing_options",
        ViewingOptions,
        ViewingOptionsRequest,
        owner="transactions",
    ),
    RouteContract(
        "POST",
        "/booking-drafts",
        "create_booking_draft",
        BookingDraft,
        BookingDraftCreate,
        True,
        True,
        "transactions",
        201,
    ),
    RouteContract(
        "GET",
        "/booking-drafts/{draft_id}",
        "get_booking_draft",
        BookingDraft,
        private=True,
        owner="transactions",
    ),
    RouteContract(
        "PATCH",
        "/booking-drafts/{draft_id}",
        "update_booking_draft",
        BookingDraft,
        BookingDraftUpdate,
        True,
        True,
        "transactions",
    ),
    RouteContract(
        "POST",
        "/booking-drafts/{draft_id}/confirm",
        "confirm_booking_draft",
        OperationStatus,
        ConfirmRequest,
        True,
        True,
        "transactions",
    ),
    RouteContract(
        "GET",
        "/operations/{operation_key}",
        "get_operation",
        OperationStatus,
        private=True,
        owner="transactions",
    ),
    RouteContract(
        "GET",
        "/bookings/{booking_id}",
        "get_booking",
        BookingReceipt,
        private=True,
        owner="transactions",
    ),
    RouteContract(
        "POST",
        "/leads",
        "save_local_enquiry",
        LeadSaveResult,
        LeadSaveRequest,
        True,
        True,
        "transactions",
        201,
    ),
    RouteContract(
        "GET",
        "/leads/current",
        "get_current_local_enquiry",
        LeadRecord | NoLead,
        private=True,
        owner="transactions",
    ),
    RouteContract(
        "GET",
        "/leads/{lead_id}",
        "get_local_enquiry",
        LeadRecord,
        private=True,
        owner="transactions",
    ),
    RouteContract(
        "PATCH",
        "/leads/{lead_id}",
        "update_local_enquiry",
        LeadSaveResult,
        LeadUpdateRequest,
        True,
        True,
        "transactions",
    ),
)


def _endpoint(spec: RouteContract) -> Any:
    def contract_only(**kwargs: Any) -> None:
        raise RuntimeError("Contract-only route must never be mounted in the runtime app.")

    parameters: list[inspect.Parameter] = []
    for segment in spec.path.split("/"):
        if segment.startswith("{"):
            name = segment[1:-1]
            annotation: Any = (
                Annotated[OpaqueKey, Path()] if name == "operation_key" else Annotated[Id, Path()]
            )
            if name in REF_PATH_PATTERNS:
                # Same explicit FastAPI Path constraint as the existing public
                # Inventory/Shortlist routers; do not weaken runtime validation.
                annotation = Annotated[str, Path(pattern=REF_PATH_PATTERNS[name])]
            parameters.append(
                inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
            )
    if spec.request:
        parameters.append(
            inspect.Parameter("body", inspect.Parameter.KEYWORD_ONLY, annotation=spec.request)
        )
    if spec.private:
        parameters.append(
            inspect.Parameter(
                "identity_context",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=Annotated[Id, Header(alias="X-Identity-Context")],
            )
        )
    if spec.private and spec.mutates:
        parameters.append(
            inspect.Parameter(
                "csrf_token",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=Annotated[OpaqueKey, Header(alias="X-CSRF-Token")],
            )
        )
    if spec.mutates:
        parameters.append(
            inspect.Parameter(
                "origin",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=str,
                default=Header(alias="Origin"),
            )
        )
    if spec.method == "DELETE":
        parameters.extend(
            [
                inspect.Parameter(
                    "client_action_id",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=Annotated[Id, Header(alias="X-Client-Action-ID")],
                ),
                inspect.Parameter(
                    "expected_revision",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=int,
                    default=Header(alias="X-Expected-Revision", ge=0, le=2_147_483_647),
                ),
            ]
        )
    if spec.operation_id == "get_operation":
        parameters.append(
            inspect.Parameter(
                "submitted_store_generation",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=Id | None,
                default=Query(None),
            )
        )
    if spec.operation_id in {"get_session_messages", "get_shortlist"}:
        parameters.extend(
            [
                inspect.Parameter(
                    "page_size",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=int,
                    default=Query(20, ge=1, le=50),
                ),
                inspect.Parameter(
                    "cursor",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=str | None,
                    default=Query(None, max_length=2048),
                ),
            ]
        )
    contract_only.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    return contract_only


def create_contract_app() -> FastAPI:
    application = FastAPI(title="Car Shopping Assistant", version="1.0.0")
    install_owner_cookie_schema(application)
    for route in ROUTES:
        responses: dict[int | str, dict[str, Any]] = {
            code: {"model": ErrorEnvelope}
            for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504)
        }
        if route.operation_id == "confirm_booking_draft":
            responses[409] = {"model": ErrorEnvelope | Envelope[OperationRejected]}
        if route.operation_id == "bootstrap_identity":
            responses[200] = {
                "model": Envelope[RecognizedIdentity],
                "description": "Existing valid identity",
            }
        application.add_api_route(
            "/api/v1" + route.path,
            _endpoint(route),
            methods=[route.method],
            operation_id=route.operation_id,
            response_model=Envelope.__class_getitem__(route.response),
            status_code=route.status,
            responses=responses,
            tags=[route.owner],
            openapi_extra={
                "x-domain-owner": route.owner,
                "x-mutates-state": route.mutates,
                "x-private": route.private,
                "x-implementation": "contract-only",
                "security": [{"OwnerCookie": []}] if route.private else [],
            },
        )
    return application
