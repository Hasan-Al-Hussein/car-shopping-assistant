import { useLayoutEffect, useRef, useState } from "react";
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useNavigationType,
} from "react-router";
import { Button } from "../shared/ui/Button";
import { ListingPhoto } from "../shared/ui/ListingPhoto";
import { proofListings } from "./fixtures";
import { displayCarName } from "./displayNames";
import { Fact } from "./Fact";
import {
  listingPath,
  refKey,
  type ProofListing,
  type Ref,
  type Schema,
} from "./types";
import {
  appointmentLabel,
  makeProofReview,
  proofConfirmation,
  proofUnknown,
} from "./operations";
import "./proof.css";
import { CinemaBrowse, CinemaDetail, CinemaHeader } from "./CinematicShowroom";
import "./cinematic.css";
import "../styles/inner-workspace.css";
import "../styles/inner-v7.css";
import "../styles/inner-pages.css";
import "../styles/dubizzle.css";
import { ComparisonWorkspace } from "../shared/ui/inner/ComparisonWorkspace";
import { InternalPageHeader } from "../shared/ui/inner/InternalPageHeader";
import { TaskState } from "../shared/ui/inner/TaskState";
import { useScrollReveal } from "../shared/ui/useScrollReveal";

const listings: ProofListing[] = proofListings;
type Shared = {
  selected: Ref[];
  toggle: (ref: Ref) => void;
  failPhoto: boolean;
  startReview: (ref: Ref) => void;
  unresolved: boolean;
};

export function DesignProof() {
  return (
    <BrowserRouter>
      <ProofShell />
    </BrowserRouter>
  );
}

function ProofShell() {
  const [selected, setSelected] = useState<Ref[]>([]);
  const [search, setSearch] = useState("");
  const [failPhoto, setFailPhoto] = useState(false);
  const [doubleText, setDoubleText] = useState(false);
  const [announcement, setAnnouncement] = useState<{
    routeKey: string;
    text: string;
  } | null>(null);
  const [review, setReview] = useState<Schema<"BookingReview">>();
  const [outcome, setOutcome] = useState<Schema<"OperationNotObserved">>();
  const [statusChecks, setStatusChecks] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const currentAnnouncement =
    announcement?.routeKey === location.key ? announcement.text : "";
  const navigationType = useNavigationType();
  const revealRoot = useRef<HTMLDivElement>(null);
  useScrollReveal(revealRoot, location.key, navigationType === "POP");
  const scrollPositions = useRef(new Map<string, number>());
  const previousPath = useRef(location.pathname);
  const previousRouteKey = useRef(location.key);
  const selectionTray = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const tray = selectionTray.current;
    if (!tray) return;
    const resize = () =>
      document.documentElement.style.setProperty(
        "--comparison-tray-height",
        `${tray.getBoundingClientRect().height}px`,
      );
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(tray);
    return () => {
      observer.disconnect();
      document.documentElement.style.removeProperty("--comparison-tray-height");
    };
  }, [selected.length, location.pathname]);
  useLayoutEffect(() => {
    if (
      previousPath.current !== location.pathname ||
      previousRouteKey.current !== location.key
    )
      document.getElementById("page-heading")?.focus({ preventScroll: true });
    previousPath.current = location.pathname;
    previousRouteKey.current = location.key;
    window.scrollTo({
      top:
        navigationType === "POP"
          ? (scrollPositions.current.get(location.pathname) ?? 0)
          : 0,
      behavior: "instant",
    });
    const remember = () =>
      scrollPositions.current.set(location.pathname, window.scrollY);
    window.addEventListener("scroll", remember, { passive: true });
    return () => window.removeEventListener("scroll", remember);
  }, [location.pathname, location.key, navigationType]);

  useLayoutEffect(() => {
    if (!location.hash) return;
    const frame = requestAnimationFrame(() => {
      const target = document.getElementById(location.hash.slice(1));
      const heading = target?.querySelector<HTMLElement>("h2[tabindex]");
      const focusTarget = heading?.getClientRects().length ? heading : target;
      const scrollTarget = target?.getClientRects().length
        ? target
        : focusTarget;
      scrollTarget?.scrollIntoView({ behavior: "instant", block: "start" });
      focusTarget?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [location.pathname, location.hash, location.key]);

  const toggle = (ref: Ref) => {
    const exists = selected.some((item) => refKey(item) === refKey(ref));
    if (!exists && selected.length === 3) {
      setAnnouncement({
        routeKey: location.key,
        text: "Comparison holds three cars. Remove one before adding another.",
      });
      return;
    }
    setSelected(
      exists
        ? selected.filter((item) => refKey(item) !== refKey(ref))
        : [...selected, ref],
    );
    setAnnouncement({
      routeKey: location.key,
      text: `Listing ${ref.source_id} ${exists ? "removed from" : "added to"} comparison.`,
    });
  };
  const startReview = (ref: Ref) => {
    if (outcome) {
      navigate("/outcome");
      return;
    }
    setReview(makeProofReview(ref, (review?.draft_revision ?? 0) + 1));
    navigate("/review");
  };
  const confirm = () => {
    if (!review || outcome) return;
    // Exercise the contract-shaped intent only. No fetch/store/booking is performed.
    const confirmation = proofConfirmation(review);
    if (confirmation.operation_key !== review.operation_key) return;
    setOutcome(proofUnknown(review));
    setReview({ ...review, state: "submitted" });
    navigate("/outcome");
  };
  const shared = {
    selected,
    toggle,
    failPhoto,
    startReview,
    unresolved: Boolean(outcome),
  };
  return (
    <div
      ref={revealRoot}
      className={`proof cinematic${location.pathname === "/" ? "" : " inner-workspace v7-workspace"}`}
      data-text-size={doubleText ? "double" : "normal"}
    >
      <a className="proof-skip" href="#main-content">
        Skip to the car decision
      </a>
      <CinemaHeader
        key={location.key}
        count={selected.length}
        path={location.pathname}
        viewingPath={review ? (outcome ? "/outcome" : "/review") : undefined}
      />
      <main id="main-content" tabIndex={-1}>
        <Routes>
          <Route
            path="/"
            element={
              <CinemaBrowse {...shared} search={search} setSearch={setSearch} />
            }
          />
          <Route
            path="/listing/:namespace/:snapshot/:sourceId"
            element={<CinemaDetail {...shared} />}
          />
          <Route
            path="/cars"
            element={
              <CinemaBrowse
                {...shared}
                inner
                search={search}
                setSearch={setSearch}
              />
            }
          />
          <Route path="/compare" element={<Comparison {...shared} />} />
          <Route
            path="/review"
            element={
              <ViewingReview
                review={review}
                outcome={outcome}
                confirm={confirm}
                edit={() =>
                  review &&
                  !outcome &&
                  setReview(
                    makeProofReview(review.ref, review.draft_revision + 1),
                  )
                }
              />
            }
          />
          <Route
            path="/outcome"
            element={
              <Outcome
                review={review}
                outcome={outcome}
                checks={statusChecks}
                check={() => setStatusChecks((value) => value + 1)}
              />
            }
          />
          <Route path="*" element={<Missing />} />
        </Routes>
      </main>
      <div className="proof-announcement" role="status">
        {currentAnnouncement}
      </div>
      {selected.length > 0 &&
        !["/compare", "/review", "/outcome"].includes(location.pathname) && (
          <aside
            ref={selectionTray}
            className="proof-selection"
            aria-label="Comparison selection"
          >
            <span>
              <strong>{selected.length} of 3</strong>
              <span className="cinema-desktop-copy"> cars for comparison</span>
              <span className="cinema-mobile-copy"> selected</span>
            </span>
            <Link className="folio-button folio-button--primary" to="/compare">
              <span className="cinema-desktop-copy">
                Compare selected cars →
              </span>
              <span className="cinema-mobile-copy">Compare cars →</span>
            </Link>
            {currentAnnouncement.startsWith("Comparison holds") && (
              <p className="proof-selection-warning">{currentAnnouncement}</p>
            )}
          </aside>
        )}
      <div className="proof-scope">
        <span>Design preview · seven source listings</span>
        <span>Simulated actions · nothing is saved or sent</span>
      </div>
      <footer className="proof-footer">
        <p>
          Source claims, held with care.
          <br />
          <span>Listing information is not independently verified.</span>
        </p>
        <details>
          <summary>Development proof controls</summary>
          <div className="proof-controls">
            <Button
              variant="secondary"
              onClick={() => setDoubleText(!doubleText)}
            >
              {doubleText ? "Restore 100% text" : "Preview 200% text"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setFailPhoto(!failPhoto)}
            >
              {failPhoto
                ? "Restore listing 27 photo"
                : "Show listing 27 photo failure"}
            </Button>
            <Link className="folio-link" to="/__specimen" reloadDocument>
              Component specimen
            </Link>
            <p>
              Reload resets this in-memory proof. Synthetic viewing data uses a
              fixed demonstration clock. No backend connection.
            </p>
          </div>
        </details>
      </footer>
    </div>
  );
}

function Photo({
  item,
  failPhoto,
  eager = false,
}: {
  item: ProofListing;
  failPhoto: boolean;
  eager?: boolean;
}) {
  const listing = item.detail.listing;
  const failed = failPhoto && listing.ref.source_id === "27";
  return (
    <figure className="proof-photo">
      <div className="proof-photo-reveal">
        <ListingPhoto
          identity={refKey(listing.ref)}
          src={
            failed ? "/__proof/controlled-unavailable-image" : listing.photo.url
          }
          alt={listing.photo.alt}
          loading={eager ? "eager" : "lazy"}
        />
      </div>
      <figcaption>
        {failed
          ? "Controlled image-failure example · source listing 27"
          : `Original listing photograph · ${item.source.photo_cell}`}
        <span>1 supplied view</span>
      </figcaption>
    </figure>
  );
}

function Comparison(shared: Shared) {
  const entries = shared.selected.flatMap((ref) =>
    listings
      .filter((item) => refKey(item.detail.listing.ref) === refKey(ref))
      .map((item) => ({
        ref,
        result: item.detail,
        listingHref: listingPath(ref),
        photoCell: item.source.photo_cell,
        photoFailureExample: shared.failPhoto && ref.source_id === "27",
        supplementalConflicts: item.conflicts.filter(
          (conflict) => conflict.attribute === "engine",
        ),
      })),
  );
  return (
    <ComparisonWorkspace
      entries={entries}
      exploreHref="/cars"
      onRemove={shared.toggle}
      preview
    />
  );
}
function ReviewIdentity({
  item,
  failPhoto = false,
}: {
  item: ProofListing;
  failPhoto?: boolean;
}) {
  return (
    <aside className="proof-review-car">
      <Photo item={item} failPhoto={failPhoto} eager />
      <p className="proof-eyebrow">
        Your selected car / {item.detail.listing.ref.source_id}
      </p>
      <h2>
        <Link to={listingPath(item.detail.listing.ref)}>
          {displayCarName(item.heading)}
        </Link>
      </h2>
      <dl>
        <dt>Cash price</dt>
        <dd>
          <Fact fact={item.detail.listing.cash_price} evidence />
        </dd>
      </dl>
      <details className="inner-card-source">
        <summary>
          {item.conflicts.length
            ? "Source conflicts to review"
            : "Original listing details"}
        </summary>
        <p className="proof-source-title" dir="auto">
          <bdi>{item.detail.listing.title}</bdi>
        </p>
        {item.conflicts.map((conflict) => (
          <p key={conflict.attribute} className="proof-alert">
            {conflict.label}
          </p>
        ))}
      </details>
    </aside>
  );
}

function ViewingReview({
  review,
  outcome,
  confirm,
  edit,
}: {
  review?: Schema<"BookingReview">;
  outcome?: Schema<"OperationNotObserved">;
  confirm: () => void;
  edit: () => void;
}) {
  if (!review)
    return (
      <section className="proof-page proof-empty">
        <InternalPageHeader
          compact
          eyebrow="Simulated viewing"
          title="Choose a car to review."
        >
          <span>Begin with an exact listing from the collection.</span>
        </InternalPageHeader>
        <TaskState
          title="No car has been selected for review."
          actions={
            <Link className="folio-button folio-button--primary" to="/cars">
              Explore cars
            </Link>
          }
        >
          <p>Opening this page does not create a viewing or a draft.</p>
        </TaskState>
      </section>
    );
  if (outcome)
    return (
      <section className="proof-page proof-empty">
        <InternalPageHeader
          compact
          eyebrow="Original viewing operation"
          title="An outcome is unresolved."
        >
          <span>Keep the same car, time and operation reference together.</span>
        </InternalPageHeader>
        <TaskState
          title="Check the original operation."
          tone="warning"
          actions={
            <Link className="folio-button folio-button--primary" to="/outcome">
              View unresolved outcome
            </Link>
          }
        >
          <p>Check the original operation before starting another review.</p>
        </TaskState>
      </section>
    );
  const item = listings.find(
    (candidate) => refKey(candidate.detail.listing.ref) === refKey(review.ref),
  )!;
  return (
    <section className="proof-page proof-review">
      <Link className="proof-back" to={listingPath(review.ref)}>
        ← Back to the car
      </Link>
      <InternalPageHeader
        compact
        eyebrow="Simulated viewing / review before confirming"
        title="Review simulated viewing."
      >
        <span>Check the proposal below. No appointment has been saved.</span>
      </InternalPageHeader>
      <div className="proof-review-layout">
        <ReviewIdentity item={item} />
        <div className="proof-review-content">
          <div className="proof-review-status">
            <span className="proof-step">01 / REVIEW</span>
            <span>Proposed · synthetic data</span>
          </div>
          <h2>Friday, 25 September 2026</h2>
          <p className="proof-appointment-time">{appointmentLabel(review)}</p>
          <p className="proof-caption">Asia/Dubai · UTC+04:00 · 30 minutes</p>
          <Button variant="quiet" onClick={edit}>
            Change the simulated time
          </Button>
          <p className="proof-caption" role="status">
            Review revision {review.draft_revision}. Changing the time replaces
            the unsubmitted review.
          </p>
          <div className="proof-review-rule">
            <h3>What you would confirm</h3>
            <ul>
              <li>A simulated local viewing for this exact car and time.</li>
              <li>
                A local enquiry containing this car and “inspect the source
                conflicts at a viewing.”
              </li>
              <li>
                No phone, email or budget is provided in this synthetic example.
              </li>
            </ul>
            <p>{review.venue_label}</p>
          </div>
          <div className="proof-confirm-box">
            <p>
              <strong>This is a demonstration.</strong> Confirming shows a
              simulated unknown outcome. Nothing is saved, reserved or sent to a
              seller.
            </p>
            <Button onClick={confirm}>Confirm simulated viewing</Button>
            <span>
              Example clock: 24 Sep 2026, 09:56 Dubai. Review expires at 10:00
              in this fixed scenario.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

function Outcome({
  review,
  outcome,
  checks,
  check,
}: {
  review?: Schema<"BookingReview">;
  outcome?: Schema<"OperationNotObserved">;
  checks: number;
  check: () => void;
}) {
  if (!review || !outcome)
    return (
      <section className="proof-page proof-empty">
        <InternalPageHeader
          compact
          eyebrow="Simulated viewing status"
          title="No submitted operation."
        >
          <span>This proof has no viewing outcome to display.</span>
        </InternalPageHeader>
        <TaskState
          title="Continue with the cars."
          actions={
            <Link className="folio-button folio-button--primary" to="/cars">
              Explore cars
            </Link>
          }
        >
          <p>Nothing is created by opening a status page.</p>
        </TaskState>
      </section>
    );
  const item = listings.find(
    (candidate) => refKey(candidate.detail.listing.ref) === refKey(review.ref),
  )!;
  return (
    <section className="proof-page proof-outcome">
      <InternalPageHeader
        compact
        eyebrow="Simulated viewing / outcome unresolved"
        title="Original operation status."
      >
        <span>
          An unknown outcome does not establish whether a real operation saved.
          This demonstration performs no save.
        </span>
      </InternalPageHeader>
      <div className="proof-review-layout">
        <ReviewIdentity item={item} />
        <div className="proof-review-content">
          <div className="proof-outcome-banner">
            <span aria-hidden="true" className="proof-pause-mark">
              Ⅱ
            </span>
            <div>
              <h2>Outcome unknown</h2>
              <p>
                The original operation is not observed. Keep checking that
                operation before trying to book again.
              </p>
              <Button onClick={check}>Check original status</Button>
              <p role="status" className="proof-check-result">
                {checks
                  ? `Check ${checks}: still not observed. The original operation is unchanged.`
                  : "No status check performed yet."}
              </p>
            </div>
          </div>
          <dl className="proof-outcome-facts">
            <div>
              <dt>Proposed viewing</dt>
              <dd>
                25 September 2026
                <br />
                {appointmentLabel(review)} · Dubai
              </dd>
            </div>
            <div>
              <dt>Booking / local enquiry / export</dt>
              <dd>
                Unresolved in this scenario.
                <br />
                No success or receipt is claimed.
              </dd>
            </div>
          </dl>
          <div className="proof-recovery">
            <h3>Keep this action together.</h3>
            <p>
              Checking status keeps the same car, reviewed time and operation
              reference. It does not submit another booking.
            </p>
            <Link className="proof-back" to="/">
              Continue exploring →
            </Link>
          </div>
          <details>
            <summary>Simulated operation reference</summary>
            <p
              className="proof-operation-key"
              data-operation-key={outcome.operation_key}
            >
              {outcome.operation_key}
            </p>
            <p className="proof-caption">
              The same reference is retained through navigation and every status
              check in this in-memory proof. Reload resets the demonstration.
            </p>
          </details>
        </div>
      </div>
    </section>
  );
}

function Missing() {
  return (
    <section className="proof-page proof-empty">
      <InternalPageHeader
        compact
        eyebrow="Exact source reference"
        title="This reference is unavailable."
      >
        <span>This address is not included in the design proof.</span>
      </InternalPageHeader>
      <TaskState
        title="Continue with the original source collection."
        tone="warning"
        actions={
          <Link className="folio-button folio-button--primary" to="/">
            Explore the sample
          </Link>
        }
      >
        <p>
          A different snapshot or listing ID cannot silently select another car.
        </p>
      </TaskState>
    </section>
  );
}
