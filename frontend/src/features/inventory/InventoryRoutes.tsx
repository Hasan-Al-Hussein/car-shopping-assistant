import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import type { Schema } from "../../shared/api/contracts";
import { Button } from "../../shared/ui/Button";
import { TextField } from "../../shared/ui/TextField";
import { ListingPhoto } from "../../shared/ui/ListingPhoto";
import { Fact } from "../../shared/ui/Fact";
import { displayCarName } from "../../shared/ui/displayNames";
import { CinematicHero } from "../../shared/ui/CinematicHero";
import { ComparisonWorkspace } from "../../shared/ui/inner/ComparisonWorkspace";
import { InternalPageHeader } from "../../shared/ui/inner/InternalPageHeader";
import { TaskState } from "../../shared/ui/inner/TaskState";
import { VehicleSummaryCard } from "../../shared/ui/inner/VehicleSummaryCard";
import { ListingDetails } from "../../shared/ui/inner/ListingDetails";
import { failureMessage } from "../../app/BrowserServices";
import { InventoryFilters } from "./InventoryFilters";
import { InventorySkeleton } from "./InventorySkeleton";
import { readInventoryCatalog } from "./inventoryCatalog";
import { suggestInventoryQuery } from "./inventoryFacets";
import { validateRequestBody } from "../../../../contracts/generated/runtime";
import { useIdentity, useServices } from "../../app/ServicesProvider";
import { ShortlistAction } from "../shortlist/ShortlistActions";
import {
  criteriaErrorLabels,
  criteriaFromFilters,
  describeCriteria,
  filtersFromCriteria,
} from "./criteria";
import {
  browseQuery,
  comparisonPath,
  decodeRef,
  encodeRef,
  listingPath,
  parseBrowseQuery,
  parseComparison,
  refKey,
  safeReturnPath,
  type InventoryRef,
} from "../../app/routes";

export type Selection = {
  refs: InventoryRef[];
  toggle: (ref: InventoryRef) => void;
};
const name = (fact: Schema<"ListingSummary">["make"]) =>
  fact.status === "known"
    ? displayCarName(fact.value)
    : fact.status === "conflicting"
      ? "Conflicting source claims"
      : "Not stated";

export function ReadFailure({
  error,
  retry,
  retrying = false,
}: {
  error: unknown;
  retry?: () => void;
  retrying?: boolean;
}) {
  const location = useLocation();
  const fields = criteriaErrorLabels(error);
  const browsing = ["/", "/cars"].includes(location.pathname);
  const title = browsing
    ? "We couldn’t load the cars."
    : "We couldn’t load these details.";
  const action = retry && (
    <Button onClick={retry} disabled={retrying}>
      {retrying ? "Trying again…" : "Try again"}
    </Button>
  );
  if (location.pathname === "/")
    return (
      <div className="cinema-empty" role="status">
        <h2>{title}</h2>
        <p>{failureMessage(error)}</p>
        <p>
          Your search is still here. Try again when the connection is available.
        </p>
        {fields.length > 0 && (
          <p>
            Check these search fields: {fields.join(", ")}. Your entered
            criteria are retained.
          </p>
        )}
        {action}
      </div>
    );
  return (
    <TaskState
      title={title}
      tone="warning"
      actions={
        <>
          {action}
          {!browsing && <Link to="/cars">Browse cars</Link>}
        </>
      }
    >
      <p>{failureMessage(error)}</p>
      {browsing && (
        <p>
          Your search is still here. Try again when the connection is available.
        </p>
      )}
      {fields.length > 0 && (
        <p>
          Check these search fields: {fields.join(", ")}. Your entered criteria
          are retained.
        </p>
      )}
    </TaskState>
  );
}

function SearchTools({
  inner,
  children,
}: {
  inner: boolean;
  children: ReactNode;
}) {
  return inner ? (
    <div className="inner-search-toolbar">{children}</div>
  ) : (
    <>{children}</>
  );
}

export function InvalidRoute({
  detail = "This address contains an invalid or incomplete reference.",
}: {
  detail?: string;
}) {
  return (
    <section className="proof-page cinema-width">
      <InternalPageHeader
        compact
        eyebrow="A clear way back"
        title="This view is unavailable."
      >
        <span>The requested address could not be opened.</span>
      </InternalPageHeader>
      <TaskState
        title="Continue with the inventory."
        tone="warning"
        actions={
          <Link
            className="folio-button folio-button--primary"
            to="/cars"
            replace
            state={null}
          >
            Browse cars
          </Link>
        }
      >
        <p>{detail}</p>
      </TaskState>
    </section>
  );
}

function CompareButton({
  listing,
  selection,
}: {
  listing: Schema<"ListingSummary">;
  selection: Selection;
}) {
  const selected = selection.refs.some(
    (ref) => refKey(ref) === refKey(listing.ref),
  );
  return (
    <Button
      variant="secondary"
      aria-pressed={selected}
      aria-label={`${selected ? "Remove" : "Compare"} listing ${listing.ref.source_id}`}
      onClick={() => selection.toggle(listing.ref)}
    >
      {selected ? "✓ Selected" : "+ Compare"}
    </Button>
  );
}

function Photo({
  listing,
  eager = false,
}: {
  listing: Schema<"ListingSummary">;
  eager?: boolean;
}) {
  return (
    <ListingPhoto
      identity={refKey(listing.ref)}
      src={listing.photo.url}
      alt={listing.photo.alt}
      loading={eager ? "eager" : "lazy"}
    />
  );
}

export function InventoryCard({
  listing,
  selection,
  index,
  from,
  inner = false,
  browseKey,
  openIdentity,
}: {
  listing: Schema<"ListingSummary">;
  selection: Selection;
  index: number;
  from: string;
  inner?: boolean;
  browseKey?: string;
  openIdentity?: () => void;
}) {
  if (inner)
    return (
      <VehicleSummaryCard
        listing={listing}
        href={listingPath(listing.ref)}
        from={from}
        browseKey={browseKey}
        extraAction={
          <ShortlistAction
            inventoryRef={listing.ref}
            openIdentity={openIdentity}
          />
        }
        eager={index < 3}
        selected={selection.refs.some(
          (ref) => refKey(ref) === refKey(listing.ref),
        )}
        onToggle={() => selection.toggle(listing.ref)}
      />
    );
  return (
    <article
      className="cinema-car inventory-polish-card"
      data-reveal={refKey(listing.ref)}
      aria-label={`Listing ${listing.ref.source_id}`}
    >
      <div className="cinema-car-photo">
        <Photo listing={listing} eager={index < 3} />
        <span className="cinema-photo-label">Original listing photo</span>
      </div>
      <div className="cinema-car-body">
        <p className="cinema-car-make">
          <bdi>{name(listing.make)}</bdi>
        </p>
        <h3>
          <Link to={listingPath(listing.ref)} state={{ from, browseKey }}>
            <bdi>{name(listing.model)}</bdi>
          </Link>
        </h3>
        <div
          className="cinema-car-price"
          data-price-state={listing.cash_price.status}
        >
          <span>Cash price</span>
          <strong>
            <Fact fact={listing.cash_price} />
          </strong>
        </div>
        <dl className="cinema-car-facts">
          <div>
            <dt>Year</dt>
            <dd>
              <Fact fact={listing.year} />
            </dd>
          </div>
          <div>
            <dt>Trim</dt>
            <dd>
              <Fact fact={listing.trim} />
            </dd>
          </div>
        </dl>
        <details
          className="inventory-card-source"
          data-warning={!!listing.evidence_warnings?.length}
        >
          <summary>
            {listing.evidence_warnings?.length
              ? "Details to check"
              : "Source details"}
          </summary>
          <p dir="auto">
            <bdi>{listing.title}</bdi>
          </p>
          {!!listing.evidence_warnings?.length && (
            <ul>
              {listing.evidence_warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          )}
          <p>
            Listing claims, not independently verified. Current availability is
            unknown.
          </p>
        </details>
        <div className="cinema-card-actions">
          <CompareButton listing={listing} selection={selection} />
          <Link
            className="folio-button folio-button--quiet"
            to={listingPath(listing.ref)}
            state={{ from, browseKey }}
          >
            View details ↗
          </Link>
        </div>
      </div>
    </article>
  );
}

export function BrowseRoute({
  selection,
  home = false,
  onFilters,
  openIdentity,
}: {
  selection: Selection;
  home?: boolean;
  onFilters?: () => void;
  openIdentity?: () => void;
}) {
  const location = useLocation();
  const route = parseBrowseQuery(location.search);
  if (!route.valid || location.state?.invalidQuery)
    return (
      <InvalidRoute detail="The address contained unsupported filters. Reset the view to browse safely." />
    );
  return (
    <BrowseResults
      key={location.key}
      selection={selection}
      home={home}
      onFilters={onFilters}
      openIdentity={openIdentity}
    />
  );
}

function BrowseResults({
  selection,
  home,
  onFilters,
  openIdentity,
}: {
  selection: Selection;
  home: boolean;
  onFilters?: () => void;
  openIdentity?: () => void;
}) {
  const services = useServices(),
    location = useLocation(),
    navigate = useNavigate();
  const identity = useIdentity();
  const route = parseBrowseQuery(location.search);
  const [hasContext] = useState(
    () =>
      (!route.cursor && typeof location.state?.browseKey !== "string") ||
      services.hasBrowseRequest(location.key) ||
      services.hasBrowseRequest(location.state?.browseKey) ||
      services.hasQueuedBrowseRequest,
  );
  const [request] = useState<Schema<"SearchRequest">>(() => {
    const initial: Schema<"SearchRequest"> = {
      client_request_id: crypto.randomUUID(),
      query: "",
      soft_preferences: [],
      filters: filtersFromCriteria(route),
      snapshot_id: route.snapshot,
      cursor: route.cursor,
      page_size: 20,
    };
    return hasContext
      ? services.browseRequest(location.key, initial, location.state?.browseKey)
      : initial;
  });
  const [entry, setEntry] = useState(request.query ?? "");
  const [criteriaError, setCriteriaError] = useState<string | null>(null);
  // Public criteria already displayed in this view remain available for its
  // return link; no owner record or credential is put in history or storage.
  useEffect(() => {
    if (hasContext) services.setBrowseRequest(location.key, request);
  }, [services, location.key, request, hasContext, identity.epoch]);
  const result = useQuery({
    ...services.queries.publicRead(
      "search_inventory",
      { body: request },
      request.snapshot_id ?? null,
    ),
    enabled: hasContext,
  });
  useEffect(() => {
    if (result.data && hasContext)
      services.retainBrowsePresentation(
        location.key,
        result.data.data.presentation,
      );
  }, [services, location.key, result.data, hasContext, identity.epoch]);
  const catalogSnapshot = result.data?.data.presentation.snapshot_id;
  const catalog = useQuery({
    queryKey: ["public", catalogSnapshot, "inventory-facet-catalog"],
    queryFn: ({ signal }) =>
      readInventoryCatalog(services.api, catalogSnapshot!, signal),
    enabled: hasContext && !!catalogSnapshot,
    staleTime: Infinity,
    retry: false,
  });
  const suggestion = catalog.data
    ? suggestInventoryQuery(request.query, catalog.data)
    : null;
  const applyCriteria = (
    criteria: Pick<
      Schema<"SearchRequest">,
      "filters" | "query" | "soft_preferences"
    >,
  ) => {
    const next = {
      ...request,
      ...criteria,
      client_request_id: crypto.randomUUID(),
      cursor: null,
      snapshot_id: null,
    };
    if (!validateRequestBody("search_inventory", next)) {
      setCriteriaError(
        "These conditions exceed a supported limit. Remove an existing condition before adding another.",
      );
      return;
    }
    setCriteriaError(null);
    services.queueBrowseRequest(next);
    navigate(
      `${location.pathname}${browseQuery({ ...criteriaFromFilters(next.filters), snapshot: null, cursor: null })}#collection`,
      { state: { browseKey: location.key } },
    );
  };
  const applySearch = (query: string) => {
    setEntry(query);
    const next = {
      ...request,
      client_request_id: crypto.randomUUID(),
      query,
      cursor: null,
      snapshot_id: null,
    };
    services.queueBrowseRequest(next);
    navigate(
      `${location.pathname}${browseQuery({ ...route, snapshot: null, cursor: null })}#collection`,
      { state: { browseKey: location.key } },
    );
  };
  const from = `${location.pathname === "/" ? "/cars" : location.pathname}${location.search}`;
  return (
    <>
      {home && (
        <CinematicHero
          applySearch={applySearch}
          browseLink="/#collection"
          searchLabel="Search the inventory"
          mobileDisclosure="Search the inventory"
          disclosure="Search by make or model. Want to talk through your options? Use Ask AI."
        />
      )}
      <section
        className={
          home ? "cinema-collection cinema-width" : "inner-browse cinema-width"
        }
        id="collection"
        aria-labelledby={home ? "collection-heading" : "page-heading"}
      >
        {home ? (
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
            <p>
              Look beyond the first impression. Get to know the cars, and the
              questions worth asking.
            </p>
            <p className="cinema-sample-note">
              Details come from the original listings. Check current
              availability before making plans.
            </p>
          </div>
        ) : (
          <InternalPageHeader
            compact
            eyebrow="Explore the inventory"
            title="Find your next car."
            art={{
              src: "/cinematic/headers/detail-cabin.jpg",
              width: 1600,
              height: 1067,
              position: "65% center",
            }}
          >
            <span>
              Look beyond the first impression. Read the original claims,
              compare the details and keep the unanswered questions in view.
            </span>
          </InternalPageHeader>
        )}
        <div className={home ? "cinema-results" : "inner-browse-results"}>
          {!home && (
            <h2
              id="collection-heading"
              tabIndex={-1}
              className="folio-visually-hidden"
            >
              Search results
            </h2>
          )}
          <SearchTools inner={!home}>
            <form
              className="cinema-search"
              onSubmit={(event) => {
                event.preventDefault();
                applySearch(entry);
              }}
            >
              <TextField
                type="search"
                label="Search inventory"
                value={entry}
                maxLength={1000}
                onChange={(event) => setEntry(event.target.value)}
                placeholder="Make, model or listing title"
              />
              <Button type="submit">Find cars</Button>
            </form>
          </SearchTools>
          {suggestion && (
            <p className="inventory-suggestion">
              Did you mean{" "}
              <button
                type="button"
                onClick={() => applySearch(suggestion.query)}
              >
                {suggestion.label}?
              </button>
              <span>Your search changes only when you choose it.</span>
            </p>
          )}
          <InventoryFilters
            criteria={request}
            catalog={catalog.data}
            loading={catalog.isFetching || !catalogSnapshot}
            failed={catalog.isError}
            retry={() => void catalog.refetch()}
            apply={applyCriteria}
            advanced={onFilters}
          />
          {criteriaError && (
            <p role="alert" className="cinema-warning">
              {criteriaError}
            </p>
          )}
          {!hasContext ? (
            <TaskState
              title="This page needs its original search."
              tone="warning"
              actions={
                <Link className="folio-button folio-button--primary" to="/cars">
                  Start a new search
                </Link>
              }
            >
              <p>
                This saved page no longer has its search details. Start a new
                search to choose your filters again.
              </p>
            </TaskState>
          ) : result.isPending ? (
            <InventorySkeleton home={home} />
          ) : result.isError ? (
            <ReadFailure
              error={result.error}
              retry={() => void result.refetch()}
              retrying={result.isFetching}
            />
          ) : (
            <>
              <p className="cinema-result-count" role="status">
                <strong>
                  {result.data.data.supported_total}{" "}
                  {result.data.data.supported_total === 1 ? "car" : "cars"}{" "}
                  found
                </strong>
                {result.data.data.supported_total >
                  result.data.data.items.length && (
                  <span> · {result.data.data.items.length} on this page</span>
                )}
              </p>
              {!!result.data.data.unsupported_constraints?.length && (
                <p className="cinema-warning">
                  We couldn’t check these conditions:{" "}
                  {result.data.data.unsupported_constraints.join(" · ")}. These
                  have not been removed from your search.
                </p>
              )}
              <details className="inner-search-evidence inventory-search-evidence">
                <summary>Search and source details</summary>
                <p>
                  Results use the original listing claims. Missing or
                  conflicting information stays visible; current availability is
                  unknown.
                </p>
                <ul>
                  {describeCriteria(result.data.data.applied_criteria).map(
                    (value, index) => (
                      <li key={index}>{value}</li>
                    ),
                  )}
                </ul>
                {result.data.data.evidence_coverage.map((coverage) => (
                  <p key={coverage.attribute}>
                    {coverage.attribute.replaceAll("_", " ")}:{" "}
                    {coverage.supported} of {coverage.source_total} listings
                    have usable evidence; {coverage.excluded_unknown} unknown,{" "}
                    {coverage.excluded_conflicting} conflicting,{" "}
                    {coverage.excluded_unsupported_qualifier} unsupported
                    qualifiers excluded.
                  </p>
                ))}
              </details>
              <div className={home ? "cinema-cards" : "inner-inventory-grid"}>
                {result.data.data.items.map((listing, index) => (
                  <InventoryCard
                    key={refKey(listing.ref)}
                    listing={listing}
                    selection={selection}
                    index={index}
                    from={from}
                    inner={!home}
                    browseKey={location.key}
                    openIdentity={openIdentity}
                  />
                ))}
              </div>
              {result.data.data.items.length === 0 &&
                (home ? (
                  <div className="cinema-empty">
                    <h2>No cars found</h2>
                    <p>
                      Try a different search or explicitly clear your filters.
                    </p>
                    <Button onClick={() => applySearch("")}>
                      Clear text search
                    </Button>{" "}
                    <Link to="/cars">Clear filters and text</Link>
                  </div>
                ) : (
                  <TaskState
                    title="No cars found."
                    actions={
                      <>
                        <Button onClick={() => applySearch("")}>
                          Clear text search
                        </Button>
                        <Link to="/cars">Clear filters and text</Link>
                      </>
                    }
                  >
                    <p>
                      Try a different search or explicitly clear your filters. A
                      car only matches when the listing has enough information
                      to check your filters.
                    </p>
                  </TaskState>
                ))}
              {result.data.data.next_cursor && (
                <Button
                  onClick={() => {
                    const nextRoute = {
                      ...route,
                      snapshot: result.data.data.presentation.snapshot_id,
                      cursor: result.data.data.next_cursor,
                    };
                    const path = `/cars${browseQuery(nextRoute)}`;
                    // Free text never enters a URL; the page request stays in same-tab memory.
                    services.queueBrowseRequest({
                      ...request,
                      client_request_id: crypto.randomUUID(),
                      snapshot_id: nextRoute.snapshot,
                      cursor: nextRoute.cursor,
                    });
                    navigate(path, { state: { browseKey: location.key } });
                  }}
                >
                  Next page
                </Button>
              )}
            </>
          )}
        </div>
      </section>
    </>
  );
}

export function DetailRoute({
  selection,
  openIdentity,
}: {
  selection: Selection;
  openIdentity?: () => void;
}) {
  const { listingRef } = useParams();
  const ref = decodeRef(listingRef);
  if (!ref) return <InvalidRoute />;
  return (
    <DetailContent
      key={refKey(ref)}
      inventoryRef={ref}
      selection={selection}
      openIdentity={openIdentity}
    />
  );
}
function DetailContent({
  inventoryRef,
  selection,
  openIdentity,
}: {
  inventoryRef: InventoryRef;
  selection: Selection;
  openIdentity?: () => void;
}) {
  const services = useServices(),
    location = useLocation();
  const result = useQuery(
    services.queries.publicRead(
      "get_listing",
      { path: inventoryRef },
      inventoryRef.snapshot_id,
    ),
  );
  const back = safeReturnPath(location.state?.from);
  const detail = result.data?.data;
  if (detail && (detail.state === "current" || detail.state === "historical")) {
    return (
      <ListingDetails
        detail={detail}
        backHref={back}
        backState={{ browseKey: location.state?.browseKey }}
        actions={
          <>
            <CompareButton listing={detail.listing} selection={selection} />
            {detail.state === "current" ? (
              <ShortlistAction
                inventoryRef={inventoryRef}
                openIdentity={openIdentity}
              />
            ) : (
              <p className="inner-muted">
                Historical listings cannot be newly saved. An existing saved
                reference can still be removed from your shortlist.
              </p>
            )}
            <p className="inner-muted">Viewing: {detail.eligibility_reason}.</p>
            {detail.state === "current" &&
              detail.eligibility === "simulated_eligible" && (
                <Link
                  className="folio-button folio-button--primary"
                  to={`/viewings/new/${encodeRef(inventoryRef)}`}
                  state={{ browseKey: location.state?.browseKey }}
                >
                  Prepare simulated viewing
                </Link>
              )}
          </>
        }
      />
    );
  }
  return (
    <section className="inner-page cinema-width">
      <Link
        className="inner-back"
        to={back}
        state={{ browseKey: location.state?.browseKey }}
      >
        ← Back to the cars
      </Link>
      <InternalPageHeader
        compact
        eyebrow="Your selected car"
        title={
          result.isPending
            ? "Loading this car…"
            : "This listing is unavailable."
        }
      >
        <span>The exact source reference is retained.</span>
      </InternalPageHeader>
      {result.isPending ? (
        <TaskState title="Checking the source details…" busy>
          <p>The selected car has not been replaced by a different listing.</p>
        </TaskState>
      ) : result.isError ? (
        <ReadFailure error={result.error} retry={() => void result.refetch()} />
      ) : (
        <TaskState
          title={
            detail?.state === "error"
              ? "The source could not be read."
              : "This exact listing is unavailable."
          }
          tone="warning"
          actions={
            <>
              {detail?.state === "error" && detail.retryable && (
                <Button onClick={() => void result.refetch()}>
                  Check again
                </Button>
              )}
              <Link
                className="folio-button folio-button--secondary"
                to={back}
                state={{ browseKey: location.state?.browseKey }}
              >
                Browse cars
              </Link>
            </>
          }
        >
          <p>
            This reference has not been replaced with a newer snapshot or
            another source row.
          </p>
        </TaskState>
      )}
    </section>
  );
}
export function CompareRoute({
  selection,
  onSelectionChange,
  openAssistant,
}: {
  selection: Selection;
  onSelectionChange: (refs: InventoryRef[]) => void;
  openAssistant?: () => void;
}) {
  const location = useLocation(),
    navigate = useNavigate();
  const refs = location.search
    ? parseComparison(location.search)
    : selection.refs;
  if (!refs) return <InvalidRoute />;
  const remove = (ref: InventoryRef) => {
    const remaining = refs.filter((item) => refKey(item) !== refKey(ref));
    onSelectionChange(remaining);
    navigate(comparisonPath(remaining), {
      replace: true,
      state: { browseKey: location.state?.browseKey },
    });
  };
  if (!refs.length)
    return (
      <ComparisonWorkspace
        entries={[]}
        exploreHref="/cars"
        browseKey={location.state?.browseKey}
        onRemove={remove}
        onOpenAssistant={openAssistant}
      />
    );
  if (refs.length === 1)
    return (
      <SingleComparisonContent
        openAssistant={openAssistant}
        key={refKey(refs[0]!)}
        inventoryRef={refs[0]!}
        remove={remove}
        browseKey={location.state?.browseKey}
      />
    );
  return (
    <ComparisonContent
      openAssistant={openAssistant}
      key={refs.map(refKey).join("|")}
      refs={refs}
      remove={remove}
      browseKey={location.state?.browseKey}
    />
  );
}

function SingleComparisonContent({
  inventoryRef,
  remove,
  browseKey,
  openAssistant,
}: {
  inventoryRef: InventoryRef;
  remove: (ref: InventoryRef) => void;
  browseKey?: string;
  openAssistant?: () => void;
}) {
  const services = useServices();
  const result = useQuery(
    services.queries.publicRead(
      "get_listing",
      { path: inventoryRef },
      inventoryRef.snapshot_id,
    ),
  );
  return (
    <ComparisonWorkspace
      onOpenAssistant={openAssistant}
      entries={
        result.data
          ? [
              {
                ref: inventoryRef,
                result: result.data.data,
                listingHref: listingPath(inventoryRef),
              },
            ]
          : []
      }
      count={1}
      exploreHref="/cars"
      browseKey={browseKey}
      onRemove={remove}
      pending={result.isPending}
      onRetry={() => void result.refetch()}
      failure={
        result.isError ? (
          <ReadFailure
            error={result.error}
            retry={() => void result.refetch()}
          />
        ) : undefined
      }
    />
  );
}

function ComparisonContent({
  refs,
  remove,
  browseKey,
  openAssistant,
}: {
  refs: InventoryRef[];
  remove: (ref: InventoryRef) => void;
  browseKey?: string;
  openAssistant?: () => void;
}) {
  const services = useServices();
  const result = useQuery(
    services.queries.publicRead("compare_listings", { body: { refs } }, null),
  );
  return (
    <ComparisonWorkspace
      onOpenAssistant={openAssistant}
      entries={
        result.data
          ? result.data.data.items.map((item, index) => ({
              ref: refs[index]!,
              result: item,
              listingHref: listingPath(refs[index]!),
            }))
          : []
      }
      count={refs.length}
      exploreHref="/cars"
      browseKey={browseKey}
      onRemove={remove}
      pending={result.isPending}
      onRetry={() => void result.refetch()}
      failure={
        result.isError ? (
          <ReadFailure
            error={result.error}
            retry={() => void result.refetch()}
          />
        ) : undefined
      }
    />
  );
}
