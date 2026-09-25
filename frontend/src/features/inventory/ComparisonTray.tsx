import { useLayoutEffect, useRef, useState, type RefObject } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { useServices } from "../../app/ServicesProvider";
import { comparisonPath, refKey, type InventoryRef } from "../../app/routes";
import type { ResponseOf } from "../../shared/api/contracts";
import { ListingPhoto } from "../../shared/ui/ListingPhoto";
import { listingName } from "../../shared/ui/inner/VehicleSummaryCard";

function SelectedCar({
  inventoryRef,
  remove,
}: {
  inventoryRef: InventoryRef;
  remove: () => void;
}) {
  const services = useServices();
  // The immutable reference must match in full, including its snapshot. Reuse
  // a public search summary before making any additional detail request.
  const [summary] = useState(() =>
    services.queries.client
      .getQueriesData<ResponseOf<"search_inventory">>({
        predicate: (query) =>
          query.queryKey[0] === "public" &&
          query.queryKey[2] === "search_inventory",
      })
      .flatMap(([, result]) => result?.data.items ?? [])
      .find((item) => refKey(item.ref) === refKey(inventoryRef)),
  );
  const detail = useQuery({
    ...services.queries.publicRead(
      "get_listing",
      { path: inventoryRef },
      inventoryRef.snapshot_id,
    ),
    enabled: !summary,
    staleTime: Infinity,
  });
  const data = detail.data?.data;
  const listing =
    summary ?? (data && "listing" in data ? data.listing : undefined);
  const title = listing
    ? listingName(listing)
    : `Listing ${inventoryRef.source_id}`;
  return (
    <li className="inventory-tray-car">
      <div className="inventory-tray-photo">
        {listing ? (
          <ListingPhoto
            identity={refKey(inventoryRef)}
            src={listing.photo.url}
            alt=""
          />
        ) : (
          <span className="inventory-tray-photo-missing" aria-hidden="true">
            —
          </span>
        )}
      </div>
      <div className="inventory-tray-name">
        <bdi>{title}</bdi>
        {!listing && (
          <small>
            {detail.isPending ? "Loading details…" : "Details unavailable"}
          </small>
        )}
      </div>
      <button
        className="inventory-tray-remove"
        type="button"
        data-remove-ref={refKey(inventoryRef)}
        aria-label={`Remove ${title} (listing ${inventoryRef.source_id}) from comparison`}
        onClick={remove}
      >
        <span aria-hidden="true">×</span>
      </button>
    </li>
  );
}

export function ComparisonTray({
  refs,
  trayRef,
  browseKey,
  warning,
  remove,
}: {
  refs: InventoryRef[];
  trayRef: RefObject<HTMLElement | null>;
  browseKey?: string;
  warning: string | null;
  remove: (ref: InventoryRef) => void;
}) {
  const nextFocus = useRef<string | null>(null);
  useLayoutEffect(() => {
    if (!nextFocus.current) return;
    const target = [
      ...(trayRef.current?.querySelectorAll<HTMLButtonElement>(
        "[data-remove-ref]",
      ) ?? []),
    ].find((button) => button.dataset.removeRef === nextFocus.current);
    target?.focus({ preventScroll: true });
    nextFocus.current = null;
  }, [refs, trayRef]);
  const removeCar = (ref: InventoryRef, index: number) => {
    const next = refs[index + 1] ?? refs[index - 1];
    if (next) nextFocus.current = refKey(next);
    else
      (
        document.getElementById("collection-heading") ??
        document.getElementById("page-heading")
      )?.focus({ preventScroll: true });
    remove(ref);
  };
  return (
    <aside
      ref={trayRef}
      className="proof-selection inventory-comparison-tray"
      aria-label="Comparison selection"
    >
      <span className="inventory-tray-count" role="status">
        {refs.length} of 3 selected
      </span>
      <ul className="inventory-tray-cars">
        {refs.map((ref, index) => (
          <SelectedCar
            key={refKey(ref)}
            inventoryRef={ref}
            remove={() => removeCar(ref, index)}
          />
        ))}
      </ul>
      <Link
        className="folio-button folio-button--primary"
        to={comparisonPath(refs)}
        state={{ browseKey }}
      >
        Compare cars →
      </Link>
      {warning && (
        <p className="proof-selection-warning" role="status">
          {warning}
        </p>
      )}
    </aside>
  );
}
