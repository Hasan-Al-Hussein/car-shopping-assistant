import { afterEach, describe, expect, test, vi } from "vitest";
import semantic from "../../../contracts/fixtures/semantic_cases.json";
import { ViewingFlow } from "../../src/features/viewings/ViewingFlow";
import { ApiClient } from "../../src/shared/api/ApiClient";
import { ClientFailure } from "../../src/shared/api/ClientFailure";
import { OwnerSession } from "../../src/shared/api/OwnerSession";
import type { ResponseOf } from "../../src/shared/api/contracts";
import { deferred } from "../harness/fixtures";
import { apiError, identity, schemaFixture, seed } from "./apiFixtures";
import {
  viewingDraft,
  viewingEnvelope,
  viewingGeneration,
  viewingLead,
  viewingSuccess,
  viewingUnknown,
  viewingValues,
} from "./viewingFixtures";

const cleanups: (() => void)[] = [];
afterEach(() => cleanups.splice(0).forEach((dispose) => dispose()));
const loss = () => new ClientFailure("network", "reconcile-original");
const denied = () =>
  new ClientFailure("api", "reidentify", {
    status: 403,
    detail: apiError("ORIGIN_DENIED").error,
  });
function setup() {
  const owner = new OwnerSession();
  owner.accept(0, identity());
  const api = new ApiClient(owner),
    changed = vi.fn(),
    flow = new ViewingFlow(owner, api, changed);
  const read = vi
    .spyOn(api, "read")
    .mockResolvedValue(viewingEnvelope(viewingDraft()));
  const write = vi
    .spyOn(api, "mutate")
    .mockResolvedValue(viewingEnvelope(viewingDraft()));
  cleanups.push(() => {
    flow.dispose();
    owner.dispose();
  });
  return { owner, api, changed, flow, read, write };
}
async function prime(
  subject: ReturnType<typeof setup>,
  viewId = "mounted-view",
) {
  const draft = viewingDraft();
  await subject.flow.readDraft(draft.draft_id, subject.owner.capture());
  await subject.flow.update(draft, "refresh_review", viewId);
  return draft.review!;
}

describe("U2 synthetic controller seam; not live transaction evidence", () => {
  test("route reads cannot approve; one explicit confirmation retains locator before dispatch and blocks a second gesture", async () => {
    const subject = setup(),
      { flow, owner, write } = subject,
      draft = viewingDraft();
    await flow.readDraft(draft.draft_id, owner.capture());
    expect(flow.canConfirm(draft.review!, "mounted-view")).toBe(false);
    expect(write).not.toHaveBeenCalled();
    await flow.update(draft, "refresh_review", "mounted-view");
    expect(flow.canConfirm(draft.review!, "mounted-view")).toBe(true);
    const pending = deferred<ResponseOf<"confirm_booking_draft">>(),
      order: string[] = [];
    write.mockImplementationOnce(async () => {
      order.push("POST");
      return pending.promise;
    });
    const first = flow.confirm(draft.review!, "mounted-view", (locator) => {
      order.push("original URL");
      expect(locator).toMatchObject({
        key: draft.review!.operation_key,
        generation: viewingGeneration,
      });
    });
    await flow.confirm(draft.review!, "mounted-view", () =>
      order.push("duplicate"),
    );
    expect(order).toEqual(["original URL", "POST"]);
    expect(write).toHaveBeenCalledTimes(2);
    expect(write.mock.calls[1]).toEqual([
      "confirm_booking_draft",
      {
        path: { draft_id: draft.draft_id },
        body: {
          review_id: draft.review!.review_id,
          expected_draft_revision: draft.revision,
          operation_key: draft.review!.operation_key,
          rules_version: draft.review!.rules_version,
          store_generation: viewingGeneration,
          confirmation: "confirm_simulated_viewing",
        },
      },
    ]);
    pending.reject(loss());
    await first;
    expect(flow.getSnapshot()).toMatchObject({
      phase: "unknown",
      operationTerminal: false,
    });
    await flow.update(draft, "refresh_review", "another-view");
    expect(write).toHaveBeenCalledTimes(2);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test("leaving during a pending review permanently revokes that pending approval", async () => {
    const { flow, owner, write } = setup(),
      draft = viewingDraft();
    await flow.readDraft(draft.draft_id, owner.capture());
    const gate = deferred<ResponseOf<"update_booking_draft">>();
    write.mockReturnValueOnce(gate.promise);
    const action = flow.update(draft, "refresh_review", "leaving-view");
    flow.revokeApproval("leaving-view");
    gate.resolve(viewingEnvelope(draft));
    await action;
    expect(flow.canConfirm(draft.review!, "leaving-view")).toBe(false);
    expect(flow.canConfirm(draft.review!, "new-view")).toBe(false);
  });

  test("same-revision invalidation observed after dispatch defeats a late valid refresh", async () => {
    const { flow, owner, write, read } = setup(),
      draft = viewingDraft();
    await flow.readDraft(draft.draft_id, owner.capture());
    const gate = deferred<ResponseOf<"update_booking_draft">>();
    write.mockReturnValueOnce(gate.promise);
    const refresh = flow.update(draft, "refresh_review", "view");
    const invalidated = {
      ...draft,
      state: "needs_details" as const,
      required_fields: ["review_refresh"],
      review: { ...draft.review!, state: "invalidated" as const },
    };
    read.mockResolvedValueOnce(viewingEnvelope(invalidated));
    await flow.readDraft(draft.draft_id, owner.capture());
    gate.resolve(viewingEnvelope(draft));
    await refresh;
    expect(flow.getSnapshot().draft?.review?.state).toBe("invalidated");
    expect(flow.canConfirm(draft.review!, "view")).toBe(false);
    read.mockResolvedValueOnce(viewingEnvelope(draft));
    await expect(
      flow.readDraft(draft.draft_id, owner.capture()),
    ).rejects.toMatchObject({ kind: "superseded" });
  });

  test("a terminal status defeats both a delayed unobserved GET and a late confirmation transport error", async () => {
    const subject = setup(),
      { flow, owner, write, read } = subject,
      review = await prime(subject);
    const confirm = deferred<ResponseOf<"confirm_booking_draft">>();
    write.mockReturnValueOnce(confirm.promise);
    const pending = flow.confirm(review, "mounted-view", () => {});
    const locator = {
      key: review.operation_key,
      generation: viewingGeneration,
      draftId: review.draft_id,
    };
    const oldGet = deferred<ResponseOf<"get_operation">>();
    read.mockReturnValueOnce(oldGet.promise);
    const old = flow.readOperation(locator, owner.capture());
    read.mockResolvedValueOnce(viewingEnvelope(viewingSuccess()));
    await flow.readOperation(locator, owner.capture());
    confirm.reject(loss());
    await pending;
    oldGet.resolve(viewingEnvelope(viewingUnknown()));
    expect((await old).data.state).toBe("succeeded");
    expect(flow.getSnapshot()).toMatchObject({
      phase: "idle",
      operationTerminal: true,
    });
  });

  test("uncertain draft replay uses identical command, accepts current changed car, and grants no review approval", async () => {
    const { flow, owner, write, read } = setup(),
      draft = viewingDraft();
    await flow.readDraft(draft.draft_id, owner.capture());
    write.mockRejectedValueOnce(loss());
    await flow.update(draft, "refresh_review", "view");
    const original = structuredClone(write.mock.calls[0]);
    read.mockResolvedValueOnce(
      viewingEnvelope({ state: "not_created" as const }),
    );
    write.mockRejectedValueOnce(denied());
    await flow.reconcileCommand();
    expect(flow.getSnapshot().phase).toBe("unknown");
    const current = viewingDraft(4);
    current.ref = { ...current.ref, source_id: "later-edited-car" };
    current.review = { ...current.review!, ref: current.ref };
    read.mockResolvedValueOnce(
      viewingEnvelope({ state: "not_created" as const }),
    );
    write.mockResolvedValueOnce(viewingEnvelope(current));
    await flow.reconcileCommand();
    expect(write.mock.calls[1]).toEqual(original);
    expect(write.mock.calls[2]).toEqual(original);
    expect(flow.getSnapshot().draft?.ref.source_id).toBe("later-edited-car");
    expect(flow.canConfirm(current.review!, "view")).toBe(false);
  });

  test("unknown enquiry save retains original values/revision and changed generation forbids replay", async () => {
    const { flow, read, write } = setup(),
      lead = viewingLead(),
      values = viewingValues();
    write.mockRejectedValueOnce(loss());
    await flow.saveEnquiry(
      viewingDraft().session_id,
      values,
      lead,
      viewingGeneration,
    );
    const original = structuredClone(write.mock.calls[0]);
    values.requirements.push("later typing");
    read.mockResolvedValueOnce(viewingEnvelope(lead));
    write.mockRejectedValueOnce(denied());
    await flow.reconcileCommand();
    expect(write.mock.calls[1]).toEqual(original);
    expect(original?.[1]).toMatchObject({
      body: {
        expected_revision: lead.revision,
        intent: "correct_local_enquiry",
        values: { requirements: ["Quiet cabin", "Room for luggage"] },
      },
    });
    read.mockResolvedValueOnce(
      viewingEnvelope(lead, seed.synthetic_generations[1]!),
    );
    await flow.reconcileCommand();
    await flow.saveEnquiry(
      viewingDraft().session_id,
      values,
      lead,
      seed.synthetic_generations[1]!,
    );
    expect(write).toHaveBeenCalledTimes(2);
    expect(flow.getSnapshot().phase).toBe("blocked");
  });

  test("old owner completion never publishes private data or approval and same owner must reconcile", async () => {
    const { flow, owner, write, changed } = setup(),
      draft = viewingDraft();
    await flow.readDraft(draft.draft_id, owner.capture());
    const gate = deferred<ResponseOf<"update_booking_draft">>();
    write.mockReturnValueOnce(gate.promise);
    const pending = flow.update(draft, "refresh_review", "old-view");
    owner.accept(owner.invalidate(), identity(1));
    gate.resolve(viewingEnvelope(draft));
    await pending;
    expect(flow.getSnapshot().draft).toBeNull();
    expect(changed).not.toHaveBeenCalled();
    owner.accept(owner.invalidate(), identity());
    expect(flow.getSnapshot().phase).toBe("unknown");
    expect(flow.canConfirm(draft.review!, "old-view")).toBe(false);
  });

  test("create captures exact car before preflight and uses the observed session revision once", async () => {
    const { flow, read, write } = setup(),
      draft = viewingDraft(),
      ref = { ...draft.ref };
    const gate = deferred<ResponseOf<"get_session">>();
    read.mockReturnValueOnce(gate.promise);
    const pending = flow.create(draft.session_id, ref, null);
    ref.source_id = "changed-local-object";
    await flow.create(draft.session_id, ref, null);
    expect(write).not.toHaveBeenCalled();
    gate.resolve(
      viewingEnvelope(
        schemaFixture("SessionState", {
          ...semantic.baselines.SessionState,
          revision: 9,
          current_draft_id: null,
        }),
      ),
    );
    await pending;
    expect(write).toHaveBeenCalledTimes(1);
    expect(write.mock.calls[0]).toEqual([
      "create_booking_draft",
      {
        body: {
          client_action_id: expect.any(String),
          session_id: draft.session_id,
          expected_session_revision: 9,
          ref: draft.ref,
          appointment: null,
        },
      },
    ]);
    expect(flow.canConfirm(draft.review!, "view")).toBe(false);
  });

  test("a session's resolved draft still requires its original terminal status before a replacement", async () => {
    const { flow, read, write } = setup(),
      draft = viewingDraft();
    const session = schemaFixture("SessionState", {
      ...semantic.baselines.SessionState,
      current_draft_id: draft.draft_id,
    });
    read.mockResolvedValueOnce(viewingEnvelope(session)).mockResolvedValueOnce(
      viewingEnvelope({
        ...draft,
        state: "resolved" as const,
        review: { ...draft.review!, state: "consumed" as const },
      }),
    );
    const result = await flow.create(draft.session_id, draft.ref, null);
    expect(result?.draft_id).toBe(draft.draft_id);
    expect(write).not.toHaveBeenCalled();
    expect(flow.getSnapshot().operationTerminal).toBe(false);
  });

  test("reading a historical receipt does not erase another unresolved original operation", async () => {
    const { flow, owner, read } = setup(),
      review = viewingDraft().review!;
    const active = {
      key: "b".repeat(43),
      generation: viewingGeneration,
      draftId: null,
    };
    read.mockResolvedValueOnce(
      viewingEnvelope({ ...viewingUnknown(), operation_key: active.key }),
    );
    await flow.readOperation(active, owner.capture());
    read.mockResolvedValueOnce(viewingEnvelope(viewingSuccess()));
    const historical = await flow.readOperation(
      {
        key: review.operation_key,
        generation: viewingGeneration,
        draftId: review.draft_id,
      },
      owner.capture(),
    );
    expect(historical.data.state).toBe("succeeded");
    expect(flow.getSnapshot()).toMatchObject({
      operation: active,
      operationTerminal: false,
    });
  });
});
