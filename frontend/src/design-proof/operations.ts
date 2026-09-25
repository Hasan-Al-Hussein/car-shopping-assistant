import type { Ref, Schema } from "./types";

/** Fixed synthetic review clock: 24 Sep 2026, 09:56 Asia/Dubai. No wall-clock/backend eligibility. */
export function makeProofReview(
  ref: Ref,
  revision = 1,
): Schema<"BookingReview"> {
  const secondSlot = revision % 2 === 0;
  return {
    review_id: `fe030000-0000-4000-8000-${revision.toString().padStart(12, "0")}`,
    draft_id: "fe030000-0000-4000-8000-000000000002",
    session_id: "fe030000-0000-4000-8000-000000000003",
    resource_id: "fe030000-0000-4000-8000-000000000004",
    draft_revision: revision,
    ref,
    starts_at_utc: `2026-09-25T06:${secondSlot ? "30" : "00"}:00Z`,
    ends_at_utc: secondSlot ? "2026-09-25T07:00:00Z" : "2026-09-25T06:30:00Z",
    local_start: `2026-09-25T10:${secondSlot ? "30" : "00"}:00+04:00`,
    timezone: "Asia/Dubai",
    venue_label: "Simulated local viewing — no real venue or reservation.",
    appointment_type: "viewing",
    rules_version: "DEMO-POLICY-1",
    eligibility_version: "fe03-synthetic-eligibility-v1",
    store_generation: "fe030000-0000-4000-8000-000000000005",
    operation_key: `fe03-listing-${ref.source_id}-revision-${revision}-`.padEnd(
      43,
      "x",
    ),
    issued_at: "2026-09-24T05:55:00Z",
    expires_at: "2026-09-24T06:00:00Z",
    lead_effect: "save_local_enquiry",
    lead_change: {
      mode: "create_from_review",
      source_session_revision: revision,
      values: {
        budget: { state: "declined", value: null },
        phone: { state: "declined", value: null },
        email: { state: "declined", value: null },
        requirements: [
          "Synthetic buyer: inspect the source conflicts at a viewing.",
        ],
        selected_refs: [ref],
      },
    },
    simulation: true,
    state: "valid",
  };
}

export function proofUnknown(
  review: Schema<"BookingReview">,
): Schema<"OperationNotObserved"> {
  return {
    state: "not_observed",
    operation_key: review.operation_key,
    observed_store_generation: review.store_generation,
    definitive_noncommit: false,
    recovery: "read_original_operation",
  };
}

export function proofConfirmation(
  review: Schema<"BookingReview">,
): Schema<"ConfirmRequest"> {
  return {
    confirmation: "confirm_simulated_viewing",
    expected_draft_revision: review.draft_revision,
    operation_key: review.operation_key,
    review_id: review.review_id,
    rules_version: review.rules_version,
    store_generation: review.store_generation,
  };
}

export function appointmentLabel(review: Schema<"BookingReview">) {
  const format = new Intl.DateTimeFormat("en-GB", {
    timeZone: review.timezone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
  return `${format.format(new Date(review.starts_at_utc))}–${format.format(new Date(review.ends_at_utc))}`;
}
