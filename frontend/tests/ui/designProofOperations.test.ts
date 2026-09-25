import { describe, expect, test } from "vitest";
import { validateSchema } from "../../../contracts/generated/runtime.schemas";
import { proofListings } from "../../src/design-proof/fixtures";
import {
  makeProofReview,
  proofConfirmation,
  proofUnknown,
} from "../../src/design-proof/operations";

describe("FE-03 synthetic operation boundary", () => {
  test("review, explicit confirmation and unknown outcome conform to the frozen contracts", () => {
    const review = makeProofReview(proofListings[0]!.detail.listing.ref);
    expect(validateSchema("BookingReview", review)).toBe(true);
    expect(validateSchema("ConfirmRequest", proofConfirmation(review))).toBe(
      true,
    );
    expect(validateSchema("OperationNotObserved", proofUnknown(review))).toBe(
      true,
    );
    expect(review.simulation).toBe(true);
    expect(review.lead_change.mode).toBe("create_from_review");
  });

  test("a material unsubmitted time edit replaces the review while retaining the exact car", () => {
    const first = makeProofReview(proofListings[1]!.detail.listing.ref);
    const edited = makeProofReview(first.ref, first.draft_revision + 1);
    expect(validateSchema("BookingReview", edited)).toBe(true);
    expect(edited.ref).toEqual(first.ref);
    expect(edited.starts_at_utc).not.toBe(first.starts_at_utc);
    expect(edited.review_id).not.toBe(first.review_id);
    expect(edited.operation_key).not.toBe(first.operation_key);
    expect(edited.draft_revision).toBe(first.draft_revision + 1);
  });

  test("a not-observed status preserves the original operation and cannot establish noncommit", () => {
    const review = makeProofReview(proofListings[2]!.detail.listing.ref);
    const status = proofUnknown(review);
    expect(status.operation_key).toBe(review.operation_key);
    expect(status.observed_store_generation).toBe(review.store_generation);
    expect(status.definitive_noncommit).toBe(false);
    expect(status.recovery).toBe("read_original_operation");
    expect(proofUnknown(review)).toEqual(status);
    expect(status).not.toHaveProperty("booking_id");
  });
});
