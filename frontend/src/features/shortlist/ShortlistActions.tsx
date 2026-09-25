import { useSyncExternalStore } from "react";
import { Link } from "react-router";
import { useIdentity, useServices } from "../../app/ServicesProvider";
import { listingPath, refKey, type InventoryRef } from "../../app/routes";
import { Button } from "../../shared/ui/Button";

export function ShortlistAction({
  inventoryRef,
  remove = false,
  openIdentity,
}: {
  inventoryRef: InventoryRef;
  remove?: boolean;
  openIdentity?: () => void;
}) {
  const services = useServices(),
    identity = useIdentity();
  const state = useSyncExternalStore(
    services.shortlist.subscribe,
    services.shortlist.getSnapshot,
  );
  const saved = state.membership[refKey(inventoryRef)];
  const unavailable = ["reading", "pending", "unknown", "blocked"].includes(
    state.phase,
  );
  if (identity.phase !== "recognized")
    return (
      <Button
        variant="secondary"
        onClick={openIdentity}
        disabled={!openIdentity}
      >
        Enable local access to save
      </Button>
    );
  if (!remove && saved === true)
    return (
      <Link className="folio-button folio-button--secondary" to="/shortlist">
        View saved cars
      </Link>
    );
  return (
    <Button
      variant="secondary"
      disabled={unavailable || (remove && saved === false)}
      onClick={async (event) => {
        const initiatingButton = event.currentTarget;
        await services.shortlist.change(inventoryRef, !remove);
        const latest = services.shortlist.getSnapshot();
        if (
          remove &&
          latest.phase === "idle" &&
          latest.membership[refKey(inventoryRef)] === false &&
          (document.activeElement === initiatingButton ||
            document.activeElement === document.body)
        )
          document
            .getElementById("page-heading")
            ?.focus({ preventScroll: true });
      }}
      aria-label={`${remove ? "Remove saved" : "Save"} listing ${inventoryRef.source_id}`}
    >
      {remove ? "Remove saved car" : "Save car"}
    </Button>
  );
}

export function ShortlistNotice() {
  const services = useServices(),
    identity = useIdentity();
  const state = useSyncExternalStore(
    services.shortlist.subscribe,
    services.shortlist.getSnapshot,
  );
  if (identity.phase !== "recognized" || !state.notice) return null;
  return (
    <aside
      className="inner-shortlist-notice cinema-width"
      aria-label="Shortlist action status"
    >
      <p role="status">{state.notice}</p>
      {(state.phase === "unknown" || state.phase === "blocked") && (
        <>
          <p>
            Retry uses the same original action. If it was not applied, it may
            now make that requested change.
          </p>
          <Button
            variant="secondary"
            onClick={() => void services.shortlist.reconcile()}
          >
            Retry original shortlist action
          </Button>
        </>
      )}
      {state.ref && (
        <Link to={listingPath(state.ref)}>Inspect this exact car</Link>
      )}
      <Link to="/shortlist">Open saved cars</Link>
    </aside>
  );
}
