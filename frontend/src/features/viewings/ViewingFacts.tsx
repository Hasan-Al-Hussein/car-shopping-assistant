import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import type { Schema } from "../../shared/api/contracts";
import { useServices } from "../../app/ServicesProvider";
import { listingPath, refKey } from "../../app/routes";
import {
  listingName,
  VehicleSummaryCard,
} from "../../shared/ui/inner/VehicleSummaryCard";
import { TaskState } from "../../shared/ui/inner/TaskState";

export const viewingTime = (value: string, zone: string) =>
  new Intl.DateTimeFormat("en-GB", {
    timeZone: zone,
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));

export function ViewingVehicle({
  inventoryRef,
}: {
  inventoryRef: Schema<"InventoryRef">;
}) {
  const services = useServices();
  const result = useQuery(
    services.queries.publicRead(
      "get_listing",
      { path: inventoryRef },
      inventoryRef.snapshot_id,
    ),
  );
  const detail = result.data?.data;
  if (detail && (detail.state === "current" || detail.state === "historical"))
    return (
      <VehicleSummaryCard
        listing={detail.listing}
        href={listingPath(inventoryRef)}
        historical={detail.state === "historical"}
        eager
      />
    );
  return (
    <TaskState
      title={
        result.isPending
          ? "Loading the selected car…"
          : "Car details unavailable."
      }
      busy={result.isPending}
      actions={
        <Link to={listingPath(inventoryRef)}>Inspect the exact car</Link>
      }
    >
      <p>
        The exact reference is retained. Source details have not been replaced.
      </p>
    </TaskState>
  );
}

export function LeadFacts({ values }: { values: Schema<"LeadValues"> }) {
  const contact = (value: Schema<"ContactValue">) =>
    value.state === "provided"
      ? value.value
      : value.state === "declined"
        ? "Declined"
        : "Not provided";
  const budget = values.budget;
  const amount = (value: number | null | undefined) =>
    value == null
      ? "open"
      : budget.value?.currency === "AED"
        ? (value / 100).toLocaleString("en-AE", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
        : `${value} minor units`;
  return (
    <dl className="inner-record-facts">
      <div>
        <dt>Cash budget</dt>
        <dd>
          {budget.state === "provided" && budget.value
            ? `${budget.value.currency} · ${amount(budget.value.minimum)}–${amount(budget.value.maximum)}`
            : budget.state === "declined"
              ? "Declined"
              : "Not provided"}
        </dd>
      </div>
      <div>
        <dt>Buyer needs</dt>
        <dd>
          {values.requirements.length
            ? values.requirements.join("; ")
            : "Not provided"}
        </dd>
      </div>
      <div>
        <dt>Email</dt>
        <dd>
          <bdi>{contact(values.email)}</bdi>
        </dd>
      </div>
      <div>
        <dt>Phone</dt>
        <dd>
          <bdi>{contact(values.phone)}</bdi>
        </dd>
      </div>
      <div>
        <dt>Selected source listings</dt>
        <dd>
          {values.selected_refs.map((ref) => (
            <p key={JSON.stringify(ref)}>
              <Link to={listingPath(ref)}>Listing {ref.source_id}</Link>
            </p>
          ))}
        </dd>
      </div>
    </dl>
  );
}

export function ReviewFacts({ review }: { review: Schema<"BookingReview"> }) {
  const services = useServices();
  // ViewingVehicle already loads this exact ref. Observe its cache without another read.
  const result = useQuery({
    ...services.queries.publicRead(
      "get_listing",
      { path: review.ref },
      review.ref.snapshot_id,
    ),
    enabled: false,
  });
  const detail = result.data?.data;
  const listing =
    detail &&
    (detail.state === "current" || detail.state === "historical") &&
    refKey(detail.listing.ref) === refKey(review.ref)
      ? detail.listing
      : null;
  return (
    <>
      <dl className="inner-record-facts">
        <div>
          <dt>Original car</dt>
          <dd>
            <Link to={listingPath(review.ref)}>
              <bdi>{listing ? listingName(listing) : "Selected car"}</bdi>
              {listing?.year.status === "known" && <> · {listing.year.value}</>}
            </Link>
            <p>
              Listing {review.ref.source_id}
              {listing &&
                detail?.state === "historical" &&
                " · Historical source"}
            </p>
            <details>
              <summary>Source reference</summary>
              <p>
                {review.ref.namespace} · snapshot {review.ref.snapshot_id}
              </p>
            </details>
          </dd>
        </div>
        <div>
          <dt>Appointment type</dt>
          <dd>{review.appointment_type} · simulated</dd>
        </div>
        <div>
          <dt>Starts</dt>
          <dd>
            <time dateTime={review.starts_at_utc}>
              {viewingTime(review.starts_at_utc, review.timezone)}
            </time>
          </dd>
        </div>
        <div>
          <dt>Ends</dt>
          <dd>
            <time dateTime={review.ends_at_utc}>
              {viewingTime(review.ends_at_utc, review.timezone)}
            </time>
          </dd>
        </div>
        <div>
          <dt>Time zone</dt>
          <dd>{review.timezone}</dd>
        </div>
        <div>
          <dt>Venue</dt>
          <dd>{review.venue_label}</dd>
        </div>
      </dl>
      <p>
        No real appointment is reserved and no dealer or staff notification is
        sent.
      </p>
    </>
  );
}
