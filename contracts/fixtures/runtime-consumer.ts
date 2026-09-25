import type { components, operations } from "../generated/api";
import {
  contractVersion,
  operationContracts,
  validateIdentity,
  validateRequestBody,
  validateResponse,
  validateParameter,
} from "../generated/runtime";
import { validateSchema } from "../generated/runtime.schemas";

export function parseIdentity(
  value: unknown,
): components["schemas"]["AnonymousIdentity"] {
  if (!validateIdentity(value) || !validateSchema("AnonymousIdentity", value))
    throw new Error("INVALID_RESPONSE");
  return value as components["schemas"]["AnonymousIdentity"];
}

export function validateBoundary(
  op: keyof operations,
  value: unknown,
): boolean {
  return (
    contractVersion === "1.0.0" &&
    operationContracts[op].method.length > 0 &&
    validateRequestBody(op, value) &&
    validateResponse(op, 200, value) &&
    validateParameter(op, "header", "X-Identity-Context", "synthetic")
  );
}

// @ts-expect-error unsupported operation must not enter a typed caller
validateResponse("invented_operation", 200, {});
// @ts-expect-error unsupported schema must not enter a typed caller
validateSchema("invented_schema", {});
