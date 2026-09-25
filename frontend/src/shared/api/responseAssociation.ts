import { operationContracts } from "../../../../contracts/generated/runtime";
import { ClientFailure } from "./ClientFailure";
import type { Operation, Schema } from "./contracts";

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function sameRef(actual: unknown, expected: unknown): boolean {
  const a = record(actual);
  const b = record(expected);
  return (
    typeof a.namespace === "string" &&
    typeof a.snapshot_id === "string" &&
    typeof a.source_id === "string" &&
    a.namespace === b.namespace &&
    a.snapshot_id === b.snapshot_id &&
    a.source_id === b.source_id
  );
}

function listingRef(value: unknown): unknown {
  const data = record(value);
  return data.state === "current" || data.state === "historical"
    ? record(data.listing).ref
    : data.ref;
}

/** JSON Schema cannot express the signed result-order equality enforced by the server. */
function checkSearchResultAssociation(search: Schema<"SearchResult">): void {
  const proof = search.presentation;
  if (
    search.items.length !== proof.ordered_refs.length ||
    !search.items.every(
      (item, index) =>
        sameRef(item.ref, proof.ordered_refs[index]) &&
        item.ref.snapshot_id === proof.snapshot_id,
    )
  )
    throw new ClientFailure("invalid-response", "read");
}
export function checkMessageResultAssociation(
  result: Schema<"MessageResult">,
): void {
  if (result.search) checkSearchResultAssociation(result.search);
}

/** Correlates already schema-valid responses with this exact request, not current UI selection. */
export function checkResponseAssociation(
  operation: Operation,
  input: {
    body?: unknown;
    path?: Record<string, unknown>;
    query?: Record<string, unknown>;
    headers?: Record<string, unknown>;
  },
  envelope: { meta: Schema<"ResponseMeta">; data: unknown },
): void {
  const body = record(input.body);
  const path = input.path ?? {};
  const data = record(envelope.data);
  const require = (condition: boolean) => {
    if (!condition)
      throw new ClientFailure(
        "invalid-response",
        operationContracts[operation].mutates ? "reconcile-original" : "read",
      );
  };
  if (operation === "submit_message")
    checkMessageResultAssociation(envelope.data as Schema<"MessageResult">);

  if (operation === "search_inventory") {
    checkSearchResultAssociation(envelope.data as Schema<"SearchResult">);
    require(data.client_request_id === body.client_request_id);
    if (body.snapshot_id)
      require(envelope.meta.inventory_snapshot_id === body.snapshot_id);
  }
  if (operation === "get_listing") require(sameRef(listingRef(data), path));
  if (operation === "compare_listings") {
    const requested = body.refs as unknown[];
    const items = data.items as unknown[];
    require(
      items.length === requested.length &&
        items.every((item, index) =>
          sameRef(listingRef(item), requested[index]),
        ),
    );
  }
  if (operation === "get_viewing_options") require(sameRef(data.ref, body.ref));
  if (operation === "create_booking_draft") {
    // Exact draft-command replay returns the authoritative current draft,
    // including a later explicit car edit. Session identity remains invariant.
    require(data.session_id === body.session_id);
  }
  if (
    operation === "get_booking_draft" ||
    operation === "update_booking_draft"
  ) {
    require(data.draft_id === path.draft_id);
  }
  if (operation === "get_operation" || operation === "confirm_booking_draft") {
    require(
      data.operation_key ===
        (operation === "get_operation"
          ? path.operation_key
          : body.operation_key),
    );
    if (
      operation === "confirm_booking_draft" &&
      (data.state === "succeeded" || data.state === "rejected")
    ) {
      require(
        data.review_id === body.review_id &&
          data.original_store_generation === body.store_generation,
      );
    }
    if (operation === "confirm_booking_draft" && data.state === "succeeded") {
      const review = record(record(data.booking).review);
      require(
        review.draft_id === path.draft_id &&
          review.review_id === body.review_id &&
          review.operation_key === body.operation_key &&
          review.store_generation === body.store_generation &&
          review.draft_revision === body.expected_draft_revision &&
          review.rules_version === body.rules_version,
      );
    }
    const submitted =
      operation === "get_operation"
        ? input.query?.submitted_store_generation
        : body.store_generation;
    if (data.state === "unresolved_generation" && submitted)
      require(data.submitted_store_generation === submitted);
  }
  if (operation === "get_booking") require(data.booking_id === path.booking_id);
  if (operation === "get_local_enquiry") require(data.lead_id === path.lead_id);
  if (operation === "update_local_enquiry")
    require(record(data.lead).lead_id === path.lead_id);
  if (
    [
      "get_session",
      "get_session_messages",
      "submit_message",
      "register_presentation",
      "select_session_listing",
    ].includes(operation)
  ) {
    require(data.session_id === path.session_id);
  }
  if (operation === "submit_message")
    require(
      data.client_message_id === body.client_message_id &&
        (body.expected_revision === undefined ||
          data.turn_revision === Number(body.expected_revision) + 1),
    );
  // Presentation IDs are newly owned server IDs, not public proof IDs.
  // Registration/selection replay returns CURRENT session state; session identity
  // remains invariant, while later selected refs/presentation IDs may differ.
  if (
    operation === "add_shortlist_membership" ||
    operation === "remove_shortlist_membership"
  ) {
    const actionId =
      operation === "add_shortlist_membership"
        ? body.client_action_id
        : Object.entries(input.headers ?? {}).find(
            ([key]) => key.toLowerCase() === "x-client-action-id",
          )?.[1];
    require(sameRef(data.ref, path) && data.client_action_id === actionId);
    // Replays may report newer authoritative membership; do not infer it from the HTTP verb.
  }
}
