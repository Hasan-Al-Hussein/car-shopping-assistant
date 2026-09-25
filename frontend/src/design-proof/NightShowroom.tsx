import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../shared/ui/Button";
import { ListingPhoto } from "../shared/ui/ListingPhoto";
import { TextField } from "../shared/ui/TextField";
import { Fact } from "./Fact";
import { proofListings } from "./fixtures";
import { listingPath, refKey, type ProofListing, type Ref } from "./types";

export type NightShared = {
  selected: Ref[];
  toggle: (ref: Ref) => void;
  failPhoto: boolean;
  startReview: (ref: Ref) => void;
  unresolved: boolean;
};

// Source-row order is presentation only; lookup, links and actions use the full immutable ref.
const inventory: ProofListing[] = [...proofListings].sort(
  (left, right) =>
    Number(left.source.title_cell.slice(1)) -
    Number(right.source.title_cell.slice(1)),
);
const sourceLabel = (fact: ProofListing["detail"]["listing"]["make"]) =>
  fact.status === "known" ? fact.value : "Not stated";

export function NightHeader({
  count,
  detail,
  viewingPath,
}: {
  count: number;
  detail: boolean;
  viewingPath?: string;
}) {
  return (
    <header className="night-header night-width">
      <Link to="/" className="night-brand" aria-label="Car decision folio home">
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <path d="M6 27 12 5M26 27 20 5M16 8v5m0 5v6" />
        </svg>
        <span>
          FOLIO<small>CAR DECISIONS</small>
        </span>
      </Link>
      <nav aria-label="Main">
        <Link to="/" aria-current={!detail ? "page" : undefined}>
          Explore cars
        </Link>
        <Link to="/compare">
          Compare <span>{count}</span>
        </Link>
        {viewingPath && (
          <Link to={viewingPath}>
            Viewing {viewingPath === "/outcome" ? "outcome" : "review"}
          </Link>
        )}
      </nav>
      <span className="night-header-note">
        THE SOURCE COLLECTION<span>07 / AUDITED SAMPLE</span>
      </span>
    </header>
  );
}

function NightPhoto({
  item,
  failed,
  eager = false,
  compact = false,
}: {
  item: ProofListing;
  failed: boolean;
  eager?: boolean;
  compact?: boolean;
}) {
  const plane = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = plane.current;
    if (!element || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          element.dataset.entered = "true";
          observer.disconnect();
        }
      },
      { threshold: 0.08 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const listing = item.detail.listing;
  const unavailable = failed && listing.ref.source_id === "27";
  return (
    <figure
      className={`night-photo ${listing.ref.source_id === "12" ? "night-photo--portrait" : ""} ${compact ? "night-photo--compact" : ""}`}
    >
      <div className="night-photo-plane" ref={plane}>
        <div className="night-photo-frame">
          <ListingPhoto
            identity={refKey(listing.ref)}
            src={
              unavailable
                ? "/__proof/controlled-unavailable-image"
                : listing.photo.url
            }
            alt={listing.photo.alt}
            loading={eager ? "eager" : "lazy"}
          />
        </div>
      </div>
      <figcaption>
        <span>
          {unavailable
            ? "Controlled photo-failure example"
            : "Original listing photograph"}
        </span>
        <span>
          {unavailable
            ? `Listing ${listing.ref.source_id}`
            : `One supplied view · ${item.source.photo_cell}`}
        </span>
      </figcaption>
    </figure>
  );
}

function SelectForCompare({
  item,
  selected,
  toggle,
}: Pick<NightShared, "selected" | "toggle"> & { item: ProofListing }) {
  const chosen = selected.some(
    (ref) => refKey(ref) === refKey(item.detail.listing.ref),
  );
  return (
    <Button
      variant="secondary"
      aria-pressed={chosen}
      aria-label={`${chosen ? "Remove" : "Compare"} listing ${item.detail.listing.ref.source_id}`}
      onClick={() => toggle(item.detail.listing.ref)}
    >
      {chosen ? "✓ In comparison" : "+ Compare"}
    </Button>
  );
}

function CarIdentity({
  item,
  detail = false,
  index,
}: {
  item: ProofListing;
  detail?: boolean;
  index?: number;
}) {
  const listing = item.detail.listing,
    model = sourceLabel(listing.model),
    make = sourceLabel(listing.make);
  const className = `night-model ${model.length > 10 ? "night-model--long" : ""}`;
  return (
    <div className="night-identity">
      <p className="night-source-order">
        <span>
          {detail
            ? "THE INSPECTION"
            : `RESULT ${String(index ?? 1).padStart(2, "0")} / SOURCE ORDER`}
        </span>
        <span>LISTING {listing.ref.source_id.padStart(2, "0")}</span>
      </p>
      <p className="night-make">
        <bdi>{make}</bdi>
      </p>
      {detail ? (
        <h1
          id="page-heading"
          tabIndex={-1}
          className={className}
          aria-label={`${make} ${model}`}
        >
          <bdi>{model}</bdi>
        </h1>
      ) : (
        <h2 className={className}>
          <Link to={listingPath(listing.ref)} aria-label={`${make} ${model}`}>
            <bdi>{model}</bdi>
          </Link>
        </h2>
      )}
      <p className="night-source-title">
        <span>Source title</span>
        <bdi dir="auto">{listing.title}</bdi>
      </p>
      <p className="night-mobile-price">
        Cash price <Fact fact={listing.cash_price} />
      </p>
      {item.conflicts.length > 0 && (
        <p className="night-mobile-conflict">
          <strong>Source conflict</strong> {item.conflicts[0]!.label}
        </p>
      )}
    </div>
  );
}

function DecisionFacts({
  item,
  detail = false,
}: {
  item: ProofListing;
  detail?: boolean;
}) {
  const listing = item.detail.listing;
  return (
    <div className="night-decisions">
      <div className="night-price">
        <span>Cash price</span>
        <strong>
          <Fact fact={listing.cash_price} />
        </strong>
        <small>
          {listing.cash_price.status === "known"
            ? "Listing claim · not independently verified"
            : listing.cash_price.status === "unknown" &&
                listing.cash_price.reason === "not_stated"
              ? "No cash price is stated in this listing."
              : "The cash price needs clarification."}
        </small>
      </div>
      <dl className="night-fact-strip">
        <div>
          <dt>Model year</dt>
          <dd>
            <Fact fact={listing.year} />
          </dd>
        </div>
        <div>
          <dt>Mileage</dt>
          <dd>
            <Fact fact={listing.mileage_km} unit="km" />
          </dd>
        </div>
        {detail && (
          <div className="night-trim">
            <dt>Trim</dt>
            <dd>
              <Fact fact={listing.trim} />
            </dd>
          </div>
        )}
      </dl>
      {item.conflicts.length > 0 ? (
        <div className="night-conflict-note">
          <span className="night-conflict-mark" aria-hidden="true">
            ≠
          </span>
          <p>
            <strong>Source conflict</strong>
            {item.conflicts[0]!.label}
          </p>
        </div>
      ) : (
        <p className="night-verification-note">
          Listing claims are not independently verified.
        </p>
      )}
    </div>
  );
}

function HeroCar({
  item,
  shared,
  detail = false,
}: {
  item: ProofListing;
  shared: NightShared;
  detail?: boolean;
}) {
  return (
    <article
      className={`night-hero ${detail ? "night-hero--detail" : ""}`}
      aria-label={`Listing ${item.detail.listing.ref.source_id}`}
    >
      <div className="night-info">
        <CarIdentity item={item} detail={detail} index={1} />
        <DecisionFacts item={item} detail={detail} />
        <div className="night-actions">
          {detail ? (
            <Button onClick={() => shared.startReview(item.detail.listing.ref)}>
              {shared.unresolved
                ? "View unresolved outcome"
                : "Review simulated viewing →"}
            </Button>
          ) : (
            <Link
              className="folio-button folio-button--primary"
              to={listingPath(item.detail.listing.ref)}
            >
              Inspect this car <span aria-hidden="true">↗</span>
            </Link>
          )}
          <SelectForCompare
            item={item}
            selected={shared.selected}
            toggle={shared.toggle}
          />
        </div>
      </div>
      <NightPhoto item={item} failed={shared.failPhoto} eager />
    </article>
  );
}

export function NightBrowse(
  shared: NightShared & { search: string; setSearch: (value: string) => void },
) {
  const [entry, setEntry] = useState(shared.search);
  const filtered = inventory.filter((item) =>
    `${item.heading} ${item.detail.listing.title}`
      .toLocaleLowerCase()
      .includes(shared.search.trim().toLocaleLowerCase()),
  );
  const lead = filtered[0],
    rest = filtered.slice(1);
  return (
    <section className="night-browse night-width">
      <div className="night-toolbar">
        <div>
          <p className="night-overline">THE INVENTORY</p>
          <h1 id="page-heading" tabIndex={-1}>
            Explore cars<span>{String(filtered.length).padStart(2, "0")}</span>
          </h1>
        </div>
        <form
          className="night-search"
          onSubmit={(event) => {
            event.preventDefault();
            shared.setSearch(entry);
          }}
        >
          <TextField
            type="search"
            label="Search these seven listings"
            value={entry}
            onChange={(event) => setEntry(event.target.value)}
            placeholder="Make, model or a word from the listing"
          />
          <Button type="submit">Find cars ↗</Button>
          {shared.search && (
            <Button
              variant="quiet"
              onClick={() => {
                setEntry("");
                shared.setSearch("");
              }}
            >
              Clear search
            </Button>
          )}
        </form>
      </div>
      <p className="night-results-context" role="status">
        {shared.search
          ? `${filtered.length} matching ${filtered.length === 1 ? "listing" : "listings"} for “${shared.search}”`
          : "Seven audited listings. Source order, with no ranking implied."}
      </p>
      {lead ? (
        <HeroCar item={lead} shared={shared} />
      ) : (
        <div className="night-empty">
          <h2>No matches in this sample.</h2>
          <p>Try a make or a word from a listing title.</p>
          <Button
            onClick={() => {
              setEntry("");
              shared.setSearch("");
            }}
          >
            Show all seven listings
          </Button>
        </div>
      )}
      {rest.length > 0 && (
        <section
          className="night-candidates"
          aria-labelledby="more-cars-heading"
        >
          <div className="night-section-heading">
            <h2 id="more-cars-heading">Keep looking.</h2>
            <p>
              {rest.length} more in this source sample{" "}
              <span aria-hidden="true">↓</span>
            </p>
          </div>
          <div className="night-candidate-list">
            {rest.map((item, index) => {
              const listing = item.detail.listing;
              return (
                <article
                  key={refKey(listing.ref)}
                  className="night-candidate"
                  aria-label={`Listing ${listing.ref.source_id}`}
                >
                  <span className="night-candidate-order">
                    {String(index + 2).padStart(2, "0")}
                  </span>
                  <NightPhoto item={item} failed={shared.failPhoto} compact />
                  <div className="night-candidate-identity">
                    <span className="night-candidate-make">
                      {sourceLabel(listing.make)}{" "}
                      <span> / {listing.ref.source_id}</span>
                    </span>
                    <h3>
                      <Link to={listingPath(listing.ref)}>
                        {sourceLabel(listing.model)}
                      </Link>
                    </h3>
                    <p dir="auto">
                      <bdi>{listing.title}</bdi>
                    </p>
                    {item.conflicts.length > 0 && (
                      <span className="night-candidate-warning">
                        Source details conflict
                      </span>
                    )}
                  </div>
                  <dl className="night-candidate-facts">
                    <div>
                      <dt>Cash price</dt>
                      <dd>
                        <Fact fact={listing.cash_price} />
                      </dd>
                    </div>
                    <div>
                      <dt>Model year</dt>
                      <dd>
                        <Fact fact={listing.year} />
                      </dd>
                    </div>
                  </dl>
                  <div className="night-candidate-actions">
                    <Link
                      className="folio-button folio-button--secondary"
                      to={listingPath(listing.ref)}
                    >
                      Inspect <span aria-hidden="true">↗</span>
                    </Link>
                    <SelectForCompare
                      item={item}
                      selected={shared.selected}
                      toggle={shared.toggle}
                    />
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </section>
  );
}

export function NightDetail(shared: NightShared) {
  const params = useParams();
  const item = inventory.find((candidate) => {
    const ref = candidate.detail.listing.ref;
    return (
      ref.namespace === params.namespace &&
      ref.snapshot_id === params.snapshot &&
      ref.source_id === params.sourceId
    );
  });
  if (!item)
    return (
      <section className="night-width night-empty">
        <h1 id="page-heading" tabIndex={-1}>
          This reference is not in the proof.
        </h1>
        <p>
          A different snapshot or listing ID cannot silently select another car.
        </p>
        <Link className="folio-button folio-button--primary" to="/">
          Explore the sample
        </Link>
      </section>
    );
  const listing = item.detail.listing;
  return (
    <section className="night-detail">
      <div className="night-width">
        <div className="night-detail-toolbar">
          <Link to="/" className="night-back">
            ← Back to the source collection
          </Link>
          <span>One car. A closer look.</span>
        </div>
        <HeroCar item={item} shared={shared} detail />
        <p className="night-inspection-caption">
          The photograph and listing are source material. Current condition and
          availability are not established.
        </p>
      </div>
      <section
        className="night-evidence night-mineral"
        aria-labelledby="evidence-heading"
      >
        <div className="night-width">
          <header className="night-evidence-heading">
            <div>
              <p className="night-overline">WHAT THE SOURCE SAYS</p>
              <h2 id="evidence-heading">
                {item.conflicts.length
                  ? "Where claims differ."
                  : "The details, in context."}
              </h2>
            </div>
            <p>
              Facts can be incomplete.
              <br />
              Claims can disagree.
              <br />
              Keep the difference visible.
            </p>
          </header>
          {item.conflicts.map((conflict) => (
            <div className="night-evidence-block" key={conflict.attribute}>
              <div className="night-evidence-label">
                <span>Source conflict</span>
                <h3>{conflict.attribute.replaceAll("_", " ")}</h3>
                <p>{conflict.label}</p>
              </div>
              <div className="night-claims">
                {conflict.fact.claims.map((claim, index) => (
                  <blockquote key={index}>
                    <span>
                      {claim.evidence[0]?.category === "structured_source"
                        ? "Structured field"
                        : claim.evidence[0]?.cell.startsWith("F")
                          ? "Listing title"
                          : "Listing description"}
                    </span>
                    <strong>
                      <bdi>{claim.value}</bdi>
                    </strong>
                    <p dir="auto">“{claim.evidence[0]?.raw_text}”</p>
                    <cite>
                      {item.source.sheet} ·{" "}
                      {claim.evidence.map((e) => e.cell).join(" / ")}
                    </cite>
                  </blockquote>
                ))}
              </div>
              <p className="night-no-resolution">
                No preferred value has been selected. All claims remain
                unverified.
              </p>
            </div>
          ))}
          <div className="night-source-disclosures">
            {item.detail.description.trim() === "." && (
              <p className="night-missing-description">
                No meaningful description is supplied. The source cell contains
                only a dot.
              </p>
            )}
            <details>
              <summary>
                Read the original listing description{" "}
                <span>{item.source.description_cell} ↗</span>
              </summary>
              <p className="folio-source-text" dir="auto">
                {item.detail.description}
              </p>
              <p>
                Original listing text; offers, contact details and condition
                claims are unverified source content.
              </p>
            </details>
            <details>
              <summary>
                Source identity and provenance <span>↗</span>
              </summary>
              <dl>
                <dt>Workbook SHA-256</dt>
                <dd>{item.source.workbook_sha256}</dd>
                <dt>Sheet / source ID</dt>
                <dd>
                  {item.source.sheet} / {listing.ref.source_id}
                </dd>
                <dt>Title / description / photo cells</dt>
                <dd>
                  {item.source.title_cell} / {item.source.description_cell} /{" "}
                  {item.source.photo_cell}
                </dd>
                <dt>Proof-only snapshot</dt>
                <dd>{listing.ref.snapshot_id}</dd>
                <dt>Original trim field · {item.source.trim_cell}</dt>
                <dd>
                  {item.source.trim_raw}
                  {item.source.trim_raw === "other"
                    ? " (placeholder; displayed as not stated)"
                    : ""}
                </dd>
              </dl>
            </details>
          </div>
        </div>
      </section>
    </section>
  );
}
