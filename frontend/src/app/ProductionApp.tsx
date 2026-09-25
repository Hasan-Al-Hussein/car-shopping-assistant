/// <reference types="vite/client" />
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigationType,
} from "react-router";
import { useQuery } from "@tanstack/react-query";
import { BrowserServices } from "./BrowserServices";
import { ServicesProvider, useServices } from "./ServicesProvider";
import { ContextPanel, type PanelKind } from "./ContextPanel";
import { CinemaHeader } from "../shared/ui/CinemaHeader";
import { AboutRoute } from "../features/about/AboutRoute";
import { useScrollReveal } from "../shared/ui/useScrollReveal";
import { ShortlistNotice } from "../features/shortlist/ShortlistActions";
import {
  NewViewingRoute,
  ViewingNotice,
} from "../features/viewings/ViewingRoutes";
import {
  DraftRoute,
  OwnedOperationRoute,
  OwnerGate,
  ShortlistRoute,
} from "./OwnedRoutes";
import {
  BrowseRoute,
  CompareRoute,
  DetailRoute,
  InvalidRoute,
} from "../features/inventory/InventoryRoutes";
import {
  comparisonPath,
  parseBrowseQuery,
  parseComparison,
  parseOperationQuery,
  refKey,
  type InventoryRef,
} from "./routes";
import "../design-proof/proof.css";
import "../design-proof/cinematic.css";
import "./workspace.css";
import "../styles/inner-workspace.css";
import "../styles/inner-v7.css";
import "../styles/inner-pages.css";
import "../styles/inner-panels.css";
import "../styles/dubizzle.css";
import "../styles/context-panel-layout.css";
import "../styles/feedback.css";

const browserServices = new BrowserServices();
export function ProductionApp({
  services = browserServices,
}: {
  services?: BrowserServices;
}) {
  return (
    <ServicesProvider services={services}>
      <BrowserRouter basename={import.meta.env.DEV ? "/__app" : undefined}>
        <Workspace />
      </BrowserRouter>
    </ServicesProvider>
  );
}

function QueryGuard({ children }: { children: ReactNode }) {
  const location = useLocation();
  const valid =
    location.pathname === "/" || location.pathname === "/cars"
      ? parseBrowseQuery(location.search).valid
      : location.pathname === "/compare"
        ? parseComparison(location.search) !== null
        : location.pathname.startsWith("/operations/")
          ? parseOperationQuery(location.search).valid
          : !location.search;
  const supportedHash =
    ["#collection", "#assistant"].includes(location.hash) ||
    (location.pathname.startsWith("/cars/") &&
      ["#detail-specifications", "#detail-description"].includes(
        location.hash,
      ));
  if (!valid || (location.hash && !supportedHash))
    return (
      <Navigate to={location.pathname} replace state={{ invalidQuery: true }} />
    );
  if (location.state?.invalidQuery)
    return (
      <InvalidRoute detail="Unsupported address parameters were removed. Use Browse cars to continue." />
    );
  return children;
}

function Workspace() {
  const services = useServices(),
    location = useLocation(),
    navigation = useNavigationType();
  const revealRoot = useRef<HTMLDivElement>(null);
  useScrollReveal(revealRoot, location.key, navigation === "POP");
  const health = useQuery(services.queries.publicRead("get_health", {}, null));
  const [panel, setPanel] = useState<PanelKind | null>(null);
  // Explicit public comparison is view state, independent of private-owner epochs.
  const [refs, setSelected] = useState<InventoryRef[]>([]);
  const [adoptedLocation, setAdoptedLocation] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const browseKey = ["/", "/cars"].includes(location.pathname)
    ? location.key
    : typeof location.state?.browseKey === "string"
      ? location.state.browseKey
      : services.currentBrowseKey;
  const navigationRefs =
    location.pathname === "/compare" && location.search
      ? (parseComparison(location.search) ?? refs)
      : refs;
  const fromAddress =
    location.pathname === "/compare" && location.search
      ? parseComparison(location.search)
      : null;
  // Adopt a changed public URL before rendering its children, so Browse/Back
  // retain the comparison without an effect-triggered intermediate render.
  const locationIdentity = location.key;
  if (adoptedLocation !== locationIdentity) {
    setAdoptedLocation(locationIdentity);
    if (fromAddress) setSelected(fromAddress);
  }
  const opener = useRef<HTMLElement | null>(null),
    tray = useRef<HTMLElement>(null);
  const positions = useRef(new Map<string, number>()),
    previousKey = useRef(location.key);
  const open = (kind: PanelKind) => {
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setPanel(kind);
  };
  const toggle = (ref: InventoryRef) => {
    const exists = refs.some((item) => refKey(item) === refKey(ref));
    if (!exists && refs.length === 3) {
      setWarning("Compare up to three cars. Remove one before adding another.");
      return;
    }
    setWarning(null);
    setSelected(
      exists
        ? refs.filter((item) => refKey(item) !== refKey(ref))
        : [...refs, ref],
    );
  };
  useLayoutEffect(() => {
    const element = tray.current;
    if (!element) return;
    const update = () =>
      document.documentElement.style.setProperty(
        "--comparison-tray-height",
        `${element.getBoundingClientRect().height}px`,
      );
    const observer = new ResizeObserver(update);
    observer.observe(element);
    update();
    return () => {
      observer.disconnect();
      document.documentElement.style.removeProperty("--comparison-tray-height");
    };
  }, [refs.length, location.pathname]);
  useLayoutEffect(() => {
    const changed = previousKey.current !== location.key;
    previousKey.current = location.key;
    if (changed) {
      if (navigation === "POP")
        window.scrollTo(0, positions.current.get(location.key) ?? 0);
      else {
        window.scrollTo(0, 0);
        document.getElementById("page-heading")?.focus({ preventScroll: true });
      }
    }
    if (location.hash === "#collection") {
      document.getElementById("collection")?.scrollIntoView({ block: "start" });
      document
        .getElementById("collection-heading")
        ?.focus({ preventScroll: true });
    }
    if (
      ["#detail-specifications", "#detail-description"].includes(location.hash)
    ) {
      const heading = document.getElementById(location.hash.slice(1));
      heading?.scrollIntoView({ block: "start" });
      heading?.focus({ preventScroll: true });
    }
    const save = () => positions.current.set(location.key, window.scrollY);
    window.addEventListener("scroll", save, { passive: true });
    return () => window.removeEventListener("scroll", save);
  }, [location.key, location.hash, navigation]);
  const own = (children: ReactNode) => (
    <OwnerGate openIdentity={() => open("identity")}>{children}</OwnerGate>
  );
  const showTray =
    refs.length > 0 &&
    ["/", "/cars"].some(
      (path) =>
        location.pathname === path ||
        (path === "/cars" && location.pathname.startsWith("/cars/")),
    );
  return (
    <div
      ref={revealRoot}
      className={`proof cinematic workspace${location.pathname === "/" ? "" : " inner-workspace v7-workspace"}`}
      data-text-size="normal"
      data-context-panel={panel ?? undefined}
    >
      <a className="folio-skip-link" href="#main-content">
        Skip to cars
      </a>
      <CinemaHeader
        key={location.pathname}
        count={navigationRefs.length}
        path={location.pathname}
        compareHref={comparisonPath(navigationRefs)}
        browseKey={browseKey}
        onAssistant={() => open("assistant")}
        onHelp={() => open("help")}
      />
      {(health.isError ||
        (health.data && health.data.data.inventory.state !== "ready")) && (
        <p className="workspace-capability cinema-width" role="status">
          Inventory: {health.data?.data.inventory.state ?? "unavailable"}.{" "}
          {health.data?.data.inventory.reason ??
            "The service could not be reached. Reads will show their actual result."}
        </p>
      )}
      <main id="main-content" tabIndex={-1}>
        {location.pathname !== "/" && (
          <>
            <ShortlistNotice />
            <ViewingNotice />
          </>
        )}
        <QueryGuard>
          <Routes>
            <Route
              path="/"
              element={
                <BrowseRoute
                  home
                  onFilters={() => open("filters")}
                  selection={{ refs, toggle }}
                  openIdentity={() => open("identity")}
                />
              }
            />
            <Route
              path="/cars"
              element={
                <BrowseRoute
                  selection={{ refs, toggle }}
                  onFilters={() => open("filters")}
                  openIdentity={() => open("identity")}
                />
              }
            />
            <Route
              path="/cars/:listingRef"
              element={
                <DetailRoute
                  selection={{ refs, toggle }}
                  openIdentity={() => open("identity")}
                />
              }
            />
            <Route
              path="/compare"
              element={
                <CompareRoute
                  selection={{ refs, toggle }}
                  openAssistant={() => open("assistant")}
                  onSelectionChange={(next) => {
                    setWarning(null);
                    setSelected(next);
                  }}
                />
              }
            />
            <Route
              path="/shortlist"
              element={own(<ShortlistRoute selection={{ refs, toggle }} />)}
            />
            <Route
              path="/viewings/new/:listingRef"
              element={
                <NewViewingRoute openIdentity={() => open("identity")} />
              }
            />
            <Route
              path="/viewings/drafts/:draftId"
              element={own(<DraftRoute />)}
            />
            <Route
              path="/viewings/drafts/:draftId/review"
              element={own(<DraftRoute />)}
            />
            <Route
              path="/operations/:operationKey"
              element={
                <OwnedOperationRoute openIdentity={() => open("identity")} />
              }
            />
            <Route path="/about" element={<AboutRoute />} />
            <Route path="*" element={<InvalidRoute />} />
          </Routes>
        </QueryGuard>
      </main>
      {showTray && (
        <aside
          ref={tray}
          className="proof-selection"
          aria-label="Comparison selection"
        >
          <span>{refs.length} of 3 selected</span>
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
      )}
      <ContextPanel
        kind={panel}
        close={() => setPanel(null)}
        opener={() => opener.current}
        inner={location.pathname !== "/"}
        openIdentity={() => setPanel("identity")}
      />
    </div>
  );
}
