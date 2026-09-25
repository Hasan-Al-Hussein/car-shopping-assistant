import { afterEach, describe, expect, test, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { OperationRoute } from "../../src/app/OwnedRoutes";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import { encodeRef, listingPath, operationPath } from "../../src/app/routes";
import { NewViewingRoute } from "../../src/features/viewings/ViewingRoutes";
import type { ResponseOf, Schema } from "../../src/shared/api/contracts";
import { deferred, scriptedFetch, type ReplyStep } from "../harness/fixtures";
import {
  apiError,
  identity,
  listingDetail,
  meta,
  schemaFixture,
} from "./apiFixtures";
import {
  viewingDraft,
  viewingEnvelope,
  viewingGeneration,
  viewingSuccess,
  viewingUnknown,
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

function setup(script: readonly ReplyStep[]) {
  const transport = vi.fn(scriptedFetch(script));
  const service = new BrowserServices(transport);
  services.push(service);
  // Identity lifecycle is covered elsewhere; retain the real typed API boundary.
  vi.spyOn(service, "start").mockImplementation(() => {});
  service.owner.accept(0, identity());
  const write = vi.spyOn(service.api, "mutate");
  return { service, transport, write };
}

function operationStep(data: ResponseOf<"get_operation">["data"]): ReplyStep {
  return {
    method: "GET",
    path: `/api/v1/operations/${data.operation_key}`,
    contextId: identity().context_id,
    body: viewingEnvelope(data),
  };
}

function exactDetail(): Schema<"ListingDetail"> {
  const detail = listingDetail();
  detail.listing.ref = structuredClone(viewingDraft().ref);
  return detail;
}

function detailPath() {
  const ref = viewingDraft().ref;
  return `/api/v1/listings/${ref.namespace}/${ref.snapshot_id}/${ref.source_id}`;
}

function detailStep(detail = exactDetail()): ReplyStep {
  const body: ResponseOf<"get_listing"> = {
    meta: { ...meta(), inventory_snapshot_id: detail.listing.ref.snapshot_id },
    data: schemaFixture("ListingDetail", detail),
  };
  return { method: "GET", path: detailPath(), body };
}

function show(service: BrowserServices, path: string) {
  render(
    <ServicesProvider services={service}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/operations/:operationKey"
            element={<OperationRoute />}
          />
          <Route
            path="/viewings/new/:listingRef"
            element={<NewViewingRoute openIdentity={() => {}} />}
          />
        </Routes>
      </MemoryRouter>
    </ServicesProvider>,
  );
}

function expectOriginalReads(
  transport: ReturnType<typeof setup>["transport"],
  operationKey: string,
) {
  const reads = transport.mock.calls.filter(([input]) =>
    String(input).includes("/api/v1/operations/"),
  );
  expect(reads).toHaveLength(2);
  for (const [input, init] of reads) {
    const url = new URL(String(input), "http://fixture.invalid");
    expect(url.pathname).toBe(`/api/v1/operations/${operationKey}`);
    expect([...url.searchParams]).toEqual([
      ["submitted_store_generation", viewingGeneration],
    ]);
    expect(init?.method).toBe("GET");
  }
}

const exportCases = [
  ["pending", "Not yet up to date", "CSV_AUDIT_PENDING"],
  ["failed", "Export needs attention", "CSV_EXPORT_FAILED"],
] as const;
const rejectionCodes = ["REVIEW_STALE", "CAPACITY_UNAVAILABLE"] as const;
const eligibilityCases = [
  ["unavailable", "This listing is not eligible for simulated viewing."],
  ["configuration_missing", "Viewing eligibility has not been configured."],
] as const;

describe("authoritative route states through synthetic typed HTTP; not backend or browser proof", () => {
  test.each(["CSV failure", "read failure"] as const)(
    "status refresh retains its focusable control and prevents duplicate reads through %s",
    async (settlement) => {
      const pending = schemaFixture("OperationSucceeded", {
        ...viewingSuccess(),
        csv: {
          ...viewingSuccess().csv,
          state: "pending",
          code: "CSV_AUDIT_PENDING",
          canonical_version: 3,
          exported_version: 1,
        },
      });
      const failed = schemaFixture("OperationSucceeded", {
        ...pending,
        csv: { ...pending.csv, state: "failed", code: "CSV_EXPORT_FAILED" },
      });
      const gate = deferred<void>();
      const { service, transport, write } = setup([
        operationStep(pending),
        detailStep(),
        {
          ...operationStep(failed),
          gate: gate.promise,
          loseResponse: settlement === "read failure",
        },
        ...(settlement === "read failure"
          ? [{ ...operationStep(failed), loseResponse: true }]
          : []),
        operationStep(failed),
      ]);
      show(service, operationPath(pending.operation_key, viewingGeneration));
      await flush();
      const button = screen.getByRole("button", {
        name: "Check viewing status",
      });
      button.focus();
      // Two activations before a render must not cancel and restart this read.
      act(() => {
        fireEvent.click(button);
        fireEvent.click(button);
      });
      await flush();
      expect(button).not.toBeDisabled();
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button).toHaveAttribute("aria-busy", "true");
      expect(button).toHaveFocus();
      expect(screen.getByRole("status")).toHaveTextContent(
        "Checking the original viewing status…",
      );
      expect(screen.getByText(/^Not yet up to date\./)).toBeInTheDocument();
      expect(transport).toHaveBeenCalledTimes(3);
      fireEvent.click(button);
      await flush();
      expect(transport).toHaveBeenCalledTimes(3);
      gate.resolve();
      await flush();
      if (settlement === "read failure") {
        // ApiClient allows two read attempts with a 250ms retry delay.
        expect(button).toHaveAttribute("aria-busy", "true");
        expect(transport).toHaveBeenCalledTimes(3);
        await act(async () => {
          await vi.advanceTimersByTimeAsync(250);
        });
        await flush();
        expect(transport).toHaveBeenCalledTimes(4);
      }
      expect(screen.getByRole("button", { name: "Check viewing status" })).toBe(
        button,
      );
      expect(button).toHaveFocus();
      expect(button).toHaveAttribute("aria-busy", "false");
      expect(button).toHaveAttribute("aria-disabled", "false");
      expect(screen.getByText("Simulated action saved.")).toBeInTheDocument();
      if (settlement === "read failure")
        expect(
          screen.getByText(/last confirmed outcome remains/),
        ).toBeInTheDocument();
      else
        expect(
          screen.getByText(/^Export needs attention\./),
        ).toBeInTheDocument();
      fireEvent.click(button);
      await flush();
      expect(transport).toHaveBeenCalledTimes(
        settlement === "read failure" ? 5 : 4,
      );
      expect(screen.getByText(/^Export needs attention\./)).toBeInTheDocument();
      expect(write).not.toHaveBeenCalled();
    },
  );

  test.each(exportCases)(
    "saved booking and enquiry remain saved while authoritative CSV is %s",
    async (state, label, code) => {
      const saved = viewingSuccess();
      const outcome = schemaFixture("OperationSucceeded", {
        ...saved,
        csv: {
          state,
          code,
          store_generation: viewingGeneration,
          observed_at: "2026-09-24T04:00:01Z",
          canonical_version: 3,
          exported_version: 1,
          version_scope: "global_projection",
        },
      });
      const current = schemaFixture("OperationSucceeded", {
        ...outcome,
        csv: {
          state: "current",
          store_generation: viewingGeneration,
          observed_at: "2026-09-24T04:00:02Z",
          canonical_version: 3,
          exported_version: 3,
          version_scope: "global_projection",
        },
      });
      const { service, transport, write } = setup([
        operationStep(outcome),
        detailStep(),
        operationStep(current),
      ]);
      show(service, operationPath(outcome.operation_key, viewingGeneration));
      await flush();
      expect(
        screen.getByRole("heading", { name: "Simulated action saved." }),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Enquiry saved with this viewing"),
      ).toBeInTheDocument();
      expect(screen.getByText(new RegExp(`^${label}\\.`))).toBeInTheDocument();
      expect(
        screen.getByText(
          /Your simulated viewing and enquiry are saved\. The CSV export is not up to date\./,
        ),
      ).toBeInTheDocument();
      expect(
        screen.getByText("No external delivery is claimed."),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/latest status check failed/),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(
          new RegExp(
            `Enquiry reference ${saved.lead.lead_id}.*accepted revision ${saved.lead.revision}`,
          ),
        ),
      ).toBeInTheDocument();
      const starts = document.querySelector("time[datetime]");
      expect(starts).toHaveAttribute(
        "datetime",
        saved.booking.review.starts_at_utc,
      );
      expect(transport).toHaveBeenCalledTimes(2);

      fireEvent.click(
        screen.getByRole("button", { name: "Check viewing status" }),
      );
      await flush();
      expect(
        screen.getByRole("heading", { name: "Simulated action saved." }),
      ).toBeInTheDocument();
      expect(screen.getByText(/^Up to date\./)).toBeInTheDocument();
      expect(
        screen.getByText(
          new RegExp(
            `Enquiry reference ${saved.lead.lead_id}.*accepted revision ${saved.lead.revision}`,
          ),
        ),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/The CSV export is not up to date\./),
      ).not.toBeInTheDocument();
      expect(transport).toHaveBeenCalledTimes(3);
      expectOriginalReads(transport, outcome.operation_key);
      expect(write).not.toHaveBeenCalled();
    },
  );

  test.each(rejectionCodes)(
    "%s stays a retained rejection after an absent status response and grants no replacement action",
    async (rejectionCode) => {
      const saved = viewingSuccess();
      const rejected = schemaFixture("OperationRejected", {
        state: "rejected",
        operation_key: saved.operation_key,
        review_id: saved.review_id,
        original_store_generation: saved.original_store_generation,
        terminal_at: saved.terminal_at,
        replay_valid_until: saved.replay_valid_until,
        rejection_code: rejectionCode,
        booking: { state: "not_created" },
        lead: { state: "not_requested" },
        csv: { state: "not_requested" },
      });
      const { service, transport, write } = setup([
        operationStep(rejected),
        operationStep(schemaFixture("OperationNotObserved", viewingUnknown())),
      ]);
      show(service, operationPath(rejected.operation_key, viewingGeneration));
      await flush();
      expect(
        screen.getByRole("heading", { name: "Action rejected." }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          `Retained rejection: ${rejectionCode.replaceAll("_", " ")}`,
        ),
      ).toBeInTheDocument();
      fireEvent.click(
        screen.getByRole("button", { name: "Check viewing status" }),
      );
      await flush();
      expect(
        screen.getByRole("heading", { name: "Action rejected." }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          `Retained rejection: ${rejectionCode.replaceAll("_", " ")}`,
        ),
      ).toBeInTheDocument();
      expect(screen.queryByText("Outcome unknown.")).not.toBeInTheDocument();
      expect(
        screen.queryByText("Enquiry saved with this viewing"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("CSV export status")).not.toBeInTheDocument();
      expect(
        screen.getByText(
          /This operation did not create a booking or request a local enquiry\./,
        ),
      ).toBeInTheDocument();
      expect(screen.getAllByRole("button")).toEqual([
        screen.getByRole("button", { name: "Check viewing status" }),
      ]);
      expect(transport).toHaveBeenCalledTimes(2);
      expectOriginalReads(transport, rejected.operation_key);
      expect(write).not.toHaveBeenCalled();
    },
  );

  test("not observed is not noncommit, even with an original-retry hint; the page only reads the same operation", async () => {
    const absent = schemaFixture("OperationNotObserved", {
      ...viewingUnknown(),
      recovery: "retry_original_operation",
    });
    const { service, transport, write } = setup([
      operationStep(absent),
      operationStep(absent),
    ]);
    show(service, operationPath(absent.operation_key, viewingGeneration));
    await flush();
    expect(
      screen.getByRole("heading", { name: "Outcome unknown." }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /A timeout or absent result does not establish that nothing was saved\./,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Don’t submit a replacement for this viewing while the result is unknown\./,
      ),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Check viewing status" }),
    );
    await flush();
    expect(
      screen.getByRole("heading", { name: "Outcome unknown." }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Simulated action saved."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Action rejected.")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/This operation did not create a booking/),
    ).not.toBeInTheDocument();
    expect(screen.getAllByRole("button")).toEqual([
      screen.getByRole("button", { name: "Check viewing status" }),
    ]);
    expect(transport).toHaveBeenCalledTimes(2);
    expectOriginalReads(transport, absent.operation_key);
    expect(write).not.toHaveBeenCalled();
  });

  test.each(eligibilityCases)(
    "%s entry retains the exact car and offers no slot, session or draft action",
    async (eligibility, reason) => {
      const detail = exactDetail();
      detail.eligibility = eligibility;
      detail.eligibility_reason = reason;
      const { service, transport, write } = setup([detailStep(detail)]);
      show(service, `/viewings/new/${encodeRef(detail.listing.ref)}`);
      await flush();
      expect(
        screen.getByRole("heading", {
          name: "Viewing is unavailable for this car.",
        }),
      ).toBeInTheDocument();
      expect(screen.getByText(reason)).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Return to this car →" }),
      ).toHaveAttribute("href", listingPath(detail.listing.ref));
      expect(
        screen.queryByRole("region", { name: "Viewing times" }),
      ).not.toBeInTheDocument();
      expect(screen.queryByRole("radio")).not.toBeInTheDocument();
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
      expect(transport).toHaveBeenCalledTimes(1);
      expect(String(transport.mock.calls[0]?.[0])).toBe(detailPath());
      expect(write).not.toHaveBeenCalled();
    },
  );

  test("an unmapped eligible car's typed 409 preserves its reference and permits only an explicit detail read", async () => {
    const denied = schemaFixture("ErrorEnvelope", {
      error: { ...apiError("ELIGIBILITY_UNAVAILABLE").error, fields: [] },
    });
    const step: ReplyStep = {
      method: "GET",
      path: detailPath(),
      status: 409,
      body: denied,
    };
    const { service, transport, write } = setup([step, step]);
    show(service, `/viewings/new/${encodeRef(viewingDraft().ref)}`);
    await flush();
    expect(
      screen.getByRole("heading", { name: "Unable to load this view" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Return to this car →" }),
    ).toHaveAttribute("href", listingPath(viewingDraft().ref));
    expect(
      screen.queryByRole("region", { name: "Viewing times" }),
    ).not.toBeInTheDocument();
    expect(transport).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    await flush();
    expect(
      screen.getByRole("heading", { name: "Unable to load this view" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toEqual([
      screen.getByRole("button", { name: "Check again" }),
    ]);
    expect(transport).toHaveBeenCalledTimes(2);
    for (const [input, init] of transport.mock.calls) {
      expect(String(input)).toBe(detailPath());
      expect(init?.method).toBe("GET");
    }
    expect(write).not.toHaveBeenCalled();
  });
});
