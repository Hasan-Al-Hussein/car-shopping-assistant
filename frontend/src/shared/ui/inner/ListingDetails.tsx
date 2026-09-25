import { useLayoutEffect, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import type { Schema } from "../../api/contracts";
import { ListingPhoto } from "../ListingPhoto";
import { CinemaIcon } from "../CinemaIcon";
import { ComparisonFact } from "./ComparisonFact";
import { listingName } from "./VehicleSummaryCard";
import { TaskSupport } from "./TaskState";
import { InternalPageHeader } from "./InternalPageHeader";

export function ListingDetails({
  detail,
  backHref,
  backState,
  actions,
  preview = false,
  photoFailure = false,
  photoCaption,
  extraEvidence,
}: {
  detail: Schema<"ListingDetail">;
  backHref: string;
  backState?: { browseKey?: string };
  actions: ReactNode;
  preview?: boolean;
  photoFailure?: boolean;
  photoCaption?: string;
  extraEvidence?: ReactNode;
}) {
  const listing = detail.listing;
  const warnings = listing.evidence_warnings ?? [];
  const location = useLocation();
  useLayoutEffect(() => {
    if (
      ["#detail-specifications", "#detail-description"].includes(location.hash)
    ) {
      const heading = document.getElementById(location.hash.slice(1));
      heading?.scrollIntoView({ block: "start" });
      heading?.focus({ preventScroll: true });
    }
  }, [location.hash, location.key]);
  return (
    <section className="inner-detail cinema-width">
      <Link className="inner-back" to={backHref} state={backState}>
        ← Back to the cars
      </Link>
      <InternalPageHeader
        detail
        eyebrow="Your selected car"
        title={<bdi>{listingName(listing)}</bdi>}
        listingPhoto={{
          identity: JSON.stringify(listing.ref),
          src:
            !photoFailure && listing.photo.state === "source_present"
              ? listing.photo.url
              : null,
        }}
        art={{
          src: "/cinematic/headers/viewing-parked-car.jpg",
          width: 1600,
          height: 1067,
          position: "60% 75%",
          fade: "short",
        }}
      >
        <span>
          Original source details.
          <br />
          Questions worth asking.
        </span>
      </InternalPageHeader>
      {detail.state === "historical" && (
        <p className="inner-notice">
          Historical source snapshot. Current condition and availability are not
          established.
        </p>
      )}
      <div className="inner-detail-overview">
        <figure className="inner-detail-photo">
          <ListingPhoto
            identity={JSON.stringify(listing.ref)}
            src={
              photoFailure
                ? "/__proof/controlled-unavailable-image"
                : listing.photo.url
            }
            alt={listing.photo.alt}
            loading="eager"
          />
          <figcaption>
            <span>
              {photoFailure
                ? "Controlled photo-failure example"
                : "Original listing photograph"}
            </span>
            <span>{photoCaption ?? "One supplied view"}</span>
          </figcaption>
        </figure>
        <section
          className="inner-detail-decision"
          aria-labelledby="detail-price-heading"
        >
          <p className="inner-eyebrow" id="detail-price-heading">
            Cash price
          </p>
          <div className="inner-detail-price">
            <ComparisonFact fact={listing.cash_price} />
          </div>
          <p className="inner-muted">
            Source claim · not independently verified
          </p>
          <dl className="inner-detail-quick">
            <div>
              <dt>Model year</dt>
              <dd>
                <ComparisonFact fact={listing.year} />
              </dd>
            </div>
            <div>
              <dt>Trim</dt>
              <dd>
                <ComparisonFact fact={listing.trim} />
              </dd>
            </div>
            <div>
              <dt>Mileage</dt>
              <dd>
                <ComparisonFact fact={listing.mileage_km} unit="km" />
              </dd>
            </div>
          </dl>
          {warnings.length > 0 && (
            <details className="inner-card-source">
              <summary>Source details need checking</summary>
              <ul>
                {warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </details>
          )}
          <p className="inner-notice">
            Current condition and availability are not established.
          </p>
          <div className="inner-detail-actions">{actions}</div>
        </section>
      </div>
      <div className="inner-detail-lower">
        <div className="inner-detail-record">
          <section
            className="inner-detail-section"
            data-reveal="detail-specifications"
            aria-labelledby="detail-specifications"
          >
            <p className="inner-eyebrow">The same careful questions</p>
            <h2 id="detail-specifications" tabIndex={-1}>
              Specifications & history.
            </h2>
            <dl className="inner-fact-grid">
              {(
                [
                  ["Body type", detail.body_type],
                  ["Fuel", detail.fuel_type],
                  ["Transmission", detail.transmission],
                  ["Location", detail.location],
                  ["Service history", detail.service_history],
                  ["Warranty", detail.warranty],
                ] as const
              ).map(([label, fact]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>
                    <ComparisonFact fact={fact} />
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          <section
            className="inner-detail-section"
            data-reveal="detail-description"
            aria-labelledby="detail-description"
          >
            <p className="inner-eyebrow">In the source’s own words</p>
            <h2 id="detail-description" tabIndex={-1}>
              Original listing.
            </h2>
            <p className="inner-original-title" dir="auto">
              <bdi>{listing.title}</bdi>
            </p>
            {(detail.description.trim() === "." ||
              !detail.description.trim()) && (
              <p className="inner-muted">
                No substantive description is supplied. The original text is
                retained below.
              </p>
            )}
            <details className="inner-original-description">
              <summary>Read the complete description</summary>
              <p dir="auto">{detail.description}</p>
            </details>
            <p className="inner-muted">
              Offers, contacts and condition claims in the original text remain
              unverified.
            </p>
          </section>
          {extraEvidence}
        </div>
        <TaskSupport
          title="dubizzle car assistant"
          status={
            preview
              ? "Design preview · conversation unavailable"
              : "Conversation unavailable in this view"
          }
        >
          <div className="inner-support-response">
            <p>Start with what this listing leaves open.</p>
            <span>
              Missing information and conflicting claims need clarification
              before a decision.
            </span>
          </div>
          <a href="#detail-specifications">
            <CinemaIcon kind="source" />
            Inspect the source facts
            <CinemaIcon kind="arrow" />
          </a>
          <a href="#detail-description">
            <CinemaIcon kind="search" />
            Read the original description
            <CinemaIcon kind="arrow" />
          </a>
          <p>
            These actions navigate this car’s source details. No AI answer or
            reservation is created.
          </p>
        </TaskSupport>
      </div>
    </section>
  );
}
