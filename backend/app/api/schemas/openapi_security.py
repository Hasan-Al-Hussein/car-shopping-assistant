"""One documented cookie scheme; install lazily without changing authorization."""

from typing import Any

from fastapi import FastAPI


def owner_cookie_scheme() -> dict[str, str]:
    # Exact existing exported contract definition. Runtime credential parsing and
    # profile-specific cookie policy remain in Identity, not in OpenAPI metadata.
    return {
        "type": "apiKey",
        "in": "cookie",
        "name": "csa_owner",
        "description": "Opaque browser credential; never a request owner field.",
    }


def install_owner_cookie_schema(application: FastAPI) -> None:
    original = application.openapi

    def openapi() -> dict[str, Any]:
        document = original()
        components = document.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["OwnerCookie"] = owner_cookie_scheme()
        return document

    application.openapi = openapi  # type: ignore[method-assign]
