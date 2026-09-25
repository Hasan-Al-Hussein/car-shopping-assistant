export { CinemaHeader } from "../shared/ui/CinemaHeader";
import { CinematicHero } from "../shared/ui/CinematicHero";
import { CinemaIcon as Icon } from "../shared/ui/CinemaIcon";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../shared/ui/Button";
import { ListingPhoto } from "../shared/ui/ListingPhoto";
import { TextField } from "../shared/ui/TextField";
import { Fact } from "./Fact";
import { proofListings } from "./fixtures";
import { displayCarName } from "./displayNames";
import { listingPath, refKey, type ProofListing, type Ref } from "./types";
import { InternalPageHeader } from "../shared/ui/inner/InternalPageHeader";
import { VehicleSummaryCard } from "../shared/ui/inner/VehicleSummaryCard";
import { ListingDetails } from "../shared/ui/inner/ListingDetails";
import { TaskState } from "../shared/ui/inner/TaskState";

export type CinemaShared = {
  selected: Ref[];
  toggle: (ref: Ref) => void;
  failPhoto: boolean;
  startReview: (ref: Ref) => void;
  unresolved: boolean;
};
const inventory: ProofListing[] = [...proofListings].sort(
  (a, b) =>
    Number(a.source.title_cell.slice(1)) - Number(b.source.title_cell.slice(1)),
);
const label = (fact: ProofListing["detail"]["listing"]["make"]) =>
  fact.status === "known" ? displayCarName(fact.value) : "Not stated";

function CompareControl({
  item,
  selected,
  toggle,
}: { item: ProofListing } & Pick<CinemaShared, "selected" | "toggle">) {
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
      {chosen ? "✓ Selected" : "+ Compare"}
    </Button>
  );
}

function SourcePhoto({
  item,
  failed,
  eager = false,
}: {
  item: ProofListing;
  failed: boolean;
  eager?: boolean;
}) {
  const listing = item.detail.listing;
  const unavailable = failed && listing.ref.source_id === "27";
  return (
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
  );
}

function ListingCard({
  item,
  shared,
  index,
}: {
  item: ProofListing;
  shared: CinemaShared;
  index: number;
}) {
  const listing = item.detail.listing;
  return (
    <article
      className="cinema-car"
      data-reveal={refKey(listing.ref)}
      aria-label={`Listing ${listing.ref.source_id}`}
    >
      <div
        className={`cinema-car-photo ${listing.ref.source_id === "12" ? "cinema-car-photo--portrait" : ""}`}
      >
        <SourcePhoto item={item} failed={shared.failPhoto} eager={index < 3} />
        <span className="cinema-photo-label">Original listing photo</span>
      </div>
      <div className="cinema-car-body">
        <p className="cinema-car-make">
          <bdi>{label(listing.make)}</bdi>
        </p>
        <h3>
          <Link to={listingPath(listing.ref)}>
            <bdi>{label(listing.model)}</bdi>
          </Link>
        </h3>
        <div className="cinema-car-facts">
          <span>
            Model year <Fact fact={listing.year} />
          </span>
          <span>
            Trim <Fact fact={listing.trim} />
          </span>
        </div>
        <div className="cinema-car-price">
          <span>Cash price</span>
          <strong>
            <Fact fact={listing.cash_price} />
          </strong>
        </div>
        {item.conflicts.length > 0 ? (
          <p className="cinema-warning">
            <span aria-hidden="true">≠</span>
            <span>{item.conflicts[0]!.label}</span>
          </p>
        ) : (
          <p className="cinema-claim-note">
            Listing claims · not independently verified
          </p>
        )}
        <div className="cinema-card-actions">
          <CompareControl
            item={item}
            selected={shared.selected}
            toggle={shared.toggle}
          />
          <Link
            className="folio-button folio-button--quiet"
            to={listingPath(listing.ref)}
          >
            View details <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </div>
    </article>
  );
}

export function CinemaBrowse(
  shared: CinemaShared & {
    search: string;
    setSearch: (value: string) => void;
    inner?: boolean;
  },
) {
  const [entry, setEntry] = useState(shared.search);
  const filtered = inventory.filter((item) =>
    `${item.heading} ${item.detail.listing.title}`
      .toLocaleLowerCase()
      .includes(shared.search.trim().toLocaleLowerCase()),
  );
  function applySearch(value: string) {
    setEntry(value);
    shared.setSearch(value);
    document
      .getElementById("collection")
      ?.scrollIntoView({ behavior: "instant", block: "start" });
    requestAnimationFrame(() =>
      document
        .getElementById("collection-heading")
        ?.focus({ preventScroll: true }),
    );
  }
  if (shared.inner)
    return (
      <section
        className="inner-browse cinema-width"
        id="collection"
        aria-labelledby="page-heading"
      >
        <InternalPageHeader
          compact
          eyebrow="Explore the source collection"
          title="Find your next car."
        >
          <span>
            Seven original listings. Compare what is stated, and keep the
            unanswered questions in view.
          </span>
        </InternalPageHeader>
        <div className="inner-browse-results">
          <h2
            id="collection-heading"
            tabIndex={-1}
            className="folio-visually-hidden"
          >
            Search results
          </h2>
          <div className="inner-search-toolbar">
            <form
              id="listing-search"
              className="cinema-search"
              onSubmit={(event) => {
                event.preventDefault();
                applySearch(entry);
              }}
            >
              <TextField
                type="search"
                label="Search these seven listings"
                value={entry}
                onChange={(event) => setEntry(event.target.value)}
                placeholder="Make, model or listing title"
              />
              <Button type="submit">Find cars</Button>
              {shared.search && (
                <Button variant="quiet" onClick={() => applySearch("")}>
                  Clear
                </Button>
              )}
            </form>
          </div>
          <div className="inner-results-heading">
            <p role="status">
              {shared.search
                ? `${filtered.length} matching ${filtered.length === 1 ? "listing" : "listings"} for “${shared.search}”`
                : "7 listings to explore"}
            </p>
            <span>
              Workbook order · current availability is not established
            </span>
          </div>
          <div className="inner-inventory-grid">
            {filtered.map((item, index) => (
              <VehicleSummaryCard
                key={refKey(item.detail.listing.ref)}
                listing={item.detail.listing}
                href={listingPath(item.detail.listing.ref)}
                selected={shared.selected.some(
                  (ref) => refKey(ref) === refKey(item.detail.listing.ref),
                )}
                onToggle={() => shared.toggle(item.detail.listing.ref)}
                eager={index < 3}
                photoFailure={
                  shared.failPhoto && item.detail.listing.ref.source_id === "27"
                }
              />
            ))}
          </div>
          {!filtered.length && (
            <TaskState
              title="No matching cars in this sample."
              eyebrow="Try a different search"
              actions={
                <Button onClick={() => applySearch("")}>
                  Show all seven listings
                </Button>
              }
            >
              <p>Try a make, model or a word from an original listing title.</p>
            </TaskState>
          )}
          <div className="inner-browse-footnote">
            <Icon kind="source" />
            <p>
              Listing claims stay separate from verified facts. Unknown does not
              mean absent or zero.
            </p>
            <Link to="/compare">
              Open comparison <Icon kind="arrow" />
            </Link>
          </div>
        </div>
      </section>
    );
  return (
    <>
      {!shared.inner && <CinematicHero applySearch={applySearch} />}
      <div className="cinema-value-strip">
        <div className="cinema-width">
          <a href="#collection">
            <Icon kind="search" />
            <span>
              <strong>Explore with intention</strong>
              <small>Search the seven-listing preview.</small>
            </span>
          </a>
          <a href="#collection">
            <Icon kind="source" />
            <span>
              <strong>The details stay visible</strong>
              <small>See missing and conflicting claims.</small>
            </span>
          </a>
          <Link to="/compare">
            <Icon kind="compare" />
            <span>
              <strong>Find your perspective</strong>
              <small>Compare up to three cars, side by side.</small>
            </span>
          </Link>
        </div>
      </div>
      <section
        className="cinema-collection cinema-width"
        id="collection"
        aria-labelledby="collection-heading"
      >
        <div className="cinema-collection-intro">
          <p className="cinema-eyebrow">EXPLORE YOUR OPTIONS</p>
          <h2 id="collection-heading" tabIndex={-1}>
            <span className="cinema-desktop-copy">
              A car for your
              <br />
              <em>next chapter.</em>
            </span>
            <span className="cinema-mobile-copy">Explore the cars.</span>
          </h2>
          {shared.inner && (
            <h1 id="page-heading" tabIndex={-1}>
              Explore the cars.
            </h1>
          )}
          <p>
            Look beyond the first impression. Get to know the cars, and the
            questions worth asking.
          </p>
          <a className="cinema-text-link" href="#listing-search">
            Find a make or model <span aria-hidden="true">↗</span>
          </a>
          <p className="cinema-sample-note">
            Seven source listings, in workbook order. No ranking or current
            availability is implied.
          </p>
        </div>
        <div className="cinema-results">
          <form
            id="listing-search"
            className="cinema-search"
            onSubmit={(e) => {
              e.preventDefault();
              applySearch(entry);
            }}
          >
            <TextField
              type="search"
              label="Search these seven listings"
              value={entry}
              onChange={(e) => setEntry(e.target.value)}
              placeholder="Make, model or listing title"
            />
            <Button type="submit">Find cars</Button>
            {shared.search && (
              <Button variant="quiet" onClick={() => applySearch("")}>
                Clear
              </Button>
            )}
          </form>
          <p className="cinema-result-count" role="status">
            {shared.search
              ? `${filtered.length} matching ${filtered.length === 1 ? "listing" : "listings"} for “${shared.search}”`
              : "7 listings to explore"}
          </p>
          <div className="cinema-cards">
            {filtered.map((item, index) => (
              <ListingCard
                key={refKey(item.detail.listing.ref)}
                item={item}
                shared={shared}
                index={index}
              />
            ))}
          </div>
          {filtered.length === 0 && (
            <div className="cinema-empty">
              <h3>No matching cars in this sample.</h3>
              <p>Try a different make or a word from the title.</p>
              <Button onClick={() => applySearch("")}>
                Show all seven listings
              </Button>
            </div>
          )}
        </div>
      </section>
      <section
        className="cinema-compare-invitation cinema-width"
        data-reveal="comparison-invitation"
        aria-labelledby="compare-invitation-heading"
      >
        <div className="cinema-compare-story">
          <p className="cinema-eyebrow">A DIFFERENT POINT OF VIEW</p>
          <h2 id="compare-invitation-heading">
            Good decisions
            <br />
            start side by side.
          </h2>
          <p>
            Bring up to three cars together. Compare their stated facts and keep
            the unanswered questions in view.
          </p>
          <Link className="folio-button folio-button--primary" to="/compare">
            Open comparison <span aria-hidden="true">↗</span>
          </Link>
        </div>
        <div className="cinema-compare-art">
          <img
            src="/cinematic/editorial/alpine-road.jpg"
            alt="Illustrative mountain drive, not a listing"
            loading="lazy"
          />
          <div>
            <span>
              {shared.selected.length
                ? `${shared.selected.length} of 3 selected`
                : "Your comparison starts with a car."}
            </span>
            <p>
              {shared.selected.length
                ? "Your current selection is kept while you explore."
                : "Choose + Compare on any listing to begin."}
            </p>
          </div>
          <small>Illustrative photograph · Zieben VH / Unsplash</small>
        </div>
      </section>
    </>
  );
}

function Evidence({ item }: { item: ProofListing }) {
  const listing = item.detail.listing;
  return (
    <section className="cinema-evidence" aria-labelledby="evidence-heading">
      <div className="cinema-evidence-intro">
        <p className="cinema-eyebrow">A CLOSER LOOK</p>
        <h2 id="evidence-heading" tabIndex={-1}>
          The details.
          <br />
          <em>In their own words.</em>
        </h2>
        <p>
          The original listing may be incomplete or inconsistent. These are
          source claims, not independently verified facts.
        </p>
      </div>
      <div className="cinema-evidence-content">
        {item.conflicts.map((conflict) => (
          <div className="cinema-conflict-block" key={conflict.attribute}>
            <p className="cinema-conflict-label">
              Source conflict · {conflict.attribute.replaceAll("_", " ")}
            </p>
            <h3>{conflict.label}</h3>
            <div className="cinema-claims">
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
            <p className="cinema-unresolved-fact">
              No preferred value has been selected. All claims remain
              unverified.
            </p>
          </div>
        ))}
        <details>
          <summary>
            Source identity and provenance <span aria-hidden="true">+</span>
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
    </section>
  );
}

export function CinemaDetail(shared: CinemaShared) {
  const params = useParams();
  const item = inventory.find(
    ({
      detail: {
        listing: { ref },
      },
    }) =>
      ref.namespace === params.namespace &&
      ref.snapshot_id === params.snapshot &&
      ref.source_id === params.sourceId,
  );
  if (!item)
    return (
      <section className="inner-page cinema-width">
        <InternalPageHeader
          compact
          eyebrow="Exact source reference"
          title="This listing is unavailable."
        >
          <span>
            A different snapshot or listing cannot silently replace this car.
          </span>
        </InternalPageHeader>
        <TaskState
          title="Continue with the source collection."
          actions={
            <Link to="/cars" className="folio-button folio-button--primary">
              Explore the sample
            </Link>
          }
        >
          <p>
            This exact reference is not included in the seven-listing design
            proof.
          </p>
        </TaskState>
      </section>
    );
  return (
    <ListingDetails
      detail={item.detail}
      backHref="/cars"
      preview
      photoFailure={
        shared.failPhoto && item.detail.listing.ref.source_id === "27"
      }
      photoCaption={`One supplied view · ${item.source.photo_cell}`}
      extraEvidence={<Evidence item={item} />}
      actions={
        <>
          <Button onClick={() => shared.startReview(item.detail.listing.ref)}>
            {shared.unresolved
              ? "View unresolved outcome"
              : "Review simulated viewing →"}
          </Button>
          <CompareControl
            item={item}
            selected={shared.selected}
            toggle={shared.toggle}
          />
          <p className="inner-muted">
            A design preview. Nothing is reserved or sent.
          </p>
        </>
      }
    />
  );
}
