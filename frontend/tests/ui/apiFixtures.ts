import cases from "../../../contracts/fixtures/cases.json";
import semantic from "../../../contracts/fixtures/semantic_cases.json";
import { validateSchema } from "../../../contracts/generated/runtime.schemas";
import type { components } from "../../../contracts/generated/api";
import { newSeed } from "../harness/fixtures";
import type { Schema } from "../../src/shared/api/contracts";

export const seed = newSeed();
export const requestId = "90000000-0000-4000-8000-000000000001";

export function schemaFixture<Name extends keyof components["schemas"]>(
  name: Name,
  value: unknown,
): Schema<Name> {
  if (!validateSchema(name, value))
    throw new Error(`Invalid synthetic fixture: ${name}`);
  return structuredClone(value) as Schema<Name>;
}

export function identity(index = 0): Schema<"RecognizedIdentity"> {
  return {
    state: "recognized",
    context_id: seed.owners[index]!.context_id,
    csrf_token: (index ? "b" : "a").repeat(43),
    expires_at: "2026-10-20T00:00:00Z",
    display_name: "Synthetic Buyer",
    continuity: "this_browser_only",
  };
}

export function meta(contextId: string | null = null): Schema<"ResponseMeta"> {
  return {
    request_id: requestId,
    contract_version: "1.0.0",
    policy_version: "DEMO-POLICY-1",
    identity_context_id: contextId,
    store_generation: seed.synthetic_generations[0],
    inventory_snapshot_id: null,
    entity_revision: null,
  };
}

export function config() {
  return {
    meta: meta(),
    data: schemaFixture("PublicConfig", {
      limits: {},
      viewing_venue: "Simulated local viewing — no real venue or reservation.",
      mode: "local_simulated",
      policy_version: "DEMO-POLICY-1",
      language: "en",
      timezone: "Asia/Dubai",
      identity_mode: "browser_local_explicit_save",
      notice_version: "DEMO-POLICY-1",
      optional_features: [],
    }),
  };
}

export function apiError(
  code: Schema<"ApiError">["code"],
  retry = false,
): Schema<"ErrorEnvelope"> {
  return {
    error: {
      code,
      message: "Synthetic safe error",
      request_id: requestId,
      retryable: retry,
      retry_action: retry ? "read" : "none",
      fields: [{ path: ["filters", "budget"], code: "invalid_range" }],
    },
  };
}

export function confirmation(): Schema<"ConfirmRequest"> {
  return schemaFixture(
    "ConfirmRequest",
    cases.find((item) => item.id === "exact-confirm")!.payload,
  );
}

export function shortlist(contextId = identity().context_id) {
  return {
    meta: meta(contextId),
    data: schemaFixture("ShortlistResult", semantic.baselines.ShortlistResult),
  };
}

export function searchResult() {
  const data = schemaFixture("SearchResult", semantic.baselines.SearchResult);
  return {
    meta: { ...meta(), inventory_snapshot_id: data.presentation.snapshot_id },
    data,
  };
}

export function operationFixture(id: string): unknown {
  return structuredClone(cases.find((item) => item.id === id)!.payload);
}

export function listingDetail(): Schema<"ListingDetail"> {
  return schemaFixture("ListingDetail", {
    state: "current",
    listing: semantic.baselines.ShortlistItem.listing,
    description: "Synthetic source details — not verified condition.",
    fuel_type: { status: "unknown", reason: "not_stated" },
    body_type: { status: "unknown", reason: "not_stated" },
    transmission: { status: "unknown", reason: "not_stated" },
    location: { status: "unknown", reason: "not_stated" },
    warranty: { status: "unknown", reason: "not_stated" },
    service_history: { status: "unknown", reason: "not_stated" },
    eligibility: "configuration_missing",
    eligibility_reason: "Synthetic fixture only",
  });
}
