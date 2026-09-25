import { Link } from "react-router";
import type { ReactNode } from "react";
import type { Schema } from "../../api/contracts";
import { ListingPhoto } from "../ListingPhoto";
import { Button } from "../Button";
import { CinemaIcon } from "../CinemaIcon";
import { displayCarName } from "../displayNames";
import { ComparisonFact } from "./ComparisonFact";

const name = (fact: Schema<"ListingSummary">["make"]) =>
  fact.status === "known"
    ? displayCarName(fact.value)
    : fact.status === "conflicting"
      ? "Conflicting source claims"
      : "Not stated";
export const listingName = (listing: Schema<"ListingSummary">) =>
  `${name(listing.make)} ${name(listing.model)}`;

export function VehicleSummaryCard({
  listing,
  href,
  selected,
  onToggle,
  eager = false,
  photoFailure = false,
  historical = false,
  from,
  browseKey,
  extraAction,
}: {
  listing: Schema<"ListingSummary">;
  href: string;
  selected?: boolean;
  onToggle?: () => void;
  eager?: boolean;
  photoFailure?: boolean;
  historical?: boolean;
  from?: string;
  browseKey?: string;
  extraAction?: ReactNode;
}) {
  const ref = listing.ref;
  const warnings = listing.evidence_warnings ?? [];
  return (
    <article
      className="cinema-car inner-vehicle-card"
      data-reveal={JSON.stringify(listing.ref)}
      aria-label={`Listing ${ref.source_id}`}
    >
      <div className="inner-vehicle-image">
        <ListingPhoto
          identity={JSON.stringify(ref)}
          src={
            photoFailure
              ? "/__proof/controlled-unavailable-image"
              : listing.photo.url
          }
          alt={listing.photo.alt}
          loading={eager ? "eager" : "lazy"}
        />
      </div>
      <div className="inner-vehicle-body">
        <p className="inner-image-caption">
          {photoFailure
            ? "Controlled photo-failure example"
            : "Original listing photo"}
        </p>
        <h2>
          <Link to={href} state={from ? { from, browseKey } : undefined}>
            <bdi>{listingName(listing)}</bdi>
          </Link>
        </h2>
        {historical && (
          <p className="inner-notice">
            Historical snapshot · current availability is unknown.
          </p>
        )}
        <dl className="inner-vehicle-facts">
          <div>
            <dt>Model year</dt>
            <dd>
              <ComparisonFact fact={listing.year} showSources={false} />
            </dd>
          </div>
          <div>
            <dt>Trim</dt>
            <dd>
              <ComparisonFact fact={listing.trim} showSources={false} />
            </dd>
          </div>
        </dl>
        <div className="inner-vehicle-price">
          <span>Cash price</span>
          <ComparisonFact fact={listing.cash_price} showSources={false} />
        </div>
        <details className="inner-card-source">
          <summary>
            {warnings.length
              ? "Source details to check"
              : "Original listing details"}
          </summary>
          <p dir="auto">
            <bdi>{listing.title}</bdi>
          </p>
          {warnings.length > 0 && (
            <ul>
              {warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          )}
          <p>Listing claims, not independently verified.</p>
        </details>
        <div className="inner-vehicle-actions">
          <Link
            className="folio-button folio-button--primary"
            to={href}
            state={from ? { from, browseKey } : undefined}
          >
            View car <CinemaIcon kind="arrow" />
          </Link>
          {onToggle && (
            <Button
              variant="secondary"
              aria-pressed={selected}
              aria-label={`${selected ? "Remove" : "Compare"} listing ${ref.source_id}`}
              onClick={onToggle}
            >
              {selected ? "Selected" : "Compare"}
            </Button>
          )}
          {extraAction}
        </div>
      </div>
    </article>
  );
}
