import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { ConversationAnswer } from "../../src/features/conversation/ConversationContent";
import { listingPath } from "../../src/app/routes";
import type { Schema } from "../../src/shared/api/contracts";
import { searchResult } from "./apiFixtures";
import {
  conversationResult,
  conversationSession,
} from "./conversationFixtures";

vi.mock("../../src/app/ServicesProvider", () => ({
  useServices: () => ({ queueBrowseRequest: vi.fn() }),
}));

function renderAnswer(result: Schema<"MessageResult">, disabled = false) {
  const context = vi.fn(),
    close = vi.fn();
  render(
    <MemoryRouter>
      <ConversationAnswer
        result={result}
        onContext={context}
        close={close}
        contextDisabled={disabled}
      />
    </MemoryRouter>,
  );
  return { context, close };
}

const legacyText = [
  "The inventory reports 1 supported matches; this page contains 1. Your hard conditions were not relaxed.",
  "Car 1: supplied source claims.",
  "The make is not stated in the supplied evidence.",
  "The model is not stated in the supplied evidence.",
  "The model year is not stated in the supplied evidence.",
  "The cash asking price is not stated in the supplied evidence.",
  "Static source matches do not verify live stock, inspection or finance approval.",
].join("\n");

test.each([true, false])(
  "clarification appears once when already in prose: %s",
  (inProse) => {
    const question = "Which currency should I use?";
    const result = conversationResult();
    result.text = inProse ? question : "I need one detail to search.";
    result.pending_intent = {
      kind: "clarification",
      intent_id: "90000000-0000-4000-8000-000000000001",
      created_revision: 1,
      purpose: "search_criteria",
      targets: ["budget"],
      question,
    };
    renderAnswer(result);
    expect(
      screen.getAllByText(new RegExp(question.replace("?", "\\?"))),
    ).toHaveLength(1);
  },
);

const currentText = [
  "Found 1 matching car in the supplied listings.",
  "",
  "1. Make: not stated. Model: not stated. Year: not stated.",
  "   Price: not stated.",
  "",
  "Confirm current availability and condition with the seller.",
].join("\n");

function resultWithSearch(text: string): Schema<"MessageResult"> {
  return { ...conversationResult(), text, search: searchResult().data };
}

const evidence: Schema<"SourceLocator">[] = [
  {
    category: "structured_source",
    cell: "A1",
    evidence_id: "90000000-0000-4000-8000-000000000001",
    extraction_version: "synthetic-test",
    raw_text: "Synthetic claim",
    review_status: "not_reviewed",
    sheet: "Synthetic",
    span_start: 0,
    span_end: 15,
    verification: "source_claim",
    workbook_sha256: "a".repeat(64),
  },
];
function knownText(value: string): Schema<"ListingSummary">["make"] {
  return { status: "known", value, qualifier: "exact", evidence };
}
function orderedSearch() {
  const search = searchResult().data;
  const base = search.items[0]!;
  search.items = ["first", "second", "third"].map((sourceId, index) => ({
    ...base,
    ref: { ...base.ref, source_id: sourceId },
    title: `Synthetic source ${sourceId}`,
    make: knownText("Nissan"),
    model: knownText(["Patrol", "X-Trail", "Altima"][index]!),
    trim: knownText("SV"),
    year: {
      status: "known" as const,
      value: 2021 + index,
      qualifier: "exact" as const,
      evidence,
    },
  }));
  search.items[0]!.cash_price = {
    status: "known",
    value: { currency: "AED", minor_units: 8500000, basis: "cash" },
    qualifier: "approximate",
    evidence,
  };
  search.items[1]!.cash_price = { status: "unknown", reason: "not_stated" };
  search.items[2]!.cash_price = {
    status: "conflicting",
    claims: [
      {
        value: { currency: "AED", minor_units: 7000000, basis: "cash" },
        qualifier: "at_least",
        evidence,
      },
      {
        value: { currency: "AED", minor_units: 8000000, basis: "cash" },
        qualifier: "at_most",
        evidence,
      },
    ],
  };
  search.supported_total = 3;
  search.presentation.ordered_refs = search.items.map((item) => item.ref);
  return search;
}

describe("Conversation structured results; synthetic component evidence only", () => {
  test("natural grounded prose stays visible above matching cars without legacy boilerplate", () => {
    const text =
      "There are 3 Nissan cars in these results. The Altima has the newest listed model year, 2023.\n\nIts price has conflicting source values, so I would check that before comparing budgets.";
    renderAnswer({ ...conversationResult(), search: orderedSearch(), text });
    const answer = screen.getByText(
      (_, element) => element?.tagName === "P" && element.textContent === text,
    );
    expect(answer).toBeVisible();
    expect(
      screen.queryByText("Original answer details"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "3 matching cars" }),
    ).toBeVisible();
    expect(
      answer.compareDocumentPosition(
        screen.getByRole("heading", { name: "3 matching cars" }),
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
  test("result cards replace duplicate template text without changing the saved reply", () => {
    const result = resultWithSearch(currentText);
    renderAnswer(result);
    expect(
      screen.queryByText("Original answer details"),
    ).not.toBeInTheDocument();
    expect(result.text).toBe(currentText);
    expect(
      screen.getByRole("heading", { name: "1 matching car" }),
    ).toBeVisible();
  });

  test.each([true, false])(
    "budget currency stays visible with new or saved search text: %s",
    (withNote) => {
      const note =
        "Budget currency: AED. Prices in other currencies are not converted.";
      const text = withNote
        ? currentText.replace("listings.\n", `listings.\n${note}\n`)
        : currentText;
      const result = resultWithSearch(text);
      result.search!.applied_criteria.filters = {
        budget: {
          minimum: null,
          maximum: 5000000,
          currency: "AED",
          basis: "cash",
        },
      };
      renderAnswer(result);
      expect(
        screen.queryByText("Original answer details"),
      ).not.toBeInTheDocument();
      expect(result.text).toBe(text);
      expect(screen.getByText(note)).toBeVisible();
    },
  );

  test("non-AED cash remains explicit in minor units when exact current wording is folded", () => {
    const result = resultWithSearch(
      currentText.replace(
        "Price: not stated.",
        "Price: approximately JPY 10,000 minor units cash.",
      ),
    );
    result.search!.items[0]!.cash_price = {
      status: "known",
      value: { currency: "JPY", minor_units: 10000, basis: "cash" },
      qualifier: "approximate",
      evidence,
    };
    renderAnswer(result);
    expect(
      screen.queryByText("Original answer details"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("JPY 10,000 minor units cash")).toBeVisible();
    expect(screen.getByText("Approximately")).toBeVisible();
    expect(screen.queryByText("JPY 100")).not.toBeInTheDocument();
  });

  test("current wording matches exact DTO values including cash qualifiers and conflicts", () => {
    const text = [
      "Found 3 matching cars in the supplied listings.",
      "",
      '1. Make: "Nissan". Model: "Patrol". Year: 2021.',
      "   Price: approximately AED 85,000.00 cash.",
      "",
      '2. Make: "Nissan". Model: "X-Trail". Year: 2022.',
      "   Price: not stated.",
      "",
      '3. Make: "Nissan". Model: "Altima". Year: 2023.',
      "   Price: conflicting listing values — at least AED 70,000.00 cash versus at most AED 80,000.00 cash. No value is resolved.",
      "",
      "Confirm current availability and condition with the seller.",
    ].join("\n");
    renderAnswer({ ...conversationResult(), search: orderedSearch(), text });
    expect(
      screen.queryByText("Original answer details"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Conflicting source claims")).toBeVisible();
  });

  test.each([
    currentText + "\nWhich option would you prefer?",
    currentText.replace("Make: not stated.", 'Make: "Nissan".'),
    currentText.replace(
      "Confirm current availability and condition with the seller.",
      "Finance is approved.",
    ),
  ])(
    "current-looking prose remains expanded when it differs from the DTO template: %s",
    (text) => {
      renderAnswer(resultWithSearch(text));
      expect(
        screen.queryByText("Original answer details"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(
          (_, element) =>
            element?.tagName === "P" && element.textContent === text,
        ),
      ).toBeVisible();
    },
  );

  test.each([
    "clarification",
    "action",
    "not_saved",
    "provider_unavailable",
    "superseded",
  ] as const)(
    "current deterministic wording stays expanded for %s",
    (guard) => {
      const result = resultWithSearch(currentText);
      if (guard === "clarification")
        result.pending_intent = {
          kind: "clarification",
          intent_id: "90000000-0000-4000-8000-000000000001",
          created_revision: 1,
          purpose: "search_criteria",
          targets: ["budget"],
          question: "What is your cash budget?",
        };
      if (guard === "action")
        result.actions = {
          ...result.actions,
          preferences: {
            state: "succeeded",
            client_action_id: "90000000-0000-4000-8000-000000000001",
            result: conversationSession().recalled_preferences,
          },
        };
      if (guard === "not_saved") result.persistence = "not_saved";
      if (guard === "provider_unavailable" || guard === "superseded")
        result.state = guard;
      renderAnswer(result);
      expect(
        screen.queryByText("Original answer details"),
      ).not.toBeInTheDocument();
    },
  );

  test("saved legacy search text is replaced by cards without changing the saved reply", () => {
    const result = resultWithSearch(legacyText);
    renderAnswer(result);
    expect(
      screen.queryByText("Original answer details"),
    ).not.toBeInTheDocument();
    expect(result.text).toBe(legacyText);
    expect(
      screen.getByRole("heading", { name: "1 matching car" }),
    ).toBeVisible();
  });

  test.each([
    "The Patrol may suit your needs, but ask about the service history before choosing.",
    `${legacyText}\nPlease tell me whether you prefer the newer car.`,
    legacyText.replace(
      "The make is not stated in the supplied evidence.",
      'The supplied source states make: "Nissan". Finance is approved.',
    ),
    "The inventory reports several options. Here is what matters for your family.",
  ])("arbitrary or extended answers remain visible: %s", (text) => {
    renderAnswer(resultWithSearch(text));
    expect(
      screen.queryByText("Original answer details"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName === "P" && element.textContent === text,
      ),
    ).toBeVisible();
  });

  test("result order, exact routes and staged context stay intact with cash qualifiers", () => {
    const search = orderedSearch();
    const { context, close } = renderAnswer({
      ...conversationResult(),
      search,
    });
    const rows = within(
      screen.getByRole("list", { name: "Matching cars in original order" }),
    ).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(
      rows.map((row) => within(row).getByRole("heading").textContent),
    ).toEqual([
      "2021 Nissan Patrol SV",
      "2022 Nissan X-Trail SV",
      "2023 Nissan Altima SV",
    ]);
    expect(rows[0]).toHaveTextContent("Approximately AED 85,000");
    expect(rows[1]).toHaveTextContent("Cash priceNot stated");
    expect(rows[2]).toHaveTextContent("Conflicting source claims");
    expect(rows[2]).toHaveTextContent("At least AED 70,000");
    expect(rows[2]).toHaveTextContent("At most AED 80,000");
    rows.forEach((row, index) => {
      expect(
        within(row).getByRole("link", { name: "View car" }),
      ).toHaveAttribute("href", listingPath(search.items[index]!.ref));
      fireEvent.click(
        within(row).getByRole("button", { name: "Ask about this" }),
      );
      expect(context).toHaveBeenNthCalledWith(index + 1, {
        label: `Car ${index + 1} from this answer · listing ${search.items[index]!.ref.source_id}`,
        selectedRef: search.items[index]!.ref,
        presentation: search.presentation,
      });
    });
    expect(close).not.toHaveBeenCalled();
  });

  test("busy original requests disable each car context action", () => {
    const { context } = renderAnswer(
      { ...conversationResult(), search: orderedSearch() },
      true,
    );
    screen
      .getAllByRole("button", { name: "Ask about this" })
      .forEach((button) => expect(button).toBeDisabled());
    expect(context).not.toHaveBeenCalled();
  });

  test.each(["provider_unavailable", "superseded"] as const)(
    "%s retains original prose and visible outcome notice",
    (state) => {
      renderAnswer({ ...resultWithSearch(legacyText), state });
      expect(
        screen.queryByText("Original answer details"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(
          (_, element) =>
            element?.tagName === "P" && element.textContent === legacyText,
        ),
      ).toBeVisible();
      expect(
        screen.getByText(
          state === "superseded"
            ? /Historical reply to an earlier revision/
            : /I could not complete this answer/,
        ),
      ).toBeVisible();
    },
  );

  test.each(["clarification", "saved action", "not saved"] as const)(
    "legacy-shaped prose stays expanded with %s",
    (kind) => {
      const result = resultWithSearch(legacyText);
      if (kind === "clarification")
        result.pending_intent = {
          kind: "clarification",
          intent_id: "90000000-0000-4000-8000-000000000001",
          created_revision: 1,
          purpose: "search_criteria",
          targets: ["budget"],
          question: "What is your cash budget?",
        };
      if (kind === "saved action")
        result.actions = {
          ...result.actions,
          preferences: {
            state: "succeeded",
            client_action_id: "90000000-0000-4000-8000-000000000001",
            result: conversationSession().recalled_preferences,
          },
        };
      if (kind === "not saved") result.persistence = "not_saved";
      renderAnswer(result);
      expect(
        screen.queryByText("Original answer details"),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(
          (_, element) =>
            element?.tagName === "P" && element.textContent === legacyText,
        ),
      ).toBeVisible();
    },
  );

  test("unknown reasons and conflicting model-year qualifiers stay explicit", () => {
    const search = orderedSearch();
    search.items[0]!.trim = { status: "unknown", reason: "not_applicable" };
    search.items[0]!.year = {
      status: "conflicting",
      claims: [
        { value: 2020, qualifier: "at_least", evidence },
        { value: 2022, qualifier: "approximate", evidence },
      ],
    };
    renderAnswer({ ...conversationResult(), search });
    expect(
      screen.queryByText("Not applicable in the source"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Listing source details"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName === "DIV" && element.textContent === "At least 2020",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName === "DIV" &&
          element.textContent === "Approximately 2022",
      ),
    ).toBeVisible();
  });

  test("optional trim details stay on the car page while trim conflicts remain visible", () => {
    const search = orderedSearch();
    search.items[0]!.trim = { status: "unknown", reason: "not_stated" };
    search.items[1]!.trim = {
      status: "conflicting",
      claims: [
        { value: "SV", qualifier: "exact", evidence },
        { value: "SL", qualifier: "exact", evidence },
      ],
    };
    renderAnswer({ ...conversationResult(), search });
    const rows = within(
      screen.getByRole("list", { name: "Matching cars in original order" }),
    ).getAllByRole("listitem");
    expect(
      within(rows[0]!).queryByText("Listing source details"),
    ).not.toBeInTheDocument();
    expect(
      within(rows[0]!).getByRole("link", { name: "View car" }),
    ).toHaveAttribute("href", listingPath(search.items[0]!.ref));
    expect(
      within(rows[1]!).getByText("Conflicting source claims"),
    ).toBeVisible();
    expect(within(rows[1]!).getByText("SV")).toBeVisible();
    expect(within(rows[1]!).getByText("SL")).toBeVisible();
    expect(within(rows[2]!).getByRole("heading")).toHaveTextContent(
      "2023 Nissan Altima SV",
    );
  });
});
