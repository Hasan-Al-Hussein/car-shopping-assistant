import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import type { Schema } from "../../shared/api/contracts";
import { useIdentity, useServices } from "../../app/ServicesProvider";
import {
  decodeRef,
  isLocator,
  listingPath,
  operationPath,
  refKey,
} from "../../app/routes";
import { Button } from "../../shared/ui/Button";
import { InternalPageHeader } from "../../shared/ui/inner/InternalPageHeader";
import { TaskState } from "../../shared/ui/inner/TaskState";
import { InvalidRoute, ReadFailure } from "../inventory/InventoryRoutes";
import { EnquiryForm } from "./EnquiryForm";
import {
  LeadFacts,
  ReviewFacts,
  ViewingVehicle,
  viewingTime,
} from "./ViewingFacts";
import { ViewingSlots } from "./ViewingSlots";

export function ViewingNotice() {
  const services = useServices(),
    identity = useIdentity();
  const state = useSyncExternalStore(
    services.viewings.subscribe,
    services.viewings.getSnapshot,
  );
  if (
    identity.phase !== "recognized" ||
    (!state.notice && !state.draft && !state.operation)
  )
    return null;
  const labels: Record<string, string> = {
    appointment: "viewing time",
    starts_at_utc: "viewing start",
    budget: "cash budget",
    requirements: "buyer needs",
    email: "email",
    phone: "phone",
    ref: "selected car",
    expected_revision: "current draft or enquiry revision",
    expected_session_revision: "current session",
  };
  const fields = [
    ...new Set(
      (state.error?.detail?.fields ?? []).flatMap((field) =>
        field.path
          .map(String)
          .flatMap((part) =>
            Object.hasOwn(labels, part) ? [labels[part]!] : [],
          ),
      ),
    ),
  ];
  return (
    <aside
      className="inner-shortlist-notice cinema-width"
      aria-label="Viewing action status"
    >
      {state.notice && <p role="status">{state.notice}</p>}
      {!!fields.length && (
        <p>Check: {fields.join(", ")}. Valid entries remain in the form.</p>
      )}
      {(state.phase === "unknown" || state.phase === "blocked") &&
        services.viewings.hasPendingCommand() && (
          <>
            <p>
              Retry sends the retained draft or enquiry command unchanged. It
              may apply the original requested change if that did not happen
              earlier.
            </p>
            <Button
              variant="secondary"
              onClick={() => void services.viewings.reconcileCommand()}
            >
              Retry original draft or enquiry command
            </Button>
          </>
        )}
      {state.operation && (
        <Link
          to={operationPath(state.operation.key, state.operation.generation)}
        >
          Read original viewing outcome
        </Link>
      )}
      {state.draft &&
        (!state.operation || state.operationTerminal) &&
        !["discarded", "resolved", "unresolved"].includes(
          state.draft.state,
        ) && (
          <Link to={`/viewings/drafts/${state.draft.draft_id}`}>
            Return to viewing draft
          </Link>
        )}
    </aside>
  );
}

export function NewViewingRoute({
  openIdentity,
}: {
  openIdentity: () => void;
}) {
  const { listingRef } = useParams(),
    ref = decodeRef(listingRef);
  if (!ref) return <InvalidRoute />;
  return (
    <NewViewing
      key={refKey(ref)}
      inventoryRef={ref}
      openIdentity={openIdentity}
    />
  );
}
function NewViewing({
  inventoryRef,
  openIdentity,
}: {
  inventoryRef: Schema<"InventoryRef">;
  openIdentity: () => void;
}) {
  const services = useServices(),
    identity = useIdentity(),
    navigate = useNavigate(),
    location = useLocation();
  const state = useSyncExternalStore(
    services.viewings.subscribe,
    services.viewings.getSnapshot,
  );
  const [appointment, setAppointment] =
    useState<Schema<"AppointmentSelection"> | null>(null);
  const detail = useQuery(
    services.queries.publicRead(
      "get_listing",
      { path: inventoryRef },
      inventoryRef.snapshot_id,
    ),
  );
  const car = detail.data?.data,
    eligible =
      car?.state === "current" && car.eligibility === "simulated_eligible";
  const busy =
    ["reading", "pending", "unknown", "blocked"].includes(state.phase) ||
    (!!state.operation && !state.operationTerminal);
  return (
    <section className="inner-page cinema-width">
      <InternalPageHeader
        compact
        eyebrow="Your exact car / simulated viewing"
        title="Prepare a viewing."
        listingPhoto={
          car && (car.state === "current" || car.state === "historical")
            ? {
                identity: JSON.stringify(car.listing.ref),
                src:
                  car.listing.photo.state === "source_present"
                    ? car.listing.photo.url
                    : null,
              }
            : undefined
        }
        art={{
          src: "/cinematic/headers/viewing-parked-car.jpg",
          width: 1600,
          height: 1067,
          position: "60% 75%",
          fade: "short",
        }}
      >
        <span>
          Choose a time and review your simulated viewing request. Nothing is
          reserved yet.
        </span>
      </InternalPageHeader>
      <div className="inner-review-layout">
        <div className="inner-review-record">
          {detail.isPending ? (
            <TaskState title="Checking viewing eligibility…" busy>
              <p>The selected source reference is unchanged.</p>
            </TaskState>
          ) : detail.isError ? (
            <ReadFailure
              error={detail.error}
              retry={() => void detail.refetch()}
            />
          ) : !eligible ? (
            <TaskState
              title="Viewing is unavailable for this car."
              tone="warning"
            >
              <p>
                {car && (car.state === "current" || car.state === "historical")
                  ? car.eligibility_reason
                  : "The exact listing is unavailable."}
              </p>
            </TaskState>
          ) : (
            <>
              <ViewingSlots
                inventoryRef={inventoryRef}
                selected={appointment}
                onSelect={setAppointment}
                disabled={busy}
              />
              {identity.phase !== "recognized" ? (
                <Button onClick={openIdentity}>
                  Enable browser access to plan a viewing
                </Button>
              ) : !identity.session ? (
                <>
                  <p>A viewing draft belongs to a local session.</p>
                  <Button
                    onClick={() => void services.createSession()}
                    disabled={identity.pending || busy}
                  >
                    Start viewing session
                  </Button>
                </>
              ) : (
                <Button
                  disabled={busy || identity.pending}
                  onClick={async () => {
                    const draft = await services.viewings.create(
                      identity.session!.session_id,
                      inventoryRef,
                      appointment,
                    );
                    if (draft)
                      navigate(`/viewings/drafts/${draft.draft_id}`, {
                        state: { browseKey: location.state?.browseKey },
                      });
                  }}
                >
                  Create viewing draft
                </Button>
              )}
              {!appointment && (
                <p>
                  You can create a draft now and choose a time before review.
                </p>
              )}
            </>
          )}
          <Link
            className="inner-back"
            to={listingPath(inventoryRef)}
            state={{ browseKey: location.state?.browseKey }}
          >
            Return to this car →
          </Link>
        </div>
        <ViewingVehicle inventoryRef={inventoryRef} />
      </div>
    </section>
  );
}

export function DraftRoute() {
  const { draftId } = useParams(),
    location = useLocation();
  if (!isLocator(draftId)) return <InvalidRoute />;
  return (
    <DraftRead
      key={`${draftId}:${location.key}`}
      draftId={draftId}
      reviewMode={location.pathname.endsWith("/review")}
    />
  );
}
function DraftRead({
  draftId,
  reviewMode,
}: {
  draftId: string;
  reviewMode: boolean;
}) {
  const services = useServices(),
    owner = services.owner.capture();
  const state = useSyncExternalStore(
    services.viewings.subscribe,
    services.viewings.getSnapshot,
  );
  const result = useQuery({
    ...services.queries.privateRead("get_booking_draft", {
      path: { draft_id: draftId },
    }),
    queryFn: ({ signal }) =>
      services.viewings.readDraft(draftId, owner, signal),
    refetchOnMount: "always",
  });
  const draft =
    state.draft?.draft_id === draftId ? state.draft : result.data?.data;
  return (
    <section className="inner-page cinema-width">
      <InternalPageHeader
        compact
        eyebrow="Simulated viewing / original draft"
        title="Your viewing draft."
        art={{
          src: "/cinematic/headers/viewing-parked-car.jpg",
          width: 1600,
          height: 1067,
          position: "60% 75%",
          fade: "short",
        }}
      >
        <span>
          A draft does not reserve a time. Review your viewing details before
          confirming.
        </span>
      </InternalPageHeader>
      {draft ? (
        <DraftEditor draft={draft} reviewMode={reviewMode} />
      ) : result.isError ? (
        <ReadFailure error={result.error} retry={() => void result.refetch()} />
      ) : (
        <TaskState title="Checking the original draft…" busy>
          <p>Opening this address does not create or confirm anything.</p>
        </TaskState>
      )}
      {draft && result.isError && (
        <ReadFailure error={result.error} retry={() => void result.refetch()} />
      )}
      {draft && (
        <Button
          variant="quiet"
          disabled={result.isFetching}
          onClick={() => void result.refetch()}
        >
          Check current draft
        </Button>
      )}
    </section>
  );
}

export function reviewedLeadMatches(
  review: Schema<"BookingReview">,
  current: Schema<"LeadRecord"> | null,
  generation: string | null,
) {
  if (generation !== review.store_generation) return false;
  return review.lead_change.mode === "create_from_review"
    ? current === null
    : current?.lead_id === review.lead_change.lead_id &&
        current.revision === review.lead_change.expected_revision;
}
function DraftEditor({
  draft,
  reviewMode,
}: {
  draft: Schema<"BookingDraft">;
  reviewMode: boolean;
}) {
  const services = useServices();
  const state = useSyncExternalStore(
    services.viewings.subscribe,
    services.viewings.getSnapshot,
  );
  const [viewId] = useState(() => crypto.randomUUID()),
    [reviewStep, setReviewStep] = useState(reviewMode);
  const [appointment, setAppointment] =
    useState<Schema<"AppointmentSelection"> | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(
    () => () => services.viewings.revokeApproval(viewId),
    [services, viewId],
  );
  useEffect(() => {
    if (reviewStep) heading.current?.focus();
  }, [reviewStep]);
  const enquiry = useQuery({
    ...services.queries.privateRead("get_current_local_enquiry", {}),
    refetchOnMount: "always",
  });
  const current =
    enquiry.data && "lead_id" in enquiry.data.data ? enquiry.data.data : null;
  const generation = enquiry.data?.meta.store_generation ?? null;
  const busy =
    ["reading", "pending", "unknown", "blocked"].includes(state.phase) ||
    (!!state.operation && !state.operationTerminal);
  const review = draft.review;
  const submitted =
    draft.state === "unresolved" ||
    draft.state === "resolved" ||
    review?.state === "submitted" ||
    review?.state === "consumed";
  const closed = submitted || draft.state === "discarded";
  const selected = appointment ?? draft.appointment;
  const refresh = async () => {
    if (busy || closed) return;
    const edited =
      !!appointment &&
      appointment.starts_at_utc !== draft.appointment?.starts_at_utc;
    const updated = await services.viewings.update(
      draft,
      edited ? "edit" : "refresh_review",
      viewId,
      edited ? appointment : undefined,
    );
    if (updated?.review) {
      setAppointment(null);
      setReviewStep(true);
      heading.current?.focus();
    }
  };
  const leadMatches =
    !!review &&
    !!enquiry.data &&
    !enquiry.isError &&
    !enquiry.isFetching &&
    reviewedLeadMatches(review, current, generation);
  return (
    <div className="inner-review-layout">
      <div className="inner-review-record">
        <div className="inner-status-row">
          <span className="inner-status-label">
            {draft.state.replaceAll("_", " ")}
          </span>
          <span>Draft revision {draft.revision}</span>
        </div>
        {closed ? (
          <TaskState
            title={
              draft.state === "discarded"
                ? "This uncommitted draft was discarded."
                : "Continue with the original operation."
            }
            actions={
              review && submitted ? (
                <Link
                  className="folio-button folio-button--primary"
                  to={operationPath(
                    review.operation_key,
                    review.store_generation,
                  )}
                >
                  Read original viewing outcome
                </Link>
              ) : undefined
            }
          >
            <p>
              {draft.state === "discarded"
                ? "No confirmed booking was cancelled."
                : "This draft cannot be edited or submitted as a new action. Its original outcome must be resolved first."}
            </p>
          </TaskState>
        ) : (
          <>
            <Button
              variant="quiet"
              disabled={enquiry.isFetching}
              onClick={() => void enquiry.refetch()}
            >
              Check saved enquiry details
            </Button>
            {draft.required_fields.length > 0 && (
              <div className="inner-record-note">
                <h3>Before confirmation</h3>
                <ul>
                  {draft.required_fields.map((field) => (
                    <li key={field}>
                      {field === "appointment"
                        ? "Choose one of the available viewing times."
                        : field === "review_refresh"
                          ? "Check your details, then update your viewing review."
                          : field === "draft_expired"
                            ? "This draft expired. Update its review or edit the details to continue."
                            : "Update your viewing details before reviewing."}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {reviewStep && review ? (
              <>
                <h2 ref={heading} tabIndex={-1}>
                  Review this simulated viewing
                </h2>
                <ReviewFacts review={review} />
                <p>
                  Review {review.state} · expires{" "}
                  {viewingTime(review.expires_at, review.timezone)} ·{" "}
                  {review.timezone}.
                </p>
                <h3>Local enquiry included with confirmation</h3>
                {review.lead_change.mode === "create_from_review" ? (
                  <>
                    <p>
                      Confirming saves the enquiry details shown below and
                      requests a CSV export.
                    </p>
                    <LeadFacts values={review.lead_change.values} />
                  </>
                ) : leadMatches && current ? (
                  <>
                    <p>
                      Confirming keeps the enquiry details shown below and links
                      them to this simulated viewing.
                    </p>
                    <p>
                      Enquiry reference {current.lead_id} · reviewed revision{" "}
                      {review.lead_change.expected_revision}.
                    </p>
                    <LeadFacts values={current.values} />
                  </>
                ) : (
                  <p role="status">
                    Check your saved enquiry details, then refresh the viewing
                    review before confirming.
                  </p>
                )}
                {enquiry.isError && (
                  <ReadFailure
                    error={enquiry.error}
                    retry={() => void enquiry.refetch()}
                  />
                )}
                <Confirmation
                  review={review}
                  viewId={viewId}
                  leadMatches={leadMatches}
                />
                <div className="inner-viewing-actions">
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => {
                      services.viewings.revokeApproval(viewId);
                      setReviewStep(false);
                    }}
                  >
                    Edit viewing details
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={busy || enquiry.isFetching}
                    onClick={() => void refresh()}
                  >
                    Refresh viewing review
                  </Button>
                </div>
              </>
            ) : (
              <>
                <h2>Viewing details</h2>
                {draft.appointment && (
                  <p>
                    Proposed start:{" "}
                    {viewingTime(
                      draft.appointment.starts_at_utc,
                      draft.appointment.timezone,
                    )}{" "}
                    · {draft.appointment.timezone}. You can check the end time
                    before confirming.
                  </p>
                )}
                {draft.state === "suspended" ? (
                  <TaskState title="This draft is suspended.">
                    <p>
                      Resume explicitly to obtain a fresh review of the saved
                      details.
                    </p>
                  </TaskState>
                ) : (
                  <ViewingSlots
                    inventoryRef={draft.ref}
                    selected={appointment}
                    disabled={busy}
                    onSelect={(value) => {
                      services.viewings.revokeApproval(viewId);
                      setAppointment(value);
                    }}
                  />
                )}
                {enquiry.isPending ? (
                  <p role="status">Reading saved enquiry details…</p>
                ) : enquiry.isError ? (
                  <ReadFailure
                    error={enquiry.error}
                    retry={() => void enquiry.refetch()}
                  />
                ) : (
                  generation && (
                    <EnquiryForm
                      sessionId={draft.session_id}
                      refValue={draft.ref}
                      current={current}
                      generation={generation}
                    />
                  )
                )}
                <Button
                  disabled={
                    busy ||
                    (!selected && draft.state !== "suspended") ||
                    enquiry.isFetching ||
                    enquiry.isError
                  }
                  onClick={() => void refresh()}
                >
                  {draft.state === "suspended"
                    ? "Resume and refresh review"
                    : "Review simulated viewing"}
                </Button>
              </>
            )}
            <div className="inner-viewing-actions">
              {draft.state !== "suspended" && (
                <Button
                  variant="quiet"
                  disabled={busy}
                  onClick={async () => {
                    services.viewings.revokeApproval(viewId);
                    const updated = await services.viewings.update(
                      draft,
                      "suspend",
                      viewId,
                    );
                    if (updated) {
                      setReviewStep(false);
                      setAppointment(null);
                    }
                  }}
                >
                  Suspend draft
                </Button>
              )}
              <Button
                variant="quiet"
                disabled={busy}
                onClick={async () => {
                  services.viewings.revokeApproval(viewId);
                  await services.viewings.update(draft, "discard", viewId);
                }}
              >
                Discard uncommitted draft
              </Button>
            </div>
          </>
        )}
        <Link
          className="inner-back"
          to="/cars"
          state={{ browseKey: services.currentBrowseKey }}
        >
          Continue browsing →
        </Link>
        <p>
          Leaving keeps the draft; returning requires a fresh review. It does
          not cancel a submitted action.
        </p>
      </div>
      <ViewingVehicle inventoryRef={draft.ref} />
    </div>
  );
}

function Confirmation({
  review,
  viewId,
  leadMatches,
}: {
  review: Schema<"BookingReview">;
  viewId: string;
  leadMatches: boolean;
}) {
  const services = useServices(),
    navigate = useNavigate();
  useSyncExternalStore(
    services.viewings.subscribe,
    services.viewings.getSnapshot,
  );
  const [, setTime] = useState(Date.now);
  useEffect(() => {
    const remaining = Date.parse(review.expires_at) - Date.now();
    if (remaining <= 0) return;
    const timer = setTimeout(
      () => setTime(Date.now()),
      Math.min(remaining + 1, 2_147_483_647),
    );
    return () => clearTimeout(timer);
  }, [review.expires_at]);
  const ready = leadMatches && services.viewings.canConfirm(review, viewId);
  return (
    <div className="inner-record-note">
      <p>
        Confirming saves a simulated viewing and the disclosed local enquiry,
        then requests a CSV export. It does not contact a dealer or create a
        real reservation.
      </p>
      {!ready && (
        <p>
          Check the viewing and enquiry details, then choose Refresh viewing
          review to enable confirmation. After reopening this page, refresh the
          review again.
        </p>
      )}
      <Button
        disabled={!ready}
        onClick={() => {
          if (!leadMatches) return;
          void services.viewings.confirm(review, viewId, (locator) =>
            navigate(operationPath(locator.key, locator.generation), {
              replace: true,
            }),
          );
        }}
      >
        Confirm simulated viewing
      </Button>
    </div>
  );
}
