import { afterEach, describe, expect, test, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import { OperationRoute } from "../../src/app/OwnedRoutes";
import {
  DraftRoute,
  NewViewingRoute,
  reviewedLeadMatches,
} from "../../src/features/viewings/ViewingRoutes";
import {
  EnquiryForm,
  enquiryValues,
} from "../../src/features/viewings/EnquiryForm";
import { encodeRef } from "../../src/app/routes";
import type { ResponseOf, Schema } from "../../src/shared/api/contracts";
import { deferred } from "../harness/fixtures";
import { identity, listingDetail, meta } from "./apiFixtures";
import {
  viewingDraft,
  viewingEnvelope,
  viewingGeneration,
  viewingLead,
  viewingSuccess,
  viewingUnknown,
  viewingValues,
} from "./viewingFixtures";

const services: BrowserServices[] = [];
afterEach(() => {
  cleanup();
  services.splice(0).forEach((service) => service.dispose());
});
const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 20; i++) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1);
  });
};
function setup() {
  const service = new BrowserServices();
  services.push(service);
  vi.spyOn(service, "start").mockImplementation(() => {});
  service.owner.accept(0, identity());
  const read = vi
    .spyOn(service.api, "read")
    .mockImplementation(async (operation) => {
      if (operation === "get_booking_draft")
        return viewingEnvelope(viewingDraft());
      if (operation === "get_current_local_enquiry")
        return viewingEnvelope({ state: "not_created" as const });
      if (operation === "get_operation")
        return viewingEnvelope(viewingUnknown());
      if (operation === "get_listing")
        return { meta: meta(), data: listingDetail() };
      throw Error(`UNSCRIPTED_OPERATION:${operation}`);
    });
  const write = vi
    .spyOn(service.api, "mutate")
    .mockResolvedValue(viewingEnvelope(viewingDraft()));
  return { service, read, write };
}
function Address() {
  const location = useLocation();
  return (
    <output aria-label="Current address">
      {location.pathname}
      {location.search}
    </output>
  );
}
function DraftHarness({
  service,
  path = `/viewings/drafts/${viewingDraft().draft_id}/review`,
}: {
  service: BrowserServices;
  path?: string;
}) {
  return (
    <ServicesProvider services={service}>
      <MemoryRouter initialEntries={[path]}>
        <Address />
        <Routes>
          <Route path="/viewings/drafts/:draftId" element={<DraftRoute />} />
          <Route
            path="/viewings/drafts/:draftId/review"
            element={<DraftRoute />}
          />
          <Route
            path="/operations/:operationKey"
            element={<OperationRoute />}
          />
          <Route
            path="/cars"
            element={
              <Link to={`/viewings/drafts/${viewingDraft().draft_id}/review`}>
                Return to original draft
              </Link>
            }
          />
        </Routes>
      </MemoryRouter>
    </ServicesProvider>
  );
}

describe("U2 real components with synthetic services; browser proof remains separate", () => {
  test("discard keeps its terminal view mounted while invalidated reads settle", async () => {
    const { service, read, write } = setup();
    const discarded = {
      ...viewingDraft(2),
      state: "discarded" as const,
      review: null,
    };
    const draftRead = deferred<ResponseOf<"get_booking_draft">>();
    const enquiryRead = deferred<ResponseOf<"get_current_local_enquiry">>();
    const signals: AbortSignal[] = [];
    render(<DraftHarness service={service} />);
    await flush();
    read.mockImplementation(async (operation, request) => {
      if (operation === "get_booking_draft") {
        if (request.signal) signals.push(request.signal);
        return draftRead.promise;
      }
      if (operation === "get_current_local_enquiry") {
        if (request.signal) signals.push(request.signal);
        return enquiryRead.promise;
      }
      throw Error(`UNSCRIPTED_OPERATION:${operation}`);
    });
    write.mockResolvedValueOnce(viewingEnvelope(discarded));
    fireEvent.click(
      screen.getByRole("button", { name: "Discard uncommitted draft" }),
    );
    await flush();
    expect(
      screen.getByRole("heading", {
        name: "This uncommitted draft was discarded.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm simulated viewing" }),
    ).not.toBeInTheDocument();
    expect(signals).toHaveLength(2);
    expect(signals.every((signal) => !signal.aborted)).toBe(true);
    expect(write).toHaveBeenCalledTimes(1);
    expect(write.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({
        body: expect.objectContaining({ intent: "discard" }),
      }),
    );
    draftRead.resolve(viewingEnvelope(discarded));
    enquiryRead.resolve(viewingEnvelope({ state: "not_created" as const }));
    await flush();
    expect(service.viewings.getSnapshot().draft?.state).toBe("discarded");
  });

  test("direct review is read-only; leaving a fresh review and returning requires fresh approval", async () => {
    const { service, write } = setup();
    render(<DraftHarness service={service} />);
    await flush();
    expect(
      screen.getByRole("button", { name: "Confirm simulated viewing" }),
    ).toBeDisabled();
    expect(write).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh viewing review" }),
    );
    await flush();
    expect(
      screen.getByRole("button", { name: "Confirm simulated viewing" }),
    ).toBeEnabled();
    fireEvent.click(screen.getByRole("link", { name: /Continue browsing/ }));
    await flush();
    fireEvent.click(
      screen.getByRole("link", { name: "Return to original draft" }),
    );
    await flush();
    expect(
      screen.getByRole("button", { name: "Confirm simulated viewing" }),
    ).toBeDisabled();
    expect(write).toHaveBeenCalledTimes(1);
    expect(write.mock.calls[0]?.[0]).toBe("update_booking_draft");
  });

  test("confirmation replaces route with original generation before POST and status reads never repeat it", async () => {
    const { service, write } = setup();
    render(<DraftHarness service={service} />);
    await flush();
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh viewing review" }),
    );
    await flush();
    const gate = deferred<ResponseOf<"confirm_booking_draft">>();
    write.mockReturnValueOnce(gate.promise);
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm simulated viewing" }),
    );
    await flush();
    expect(screen.getByLabelText("Current address")).toHaveTextContent(
      `/operations/${viewingDraft().review!.operation_key}?submitted_store_generation=${viewingGeneration}`,
    );
    expect(
      write.mock.calls.filter(
        ([operation]) => operation === "confirm_booking_draft",
      ),
    ).toHaveLength(1);
    fireEvent.click(
      screen.getByRole("button", { name: "Check viewing status" }),
    );
    await flush();
    expect(
      write.mock.calls.filter(
        ([operation]) => operation === "confirm_booking_draft",
      ),
    ).toHaveLength(1);
    gate.resolve(viewingEnvelope(viewingUnknown()));
    await flush();
    expect(screen.getByText("Outcome unknown.")).toBeInTheDocument();
  });

  test("an incomplete suspended draft can resume without inventing a viewing time", async () => {
    const { service, read, write } = setup(),
      draft = {
        ...viewingDraft(),
        state: "suspended" as const,
        appointment: null,
        review: null,
        required_fields: ["appointment"],
      };
    read.mockImplementation(async (operation) =>
      operation === "get_booking_draft"
        ? viewingEnvelope(draft)
        : operation === "get_current_local_enquiry"
          ? viewingEnvelope({ state: "not_created" as const })
          : { meta: meta(), data: listingDetail() },
    );
    write.mockResolvedValueOnce(
      viewingEnvelope({
        ...draft,
        state: "needs_details" as const,
        revision: 2,
      }),
    );
    render(
      <DraftHarness
        service={service}
        path={`/viewings/drafts/${draft.draft_id}`}
      />,
    );
    await flush();
    fireEvent.click(
      screen.getByRole("button", { name: "Resume and refresh review" }),
    );
    await flush();
    expect(write.mock.calls[0]).toEqual([
      "update_booking_draft",
      {
        path: { draft_id: draft.draft_id },
        body: {
          client_action_id: expect.any(String),
          expected_revision: 1,
          intent: "refresh_review",
        },
      },
    ]);
    expect(
      screen.getByRole("button", { name: "Check viewing times" }),
    ).toBeInTheDocument();
  });

  test("a failed status refresh preserves known booking, accepted lead and last CSV observation", async () => {
    const { service, read, write } = setup(),
      outcome = viewingSuccess();
    read.mockImplementation(async (operation) =>
      operation === "get_operation"
        ? viewingEnvelope(outcome)
        : { meta: meta(), data: listingDetail() },
    );
    render(
      <DraftHarness
        service={service}
        path={`/operations/${outcome.operation_key}?submitted_store_generation=${viewingGeneration}`}
      />,
    );
    await flush();
    expect(screen.getByText("Simulated action saved.")).toBeInTheDocument();
    read.mockRejectedValueOnce(Error("synthetic offline"));
    fireEvent.click(
      screen.getByRole("button", { name: "Check viewing status" }),
    );
    await flush();
    expect(screen.getByText("Simulated action saved.")).toBeInTheDocument();
    expect(
      screen.getByText("Enquiry saved with this viewing"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/last confirmed outcome remains/),
    ).toBeInTheDocument();
    expect(write).not.toHaveBeenCalled();
  });

  test("eligibility, slot reads and a radio choice never create a draft, enquiry or reservation", async () => {
    const { service, read, write } = setup(),
      draft = viewingDraft(),
      detail = {
        ...listingDetail(),
        eligibility: "simulated_eligible" as const,
      };
    read.mockImplementation(async (operation) =>
      operation === "get_viewing_options"
        ? {
            meta: meta(),
            data: {
              ref: draft.ref,
              state: "available" as const,
              rules_version: "DEMO-POLICY-1",
              eligibility_version: "demo-1",
              calculated_at: "2026-09-24T04:00:00Z",
              no_hold: true as const,
              slots: [
                {
                  starts_at_utc: draft.review!.starts_at_utc,
                  ends_at_utc: draft.review!.ends_at_utc,
                  timezone: "Asia/Dubai" as const,
                },
              ],
            },
          }
        : { meta: meta(), data: detail },
    );
    render(
      <ServicesProvider services={service}>
        <MemoryRouter
          initialEntries={[`/viewings/new/${encodeRef(draft.ref)}`]}
        >
          <Routes>
            <Route
              path="/viewings/new/:listingRef"
              element={<NewViewingRoute openIdentity={() => {}} />}
            />
          </Routes>
        </MemoryRouter>
      </ServicesProvider>,
    );
    await flush();
    expect(write).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Check viewing times" }),
    );
    await flush();
    fireEvent.click(screen.getByRole("radio"));
    await flush();
    expect(
      read.mock.calls.some(
        ([operation]) => operation === "get_viewing_options",
      ),
    ).toBe(true);
    expect(write).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Available simulated intervals/),
    ).toBeInTheDocument();
  });

  test("bad budget retains valid siblings; explicit save uses the exact original lead revision", async () => {
    const { service } = setup(),
      lead = viewingLead(),
      save = vi.spyOn(service.viewings, "saveEnquiry").mockResolvedValue();
    render(
      <ServicesProvider services={service}>
        <MemoryRouter>
          <EnquiryForm
            sessionId={viewingDraft().session_id}
            refValue={viewingDraft().ref}
            current={lead}
            generation={viewingGeneration}
          />
        </MemoryRouter>
      </ServicesProvider>,
    );
    fireEvent.click(
      screen.getByText("Budget, needs and optional contact details"),
    );
    fireEvent.change(
      screen.getByLabelText("What you need from the car (one per line)"),
      { target: { value: "Quiet cabin\nValid retained sibling" } },
    );
    fireEvent.change(screen.getByLabelText("Minimum cash budget (AED)"), {
      target: { value: "40000" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save enquiry details" }),
    );
    await flush();
    expect(save).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByLabelText("What you need from the car (one per line)"),
    ).toHaveValue("Quiet cabin\nValid retained sibling");
    fireEvent.change(screen.getByLabelText("Maximum cash budget (AED)"), {
      target: { value: "50000.25" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save enquiry details" }),
    );
    await flush();
    expect(save).toHaveBeenCalledTimes(1);
    expect(save.mock.calls[0]).toEqual([
      viewingDraft().session_id,
      expect.objectContaining({
        budget: {
          state: "provided",
          value: {
            currency: "AED",
            basis: "cash",
            minimum: 4000000,
            maximum: 5000025,
          },
        },
        requirements: ["Quiet cabin", "Valid retained sibling"],
        email: { state: "declined", value: null },
        phone: { state: "missing", value: null },
      }),
      lead,
      viewingGeneration,
    ]);
  });

  test("an observed lead expiry can be explicitly reloaded as unsaved staging", async () => {
    const { service } = setup(),
      lead = viewingLead(),
      save = vi.spyOn(service.viewings, "saveEnquiry").mockResolvedValue();
    const view = (current: Schema<"LeadRecord"> | null) => (
      <ServicesProvider services={service}>
        <MemoryRouter>
          <EnquiryForm
            sessionId={viewingDraft().session_id}
            refValue={viewingDraft().ref}
            current={current}
            generation={viewingGeneration}
          />
        </MemoryRouter>
      </ServicesProvider>
    );
    const mounted = render(view(lead));
    fireEvent.click(
      screen.getByText("Budget, needs and optional contact details"),
    );
    mounted.rerender(view(null));
    expect(
      screen.getByRole("button", { name: "Save enquiry details" }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Reload saved details" }),
    );
    expect(
      screen.getByRole("button", { name: "Save enquiry details" }),
    ).toBeEnabled();
    expect(save).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Email information (optional)")).toHaveValue(
      "missing",
    );
  });

  test("reviewed existing lead must match identity, revision and store generation exactly", () => {
    const lead = viewingLead(),
      review = {
        ...viewingDraft().review!,
        lead_change: {
          mode: "preserve_existing" as const,
          lead_id: lead.lead_id,
          expected_revision: lead.revision,
        },
      };
    expect(reviewedLeadMatches(review, lead, viewingGeneration)).toBe(true);
    expect(
      reviewedLeadMatches(
        review,
        { ...lead, revision: lead.revision + 1 },
        viewingGeneration,
      ),
    ).toBe(false);
    expect(
      reviewedLeadMatches(
        review,
        { ...lead, lead_id: identity(1).context_id },
        viewingGeneration,
      ),
    ).toBe(false);
    expect(reviewedLeadMatches(review, lead, identity(1).context_id)).toBe(
      false,
    );
    expect(reviewedLeadMatches(review, null, viewingGeneration)).toBe(false);
  });

  test("unchanged foreign-currency budget and multiline need remain intact when another field changes", () => {
    const values = {
      ...viewingValues(),
      budget: {
        state: "provided" as const,
        value: {
          currency: "USD",
          basis: "cash" as const,
          minimum: null,
          maximum: 500000,
        },
      },
      requirements: ["One need\nwith a retained newline"],
    };
    const result = enquiryValues(
      {
        budgetState: "provided",
        minimum: "",
        maximum: "",
        needs: values.requirements.join("\n"),
        emailState: "declined",
        email: "",
        phoneState: "provided",
        phone: "+971 50 000 0000",
      },
      values,
      viewingDraft().ref,
    );
    expect(result.budget).toEqual(values.budget);
    expect(result.requirements).toEqual(values.requirements);
    expect(result.phone).toEqual({
      state: "provided",
      value: "+971 50 000 0000",
    });
  });
});
