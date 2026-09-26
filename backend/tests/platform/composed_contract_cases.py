"""Compare wire contracts, preserving property names and all validation constraints."""

import json
from typing import Any

METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})
ANNOTATIONS = frozenset({"title", "description", "examples", "example"})
SCHEMA_MAPS = frozenset({"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"})
SCHEMA_LISTS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
SCHEMA_VALUES = frozenset({
    "items", "additionalProperties", "unevaluatedProperties", "unevaluatedItems",
    "contains", "if", "then", "else", "not", "propertyNames", "contentSchema",
})


def same_json(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def schema_shape(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    shaped: dict[str, Any] = {}
    for key, item in value.items():
        if key in ANNOTATIONS:
            continue
        if key in SCHEMA_MAPS:
            shaped[key] = {name: schema_shape(child) for name, child in item.items()}
        elif key in SCHEMA_LISTS:
            shaped[key] = [schema_shape(child) for child in item]
        elif key in SCHEMA_VALUES:
            shaped[key] = schema_shape(item)
        else:
            # const/enum/default objects, discriminator mappings, extension values
            # and unknown keywords are literal data, not nested schema objects.
            shaped[key] = item
    return shaped


def parameter_shape(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: schema_shape(item) if key == "schema" else item
        for key, item in value.items()
        if key not in {"description", "example", "examples"}
    }


def operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (path, method): operation
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if method in METHODS
    }


def content_shape(value: dict[str, Any]) -> dict[str, Any]:
    return {media: schema_shape(item["schema"]) for media, item in value.get("content", {}).items()}


def assert_wire_contract(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    assert actual.get("security", []) == expected.get("security", []) == [], "root security"
    for key in ("openapi", "jsonSchemaDialect"):
        assert same_json(actual.get(key), expected.get(key)), key
    assert same_json(actual.get("info", {}).get("version"), expected.get("info", {}).get("version")), "API version"
    actual_routes, expected_routes = operations(actual), operations(expected)
    assert actual_routes.keys() == expected_routes.keys(), "path/method contract differs"
    for locator, required in expected_routes.items():
        observed = actual_routes[locator]
        for key in ("operationId", "x-domain-owner", "x-private", "x-mutates-state"):
            assert same_json(observed.get(key), required.get(key)), (locator, key)
        assert same_json(observed.get("security", []), required.get("security", [])), (locator, "security")
        observed_parameters = {
            (item["in"], item["name"]): parameter_shape(item)
            for item in observed.get("parameters", [])
        }
        required_parameters = {
            (item["in"], item["name"]): parameter_shape(item)
            for item in required.get("parameters", [])
        }
        assert len(observed_parameters) == len(observed.get("parameters", [])), (locator, "duplicate parameters")
        assert len(required_parameters) == len(required.get("parameters", [])), (locator, "duplicate expected parameters")
        assert same_json(sorted(observed_parameters.items()), sorted(required_parameters.items())), (locator, "parameters")
        observed_body, required_body = observed.get("requestBody", {}), required.get("requestBody", {})
        assert same_json(observed_body.get("required", False), required_body.get("required", False)), locator
        assert same_json(content_shape(observed_body), content_shape(required_body)), (locator, "request body")
        assert observed["responses"].keys() == required["responses"].keys(), (locator, "statuses")
        for status, response in required["responses"].items():
            candidate = observed["responses"][status]
            assert same_json(content_shape(candidate), content_shape(response)), (locator, status, "body")
            assert same_json({
                name: parameter_shape(header) for name, header in candidate.get("headers", {}).items()
            }, {
                name: parameter_shape(header) for name, header in response.get("headers", {}).items()
            }), (
                locator, status, "headers",
            )
    expected_components = expected.get("components", {})
    observed_components = actual.get("components", {})
    for name, schema in expected_components.get("schemas", {}).items():
        assert same_json(schema_shape(observed_components.get("schemas", {}).get(name)), schema_shape(schema)), name
    assert same_json({
        name: {key: value for key, value in scheme.items() if key != "description"}
        for name, scheme in observed_components.get("securitySchemes", {}).items()
    }, {
        name: {key: value for key, value in scheme.items() if key != "description"}
        for name, scheme in expected_components.get("securitySchemes", {}).items()
    }), "security schemes"
