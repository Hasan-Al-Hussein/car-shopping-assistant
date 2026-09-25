import { ApiClient } from "../../shared/api/ApiClient";
import { ClientFailure } from "../../shared/api/ClientFailure";
import {
  OwnerSession,
  type OwnerSnapshot,
} from "../../shared/api/OwnerSession";
import type { RequestOf, ResponseOf, Schema } from "../../shared/api/contracts";
import { isLocator, refKey, type InventoryRef } from "../../app/routes";

export type OperationLocator = {
  key: string;
  generation: string;
  draftId: string | null;
};
type Command =
  | { kind: "create"; request: RequestOf<"create_booking_draft"> }
  | { kind: "update"; request: RequestOf<"update_booking_draft"> }
  | { kind: "lead-create"; request: RequestOf<"save_local_enquiry"> }
  | { kind: "lead-update"; request: RequestOf<"update_local_enquiry"> };
type Pending = { command: Command; generation: string; uncertain: boolean };
type Approval = {
  viewId: string;
  owner: OwnerSnapshot;
  review: Schema<"BookingReview">;
};
export type ViewingFlowView = {
  phase: "idle" | "reading" | "pending" | "unknown" | "blocked" | "error";
  notice: string | null;
  error: ClientFailure | null;
  draft: Schema<"BookingDraft"> | null;
  generation: string | null;
  operation: OperationLocator | null;
  operationTerminal: boolean;
  enquiryChanges: number;
};
const blank = (): ViewingFlowView => ({
  phase: "idle",
  notice: null,
  error: null,
  draft: null,
  generation: null,
  operation: null,
  operationTerminal: false,
  enquiryChanges: 0,
});

/** One explicit write at a time; route reads can never create or confirm intent. */
export class ViewingFlow {
  #view = blank();
  #listeners = new Set<() => void>();
  #pending = new Map<string, Pending>();
  #operations = new Map<
    string,
    { locator: OperationLocator; terminal: boolean }
  >();
  #locks = new Set<string>();
  #approval: Approval | null = null;
  #viewVersions = new Map<string, number>();
  #terminalResults = new Map<string, ResponseOf<"get_operation">["data"]>();
  #sequence = 0;
  #observedSequence = 0;
  #retiredGenerations = new Set<string>();
  #versions = new Map<
    string,
    {
      revision: number;
      sequence: number;
      reviewId: string | null;
      reviewState: string | null;
    }
  >();
  #unsubscribe: () => void;
  constructor(
    private owner: OwnerSession,
    private api: ApiClient,
    private changed: () => void,
  ) {
    this.#unsubscribe = owner.subscribe(() => {
      this.#approval = null;
      this.#versions.clear();
      this.#viewVersions.clear();
      this.#terminalResults.clear();
      this.#retiredGenerations.clear();
      this.#observedSequence = 0;
      const context = owner.capture().contextId,
        operation = context ? this.#operations.get(context) : undefined;
      this.#view = {
        ...blank(),
        operation: operation?.locator ?? null,
        operationTerminal: operation?.terminal ?? false,
      };
      if (context && this.#pending.has(context))
        this.#view = {
          ...this.#view,
          phase: "unknown",
          notice:
            "An earlier draft or enquiry command is unresolved. Reconcile the original command before another change.",
        };
      this.#emit();
    });
  }
  getSnapshot = () => this.#view;
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  };
  #emit() {
    this.#view = { ...this.#view };
    for (const listener of this.#listeners) listener();
  }
  hasPendingCommand() {
    const context = this.owner.capture().contextId;
    return !!context && this.#pending.has(context);
  }
  #publish(owner: OwnerSnapshot, update: Partial<ViewingFlowView>) {
    if (this.owner.isCurrent(owner)) {
      this.#view = { ...this.#view, ...update };
      this.#emit();
    }
  }
  #blocked(owner: OwnerSnapshot) {
    return (
      !owner.contextId ||
      this.#locks.has(owner.contextId) ||
      this.#pending.has(owner.contextId) ||
      (this.#operations.has(owner.contextId) &&
        !this.#operations.get(owner.contextId)!.terminal)
    );
  }
  #generation(
    owner: OwnerSnapshot,
    generation: string | null | undefined,
    sequence: number,
  ) {
    this.owner.assertCurrent(owner);
    if (!isLocator(generation))
      throw new ClientFailure("invalid-response", "read");
    if (
      this.#retiredGenerations.has(generation) ||
      (generation !== this.#view.generation &&
        sequence < this.#observedSequence)
    )
      throw new ClientFailure("superseded", "read");
    if (this.#view.generation && generation !== this.#view.generation) {
      this.#retiredGenerations.add(this.#view.generation);
      this.#versions.clear();
      this.#approval = null;
    }
    this.#observedSequence = Math.max(sequence, this.#observedSequence);
    this.#publish(owner, { generation });
    return generation;
  }
  #acceptDraft(
    owner: OwnerSnapshot,
    response: ResponseOf<"get_booking_draft">,
    sequence: number,
  ) {
    this.#generation(owner, response.meta.store_generation, sequence);
    const draft = response.data,
      previous = this.#versions.get(draft.draft_id);
    if (
      previous &&
      (draft.revision < previous.revision ||
        (draft.revision === previous.revision &&
          sequence < previous.sequence) ||
        (previous.reviewId === draft.review?.review_id &&
          previous.reviewState !== "valid" &&
          draft.review?.state === "valid"))
    )
      throw new ClientFailure("superseded", "read");
    this.#versions.set(draft.draft_id, {
      revision: draft.revision,
      sequence,
      reviewId: draft.review?.review_id ?? null,
      reviewState: draft.review?.state ?? null,
    });
    if (
      this.#approval &&
      (this.#approval.review.draft_id !== draft.draft_id ||
        this.#approval.review.review_id !== draft.review?.review_id ||
        draft.review?.state !== "valid")
    )
      this.#approval = null;
    const review = draft.review;
    if (
      review &&
      (draft.state === "unresolved" ||
        draft.state === "resolved" ||
        review.state === "submitted" ||
        review.state === "consumed")
    ) {
      const prior = this.#operations.get(owner.contextId!);
      const locator = {
        key: review.operation_key,
        generation: review.store_generation,
        draftId: draft.draft_id,
      };
      if (!prior || prior.terminal || prior.locator.key === locator.key) {
        const terminal =
          prior?.locator.key === locator.key && prior?.terminal === true;
        this.#operations.set(owner.contextId!, { locator, terminal });
        this.#publish(owner, {
          operation: locator,
          operationTerminal: terminal,
        });
      }
    }
    this.#publish(owner, { draft });
    return draft;
  }
  async readDraft(id: string, owner: OwnerSnapshot, signal?: AbortSignal) {
    this.owner.assertCurrent(owner);
    const sequence = ++this.#sequence;
    const response = await this.api.read("get_booking_draft", {
      path: { draft_id: id },
      signal,
    });
    this.#acceptDraft(owner, response, sequence);
    return response;
  }
  revokeApproval(viewId: string) {
    this.#viewVersions.set(viewId, (this.#viewVersions.get(viewId) ?? 0) + 1);
    if (this.#approval?.viewId === viewId) this.#approval = null;
    this.#emit();
  }
  canConfirm(review: Schema<"BookingReview">, viewId: string) {
    const approval = this.#approval;
    return (
      !!approval &&
      approval.viewId === viewId &&
      this.owner.isCurrent(approval.owner) &&
      !this.#blocked(approval.owner) &&
      review.state === "valid" &&
      Date.parse(review.expires_at) > Date.now() &&
      JSON.stringify(approval.review) === JSON.stringify(review)
    );
  }
  async create(
    sessionId: string,
    ref: InventoryRef,
    appointment: Schema<"AppointmentSelection"> | null,
  ) {
    const owner = this.owner.capture();
    if (this.#blocked(owner)) return;
    const exact = structuredClone(ref),
      selected = structuredClone(appointment);
    this.#locks.add(owner.contextId!);
    this.#publish(owner, {
      phase: "reading",
      notice: "Checking this viewing session…",
      error: null,
    });
    try {
      const sequence = ++this.#sequence;
      const response = await this.api.read("get_session", {
        path: { session_id: sessionId },
      });
      const generation = this.#generation(
          owner,
          response.meta.store_generation,
          sequence,
        ),
        session = response.data;
      if (session.current_draft_id) {
        const existing = await this.readDraft(session.current_draft_id, owner);
        const operation = this.#operations.get(owner.contextId!);
        const knownResolved =
          existing.data.state === "resolved" &&
          operation?.terminal === true &&
          operation.locator.key === existing.data.review?.operation_key;
        if (existing.data.state !== "discarded" && !knownResolved) {
          this.#publish(owner, {
            phase: "idle",
            notice:
              existing.data.state === "resolved" ||
              existing.data.state === "unresolved"
                ? "This session has an original submitted action. Read its original outcome before preparing a replacement."
                : "This session already has a draft. Continue or explicitly discard that exact draft first.",
          });
          return existing.data;
        }
      }
      return await this.#execute(
        owner,
        {
          kind: "create",
          request: {
            body: {
              client_action_id: crypto.randomUUID(),
              session_id: sessionId,
              expected_session_revision: session.revision,
              ref: exact,
              appointment: selected,
            },
          },
        },
        generation,
      );
    } catch (error) {
      this.#failure(owner, error);
    } finally {
      this.#locks.delete(owner.contextId!);
      this.#emit();
    }
  }
  async update(
    draft: Schema<"BookingDraft">,
    intent: Schema<"BookingDraftUpdate">["intent"],
    viewId: string,
    appointment?: Schema<"AppointmentSelection">,
  ) {
    const owner = this.owner.capture();
    if (this.#blocked(owner)) return;
    const current = structuredClone(draft),
      selected = appointment ? structuredClone(appointment) : undefined;
    if (!this.#view.generation) return;
    this.#locks.add(owner.contextId!);
    this.#approval = null;
    try {
      return await this.#execute(
        owner,
        {
          kind: "update",
          request: {
            path: { draft_id: current.draft_id },
            body: {
              client_action_id: crypto.randomUUID(),
              expected_revision: current.revision,
              intent,
              ...(selected ? { appointment: selected } : {}),
            },
          },
        },
        this.#view.generation,
        intent === "edit" || intent === "refresh_review"
          ? {
              viewId,
              version: this.#viewVersions.get(viewId) ?? 0,
              ref: current.ref,
            }
          : undefined,
      );
    } catch (error) {
      this.#failure(owner, error);
    } finally {
      this.#locks.delete(owner.contextId!);
      this.#emit();
    }
  }
  async saveEnquiry(
    sessionId: string,
    values: Schema<"LeadValues">,
    current: Schema<"LeadRecord"> | null,
    generation: string,
  ) {
    const owner = this.owner.capture();
    if (this.#blocked(owner) || !isLocator(generation)) return;
    this.#locks.add(owner.contextId!);
    this.#approval = null;
    const copied = structuredClone(values),
      action = crypto.randomUUID();
    const command: Command = current
      ? {
          kind: "lead-update",
          request: {
            path: { lead_id: current.lead_id },
            body: {
              client_action_id: action,
              expected_revision: current.revision,
              session_id: sessionId,
              intent: "correct_local_enquiry",
              values: copied,
            },
          },
        }
      : {
          kind: "lead-create",
          request: {
            body: {
              client_action_id: action,
              session_id: sessionId,
              intent: "save_local_enquiry",
              values: copied,
            },
          },
        };
    try {
      await this.#execute(owner, command, generation);
    } catch (error) {
      this.#failure(owner, error);
    } finally {
      this.#locks.delete(owner.contextId!);
      this.#emit();
    }
  }
  async #execute(
    owner: OwnerSnapshot,
    command: Command,
    generation: string,
    approval?: { viewId: string; version: number; ref: InventoryRef },
  ) {
    const context = owner.contextId!,
      pending = this.#pending.get(context) ?? {
        command,
        generation,
        uncertain: false,
      };
    this.#pending.set(context, pending);
    this.#publish(owner, {
      phase: "pending",
      error: null,
      notice: command.kind.startsWith("lead")
        ? "Saving the explicitly supplied enquiry details locally…"
        : "Updating this exact draft; no viewing is reserved…",
    });
    const sequence = ++this.#sequence;
    if (command.kind === "create" || command.kind === "update") {
      const response =
        command.kind === "create"
          ? await this.api.mutate("create_booking_draft", command.request)
          : await this.api.mutate("update_booking_draft", command.request);
      this.owner.assertCurrent(owner);
      if (response.meta.store_generation !== generation)
        throw new ClientFailure("invalid-response", "reconcile-original");
      // Exact replay returns the current draft; it never renews review approval.
      this.#pending.delete(context);
      const draft = this.#acceptDraft(owner, response, sequence);
      if (
        approval &&
        approval.version === (this.#viewVersions.get(approval.viewId) ?? 0) &&
        !pending.uncertain &&
        draft.state === "reviewable" &&
        draft.review?.state === "valid" &&
        refKey(draft.ref) === refKey(approval.ref)
      )
        this.#approval = {
          viewId: approval.viewId,
          owner,
          review: structuredClone(draft.review),
        };
      this.#publish(owner, {
        phase: "idle",
        notice:
          draft.state === "discarded"
            ? "The uncommitted draft was discarded. No booking was cancelled."
            : draft.state === "suspended"
              ? "The draft is suspended. Resume with a fresh review."
              : pending.uncertain
                ? "The original draft command is resolved. Check the current car and refresh its review before confirming."
                : "Draft details are ready to inspect. No slot is held.",
      });
      this.changed();
      return draft;
    }
    const response =
      command.kind === "lead-create"
        ? await this.api.mutate("save_local_enquiry", command.request)
        : await this.api.mutate("update_local_enquiry", command.request);
    this.owner.assertCurrent(owner);
    if (response.meta.store_generation !== generation)
      throw new ClientFailure("invalid-response", "reconcile-original");
    this.#pending.delete(context);
    this.#publish(owner, {
      phase: "idle",
      enquiryChanges: this.#view.enquiryChanges + 1,
      notice:
        "The original enquiry save is confirmed locally. Current values will be re-read; refresh the viewing review before confirming. Nothing was sent to a dealer.",
    });
    this.changed();
  }
  async reconcileCommand() {
    const owner = this.owner.capture(),
      context = owner.contextId,
      pending = context ? this.#pending.get(context) : undefined;
    if (!context || !pending || this.#locks.has(context)) return;
    pending.uncertain = true;
    this.#locks.add(context);
    this.#publish(owner, {
      phase: "reading",
      notice: "Checking the original draft or enquiry command…",
      error: null,
    });
    try {
      const observed = await this.api.read("get_current_local_enquiry", {});
      this.owner.assertCurrent(owner);
      if (observed.meta.store_generation !== pending.generation) {
        this.#publish(owner, {
          phase: "blocked",
          notice:
            "The local store changed. Operator reconciliation is required; the original command has not been replayed or replaced.",
        });
        return;
      }
      await this.#execute(owner, pending.command, pending.generation);
    } catch (error) {
      this.#failure(owner, error);
    } finally {
      this.#locks.delete(context);
      this.#emit();
    }
  }
  async confirm(
    review: Schema<"BookingReview">,
    viewId: string,
    located: (locator: OperationLocator) => void,
  ) {
    if (!this.canConfirm(review, viewId)) return;
    const owner = this.owner.capture(),
      copy = structuredClone(review),
      context = owner.contextId!;
    const locator = {
      key: copy.operation_key,
      generation: copy.store_generation,
      draftId: copy.draft_id,
    };
    this.#locks.add(context);
    this.#approval = null;
    this.#operations.set(context, { locator, terminal: false });
    this.#publish(owner, {
      phase: "pending",
      operation: locator,
      operationTerminal: false,
      notice:
        "Submitting this exact simulated viewing. Leaving does not cancel it.",
      error: null,
    });
    try {
      // The caller writes the original recovery URL before dispatching this POST.
      located(locator);
      const response = await this.api.mutate("confirm_booking_draft", {
        path: { draft_id: copy.draft_id },
        body: {
          review_id: copy.review_id,
          expected_draft_revision: copy.draft_revision,
          operation_key: copy.operation_key,
          rules_version: copy.rules_version,
          store_generation: copy.store_generation,
          confirmation: "confirm_simulated_viewing",
        },
      });
      this.owner.assertCurrent(owner);
      this.#acceptOperation(owner, locator, response.data);
      this.changed();
    } catch {
      if (!this.#operations.get(context)?.terminal)
        this.#publish(owner, {
          phase: "unknown",
          notice:
            "The original confirmation outcome is unknown. Read its original status; no replacement review or confirmation has been created.",
        });
    } finally {
      this.#locks.delete(context);
      this.#emit();
    }
  }
  #acceptOperation(
    owner: OwnerSnapshot,
    locator: OperationLocator,
    result: ResponseOf<"get_operation">["data"],
  ) {
    this.owner.assertCurrent(owner);
    if (result.operation_key !== locator.key)
      throw new ClientFailure("invalid-response", "read");
    const terminal =
      result.state === "succeeded" || result.state === "rejected";
    if (terminal && result.original_store_generation !== locator.generation)
      throw new ClientFailure("invalid-response", "read");
    const prior = this.#operations.get(owner.contextId!);
    const resultKey = `${locator.generation}:${locator.key}`;
    if (
      !terminal &&
      (this.#terminalResults.has(resultKey) ||
        (prior?.locator.key === locator.key && prior.terminal))
    ) {
      const retained = this.#terminalResults.get(resultKey);
      if (retained) return retained;
      throw new ClientFailure("superseded", "read");
    }
    if (terminal) this.#terminalResults.set(resultKey, structuredClone(result));
    // Reading a different historical receipt must not replace the active unresolved blocker.
    if (prior && !prior.terminal && prior.locator.key !== locator.key)
      return result;
    // A delayed not-observed reply cannot undo an already retained terminal result.
    const resolved =
      terminal ||
      (prior?.locator.key === locator.key && prior.terminal === true);
    this.#operations.set(owner.contextId!, { locator, terminal: resolved });
    this.#publish(owner, {
      operation: locator,
      operationTerminal: resolved,
      phase: resolved ? "idle" : "unknown",
      notice: resolved
        ? "The original operation has an authoritative terminal result."
        : "The original outcome remains unknown. No replacement action is enabled.",
    });
    return result;
  }
  async readOperation(
    locator: OperationLocator,
    owner: OwnerSnapshot,
    signal?: AbortSignal,
  ) {
    this.owner.assertCurrent(owner);
    const prior = this.#operations.get(owner.contextId!);
    if (!prior || prior.terminal || prior.locator.key === locator.key) {
      const terminal =
        prior?.locator.key === locator.key && prior?.terminal === true;
      this.#operations.set(owner.contextId!, { locator, terminal });
      this.#publish(owner, { operation: locator, operationTerminal: terminal });
    }
    const response = await this.api.read("get_operation", {
      path: { operation_key: locator.key },
      query: { submitted_store_generation: locator.generation },
      signal,
    });
    const data = this.#acceptOperation(owner, locator, response.data);
    return { ...response, data };
  }
  #failure(owner: OwnerSnapshot, error: unknown) {
    const pending = owner.contextId
      ? this.#pending.get(owner.contextId)
      : undefined;
    const rejected =
      this.owner.isCurrent(owner) &&
      error instanceof ClientFailure &&
      (error.kind === "invalid-request" ||
        (error.kind === "api" &&
          !!error.detail &&
          [400, 401, 403, 404, 409, 422].includes(error.status ?? 0)));
    if (pending && !pending.uncertain && rejected)
      this.#pending.delete(owner.contextId!);
    else if (pending) pending.uncertain = true;
    const unknown = !!owner.contextId && this.#pending.has(owner.contextId);
    this.#publish(owner, {
      phase: unknown ? "unknown" : "error",
      error: error instanceof ClientFailure ? error : null,
      notice: unknown
        ? "The original draft or enquiry command has an unknown outcome. Retry only that retained command before making another change."
        : "The service did not confirm this change. Your entered fields are retained. Read the current draft and correct the indicated fields before another explicit action.",
    });
  }
  dispose() {
    this.#unsubscribe();
    this.#pending.clear();
    this.#operations.clear();
    this.#locks.clear();
    this.#versions.clear();
    this.#viewVersions.clear();
    this.#terminalResults.clear();
    this.#retiredGenerations.clear();
    this.#approval = null;
    this.#listeners.clear();
    this.#view = blank();
  }
}
