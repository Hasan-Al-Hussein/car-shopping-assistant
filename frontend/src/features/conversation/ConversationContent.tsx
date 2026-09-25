import { Link, useNavigate } from "react-router";
import type { Schema } from "../../shared/api/contracts";
import { useServices } from "../../app/ServicesProvider";
import {
  comparisonPath,
  listingPath,
  operationPath,
  refKey,
} from "../../app/routes";
import { Button } from "../../shared/ui/Button";
import { Fact } from "../../shared/ui/Fact";
import { displayCarName } from "../../shared/ui/displayNames";
import "./conversation-results.css";
import {
  describeCriteria,
  emptyCriteria,
  filtersFromCriteria,
} from "../inventory/criteria";
import type { ConversationContext } from "./ConversationFlow";

const qualifierLabels = {
  exact: "",
  approximate: "Approximately ",
  at_least: "At least ",
  at_most: "At most ",
};
type ResultFact = Parameters<typeof Fact>[0]["fact"];

function ResultValue({ fact }: { fact: ResultFact }) {
  if (
    fact.status === "known" &&
    typeof fact.value === "object" &&
    fact.value.currency !== "AED"
  )
    return (
      <span className="proof-fact-value">
        <bdi>
          {fact.value.currency} {fact.value.minor_units.toLocaleString("en-US")}{" "}
          minor units cash
        </bdi>
      </span>
    );
  return <Fact fact={fact} />;
}

function QualifiedFact({ fact }: { fact: ResultFact }) {
  if (fact.status === "unknown") {
    const reasons = {
      not_stated: "Not stated",
      unparseable: "Cannot read the source value",
      unsupported: "No supported source value",
      not_applicable: "Not applicable in the source",
    };
    return <span className="proof-unknown">{reasons[fact.reason]}</span>;
  }
  if (fact.status === "conflicting")
    return (
      <div className="chat-result-conflict">
        <span>Conflicting source claims</span>
        {fact.claims.map((claim, index) => (
          <div key={index}>
            {qualifierLabels[claim.qualifier]}
            <ResultValue fact={{ ...claim, status: "known" } as ResultFact} />
          </div>
        ))}
      </div>
    );
  return (
    <span>
      {qualifierLabels[fact.qualifier]}
      <ResultValue fact={fact} />
    </span>
  );
}

function carTitle(listing: Schema<"ListingSummary">) {
  return (
    [listing.year, listing.make, listing.model, listing.trim]
      .flatMap((fact) =>
        fact.status === "known"
          ? [
              `${qualifierLabels[fact.qualifier]}${displayCarName(String(fact.value))}`,
            ]
          : [],
      )
      .join(" ") || "Car details to check"
  );
}

function templateValue(value: string | number | Schema<"CashMoney">) {
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") return String(value);
  const grouped = (amount: number) =>
    amount.toLocaleString("en-US", {
      useGrouping: true,
      maximumFractionDigits: 0,
    });
  return value.currency === "AED"
    ? `AED ${grouped(Math.floor(value.minor_units / 100))}.${String(value.minor_units % 100).padStart(2, "0")} cash`
    : `${value.currency} ${grouped(value.minor_units)} minor units cash`;
}

/** Exact current backend template; unfamiliar wording safely remains expanded. */
function currentSearchTemplate(search: Schema<"SearchResult">) {
  const factText = (label: string, fact: ResultFact) => {
    const claim = (
      value: string | number | Schema<"CashMoney">,
      qualifier: keyof typeof qualifierLabels,
    ) => qualifierLabels[qualifier].toLowerCase() + templateValue(value);
    let text: string;
    if (fact.status === "unknown") {
      const reasons = {
        not_stated: "not stated",
        unparseable: "cannot be resolved from the listing wording",
        unsupported: "no supported value in these listings",
        not_applicable: "marked not applicable in the listing",
      };
      text = `${label}: ${reasons[fact.reason]}.`;
    } else if (fact.status === "known") {
      const seller = fact.evidence.some(
        (source) => source.category === "seller_description",
      )
        ? " (seller claim)"
        : "";
      text = `${label}: ${claim(fact.value, fact.qualifier)}${seller}.`;
    } else {
      text = `${label}: conflicting listing values — ${fact.claims.map((item) => claim(item.value, item.qualifier)).join(" versus ")}. No value is resolved.`;
    }
    if (Array.from(text).length > 330)
      return fact.status === "conflicting"
        ? `${label}: ${fact.claims.length} conflicting source claims; no value is resolved. See the attached evidence.`
        : `${label}: listing statement too long to summarize; see the full value and qualifiers in the listing evidence.`;
    return text;
  };
  const lines = [
    `Found ${search.supported_total} matching ${search.supported_total === 1 ? "car" : "cars"} in the supplied listings.`,
  ];
  if (search.supported_total !== search.items.length)
    lines.push(`This result page contains ${search.items.length}.`);
  search.items
    .slice(0, 5)
    .forEach((item, index) =>
      lines.push(
        "",
        `${index + 1}. ${factText("Make", item.make)} ${factText("Model", item.model)} ${factText("Year", item.year)}`,
        `   ${factText("Price", item.cash_price)}`,
      ),
    );
  if (search.items.length > 5)
    lines.push(
      "\nThe first 5 cars are summarized here; the attached results include the rest of this page.",
    );
  if (search.next_cursor !== null)
    lines.push("More matches are available on the next result page.");
  lines.push("", "Confirm current availability and condition with the seller.");
  return lines.join("\n");
}

/** Ordinary persisted legacy searches only; unfamiliar variants stay expanded. */
function legacySearchTemplate(search: Schema<"SearchResult">) {
  const lines = [
    `The inventory reports ${search.supported_total} supported matches; this page contains ${search.items.length}. Your hard conditions were not relaxed.`,
  ];
  const reasons = {
    not_stated: "is not stated in the supplied evidence",
    unparseable: "cannot be resolved from the supplied wording",
    unsupported: "has no supported value in this response",
    not_applicable: "is marked not applicable in the supplied evidence",
  };
  for (const [index, item] of search.items.slice(0, 3).entries()) {
    lines.push(`Car ${index + 1}: supplied source claims.`);
    for (const [label, fact] of [
      ["make", item.make],
      ["model", item.model],
      ["model year", item.year],
      ["cash asking price", item.cash_price],
    ] as const) {
      if (fact.status === "conflicting") return null;
      const source =
        fact.status === "known" &&
        fact.evidence.some((entry) => entry.category === "seller_description")
          ? "seller"
          : "supplied source";
      const text =
        fact.status === "unknown"
          ? `The ${label} ${reasons[fact.reason]}.`
          : `The ${source} states ${label}: ${qualifierLabels[fact.qualifier].toLowerCase()}${templateValue(fact.value)}.`;
      if (Array.from(text).length > 330) return null;
      lines.push(text);
    }
  }
  if (search.items.length > 3 || search.next_cursor !== null)
    lines.push(
      "This reply summarizes the first three cars at most; use the attached results for the remaining entries.",
    );
  lines.push(
    "Static source matches do not verify live stock, inspection or finance approval.",
  );
  return lines.join("\n");
}
/** Fold only complete deterministic search templates, never arbitrary prose. */
function isDeterministicSearchAnswer(result: Schema<"MessageResult">) {
  const search = result.search;
  if (
    !search?.items.length ||
    result.state !== "answered" ||
    result.persistence !== "saved" ||
    result.pending_intent.kind !== "none" ||
    result.operation ||
    result.handoff_summary ||
    result.comparison ||
    Object.values(result.actions ?? {}).some(
      (action) => action && action.state !== "not_requested",
    )
  )
    return false;
  return (
    result.text === currentSearchTemplate(search) ||
    result.text === legacySearchTemplate(search)
  );
}

export function RememberedPreferences({
  record,
}: {
  record: Schema<"PreferenceRecord">;
}) {
  return (
    <section
      className="conversation-memory"
      aria-label="Returned saved preferences"
    >
      <h3>Saved preferences for this conversation</h3>
      {!record.entries.length ? (
        <p>No saved preferences are available for this conversation.</p>
      ) : (
        <ul>
          {record.entries.map((entry) => (
            <li key={entry.preference.key}>
              {entry.preference.key === "budget"
                ? describeCriteria({
                    filters: {
                      ...filtersFromCriteria(emptyCriteria()),
                      budget: entry.preference.value,
                    },
                    query: "",
                    soft_preferences: [],
                  }).join(" · ")
                : `${entry.preference.key.replaceAll("_", " ")}: ${entry.preference.value.join(", ")}`}{" "}
              · {entry.preference.strength} ·{" "}
              {entry.applicability === "confirmed"
                ? "confirmed"
                : "needs reconfirmation"}
              .
              <small>
                {" "}
                Recorded{" "}
                <time dateTime={entry.confirmed_at}>{entry.confirmed_at}</time>;
                expires{" "}
                <time dateTime={entry.expires_at}>{entry.expires_at}</time>.
              </small>
            </li>
          ))}
        </ul>
      )}
      <p>
        {record.collection_mode === "disabled"
          ? "Saving preferences is disabled."
          : "Preferences are saved only through an explicit remember or correct request."}
      </p>
    </section>
  );
}

export function resultOperationPath(
  result: Schema<"MessageResult">,
): string | null {
  const operation = result.operation;
  if (!operation) return null;
  if (operation.state === "succeeded" || operation.state === "rejected")
    return operationPath(
      operation.operation_key,
      operation.original_store_generation,
    );
  if (operation.state === "unresolved_generation")
    return operationPath(
      operation.operation_key,
      operation.submitted_store_generation,
    );
  const pending = result.pending_intent;
  return pending.kind === "operation_unresolved" &&
    pending.operation_key === operation.operation_key
    ? operationPath(operation.operation_key, pending.submitted_store_generation)
    : `/operations/${operation.operation_key}`;
}

export function ConversationAnswer({
  result,
  onContext,
  close,
  contextDisabled = false,
}: {
  result: Schema<"MessageResult">;
  onContext: (context: ConversationContext) => void;
  close: () => void;
  contextDisabled?: boolean;
}) {
  const services = useServices(),
    navigate = useNavigate();
  const search = result.search,
    comparison = result.comparison,
    pending = result.pending_intent;
  const operationHref = resultOperationPath(result);
  const legacySearch = isDeterministicSearchAnswer(result);
  const open = (to: string) => (
    <Link to={to} onClick={close}>
      Read original viewing outcome
    </Link>
  );
  return (
    <div className="conversation-answer">
      {!legacySearch && (
        <p className="conversation-text" dir="auto">
          {result.text}
        </p>
      )}
      {result.state === "provider_unavailable" && (
        <p className="conversation-notice">
          I could not complete this answer. You can still browse, compare, or
          check the original request below.
        </p>
      )}
      {result.state === "superseded" && (
        <p className="conversation-notice">
          Historical reply to an earlier revision. It has not changed the
          current page or car selection.
        </p>
      )}
      {result.persistence === "not_saved" && (
        <p>This response was not saved in the server transcript.</p>
      )}
      {!!result.evidence?.length && (
        <details>
          <summary>Listing evidence for this answer</summary>
          <ul>
            {result.evidence.map((item) => (
              <li key={refKey(item.ref)}>
                <Link to={listingPath(item.ref)} onClick={close}>
                  Listing {item.ref.source_id}
                </Link>
                {item.attributes.length > 0 &&
                  ` · ${item.attributes.join(", ")}`}
              </li>
            ))}
          </ul>
        </details>
      )}
      {search && (
        <section
          className="conversation-results"
          aria-label="Original returned search order"
        >
          <h4>
            {search.items.length === search.supported_total
              ? `${search.supported_total} matching ${search.supported_total === 1 ? "car" : "cars"}`
              : `${search.items.length} of ${search.supported_total} matching cars`}
          </h4>
          <p className="chat-results-note">
            Listing claims only. Live availability and vehicle condition are not
            verified.
          </p>
          <ol
            className="chat-car-results"
            aria-label="Matching cars in original order"
          >
            {search.items.map((listing, index) => (
              <li key={refKey(listing.ref)}>
                <h5>{carTitle(listing)}</h5>
                <div className="chat-result-price">
                  <span>Cash price</span>
                  <QualifiedFact fact={listing.cash_price} />
                </div>
                {(
                  [
                    ["Year", listing.year],
                    ["Make", listing.make],
                    ["Model", listing.model],
                    ["Trim", listing.trim],
                  ] as const
                ).map(([label, fact]) =>
                  fact.status !== "known" &&
                  !(label === "Trim" && fact.status === "unknown") ? (
                    <div className="chat-result-missing" key={label}>
                      <span>{label}: </span>
                      <QualifiedFact fact={fact} />
                    </div>
                  ) : null,
                )}
                <div className="chat-result-actions">
                  <Link to={listingPath(listing.ref)} onClick={close}>
                    View car
                  </Link>
                  <Button
                    variant="quiet"
                    disabled={contextDisabled}
                    onClick={() =>
                      onContext({
                        label: `Car ${index + 1} from this answer · listing ${listing.ref.source_id}`,
                        selectedRef: listing.ref,
                        presentation: search.presentation,
                      })
                    }
                  >
                    Ask about this
                  </Button>
                </div>
                <details className="chat-result-source">
                  <summary>Listing source details</summary>
                  {listing.trim.status === "unknown" && (
                    <p>
                      Trim: <QualifiedFact fact={listing.trim} />
                    </p>
                  )}
                  <p>
                    Listing {listing.ref.source_id} · position {index + 1} in
                    this answer’s original order.
                  </p>
                  <p dir="auto">{listing.title}</p>
                  {!!listing.evidence_warnings?.length && (
                    <ul>
                      {listing.evidence_warnings.map(
                        (warning, warningIndex) => (
                          <li key={warningIndex}>{warning}</li>
                        ),
                      )}
                    </ul>
                  )}
                </details>
              </li>
            ))}
          </ol>
          {!search.items.length && (
            <p>
              No supported matches were returned. Unknown facts were not treated
              as matches.
            </p>
          )}
          {!!search.unsupported_constraints?.length && (
            <p>
              Unsupported conditions:{" "}
              {search.unsupported_constraints.join("; ")}.
            </p>
          )}
          <details className="chat-search-details">
            <summary>Search criteria and source coverage</summary>
            <p>
              Your required conditions were not relaxed. Numbers follow this
              answer’s original result order. “Ask about this” sets the next
              message context; it does not send a message.
            </p>
            <ul>
              {describeCriteria(search.applied_criteria).map(
                (criterion, index) => (
                  <li key={index}>{criterion}</li>
                ),
              )}
            </ul>
            {search.evidence_coverage.map((coverage) => (
              <p key={coverage.attribute}>
                {coverage.attribute.replaceAll("_", " ")}: {coverage.supported}{" "}
                of {coverage.source_total} listings have usable evidence;{" "}
                {coverage.excluded_unknown} unknown,{" "}
                {coverage.excluded_conflicting} conflicting and{" "}
                {coverage.excluded_unsupported_qualifier} unsupported qualifiers
                excluded.
              </p>
            ))}
            <Button
              variant="secondary"
              onClick={() => {
                services.queueBrowseRequest({
                  ...search.applied_criteria,
                  client_request_id: crypto.randomUUID(),
                  snapshot_id: search.presentation.snapshot_id,
                  cursor: null,
                  page_size: 20,
                });
                navigate("/cars");
                close();
              }}
            >
              Use these search criteria
            </Button>
            <Button
              variant="quiet"
              disabled={contextDisabled}
              onClick={() =>
                onContext({
                  label: "Original result order from this answer",
                  selectedRef: null,
                  presentation: search.presentation,
                })
              }
            >
              Use this original result order
            </Button>
          </details>
        </section>
      )}
      {legacySearch && (
        <details className="conversation-original-answer">
          <summary>Original answer details</summary>
          <p className="conversation-text" dir="auto">
            {result.text}
          </p>
        </details>
      )}
      {comparison && (
        <section aria-label="Returned comparison">
          <h4>Compared source listings</h4>
          <ol>
            {comparison.items.map((item) => {
              const ref = "listing" in item ? item.listing.ref : item.ref;
              return (
                <li key={refKey(ref)}>
                  <Link to={listingPath(ref)} onClick={close}>
                    Listing {ref.source_id}
                  </Link>{" "}
                  · {item.state}
                </li>
              );
            })}
          </ol>
          <Link
            to={comparisonPath(
              comparison.items.map((item) =>
                "listing" in item ? item.listing.ref : item.ref,
              ),
            )}
            onClick={close}
          >
            Open this comparison
          </Link>
          <p>
            Choose a car by its listing reference. ‘The first car’ in chat does
            not refer to this comparison’s order.
          </p>
        </section>
      )}
      {result.handoff_summary && (
        <section>
          <h4>Selected car summary</h4>
          <Link
            to={listingPath(result.handoff_summary.selected_ref)}
            onClick={close}
          >
            Inspect listing {result.handoff_summary.selected_ref.source_id}
          </Link>
          <ul>
            {result.handoff_summary.fit_reasons.map((reason, index) => (
              <li key={index}>{reason.text}</li>
            ))}
            {result.handoff_summary.unresolved_questions.map(
              (question, index) => (
                <li key={`question-${index}`}>
                  {question.question} · {question.reason}
                </li>
              ),
            )}
          </ul>
        </section>
      )}
      {pending.kind === "clarification" && (
        <p className="conversation-clarification">
          Clarification: {pending.question}
        </p>
      )}
      {pending.kind === "viewing_review" && (
        <p>
          <Link
            to={`/viewings/drafts/${pending.draft_id}/review`}
            onClick={close}
          >
            Open exact viewing review
          </Link>
          . Review the current server terms there before explicitly confirming;
          this answer reserves nothing.
        </p>
      )}
      {pending.kind === "operation_unresolved" && (
        <p>
          {open(
            operationPath(
              pending.operation_key,
              pending.submitted_store_generation,
            ),
          )}
          . The original outcome remains unresolved.
        </p>
      )}
      {operationHref && (
        <p>
          {open(operationHref)}.{" "}
          {result.operation?.state === "succeeded"
            ? "The service reports the original simulated booking and local enquiry saved; CSV status is separate."
            : result.operation?.state === "rejected"
              ? "The original operation has a retained rejection."
              : "An absent or changed-generation observation does not prove noncommit."}
        </p>
      )}
      {result.actions?.preferences?.state === "succeeded" && (
        <section className="conversation-action-result">
          <p>
            Preferences saved locally · revision{" "}
            {result.actions.preferences.result.revision}.
          </p>
          <RememberedPreferences record={result.actions.preferences.result} />
        </section>
      )}
      {result.actions?.shortlist?.state === "succeeded" && (
        <p className="conversation-action-result">
          The original shortlist action was recorded; current reported
          membership is{" "}
          {result.actions.shortlist.result.saved ? "saved" : "removed"}.{" "}
          <Link to="/shortlist" onClick={close}>
            Read current saved cars
          </Link>
          .
        </p>
      )}
      {result.actions?.lead?.state === "succeeded" && (
        <p className="conversation-action-result">
          Your enquiry was saved locally. CSV export status in this response:{" "}
          {result.actions.lead.result.lead.csv.state === "current"
            ? "Up to date"
            : result.actions.lead.result.lead.csv.state === "pending"
              ? "Not yet up to date"
              : "Export needs attention"}
          . Nothing was sent to a dealer. Later enquiry edits are separate.
          Accepted revision {result.actions.lead.result.lead.revision}.
        </p>
      )}
      {(["preferences", "shortlist", "lead"] as const).map((kind) => {
        const action = result.actions?.[kind];
        return action?.state === "unresolved" ? (
          <p key={kind} className="conversation-notice">
            The original {kind} action is unresolved. Current saved records
            alone cannot prove its original outcome.{" "}
            {action.recovery === "operator_reconciliation"
              ? "Operator reconciliation is required."
              : "Keep the original conversation; do not repeat the request as a fresh action."}
          </p>
        ) : action?.state === "rejected" ? (
          <p key={kind}>
            The {kind} action was rejected: {action.code.replaceAll("_", " ")}.
          </p>
        ) : null;
      })}
    </div>
  );
}
