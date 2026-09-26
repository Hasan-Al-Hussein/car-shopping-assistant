import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { Button } from "../shared/ui/Button";
import { CinemaIcon } from "../shared/ui/CinemaIcon";
import { TextField } from "../shared/ui/TextField";
import { ConversationPanel } from "../features/conversation/ConversationPanel";
import { useIdentity, useServices } from "./ServicesProvider";
import { browseQuery } from "./routes";
import {
  criterionFields,
  rangeFields,
  criteriaFromFilters,
  mergeCriteria,
  preferencesFromText,
} from "../features/inventory/criteria";
import { validateRequestBody } from "../../../contracts/generated/runtime";

export type PanelKind = "assistant" | "filters" | "help" | "identity";
const narrowQuery = "(max-width: 959px)";
const subscribeMedia = (callback: () => void) => {
  const media = window.matchMedia(narrowQuery);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
};
const getNarrow = () => window.matchMedia(narrowQuery).matches;
const titles: Record<PanelKind, string> = {
  assistant: "Car assistant",
  filters: "Find a car",
  help: "Help and browser access",
  identity: "Your browser access",
};
const descriptions: Record<PanelKind, string> = {
  assistant: "A little guidance for your next car.",
  filters: "Narrow the collection using the facts in the original listings.",
  help: "A few useful details about the cars, your context and safe next steps.",
  identity: "Control access to saved and private information in this browser.",
};

export function ContextPanel({
  kind,
  close,
  opener,
  inner,
  openIdentity,
}: {
  kind: PanelKind | null;
  close: () => void;
  opener: () => HTMLElement | null;
  inner: boolean;
  openIdentity: () => void;
}) {
  const narrow = useSyncExternalStore(subscribeMedia, getNarrow);
  const identity = useIdentity();
  const content = useRef<HTMLDivElement>(null);
  const [chatHeaderTools, setChatHeaderTools] = useState<HTMLDivElement | null>(
    null,
  );
  const previousKind = useRef(kind);
  useLayoutEffect(() => {
    // A panel switch removes its initiating control without closing the dialog.
    if (previousKind.current && kind && previousKind.current !== kind) {
      content.current?.focus({ preventScroll: true });
    }
    previousKind.current = kind;
  }, [kind]);
  return (
    <Dialog.Root
      open={kind !== null}
      modal={narrow}
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <Dialog.Portal>
        {narrow && <Dialog.Overlay className="workspace-panel-overlay" />}
        <Dialog.Content
          ref={content}
          className={`workspace-panel dubizzle-panel${inner ? " inner-panel v7-panel" : ""}${kind === "assistant" ? " conversation-shell" : ""}`}
          data-panel-kind={kind ?? undefined}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            const initiatingElement = opener();
            if (initiatingElement?.isConnected) {
              initiatingElement.focus();
            } else {
              document.getElementById("page-heading")?.focus();
            }
          }}
          onKeyDownCapture={(event) => {
            if (
              !narrow &&
              event.key === "Tab" &&
              !event.altKey &&
              !event.ctrlKey &&
              !event.metaKey
            ) {
              // Dialog loops Tab even when nonmodal. Keep native wide-page traversal.
              event.stopPropagation();
            }
          }}
          onInteractOutside={(event) => {
            if (!narrow) event.preventDefault();
          }}
        >
          {kind !== "assistant" && (
            <p className="inner-panel-eyebrow">dubizzle / your workspace</p>
          )}
          <div className="workspace-panel-header">
            {kind === "assistant" ? (
              <div className="conversation-title">
                <span className="conversation-brand-mark">
                  <CinemaIcon kind="robot" />
                </span>
                <div>
                  <Dialog.Title>{titles.assistant}</Dialog.Title>
                </div>
              </div>
            ) : (
              <Dialog.Title>{kind ? titles[kind] : "Context"}</Dialog.Title>
            )}
            {kind === "assistant" && (
              <div
                className="conversation-header-tools"
                ref={setChatHeaderTools}
              />
            )}
            <Dialog.Close asChild>
              <Button variant="quiet" aria-label="Close">
                {kind === "assistant" ? "×" : "Close"}
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description
            className={
              kind === "assistant" ? "conversation-sr-only" : undefined
            }
          >
            {kind === "assistant" || (inner && kind)
              ? descriptions[kind]
              : "Continue your task here, or close this panel to return to the cars."}
          </Dialog.Description>
          {kind === "filters" && <Filters close={close} />}
          {kind === "identity" && <IdentityControls key={identity.epoch} />}
          {kind === "assistant" && (
            <ConversationPanel
              key={identity.epoch}
              openIdentity={openIdentity}
              close={close}
              headerTools={chatHeaderTools}
            />
          )}
          {kind === "help" && (
            <Help inner={inner} openIdentity={openIdentity} />
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Filters({ close }: { close: () => void }) {
  const services = useServices();
  const [original] = useState(() => services.currentBrowseRequest());
  const [initial] = useState(() => criteriaFromFilters(original?.filters));
  const [form, setForm] = useState(initial);
  const [preferences, setPreferences] = useState(
    () => original?.soft_preferences?.join("\n") ?? "",
  );
  const [error, setError] = useState<string | null>(null);
  const errorMessage = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (error) errorMessage.current?.focus();
  }, [error]);
  const navigate = useNavigate();
  return (
    <form
      className="workspace-form"
      onSubmit={(event) => {
        event.preventDefault();
        try {
          const trimmed = Object.fromEntries(
            Object.entries(form).map(([key, value]) => [key, value.trim()]),
          ) as typeof form;
          const filters = mergeCriteria(original?.filters, trimmed, initial);
          const softPreferences =
            preferences === original?.soft_preferences?.join("\n")
              ? original.soft_preferences
              : preferencesFromText(preferences);
          const request = {
            ...original,
            client_request_id: crypto.randomUUID(),
            query: original?.query ?? "",
            soft_preferences: softPreferences,
            filters,
            snapshot_id: null,
            cursor: null,
            page_size: original?.page_size ?? 20,
          };
          if (!validateRequestBody("search_inventory", request))
            throw Error(
              "These search conditions exceed a supported limit or have an invalid combination. Keep no more than 24 required conditions and 12 preferences.",
            );
          services.queueBrowseRequest(request);
          navigate(
            `/cars${browseQuery({ ...trimmed, snapshot: null, cursor: null })}`,
            { state: { browseKey: services.currentBrowseKey } },
          );
          close();
        } catch (problem) {
          setError(
            problem instanceof Error
              ? problem.message
              : "Check the filter values.",
          );
        }
      }}
    >
      <p>
        Apply exact inventory filters. Unsupported or unknown facts will not be
        treated as matches. Closing keeps your currently applied search.
      </p>
      {criterionFields.map(([key, label]) => (
        <TextField
          key={key}
          label={label}
          value={form[key]}
          maxLength={200}
          onChange={(event) => setForm({ ...form, [key]: event.target.value })}
        />
      ))}
      {rangeFields.map(([key, label]) => (
        <TextField
          key={key}
          label={label}
          value={form[key]}
          inputMode={key.startsWith("budget") ? "decimal" : "numeric"}
          maxLength={16}
          onChange={(event) => setForm({ ...form, [key]: event.target.value })}
        />
      ))}
      <p>
        Cash budget uses AED, not finance instalments. Empty bounds leave that
        side open. Applying keeps your text search and any unchanged criteria.
      </p>
      <p>
        Budget matching excludes unknown or conflicting cash prices. Source
        coverage is shown with the results.
      </p>
      <p>
        Fields show the first value when the current search has several
        alternatives. Editing a field replaces its alternatives; unchanged
        fields keep all their values.
      </p>
      {original?.filters?.budget &&
        original.filters.budget.currency !== "AED" && (
          <p>
            The current {original.filters.budget.currency} budget is retained
            unless you enter a new AED budget.
          </p>
        )}
      <label className="folio-field">
        <span className="folio-field__label">Preferences (one per line)</span>
        <textarea
          className="folio-input"
          value={preferences}
          maxLength={2412}
          rows={3}
          onChange={(event) => setPreferences(event.target.value)}
        />
      </label>
      <p>
        Preferences guide ranking where supported. They do not relax the
        required filters above.
      </p>
      {error && (
        <p role="alert" tabIndex={-1} ref={errorMessage}>
          {error}
        </p>
      )}
      <Button type="submit">Apply filters</Button>
    </form>
  );
}

function IdentityControls() {
  const services = useServices(),
    view = useIdentity();
  const config = useQuery(services.queries.publicRead("get_config", {}, null));
  const [name, setName] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [endAcknowledged, setEndAcknowledged] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  return (
    <div className="workspace-form">
      {view.notice && <p role="status">{view.notice}</p>}
      {view.phase === "recognized" ? (
        <>
          <h3 ref={heading}>Saving and chat are enabled</h3>
          <p>
            {view.identity?.display_name || "This browser"} · This browser only.
            A display name is not a recovery credential.
          </p>
          <p>
            Preferences are saved only through explicit actions. Starting a
            conversation does not make a booking or send an enquiry.
          </p>
          <Button
            disabled={view.pending}
            onClick={() => void services.createSession()}
          >
            Start a new conversation
          </Button>
          {view.session && (
            <p role="status">
              Current conversation is available in this local context.
            </p>
          )}
          <label className="workspace-check">
            <input
              type="checkbox"
              checked={endAcknowledged}
              onChange={(event) => setEndAcknowledged(event.target.checked)}
            />
            I understand ending local access can make existing records
            inaccessible from this browser. It does not delete them.
          </label>
          <Button
            variant="secondary"
            disabled={!endAcknowledged || view.pending}
            onClick={() => void services.end(endAcknowledged)}
          >
            End browser access
          </Button>
        </>
      ) : (
        <>
          <p>
            Browse and compare without enabling access. Enable access in this
            browser to save cars and use chat.
          </p>
          <p className="inner-access-terms">
            Access is tied to this browser. Anyone using this browser profile
            can access the same saved and private information. Clearing its
            cookies or ending access may make saved records inaccessible; it
            does not delete them. Your display name cannot restore access.
            Viewing and enquiry actions are simulated and local; nothing is sent
            to a dealer.
          </p>
          <TextField
            label="Display name (optional)"
            value={name}
            maxLength={100}
            autoComplete="off"
            onChange={(event) => setName(event.target.value)}
          />
          <label className="workspace-check">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I understand how browser access and saving work.
          </label>
          <Button
            disabled={
              !acknowledged ||
              view.pending ||
              !config.data ||
              !["anonymous", "lost"].includes(view.phase)
            }
            onClick={() => {
              if (config.data)
                void services.bootstrap(
                  config.data.data.notice_version ?? "DEMO-POLICY-1",
                  acknowledged,
                  name,
                );
            }}
          >
            Enable saving and chat
          </Button>
          {view.phase === "checking" && (
            <p role="status">Checking local access…</p>
          )}
          {config.isError && (
            <p>
              The access notice could not be verified. The service must be
              available before starting local access.
            </p>
          )}
        </>
      )}
      <Button
        variant="quiet"
        disabled={view.pending}
        onClick={() => {
          void services.revalidate();
          void config.refetch();
        }}
      >
        Check browser access
      </Button>
    </div>
  );
}

function Help({
  inner,
  openIdentity,
}: {
  inner: boolean;
  openIdentity: () => void;
}) {
  const browserAccess = (
    <section>
      <h3>Your chat and browser access</h3>
      <p>
        Chat messages use a hosted AI service. Keep contact details and
        documents out of chat; use the local enquiry form for optional contact
        details.
      </p>
      <p>
        Anyone using this browser profile can access its saved cars and private
        conversations. Ending access does not delete those records.
      </p>
      <Button variant="secondary" onClick={openIdentity}>
        Manage browser access
      </Button>
    </section>
  );
  if (inner)
    return (
      <div className="workspace-form inner-help-sections">
        <section>
          <span>01 / THE LISTINGS</span>
          <h3>Read the claims in context.</h3>
          <p>
            Listing claims may be incomplete or disagree. Unknown does not mean
            absent or zero. A source photo does not verify vehicle condition.
          </p>
        </section>
        <section>
          <span>02 / YOUR COMPARISON</span>
          <h3>Three cars, side by side.</h3>
          <p>
            Comparison holds up to three cars in this browser view. It does not
            save a shortlist or reserve a car.
          </p>
        </section>
        <section>
          <span>03 / SAVING & RECOVERY</span>
          <h3>Keep the original action.</h3>
          <p>
            Saving requires an explicit action under your local access. A
            timeout or cancelled request does not prove a booking or enquiry
            failed. Keep the original operation reference and check its status.
          </p>
        </section>
        {browserAccess}
        <p className="inner-panel-simulation">
          No real dealer, calendar, payment or delivery service is connected.
        </p>
      </div>
    );
  return (
    <div className="workspace-form">
      <p>
        Listing claims may be incomplete or disagree. Unknown does not mean
        absent or zero. A source photo does not verify vehicle condition.
      </p>
      <p>
        Comparison holds up to three cars in this browser view. It does not save
        a shortlist or reserve a car.
      </p>
      <p>
        Saving requires an explicit action under your local access. A timeout or
        cancelled request does not prove a booking or enquiry failed. Keep the
        original operation reference and check its status.
      </p>
      {browserAccess}
      <p>No real dealer, calendar, payment or delivery service is connected.</p>
    </div>
  );
}
