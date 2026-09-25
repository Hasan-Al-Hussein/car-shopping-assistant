import { describe, expect, test } from "vitest";
import semantic from "../../../contracts/fixtures/semantic_cases.json";
import { validateResponse } from "../../../contracts/generated/runtime";
import {
  checkMessageResultAssociation,
  checkResponseAssociation,
} from "../../src/shared/api/responseAssociation";
import { ApiClient } from "../../src/shared/api/ApiClient";
import { OwnerSession } from "../../src/shared/api/OwnerSession";
import { deferred, scriptedFetch } from "../harness/fixtures";
import {
  confirmation,
  identity,
  listingDetail,
  meta,
  schemaFixture,
  searchResult,
} from "./apiFixtures";

describe("FE-02 exact response association beyond JSON shape", () => {
  test("presentation registration returns a newly owned ID; selection replay may return a later current car", () => {
    const data = schemaFixture("SessionState", semantic.baselines.SessionState),
      publicProof = searchResult().data.presentation;
    data.active_presentation_id = identity(1).context_id;
    data.selected_ref = { ...publicProof.ordered_refs[0]!, source_id: "later" };
    const envelope = { meta: meta(identity().context_id), data },
      path = { session_id: data.session_id };
    expect(() =>
      checkResponseAssociation(
        "register_presentation",
        { path, body: { presentation: publicProof } },
        envelope,
      ),
    ).not.toThrow();
    expect(() =>
      checkResponseAssociation(
        "select_session_listing",
        { path, body: { selected_ref: publicProof.ordered_refs[0] } },
        envelope,
      ),
    ).not.toThrow();
    expect(() =>
      checkResponseAssociation(
        "register_presentation",
        {
          path: { session_id: identity(1).context_id },
          body: { presentation: publicProof },
        },
        envelope,
      ),
    ).toThrow();
  });
  test("message accepted revision binds to the original request even if current revision is newer", () => {
    const data = schemaFixture(
        "MessageResult",
        semantic.baselines.MessageResult,
      ),
      input = {
        path: { session_id: data.session_id },
        body: {
          client_message_id: data.client_message_id,
          expected_revision: data.turn_revision - 1,
        },
      };
    data.current_revision += 5;
    const envelope = { meta: meta(identity().context_id), data };
    expect(() =>
      checkResponseAssociation("submit_message", input, envelope),
    ).not.toThrow();
    data.turn_revision += 1;
    expect(() =>
      checkResponseAssociation("submit_message", input, envelope),
    ).toThrow();
  });
  test("nested search must match every signed original ordinal and snapshot", () => {
    const result = schemaFixture(
      "MessageResult",
      semantic.baselines.MessageResult,
    );
    result.search = searchResult().data;
    expect(() => checkMessageResultAssociation(result)).not.toThrow();
    result.search.presentation.ordered_refs[0] = {
      ...result.search.presentation.ordered_refs[0]!,
      source_id: "different-ordinal",
    };
    expect(() => checkMessageResultAssociation(result)).toThrow();
  });
  test("public browse items must match the signed order before it can become conversation context", () => {
    const envelope = searchResult(),
      input = { body: { client_request_id: envelope.data.client_request_id } };
    expect(() =>
      checkResponseAssociation("search_inventory", input, envelope),
    ).not.toThrow();
    envelope.data.presentation.ordered_refs[0] = {
      ...envelope.data.presentation.ordered_refs[0]!,
      source_id: "wrong-order",
    };
    expect(() =>
      checkResponseAssociation("search_inventory", input, envelope),
    ).toThrow();
  });
  test("draft command replay may return the current edited car while preserving draft/session association", () => {
    const data = schemaFixture("BookingDraft", semantic.baselines.BookingDraft);
    const oldRef = { ...data.ref, source_id: "original-before-edit" };
    const envelope = { meta: meta(identity().context_id), data };
    expect(() =>
      checkResponseAssociation(
        "create_booking_draft",
        { body: { session_id: data.session_id, ref: oldRef } },
        envelope,
      ),
    ).not.toThrow();
    expect(() =>
      checkResponseAssociation(
        "update_booking_draft",
        {
          path: { draft_id: data.draft_id },
          body: { intent: "edit", ref: oldRef },
        },
        envelope,
      ),
    ).not.toThrow();
    expect(() =>
      checkResponseAssociation(
        "create_booking_draft",
        { body: { session_id: identity(1).context_id, ref: oldRef } },
        envelope,
      ),
    ).toThrow();
    expect(() =>
      checkResponseAssociation(
        "update_booking_draft",
        {
          path: { draft_id: identity(1).context_id },
          body: { intent: "edit", ref: oldRef },
        },
        envelope,
      ),
    ).toThrow();
  });
  test.each(["client_request_id", "snapshot_id"] as const)(
    "search rejects wrong echoed %s",
    (field) => {
      const envelope = searchResult();
      const body = {
        client_request_id: envelope.data.client_request_id,
        snapshot_id: envelope.data.presentation.snapshot_id,
      };
      expect(() =>
        checkResponseAssociation("search_inventory", { body }, envelope),
      ).not.toThrow();
      if (field === "client_request_id")
        envelope.data.client_request_id = identity(1).context_id;
      else envelope.meta.inventory_snapshot_id = "b".repeat(64);
      expect(validateResponse("search_inventory", 200, envelope)).toBe(true);
      expect(() =>
        checkResponseAssociation("search_inventory", { body }, envelope),
      ).toThrow();
    },
  );

  test.each([
    "draft_id",
    "review_id",
    "operation_key",
    "store_generation",
    "draft_revision",
    "rules_version",
  ] as const)(
    "confirmation receipt binds embedded review %s to the submitted request",
    (field) => {
      const data = schemaFixture(
        "OperationSucceeded",
        semantic.baselines.OperationSucceeded,
      );
      const review = data.booking.review;
      const body = {
        ...confirmation(),
        review_id: review.review_id,
        operation_key: review.operation_key,
        store_generation: review.store_generation,
        expected_draft_revision: review.draft_revision,
        rules_version: review.rules_version,
      };
      data.operation_key = body.operation_key;
      data.review_id = body.review_id;
      data.original_store_generation = body.store_generation;
      const envelope = { meta: meta(identity().context_id), data };
      const input = { path: { draft_id: review.draft_id }, body };
      expect(validateResponse("confirm_booking_draft", 200, envelope)).toBe(
        true,
      );
      expect(() =>
        checkResponseAssociation("confirm_booking_draft", input, envelope),
      ).not.toThrow();
      switch (field) {
        case "draft_revision":
          review.draft_revision += 1;
          break;
        case "operation_key":
          review.operation_key = "z".repeat(43);
          break;
        case "rules_version":
          review.rules_version = "different-rules";
          break;
        default:
          review[field] = identity(1).context_id;
      }
      expect(validateResponse("confirm_booking_draft", 200, envelope)).toBe(
        true,
      );
      expect(() =>
        checkResponseAssociation("confirm_booking_draft", input, envelope),
      ).toThrow();
    },
  );

  test("viewing options preserve immutable reference association", () => {
    const data = schemaFixture(
      "ViewingOptions",
      semantic.baselines.ViewingOptions,
    );
    const body = { ref: { ...data.ref } };
    const envelope = { meta: meta(), data };
    expect(validateResponse("get_viewing_options", 200, envelope)).toBe(true);
    expect(() =>
      checkResponseAssociation("get_viewing_options", { body }, envelope),
    ).not.toThrow();
    data.ref.source_id = "different-car";
    expect(validateResponse("get_viewing_options", 200, envelope)).toBe(true);
    expect(() =>
      checkResponseAssociation("get_viewing_options", { body }, envelope),
    ).toThrow();
  });

  test("session and message IDs must both match", () => {
    const data = schemaFixture(
      "MessageResult",
      semantic.baselines.MessageResult,
    );
    const input = {
      path: { session_id: data.session_id },
      body: { client_message_id: data.client_message_id },
    };
    const envelope = { meta: meta(identity().context_id), data };
    expect(() =>
      checkResponseAssociation("submit_message", input, envelope),
    ).not.toThrow();
    data.client_message_id = identity(1).context_id;
    expect(validateResponse("submit_message", 200, envelope)).toBe(true);
    expect(() =>
      checkResponseAssociation("submit_message", input, envelope),
    ).toThrow();
    data.client_message_id = input.body.client_message_id;
    data.session_id = identity(1).context_id;
    expect(() =>
      checkResponseAssociation("submit_message", input, envelope),
    ).toThrow();
  });

  test("a caller changing a path after dispatch cannot change the response comparison basis", async () => {
    const gate = deferred<void>();
    const detail = listingDetail();
    const path = { ...detail.listing.ref };
    const request = scriptedFetch([
      {
        method: "GET",
        path: `/api/v1/listings/${path.namespace}/${path.snapshot_id}/${path.source_id}`,
        body: { meta: meta(), data: detail },
        gate: gate.promise,
      },
    ]);
    const pending = new ApiClient(new OwnerSession(), request).read(
      "get_listing",
      { path },
    );
    path.source_id = "changed by caller";
    gate.resolve();
    expect((await pending).data).toEqual(detail);
  });
});
