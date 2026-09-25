import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import { listingPath } from "../../src/app/routes";
import { ReviewFacts } from "../../src/features/viewings/ViewingFacts";
import { listingDetail, meta, schemaFixture } from "./apiFixtures";
import { viewingDraft } from "./viewingFixtures";

const services: BrowserServices[] = [];
afterEach(() => {
  cleanup();
  services.splice(0).forEach((service) => service.dispose());
});

const flush = () =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });

const evidence = (row: number, raw: string) => [
  schemaFixture("SourceLocator", {
    evidence_id: `90000000-0000-4000-8000-${String(row).padStart(12, "0")}`,
    workbook_sha256: "b".repeat(64),
    sheet: "synthetic-review-identity",
    cell: `A${row}`,
    raw_text: raw,
    span_start: 0,
    span_end: raw.length,
    extraction_version: "synthetic-test-1",
    category: "structured_source",
    review_status: "not_reviewed",
    verification: "source_claim",
  }),
];

function setup() {
  const service = new BrowserServices();
  services.push(service);
  vi.spyOn(service, "start").mockImplementation(() => {});
  const read = vi.spyOn(service.api, "read");
  const write = vi.spyOn(service.api, "mutate");
  const review = viewingDraft().review!;
  const key = service.queries.publicRead(
    "get_listing",
    { path: review.ref },
    review.ref.snapshot_id,
  ).queryKey;
  const detail = listingDetail();
  detail.listing.ref = structuredClone(review.ref);
  detail.listing.make = {
    status: "known",
    qualifier: "exact",
    value: "Mercedes-Benz",
    evidence: evidence(1, "Mercedes-Benz"),
  };
  detail.listing.model = {
    status: "known",
    qualifier: "exact",
    value: "E-Class",
    evidence: evidence(2, "E-Class"),
  };
  detail.listing.year = {
    status: "known",
    qualifier: "exact",
    value: 2019,
    evidence: evidence(3, "2019"),
  };
  const show = () =>
    render(
      <ServicesProvider services={service}>
        <MemoryRouter>
          <ReviewFacts review={review} />
        </MemoryRouter>
      </ServicesProvider>,
    );
  const cache = () =>
    service.queries.client.setQueryData(key, {
      meta: { ...meta(), inventory_snapshot_id: review.ref.snapshot_id },
      data: schemaFixture("ListingDetail", detail),
    });
  return { service, read, write, review, detail, show, cache };
}

describe("Review car identity from the existing exact-listing cache", () => {
  test("names the loaded car/year, retaining the exact link and disclosed source ref", async () => {
    const { read, write, review, show, cache } = setup();
    cache();
    show();
    await flush();
    expect(
      screen.getByRole("link", { name: "Mercedes-Benz E-Class · 2019" }),
    ).toHaveAttribute("href", listingPath(review.ref));
    expect(
      screen.getByText(`Listing ${review.ref.source_id}`),
    ).toBeInTheDocument();
    const reference = screen.getByText(
      `${review.ref.namespace} · snapshot ${review.ref.snapshot_id}`,
    );
    expect(reference.closest("details")).not.toHaveAttribute("open");
    expect(read).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
  });

  test("empty cache stays honest, then updates from the existing vehicle read without fetching", async () => {
    const { read, write, review, show, cache } = setup();
    show();
    await flush();
    expect(screen.getByRole("link", { name: "Selected car" })).toHaveAttribute(
      "href",
      listingPath(review.ref),
    );
    await act(async () => {
      cache();
    });
    await flush();
    expect(
      screen.getByRole("link", { name: "Mercedes-Benz E-Class · 2019" }),
    ).toBeInTheDocument();
    expect(read).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
  });

  test("a different complete ref cannot label this review even if cached under its key", async () => {
    const { read, detail, show, cache } = setup();
    detail.listing.ref.source_id = "999";
    cache();
    show();
    await flush();
    expect(
      screen.getByRole("link", { name: "Selected car" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Mercedes-Benz/)).not.toBeInTheDocument();
    expect(read).not.toHaveBeenCalled();
  });

  test("unknown year is not invented", async () => {
    const { detail, show, cache } = setup();
    detail.listing.year = { status: "unknown", reason: "not_stated" };
    cache();
    show();
    await flush();
    expect(
      screen.getByRole("link", { name: "Mercedes-Benz E-Class" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/2019/)).not.toBeInTheDocument();
  });
});
