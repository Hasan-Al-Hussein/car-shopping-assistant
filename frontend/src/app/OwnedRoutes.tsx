import { useState, useSyncExternalStore, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router";
import {
  ReviewFacts,
  ViewingVehicle,
  viewingTime,
} from "../features/viewings/ViewingFacts";
export { DraftRoute } from "../features/viewings/ViewingRoutes";
import { Button } from "../shared/ui/Button";
import { InternalPageHeader } from "../shared/ui/inner/InternalPageHeader";
import { TaskState, TaskSupport } from "../shared/ui/inner/TaskState";
import { VehicleSummaryCard } from "../shared/ui/inner/VehicleSummaryCard";
import { useIdentity, useServices } from "./ServicesProvider";
import { listingPath, refKey, parseOperationQuery } from "./routes";
import {
  InvalidRoute,
  ReadFailure,
  type Selection,
} from "../features/inventory/InventoryRoutes";
import { ShortlistAction } from "../features/shortlist/ShortlistActions";

export function OwnerGate({
  children,
  openIdentity,
}: {
  children: ReactNode;
  openIdentity: () => void;
}) {
  const identity = useIdentity();
  if (identity.phase !== "recognized")
    return (
      <section className="inner-page cinema-width">
        <InternalPageHeader
          compact
          eyebrow="Private to this browser"
          title="Enable saving and chat."
        >
          <span>
            Enable access in this browser to save cars and return to your
            conversations and viewing requests.
          </span>
        </InternalPageHeader>
        <div className="inner-state-layout">
          <TaskState
            title={
              identity.phase === "checking"
                ? "Checking your local access…"
                : identity.phase === "lost"
                  ? "Your local access has ended."
                  : "Continue with local access."
            }
            busy={identity.phase === "checking"}
            tone={identity.phase === "lost" ? "warning" : "neutral"}
            actions={
              <>
                <Button onClick={openIdentity}>Manage browser access</Button>
                <Link
                  className="folio-button folio-button--secondary"
                  to="/cars"
                >
                  Browse cars
                </Link>
              </>
            }
          >
            <p>
              {identity.phase === "checking"
                ? "Private information stays hidden while access is checked."
                : identity.notice ||
                  "This view is private to your local browser context. It cannot be recovered by entering a name."}
            </p>
          </TaskState>
          <TaskSupport
            title="Your browsing can continue."
            status="No local access needed"
          >
            <p>
              Explore original listings and compare up to three cars without
              opening a private context.
            </p>
            <p>
              Your display name cannot restore access if this browser loses it.
            </p>
          </TaskSupport>
        </div>
      </section>
    );
  return <div key={identity.epoch}>{children}</div>;
}

export function ShortlistRoute({ selection }: { selection?: Selection }) {
  const services = useServices();
  const shortlistState = useSyncExternalStore(
    services.shortlist.subscribe,
    services.shortlist.getSnapshot,
  );
  const [pagination, setPagination] = useState(() => ({
    changeCount: shortlistState.changeCount,
    pages: [null] as (string | null)[],
  }));
  const pages =
    pagination.changeCount === shortlistState.changeCount
      ? pagination.pages
      : [null];
  const setPages = (nextPages: (string | null)[]) =>
    setPagination({
      changeCount: shortlistState.changeCount,
      pages: nextPages,
    });
  const cursor = pages[pages.length - 1]!;
  const owner = services.owner.capture();
  const result = useQuery({
    ...services.queries.privateRead("get_shortlist", {
      query: { page_size: 20, cursor },
    }),
    queryFn: ({ signal }) =>
      services.shortlist.readPage(cursor, 20, owner, signal),
  });
  const nextCursor = result.data?.data.next_cursor;
  return (
    <section className="inner-page cinema-width">
      <InternalPageHeader
        compact
        eyebrow="Your local collection"
        title="Your saved cars."
        art={{
          src: "/cinematic/headers/detail-cabin.jpg",
          width: 1600,
          height: 1067,
          position: "60% center",
        }}
      >
        <span>
          Return to the original listings that matter to you. Saving does not
          reserve a car.
        </span>
      </InternalPageHeader>
      {result.isPending ? (
        <TaskState title="Loading your shortlist…" busy>
          <p>Checking the records attached to your local access.</p>
        </TaskState>
      ) : result.isError ? (
        <ReadFailure
          error={result.error}
          retry={() => (cursor ? setPages([null]) : void result.refetch())}
        />
      ) : (
        <>
          <div className="inner-results-heading">
            <p>{result.data.data.total} saved cars</p>
            <span>Saved references are separate from comparison.</span>
          </div>
          {!result.data.data.items.length ? (
            <TaskState
              eyebrow="A place to return to"
              title="No saved cars here yet."
              actions={
                <Link className="folio-button folio-button--primary" to="/cars">
                  Explore the cars
                </Link>
              }
            >
              <p>
                Comparison is available while you browse. It is separate from
                this saved shortlist.
              </p>
            </TaskState>
          ) : (
            <div className="inner-inventory-grid">
              {result.data.data.items.map((item) =>
                item.listing ? (
                  <VehicleSummaryCard
                    key={refKey(item.ref)}
                    listing={item.listing}
                    href={listingPath(item.ref)}
                    historical={item.state === "historical"}
                    selected={selection?.refs.some(
                      (ref) => refKey(ref) === refKey(item.ref),
                    )}
                    onToggle={
                      selection ? () => selection.toggle(item.ref) : undefined
                    }
                    extraAction={
                      <ShortlistAction inventoryRef={item.ref} remove />
                    }
                  />
                ) : (
                  <TaskState
                    key={refKey(item.ref)}
                    eyebrow="Saved reference retained"
                    title="This saved listing is unavailable."
                    tone="warning"
                    actions={
                      <>
                        <Link to={listingPath(item.ref)}>
                          Inspect the exact reference
                        </Link>
                        <ShortlistAction inventoryRef={item.ref} remove />
                      </>
                    }
                  >
                    <p>
                      The source listing has not been replaced by another row or
                      snapshot.
                    </p>
                  </TaskState>
                ),
              )}
            </div>
          )}
          {nextCursor && (
            <Button
              variant="secondary"
              onClick={() => setPages([...pages, nextCursor])}
            >
              Next saved cars
            </Button>
          )}
        </>
      )}
      {pages.length > 1 && (
        <div className="inner-pagination">
          <Button
            variant="secondary"
            onClick={() => setPages(pages.slice(0, -1))}
          >
            Previous saved cars
          </Button>
          <Button variant="quiet" onClick={() => setPages([null])}>
            Return to first saved page
          </Button>
        </div>
      )}
    </section>
  );
}

/** Retain only a disclosure preference while OwnerGate removes private content. */
export function OwnedOperationRoute({
  openIdentity,
}: {
  openIdentity: () => void;
}) {
  const identity = useIdentity();
  const { operationKey } = useParams();
  const location = useLocation();
  const [reference, setReference] = useState<{
    owner: string;
    operation: string;
    query: string;
    open: boolean;
  } | null>(null);
  const owner =
    identity.phase === "recognized" ? identity.identity?.context_id : null;
  const resetReference =
    !!reference &&
    (reference.operation !== operationKey ||
      reference.query !== location.search ||
      identity.phase === "anonymous" ||
      (identity.phase === "recognized" && reference.owner !== owner));
  // Lost/checking can be transient; private content remains gated until identity resolves.
  if (resetReference) setReference(null);
  const expanded =
    !resetReference &&
    !!reference &&
    reference.owner === owner &&
    reference.operation === operationKey &&
    reference.query === location.search &&
    reference.open;
  return (
    <OwnerGate openIdentity={openIdentity}>
      <OperationRoute
        referenceOpen={expanded}
        onReferenceToggle={(open) => {
          // Reuse the boolean only after this exact owner and route are recognized again.
          // No private payload or authority is retained, and another owner never inherits it.
          if (owner && operationKey)
            setReference({
              owner,
              operation: operationKey,
              query: location.search,
              open,
            });
        }}
      />
    </OwnerGate>
  );
}

export function OperationRoute({
  referenceOpen,
  onReferenceToggle,
}: {
  referenceOpen?: boolean;
  onReferenceToggle?: (open: boolean) => void;
} = {}) {
  const { operationKey } = useParams();
  const location = useLocation(),
    query = parseOperationQuery(location.search);
  if (
    !operationKey ||
    !/^[A-Za-z0-9_-]{43}$/.test(operationKey) ||
    !query.valid
  )
    return <InvalidRoute />;
  return (
    <OperationRead
      operationKey={operationKey}
      submittedStoreGeneration={query.generation}
      referenceOpen={referenceOpen}
      onReferenceToggle={onReferenceToggle}
    />
  );
}
function OperationRead({
  operationKey,
  submittedStoreGeneration,
  referenceOpen,
  onReferenceToggle,
}: {
  operationKey: string;
  submittedStoreGeneration: string | null;
  referenceOpen?: boolean;
  onReferenceToggle?: (open: boolean) => void;
}) {
  const services = useServices(),
    owner = services.owner.capture();
  const result = useQuery({
    ...services.queries.privateRead("get_operation", {
      path: { operation_key: operationKey },
      query: { submitted_store_generation: submittedStoreGeneration },
    }),
    ...(submittedStoreGeneration
      ? {
          queryFn: ({ signal }: { signal: AbortSignal }) =>
            services.viewings.readOperation(
              {
                key: operationKey,
                generation: submittedStoreGeneration,
                draftId: null,
              },
              owner,
              signal,
            ),
        }
      : {}),
  });
  const data = result.data?.data;
  return (
    <section className="inner-page cinema-width">
      <InternalPageHeader
        compact
        eyebrow="Keep the original action together"
        title="Your viewing request."
        art={{
          src: "/cinematic/headers/viewing-parked-car.jpg",
          width: 1600,
          height: 1067,
          position: "60% 75%",
        }}
      >
        <span>
          A status check reads the original action. It never submits a
          replacement.
          {!submittedStoreGeneration &&
            " This link is missing part of the original request reference. A missing result does not mean the viewing was not saved."}
        </span>
      </InternalPageHeader>
      {result.isPending ? (
        <TaskState title="Checking your viewing request…" busy>
          <p>Do not repeat an action while its result is unknown.</p>
        </TaskState>
      ) : result.isError &&
        data?.state !== "succeeded" &&
        data?.state !== "rejected" ? (
        <ReadFailure error={result.error} retry={() => void result.refetch()} />
      ) : (
        data && (
          <div
            className={
              "inner-operation-layout" +
              (data.state === "succeeded"
                ? " inner-operation-layout--receipt"
                : "")
            }
          >
            <div>
              {result.isError && (
                <div className="inner-record-note">
                  <p>
                    The last confirmed outcome remains below. The latest status
                    check failed, so its CSV observation has not been refreshed.
                  </p>
                  <ReadFailure
                    error={result.error}
                    retry={() => void result.refetch()}
                  />
                </div>
              )}
              <TaskState
                eyebrow={
                  data.state === "succeeded"
                    ? "Service-reported result"
                    : "Original operation retained"
                }
                title={
                  data.state === "succeeded"
                    ? "Simulated action saved."
                    : data.state === "rejected"
                      ? "Action rejected."
                      : "Outcome unknown."
                }
                tone={data.state === "succeeded" ? "success" : "warning"}
                actions={
                  <Button
                    onClick={() => {
                      if (!result.isFetching)
                        void result.refetch({ cancelRefetch: false });
                    }}
                    aria-disabled={result.isFetching}
                    aria-busy={result.isFetching}
                  >
                    Check viewing status
                  </Button>
                }
              >
                {result.isFetching && (
                  <p role="status">Checking the original viewing status…</p>
                )}
                <p>
                  {data.state === "succeeded"
                    ? "The service confirms a saved simulated action. This is not a real dealer reservation or delivery."
                    : data.state === "rejected"
                      ? "The service retained a rejection for this exact operation. This view does not submit a replacement."
                      : "We can’t yet confirm whether this simulated viewing was saved. Keep this request and check its status. Don’t submit a replacement for this viewing while the result is unknown."}
                </p>
                {data.state === "unresolved_generation" && (
                  <p>
                    We can’t match this request to the app’s current saved
                    records. The person running this app needs to check it
                    before you continue with this viewing.
                  </p>
                )}
              </TaskState>
              {data.state === "succeeded" && (
                <>
                  <ReviewFacts review={data.booking.review} />
                  <dl className="inner-record-facts inner-operation-facts">
                    <div>
                      <dt>Enquiry saved with this viewing</dt>
                      <dd>
                        This enquiry was saved with this viewing. Later edits
                        are separate.
                      </dd>
                    </div>
                    <div>
                      <dt>CSV export status</dt>
                      <dd>
                        {data.csv.state === "current"
                          ? "Up to date"
                          : data.csv.state === "pending"
                            ? "Not yet up to date"
                            : "Export needs attention"}
                        . Last checked{" "}
                        {viewingTime(data.csv.observed_at, "Asia/Dubai")} ·
                        Asia/Dubai.
                      </dd>
                    </div>
                    <div>
                      <dt>Dealer delivery</dt>
                      <dd>No external delivery is claimed.</dd>
                    </div>
                  </dl>
                  {data.csv.state !== "current" && (
                    <p className="inner-record-note">
                      Your simulated viewing and enquiry are saved. The CSV
                      export is not up to date. Checking its status will not
                      submit another viewing.
                    </p>
                  )}
                </>
              )}
              <details
                className="inner-operation-reference"
                open={referenceOpen}
                onToggle={(event) => {
                  if (
                    event.currentTarget.isConnected &&
                    event.currentTarget.open !== referenceOpen
                  )
                    onReferenceToggle?.(event.currentTarget.open);
                }}
              >
                <summary
                  onClick={(event) => {
                    if (!onReferenceToggle) return;
                    event.preventDefault();
                    onReferenceToggle(
                      !(event.currentTarget.parentElement as HTMLDetailsElement)
                        .open,
                    );
                  }}
                >
                  Request reference and record details
                </summary>
                <p>{data.operation_key}</p>
                {submittedStoreGeneration && (
                  <p>Submitted store generation: {submittedStoreGeneration}</p>
                )}
                {"original_store_generation" in data && (
                  <p>
                    Original store generation: {data.original_store_generation}
                  </p>
                )}
                {"observed_store_generation" in data && (
                  <p>
                    Observed store generation: {data.observed_store_generation}
                  </p>
                )}
                {data.state === "succeeded" && (
                  <>
                    <p>
                      Enquiry reference {data.lead.lead_id} · accepted revision{" "}
                      {data.lead.revision}.
                    </p>
                    <p>
                      Shared CSV state: {data.csv.state} · canonical version{" "}
                      {data.csv.canonical_version}; exported version{" "}
                      {data.csv.exported_version ?? "not yet observed"}. Store
                      generation: {data.csv.store_generation}.
                    </p>
                  </>
                )}
                {data.state === "rejected" && (
                  <p>
                    Retained rejection:{" "}
                    {data.rejection_code.replaceAll("_", " ")}
                  </p>
                )}
              </details>
              <Link className="inner-back" to="/cars">
                Continue exploring →
              </Link>
            </div>
            {data.state === "succeeded" ? (
              <ViewingVehicle inventoryRef={data.booking.review.ref} />
            ) : (
              <TaskSupport
                title={
                  data.state === "rejected"
                    ? "The rejection is retained."
                    : "One action. One reference."
                }
                status={
                  data.state === "rejected"
                    ? "Known outcome"
                    : "A safe next step"
                }
              >
                <p>
                  {data.state === "rejected"
                    ? "This operation did not create a booking or request a local enquiry. Its rejection remains attached to the original reference."
                    : "Keep checking this operation. A timeout or absent result does not establish that nothing was saved."}
                </p>
                <p>
                  No new booking or enquiry is submitted from this status page.
                </p>
              </TaskSupport>
            )}
          </div>
        )
      )}
    </section>
  );
}
