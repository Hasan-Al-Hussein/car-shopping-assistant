import semantic from "../../../contracts/fixtures/semantic_cases.json";
import type { Schema } from "../../src/shared/api/contracts";
import { identity, meta, schemaFixture, seed } from "./apiFixtures";

export const viewingGeneration = seed.synthetic_generations[0]!;
export function viewingValues(): Schema<"LeadValues"> {
  return {
    budget: {
      state: "provided",
      value: {
        currency: "AED",
        basis: "cash",
        minimum: null,
        maximum: 3500000,
      },
    },
    requirements: ["Quiet cabin", "Room for luggage"],
    selected_refs: [structuredClone(semantic.baselines.BookingDraft.ref)],
    email: { state: "declined", value: null },
    phone: { state: "missing", value: null },
  };
}
export function viewingDraft(revision = 1): Schema<"BookingDraft"> {
  const raw = structuredClone(semantic.baselines.BookingDraft);
  return schemaFixture("BookingDraft", {
    ...raw,
    revision,
    expires_at: "2026-09-24T04:30:00Z",
    appointment: {
      ...raw.appointment,
      timezone: "Asia/Dubai",
      appointment_type: "viewing",
    },
    review: {
      ...raw.review,
      draft_revision: revision,
      appointment_type: "viewing",
      simulation: true,
      lead_effect: "save_local_enquiry",
      store_generation: viewingGeneration,
      issued_at: "2026-09-24T04:00:00Z",
      expires_at: "2026-09-24T04:05:00Z",
      lead_change: {
        mode: "create_from_review",
        source_session_revision: 2,
        values: viewingValues(),
      },
    },
  });
}
export function viewingLead(revision = 1): Schema<"LeadRecord"> {
  return schemaFixture("LeadRecord", {
    lead_id: "00000000-0000-4000-8000-000000000014",
    journey_id: "00000000-0000-4000-8000-000000000005",
    revision,
    stage: "interested",
    values: viewingValues(),
    booking_ids: [],
    updated_at: "2026-09-24T04:00:00Z",
    expires_at: "2026-10-24T04:00:00Z",
    delivery: "local_only",
    csv: {
      state: "pending",
      store_generation: viewingGeneration,
      observed_at: "2026-09-24T04:00:00Z",
      canonical_version: revision,
      exported_version: 0,
      code: null,
    },
  });
}
export const viewingEnvelope = <T>(
  data: T,
  generation = viewingGeneration,
) => ({
  meta: { ...meta(identity().context_id), store_generation: generation },
  data,
});
export function viewingSuccess(): Schema<"OperationSucceeded"> {
  const review = viewingDraft().review!;
  return schemaFixture("OperationSucceeded", {
    ...semantic.baselines.OperationSucceeded,
    original_store_generation: viewingGeneration,
    terminal_at: "2026-09-24T04:00:01Z",
    booking: {
      ...semantic.baselines.OperationSucceeded.booking,
      confirmed_at: "2026-09-24T04:00:01Z",
      review: { ...review, state: "consumed" },
    },
    csv: {
      ...semantic.baselines.OperationSucceeded.csv,
      store_generation: viewingGeneration,
      observed_at: "2026-09-24T04:00:01Z",
    },
  });
}
export function viewingUnknown(): Schema<"OperationNotObserved"> {
  return {
    state: "not_observed",
    operation_key: viewingDraft().review!.operation_key,
    observed_store_generation: viewingGeneration,
    definitive_noncommit: false,
    recovery: "read_original_operation",
  };
}
