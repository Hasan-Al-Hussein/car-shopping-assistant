import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";
import type { Schema } from "../../api/contracts";
import { ListingPhoto } from "../ListingPhoto";
import { displayCarName } from "../displayNames";
import { CinemaIcon } from "../CinemaIcon";
import { ComparisonFact, type ComparisonFactValue } from "./ComparisonFact";
import { ContextualAssistant } from "./ContextualAssistant";
import { InternalPageHeader } from "./InternalPageHeader";

type InventoryRef = Schema<"InventoryRef">;
type Result = Schema<"ComparisonResult">["items"][number];
export type ComparisonEntry = {
  ref: InventoryRef;
  result: Result;
  listingHref: string;
  photoCell?: string;
  /** Controlled missing-image proof only. Never substitutes another vehicle. */
  photoFailureExample?: boolean;
  supplementalConflicts?: {
    attribute: string;
    label: string;
    fact: ComparisonFactValue;
  }[];
};
type Row = {
  key: string;
  label: string;
  unit?: string;
  read: (entry: ComparisonEntry) => ComparisonFactValue | undefined;
};
type Section = { id: string; label: string; rows: Row[] };
const isDetail = (result: Result): result is Schema<"ListingDetail"> =>
  result.state === "current" || result.state === "historical";
const keyOf = (ref: InventoryRef) =>
  JSON.stringify([ref.namespace, ref.snapshot_id, ref.source_id]);
function factName(fact: Schema<"ListingSummary">["make"]) {
  return fact.status === "known"
    ? displayCarName(fact.value)
    : fact.status === "conflicting"
      ? "Conflicting identity claims"
      : "Not stated";
}
function carName(entry: ComparisonEntry) {
  return isDetail(entry.result)
    ? `${factName(entry.result.listing.make)} ${factName(entry.result.listing.model)}`
    : `Listing ${entry.ref.source_id}`;
}
const listingRow = (
  key: "cash_price" | "year" | "trim" | "mileage_km",
  label: string,
  unit?: string,
): Row => ({
  key,
  label,
  unit,
  read: (entry) =>
    isDetail(entry.result) ? entry.result.listing[key] : undefined,
});
const detailRow = (
  key:
    "body_type" | "fuel_type" | "transmission" | "service_history" | "warranty",
  label: string,
): Row => ({
  key,
  label,
  read: (entry) => (isDetail(entry.result) ? entry.result[key] : undefined),
});
const SECTIONS: Section[] = [
  {
    id: "key",
    label: "Key information",
    rows: [
      listingRow("cash_price", "Cash price"),
      listingRow("year", "Model year"),
      listingRow("trim", "Trim"),
      listingRow("mileage_km", "Mileage", "km"),
    ],
  },
  {
    id: "specifications",
    label: "Specifications",
    rows: [
      detailRow("body_type", "Body type"),
      detailRow("fuel_type", "Fuel type"),
      detailRow("transmission", "Transmission"),
    ],
  },
  {
    id: "history",
    label: "Condition & history",
    rows: [
      detailRow("service_history", "Service history"),
      detailRow("warranty", "Warranty"),
    ],
  },
];

export function ComparisonWorkspace({
  entries,
  count = entries.length,
  exploreHref,
  browseKey,
  onRemove,
  preview = false,
  pending = false,
  failure,
  onRetry,
  onOpenAssistant,
}: {
  entries: ComparisonEntry[];
  count?: number;
  exploreHref: string;
  browseKey?: string;
  onRemove: (ref: InventoryRef) => void;
  preview?: boolean;
  pending?: boolean;
  failure?: ReactNode;
  onRetry?: () => void;
  onOpenAssistant?: () => void;
}) {
  const [expanded, setExpanded] = useState<string[]>(["key"]);
  const [active, setActive] = useState("overview");
  const pendingFocus = useRef(false);
  const region = useRef<HTMLDivElement>(null);
  const ready = entries.length > 0 && !pending && !failure;
  const supplemental = [
    ...new Map(
      entries
        .flatMap((entry) => entry.supplementalConflicts ?? [])
        .map((conflict) => [conflict.attribute, conflict] as const),
    ).values(),
  ];
  const sections: Section[] = supplemental.length
    ? [
        ...SECTIONS,
        {
          id: "source-checks",
          label: "Additional source conflicts",
          rows: supplemental.map((conflict) => ({
            key: conflict.attribute,
            label: conflict.label,
            read: (entry: ComparisonEntry) =>
              entry.supplementalConflicts?.find(
                (item) => item.attribute === conflict.attribute,
              )?.fact,
          })),
        },
      ]
    : SECTIONS;
  useLayoutEffect(() => {
    if (!pendingFocus.current) return;
    pendingFocus.current = false;
    (
      region.current?.querySelector<HTMLButtonElement>(".comparison-remove") ??
      document.getElementById("page-heading")
    )?.focus({ preventScroll: true });
  }, [entries]);
  const goTo = (id: string) => {
    setActive(id);
    if (id !== "overview")
      setExpanded((current) =>
        current.includes(id) ? current : [...current, id],
      );
    const target = document.getElementById(`comparison-${id}`);
    target?.scrollIntoView({ block: "start", behavior: "instant" });
    target?.focus({ preventScroll: true });
  };
  const verify = () => {
    const section = sections.find((section) =>
      section.rows.some((row) =>
        entries.some((entry) => {
          const fact = row.read(entry);
          return fact?.status === "unknown" || fact?.status === "conflicting";
        }),
      ),
    );
    goTo(section?.id ?? "overview");
  };
  const changeSelection = () => {
    goTo("overview");
    region.current
      ?.querySelector<HTMLButtonElement>(".comparison-remove")
      ?.focus();
  };
  return (
    <section className="comparison-page">
      <InternalPageHeader
        eyebrow="Compare your cars"
        title="Compare cars."
        architecturalAccent
        art={{
          src: "/cinematic/headers/viewing-parked-car.jpg",
          width: 1600,
          height: 1067,
          position: "60% 75%",
        }}
      >
        <span>
          See what differs. Keep missing information and conflicting claims in
          view.
        </span>
      </InternalPageHeader>
      <div className="inner-page-toolbar">
        <Link
          className="comparison-back"
          to={exploreHref}
          state={{ browseKey }}
        >
          ← Keep exploring
        </Link>
        <p>
          <strong>{count} / 3</strong> cars selected
        </p>
        {count < 3 ? (
          <Link
            className="folio-button folio-button--secondary"
            to={exploreHref}
            state={{ browseKey }}
          >
            Add {count ? "another" : "a"} car <span aria-hidden="true">+</span>
          </Link>
        ) : (
          <button
            className="folio-button folio-button--secondary"
            type="button"
            onClick={changeSelection}
            disabled={pending || !!failure}
          >
            Change selection <CinemaIcon kind="compare" />
          </button>
        )}
      </div>
      <div className="comparison-workspace">
        <nav
          className="comparison-categories"
          aria-label="Comparison categories"
        >
          <div className="comparison-rail-count">
            <strong>
              {count}
              <span> / 3</span>
            </strong>
            <span>
              cars
              <br />
              selected
            </span>
          </div>
          {[{ id: "overview", label: "Overview" }, ...sections].map(
            (section) => (
              <button
                type="button"
                key={section.id}
                aria-current={active === section.id ? "location" : undefined}
                disabled={!ready}
                onClick={() => goTo(section.id)}
              >
                <CinemaIcon
                  kind={section.id === "overview" ? "compare" : "source"}
                />
                <span>{section.label}</span>
              </button>
            ),
          )}
          <p>
            Every car.
            <br />
            <em>The same questions.</em>
          </p>
        </nav>
        <div className="comparison-main">
          {pending ? (
            <div className="comparison-empty" role="status">
              <p className="inner-eyebrow">Bringing the details together</p>
              <h2>Loading your selected cars…</h2>
              <p>The exact listing references are being checked.</p>
            </div>
          ) : failure ? (
            <div className="comparison-empty">{failure}</div>
          ) : !entries.length ? (
            <div className="comparison-empty">
              <span className="comparison-empty-mark">
                <CinemaIcon kind="compare" />
              </span>
              <p className="inner-eyebrow">Room for three perspectives</p>
              <h2>Start with a car that interests you.</h2>
              <p>
                Choose up to three cars to compare their source details, missing
                information and conflicting claims.
              </p>
              <Link
                className="folio-button folio-button--primary"
                to={exploreHref}
                state={{ browseKey }}
              >
                Explore the cars <CinemaIcon kind="arrow" />
              </Link>
            </div>
          ) : (
            <>
              <div
                className="comparison-table-hint"
                id="comparison-instruction"
              >
                <span>
                  {count === 1
                    ? "One car selected. Add another when you’re ready."
                    : "Compare the original listing claims."}
                </span>
                <span className="comparison-scroll-hint">
                  Scroll sideways for each car <span aria-hidden="true">↔</span>
                </span>
              </div>
              <div
                className="comparison-table-region"
                ref={region}
                role="region"
                aria-label="Car comparison table"
                aria-describedby="comparison-instruction"
                tabIndex={0}
              >
                <table
                  className="comparison-table"
                  data-car-count={entries.length}
                >
                  <caption className="folio-visually-hidden">
                    Comparison of {entries.length} selected source listings.
                    Claims are not independently verified.
                  </caption>
                  <colgroup>
                    <col className="comparison-label-column" />
                    {entries.map((entry) => (
                      <col key={keyOf(entry.ref)} />
                    ))}
                  </colgroup>
                  <thead id="comparison-overview" tabIndex={-1}>
                    <tr>
                      <th scope="col" className="comparison-table-corner">
                        <span className="inner-eyebrow">The details</span>
                        <p>Details</p>
                        <span>
                          Original listings.
                          <br />
                          Open questions.
                        </span>
                      </th>
                      {entries.map((entry) => {
                        const result = entry.result;
                        return (
                          <th
                            scope="col"
                            key={keyOf(entry.ref)}
                            className="comparison-vehicle-column"
                          >
                            <div className="comparison-vehicle">
                              <div className="comparison-image-well">
                                {isDetail(result) ? (
                                  <ListingPhoto
                                    identity={keyOf(entry.ref)}
                                    src={
                                      entry.photoFailureExample
                                        ? "/__proof/controlled-unavailable-image"
                                        : result.listing.photo.url
                                    }
                                    alt={result.listing.photo.alt}
                                    loading="eager"
                                  />
                                ) : (
                                  <div className="comparison-missing-photo">
                                    Listing unavailable
                                  </div>
                                )}
                                <button
                                  type="button"
                                  className="comparison-remove"
                                  aria-label={`Remove listing ${entry.ref.source_id} from comparison`}
                                  onClick={() => {
                                    pendingFocus.current = true;
                                    onRemove(entry.ref);
                                  }}
                                >
                                  <span aria-hidden="true">×</span>
                                </button>
                              </div>
                              <div className="comparison-vehicle-copy">
                                <p className="comparison-photo-caption">
                                  {entry.photoFailureExample
                                    ? "Controlled photo-failure example"
                                    : isDetail(result)
                                      ? `Original listing photo${entry.photoCell ? ` · ${entry.photoCell}` : ""}`
                                      : "Exact reference retained"}
                                </p>
                                <h2>
                                  <bdi>{carName(entry)}</bdi>
                                </h2>
                                {isDetail(result) ? (
                                  <>
                                    {result.state === "historical" && (
                                      <p className="comparison-warning">
                                        Historical snapshot — current
                                        availability is unknown.
                                      </p>
                                    )}
                                    <details className="comparison-card-warning">
                                      <summary>
                                        {result.listing.evidence_warnings
                                          ?.length
                                          ? "Source details to check"
                                          : "Original source details"}
                                      </summary>
                                      <p
                                        className="comparison-vehicle-subtitle"
                                        dir="auto"
                                      >
                                        <bdi>{result.listing.title}</bdi>
                                      </p>
                                      <ul>
                                        {(
                                          result.listing.evidence_warnings ?? []
                                        ).map((warning, index) => (
                                          <li key={index}>{warning}</li>
                                        ))}
                                      </ul>
                                    </details>
                                    <Link
                                      className="comparison-view-link"
                                      to={entry.listingHref}
                                      state={{ from: exploreHref, browseKey }}
                                    >
                                      View listing <CinemaIcon kind="arrow" />
                                    </Link>
                                  </>
                                ) : (
                                  <>
                                    <p className="comparison-unavailable">
                                      {result.state === "error"
                                        ? "The source service could not load this listing."
                                        : "This exact source listing is unavailable."}{" "}
                                      Its reference has not been replaced.
                                    </p>
                                    {result.state === "error" &&
                                      result.retryable &&
                                      onRetry && (
                                        <button
                                          type="button"
                                          className="comparison-view-link"
                                          onClick={onRetry}
                                        >
                                          Check again{" "}
                                          <CinemaIcon kind="arrow" />
                                        </button>
                                      )}
                                  </>
                                )}
                              </div>
                            </div>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  {sections.map((section) => (
                    <tbody key={section.id}>
                      <tr className="comparison-section">
                        <th colSpan={entries.length + 1} scope="rowgroup">
                          <button
                            id={`comparison-${section.id}`}
                            type="button"
                            aria-expanded={expanded.includes(section.id)}
                            aria-controls={section.rows
                              .map(
                                (row) =>
                                  `comparison-row-${section.id}-${row.key}`,
                              )
                              .join(" ")}
                            onClick={() => {
                              setActive(section.id);
                              setExpanded((current) =>
                                current.includes(section.id)
                                  ? current.filter((id) => id !== section.id)
                                  : [...current, section.id],
                              );
                            }}
                          >
                            <CinemaIcon
                              kind={section.id === "key" ? "compare" : "source"}
                            />
                            {section.label}
                            <span aria-hidden="true">
                              {expanded.includes(section.id) ? "−" : "+"}
                            </span>
                          </button>
                        </th>
                      </tr>
                      {section.rows.map((row) => (
                        <tr
                          key={row.key}
                          id={`comparison-row-${section.id}-${row.key}`}
                          hidden={!expanded.includes(section.id)}
                        >
                          <th scope="row">{row.label}</th>
                          {entries.map((entry) => {
                            const fact = row.read(entry);
                            return (
                              <td key={keyOf(entry.ref)}>
                                {fact ? (
                                  <ComparisonFact fact={fact} unit={row.unit} />
                                ) : (
                                  <span className="comparison-unavailable">
                                    {isDetail(entry.result)
                                      ? "Not included in this comparison"
                                      : "Unavailable"}
                                  </span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  ))}
                </table>
              </div>
              <p className="comparison-table-note">
                Unknown does not mean absent or zero. Source claims can
                disagree; this comparison does not select a winner or infer
                affordability.
              </p>
            </>
          )}
        </div>
        <ContextualAssistant
          count={count}
          ready={ready}
          preview={preview}
          onVerify={verify}
          onInspect={() => goTo("overview")}
          onOpen={onOpenAssistant}
        >
          {entries
            .filter((entry) => isDetail(entry.result))
            .map((entry) => (
              <Link
                key={keyOf(entry.ref)}
                to={entry.listingHref}
                state={{ from: exploreHref, browseKey }}
              >
                <CinemaIcon kind="arrow" />
                <span>
                  <strong>View listing</strong>
                  <span>{carName(entry)}</span>
                </span>
              </Link>
            ))}
          <Link to={exploreHref} state={{ browseKey }}>
            <CinemaIcon kind="search" />
            <span>
              <strong>Keep exploring</strong>
              <span>
                {count === 3
                  ? "Remove a car to make room for another."
                  : "Find another car to consider."}
              </span>
            </span>
          </Link>
          <p>
            Viewing options belong to the selected listing. No reservation is
            made here.
          </p>
        </ContextualAssistant>
      </div>
    </section>
  );
}
