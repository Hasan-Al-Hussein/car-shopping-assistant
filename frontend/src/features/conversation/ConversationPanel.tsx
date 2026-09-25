import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router";
import type { Schema } from "../../shared/api/contracts";
import { useIdentity, useServices } from "../../app/ServicesProvider";
import {
  decodeRef,
  listingPath,
  operationPath,
  parseComparison,
  refKey,
} from "../../app/routes";
import "./conversation.css";
import { Button } from "../../shared/ui/Button";
import { CinemaIcon } from "../../shared/ui/CinemaIcon";
import {
  ConversationAnswer,
  RememberedPreferences,
} from "./ConversationContent";
import type {
  ConversationContext,
  ConversationSessionView,
} from "./ConversationFlow";

export function pageConversationContext(
  pathname: string,
  proof: Schema<"PresentationProof"> | null,
): ConversationContext | null {
  const ref = pathname.startsWith("/cars/")
    ? decodeRef(pathname.slice("/cars/".length))
    : null;
  if (ref)
    return {
      label: `Listing ${ref.source_id}`,
      selectedRef: ref,
      presentation: proof?.ordered_refs.some(
        (item) => refKey(item) === refKey(ref),
      )
        ? proof
        : null,
    };
  if (proof && (pathname === "/" || pathname === "/cars"))
    return {
      label: `Original displayed order of ${proof.ordered_refs.length} cars`,
      selectedRef: null,
      presentation: proof,
    };
  return null;
}

export function ConversationPanel({
  openIdentity,
  close,
}: {
  openIdentity: () => void;
  close: () => void;
}) {
  const services = useServices(),
    identity = useIdentity(),
    location = useLocation();
  const view = useSyncExternalStore(
    services.conversation.subscribe,
    services.conversation.getSnapshot,
  );
  const health = useQuery({
    ...services.queries.publicRead("get_health", {}, null),
    refetchOnMount: true,
  });
  const sessionId = identity.session?.session_id;
  useEffect(() => {
    if (identity.phase === "recognized" && sessionId)
      void services.conversation.activate(sessionId);
  }, [services, identity.phase, sessionId]);
  const active = view.active?.sessionId === sessionId ? view.active : null;
  const browseKey =
    location.pathname === "/" || location.pathname === "/cars"
      ? location.key
      : (location.state?.browseKey ?? services.currentBrowseKey);
  const context = pageConversationContext(
    location.pathname,
    services.browsePresentation(browseKey),
  );
  const comparison =
    location.pathname === "/compare" ? parseComparison(location.search) : null;
  const serviceState =
    health.data?.data.assistant.state ??
    (health.isError ? "unavailable" : "checking");
  const unverified =
    serviceState === "degraded" &&
    [
      "configured_not_verified",
      "Assistant access is configured but not yet verified.",
    ].includes(health.data?.data.assistant.reason ?? "");
  const serviceReady = serviceState === "ready" || serviceState === "degraded";
  const serviceLabel = unverified
    ? active
      ? "Ask about a car, or explore your options."
      : "Start a conversation to try the assistant."
    : serviceState === "ready"
      ? "Ready for your questions."
      : serviceState === "degraded"
        ? "You can try a message. Responses may be limited."
        : serviceState === "checking"
          ? "Checking the assistant…"
          : serviceState === "unconfigured"
            ? "Chat is not configured yet. You can still browse and compare."
            : "Chat is temporarily unavailable. Please check again.";
  const serviceNotice = (
    <div
      className="conversation-service"
      data-service-state={unverified ? "unverified" : serviceState}
    >
      <p role="status">{serviceLabel}</p>
      <Button
        variant="quiet"
        aria-label="Check assistant service"
        disabled={health.isFetching}
        onClick={() => void health.refetch()}
      >
        Check
      </Button>
    </div>
  );
  const accountControls = (
    <>
      {identity.notice && !sessionId && (
        <p className="conversation-notice" role="status">
          {identity.notice}
        </p>
      )}
      {services.hasUncertainSession ? (
        <div className="conversation-session-recovery">
          <p>
            We could not confirm your original conversation request. Retrying
            uses that same request and may create it now.
          </p>
          <Button
            disabled={identity.pending}
            onClick={() => void services.retryOriginalSession()}
          >
            Retry original conversation request
          </Button>
        </div>
      ) : !sessionId ? (
        <div className="conversation-welcome">
          <span className="conversation-avatar">
            <CinemaIcon kind="sparkle" />
          </span>
          <h3>Let’s find your next car.</h3>
          <p>
            Tell me what matters to you — a make, a budget, or a car you have
            your eye on.
          </p>
          <Button
            disabled={identity.pending}
            onClick={() => void services.createSession()}
          >
            {identity.pending ? "Starting conversation…" : "Start conversation"}
          </Button>
        </div>
      ) : (
        <div className="conversation-account-options">
          <p>
            A new conversation keeps permitted saved preferences and starts
            without the previous car selection.
          </p>
          <Button
            variant="quiet"
            disabled={identity.pending}
            onClick={() => void services.createSession()}
          >
            Start a new conversation
          </Button>
          <Button variant="quiet" onClick={openIdentity}>
            Manage browser access
          </Button>
          {identity.notice && <p role="status">{identity.notice}</p>}
        </div>
      )}
      {view.recoverableSessions
        .filter((id) => id !== sessionId)
        .map((id) => (
          <Button
            key={id}
            variant="quiet"
            disabled={identity.pending}
            onClick={() => void services.readSession(id)}
          >
            Return to unresolved conversation
          </Button>
        ))}
    </>
  );
  const footer = (
    <p className="conversation-footer">
      AI can make mistakes. Check the listing facts.{" "}
      <Link to="/cars" onClick={close}>
        Browse cars
      </Link>
    </p>
  );
  return (
    <div className="conversation-panel" data-chat-active={!!active}>
      {active ? (
        <ConversationWorkspace
          key={`${identity.epoch}:${active.sessionId}`}
          active={active}
          pageContext={context}
          comparison={comparison}
          serviceReady={serviceReady}
          close={close}
          options={
            <>
              {serviceReady ? serviceNotice : null}
              {accountControls}
            </>
          }
          serviceNotice={!serviceReady ? serviceNotice : null}
          footer={footer}
        />
      ) : (
        <div className="conversation-onboarding-scroll">
          {serviceNotice}
          {identity.phase !== "recognized" ? (
            <ChatOnboarding openIdentity={openIdentity} />
          ) : (
            accountControls
          )}
          {sessionId && identity.phase === "recognized" ? (
            <p role="status">Reading this conversation…</p>
          ) : null}
          {footer}
        </div>
      )}
    </div>
  );
}

function ChatOnboarding({ openIdentity }: { openIdentity: () => void }) {
  const services = useServices(),
    identity = useIdentity();
  const config = useQuery(services.queries.publicRead("get_config", {}, null));
  const [acknowledged, setAcknowledged] = useState(false);
  const canEnable =
    !!config.data && ["anonymous", "lost"].includes(identity.phase);
  return (
    <div className="conversation-onboarding">
      <div className="conversation-welcome">
        <span className="conversation-avatar">
          <CinemaIcon kind="sparkle" />
        </span>
        <h3>A little help finding the right car.</h3>
        <p>
          Ask about the cars, compare the details, or tell me what you are
          looking for.
        </p>
      </div>
      <div className="conversation-consent">
        <h3>Enable chat in this browser</h3>
        <p>
          Messages use a hosted AI assistant. Keep contact details and documents
          out of chat.
        </p>
        <details>
          <summary>How browser access works</summary>
          <p>
            Anyone using this browser profile can access its saved cars and
            private conversations. Clearing cookies or ending access may make
            records inaccessible; it does not delete them. A display name cannot
            restore access.
          </p>
          <p>
            Viewing and enquiry actions are simulated and saved locally. Nothing
            is sent to a dealer. Chat does not make a booking when you enable
            it.
          </p>
        </details>
        <label className="conversation-consent-check">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          <span>
            I understand and agree to enable browser access for chat and saving.
          </span>
        </label>
        <Button
          disabled={!acknowledged || identity.pending || !canEnable}
          onClick={() => {
            if (config.data && acknowledged)
              void services.bootstrap(
                config.data.data.notice_version ?? "DEMO-POLICY-1",
                acknowledged,
                "",
              );
          }}
        >
          {identity.pending ? "Enabling chat…" : "Enable chat"}
        </Button>
        {identity.phase === "checking" && (
          <p role="status">Checking browser access…</p>
        )}
        {identity.notice && <p role="status">{identity.notice}</p>}
        {(config.isError || identity.phase === "unavailable") && (
          <>
            <p>We could not verify browser access. Check again to continue.</p>
            <Button
              variant="secondary"
              disabled={identity.pending || config.isFetching}
              onClick={() => {
                void services.revalidate();
                void config.refetch();
              }}
            >
              Check browser access
            </Button>
          </>
        )}
        <Button variant="quiet" onClick={openIdentity}>
          More access options
        </Button>
      </div>
    </div>
  );
}

function conversationScrollOwner(transcript: HTMLElement) {
  const panel = transcript.closest<HTMLElement>(".conversation-panel");
  return panel && getComputedStyle(panel).overflowY === "auto"
    ? panel
    : transcript;
}

function ConversationWorkspace({
  active,
  pageContext,
  comparison,
  serviceReady,
  close,
  options,
  serviceNotice,
  footer,
}: {
  active: ConversationSessionView;
  pageContext: ConversationContext | null;
  comparison: Schema<"InventoryRef">[] | null;
  serviceReady: boolean;
  close: () => void;
  options: ReactNode;
  serviceNotice: ReactNode;
  footer: ReactNode;
}) {
  const services = useServices(),
    flow = services.conversation;
  const scroll = useRef<HTMLDivElement>(null),
    nearEnd = useRef(true),
    previousChange = useRef(active.turnChange),
    refreshing = useRef(false),
    composing = useRef(false);
  const [newResponse, setNewResponse] = useState(false),
    [refreshPending, setRefreshPending] = useState(false),
    [replyEnabled, setReplyEnabled] = useState(true);
  const session = active.session,
    pending = session?.pending_intent;
  const clarification = pending?.kind === "clarification" ? pending : null;
  const reply =
    replyEnabled && clarification
      ? {
          intent_id: clarification.intent_id,
          created_revision: clarification.created_revision,
        }
      : null;
  const contextLabel =
    active.stagedContext?.label ??
    (session?.selected_ref
      ? `Conversation listing ${session.selected_ref.source_id}`
      : session?.active_presentation_id
        ? "Original conversation result order"
        : (pageContext?.label ??
          "No exact car context; the assistant may ask you to clarify"));
  const busy =
    active.commandBusy ||
    active.phase === "sending" ||
    active.phase === "reading" ||
    active.phase === "blocked" ||
    active.hasOriginal;
  const reading = refreshPending || active.phase === "reading";
  useEffect(() => {
    const transcript = scroll.current;
    if (!transcript) return;
    const panel = transcript.closest<HTMLElement>(".conversation-panel");
    const track = (event: Event) => {
      const owner = conversationScrollOwner(transcript);
      if (event.currentTarget === owner)
        nearEnd.current =
          owner.scrollHeight - owner.scrollTop - owner.clientHeight < 70;
    };
    transcript.addEventListener("scroll", track, { passive: true });
    panel?.addEventListener("scroll", track, { passive: true });
    return () => {
      transcript.removeEventListener("scroll", track);
      panel?.removeEventListener("scroll", track);
    };
  }, []);
  useLayoutEffect(() => {
    const transcript = scroll.current;
    if (!transcript) return;
    const element = conversationScrollOwner(transcript);
    if (nearEnd.current) {
      const answer = element.querySelector<HTMLElement>(
        ".conversation-turns > li:last-child .conversation-assistant-message",
      );
      // Show the new answer's beginning, not the final attachment controls.
      element.scrollTop = answer
        ? element.scrollTop +
          answer.getBoundingClientRect().top -
          element.getBoundingClientRect().top -
          element.clientTop
        : element.scrollHeight;
    } else if (previousChange.current !== active.turnChange)
      setNewResponse(true);
    previousChange.current = active.turnChange;
  }, [active.turnChange]);
  const showLatest = () => {
    const transcript = scroll.current;
    if (transcript) {
      const element = conversationScrollOwner(transcript);
      element.scrollTop = element.scrollHeight;
      transcript.focus({ preventScroll: true });
    }
    nearEnd.current = true;
    setNewResponse(false);
  };
  const refreshConversation = async () => {
    if (refreshing.current || active.phase === "reading") return;
    refreshing.current = true;
    setRefreshPending(true);
    try {
      await flow.refresh(active.sessionId);
    } finally {
      refreshing.current = false;
      setRefreshPending(false);
    }
  };
  const stage = (context: ConversationContext) => {
    flow.stageContext(active.sessionId, context);
    setReplyEnabled(true);
  };
  const submit = () => {
    if (composing.current || busy || !serviceReady || !session) return;
    void flow.send(active.sessionId, pageContext, reply);
  };
  const localIds = new Set(
    active.localTurns
      .filter((turn) => turn.result)
      .map((turn) => turn.clientId),
  );
  const turns = [
    ...active.turns
      .filter((turn) => !localIds.has(turn.client_message_id))
      .map((turn) => ({
        id: turn.client_message_id,
        revision: turn.accepted_revision,
        text: turn.user_text,
        result: turn.assistant_result,
        state: turn.state,
      })),
    ...active.localTurns.map((turn) => ({
      id: turn.clientId,
      revision: turn.revision,
      text: turn.text,
      result: turn.result,
      state: "local",
    })),
  ].sort((a, b) => a.revision - b.revision);
  return (
    <div className="conversation-workspace">
      <div
        className="conversation-transcript"
        ref={scroll}
        tabIndex={0}
        role="region"
        aria-label="Conversation transcript"
      >
        {serviceNotice}
        {pending?.kind === "operation_unresolved" && (
          <p>
            <Link
              to={operationPath(
                pending.operation_key,
                pending.submitted_store_generation,
              )}
              onClick={close}
            >
              Read the original unresolved viewing outcome
            </Link>
          </p>
        )}
        {pending?.kind === "viewing_review" && (
          <p>
            <Link
              to={`/viewings/drafts/${pending.draft_id}/review`}
              onClick={close}
            >
              Open exact viewing review
            </Link>
            . Confirm only after reviewing the current terms there.
          </p>
        )}
        <ol className="conversation-turns">
          {turns.map((turn) => (
            <li key={turn.id}>
              <div className="conversation-user-message">
                <h3>You</h3>
                <p className="conversation-text" dir="auto">
                  {turn.text}
                </p>
              </div>
              {turn.result ? (
                <div className="conversation-assistant-message">
                  <h3>
                    <span className="conversation-avatar">
                      <CinemaIcon kind="robot" />
                    </span>{" "}
                    Assistant
                  </h3>
                  <ConversationAnswer
                    result={turn.result}
                    onContext={stage}
                    close={close}
                    contextDisabled={busy}
                  />
                </div>
              ) : active.phase === "sending" &&
                turn === turns[turns.length - 1] ? (
                <div className="conversation-thinking" role="status">
                  <span className="conversation-avatar">
                    <CinemaIcon kind="robot" />
                  </span>
                  <span>
                    Thinking
                    <span
                      className="conversation-thinking-dots"
                      aria-hidden="true"
                    >
                      …
                    </span>
                  </span>
                </div>
              ) : (
                <p>
                  {turn.state === "interrupted"
                    ? "This message was interrupted. Some requested changes may already have been saved. Refresh the conversation to check for updates. Don’t resend it as a new message."
                    : "We haven’t received the result yet. Refresh the conversation to check for updates. Don’t send it again as a new message while the result is unknown."}
                </p>
              )}
            </li>
          ))}
        </ol>
        {!active.turns.length && !active.localTurns.length && (
          <div className="conversation-empty">
            <span className="conversation-avatar">
              <CinemaIcon kind="sparkle" />
            </span>
            <h3>What are you looking for?</h3>
            <p>
              Try a budget, a favourite make, or a question about the car on
              this page.
            </p>
            <div className="conversation-prompts">
              {[
                "Help me find a car within my budget",
                "What should I check before choosing?",
              ].map((prompt) => (
                <button
                  type="button"
                  key={prompt}
                  disabled={busy}
                  onClick={() => flow.setText(active.sessionId, prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        {active.nextCursor && (
          <Button
            variant="secondary"
            onClick={() => void flow.loadMore(active.sessionId)}
          >
            Load more messages
          </Button>
        )}
        <p className="conversation-notice" role="status" aria-atomic="true">
          {reading ? "Reading this conversation…" : (active.notice ?? "")}
        </p>
        {clarification && (
          <div className="conversation-clarification">
            <p>{clarification.question}</p>
            <label>
              <input
                type="checkbox"
                checked={replyEnabled}
                onChange={(event) => setReplyEnabled(event.target.checked)}
              />{" "}
              Reply to this exact clarification
            </label>
          </div>
        )}
        <div className="conversation-recovery">
          {active.hasOriginal && (
            <Button
              variant="secondary"
              disabled={
                active.commandBusy ||
                active.phase === "sending" ||
                active.phase === "reading"
              }
              onClick={() => void flow.checkOriginal(active.sessionId)}
            >
              Check this request
            </Button>
          )}
          {active.canRetry && (
            <>
              <p>
                This sends the same request again. If it wasn’t received
                earlier, it may be carried out now.
              </p>
              <Button
                variant="secondary"
                disabled={active.commandBusy}
                onClick={() => void flow.retryOriginal(active.sessionId)}
              >
                Retry this request
              </Button>
            </>
          )}
        </div>
        {!serviceReady && (
          <p>
            The assistant is not currently ready. Your unsent text stays here;
            direct car tools remain available.
          </p>
        )}
        <details className="conversation-tools">
          <summary>Conversation options</summary>
          {options}
          <Button
            variant="quiet"
            aria-disabled={reading}
            aria-busy={reading}
            onClick={() => void refreshConversation()}
          >
            Refresh conversation
          </Button>
          <details className="conversation-draft-note">
            <summary>About your messages</summary>
            <p>
              Close and reopen to keep unsent text in this browser context.
              Ending or resetting access clears it. Messages use a hosted AI
              assistant; keep contacts and documents out of chat.
            </p>
          </details>
          <details
            className="conversation-context"
            aria-label="Message context"
          >
            <summary>
              Message context <span>{contextLabel}</span>
            </summary>
            {session?.selected_ref && (
              <Link to={listingPath(session.selected_ref)} onClick={close}>
                Inspect the exact conversation car
              </Link>
            )}
            {active.stagedContext?.presentation &&
              !active.stagedContext.selectedRef &&
              session?.selected_ref && (
                <p>
                  The current listing {session.selected_ref.source_id} stays
                  selected if it belongs to this result order. Otherwise choose
                  an exact returned car or start a new conversation.
                </p>
              )}
            <p>
              Sending uses the car or list named above. Choosing a car or list
              does not send a message.
            </p>
            {pageContext && (
              <Button
                variant="quiet"
                disabled={busy}
                onClick={() => stage(pageContext)}
              >
                Use this page for my next message
              </Button>
            )}
            {!!comparison?.length && (
              <details>
                <summary>Cars in the current comparison</summary>
                <ul>
                  {comparison.map((ref) => (
                    <li key={refKey(ref)}>
                      <Button
                        variant="quiet"
                        disabled={busy}
                        onClick={() =>
                          stage({
                            label: `Comparison listing ${ref.source_id}`,
                            selectedRef: ref,
                            presentation: null,
                          })
                        }
                      >{`Use listing ${ref.source_id} as context`}</Button>
                    </li>
                  ))}
                </ul>
                <p>
                  Choose a car by its listing reference. ‘The first car’ in chat
                  does not refer to this comparison’s order.
                </p>
              </details>
            )}
          </details>
          {session && (
            <details className="conversation-memory-options">
              <summary>Saved preferences recalled in this conversation</summary>
              <RememberedPreferences record={session.recalled_preferences} />
            </details>
          )}
        </details>
        {footer}
      </div>
      {newResponse && (
        <div className="conversation-new-response">
          <Button variant="secondary" onClick={showLatest}>
            New response — show latest
          </Button>
        </div>
      )}
      <form
        className="conversation-composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="conversation-sr-only" htmlFor="conversation-message">
          Message the car-shopping assistant
        </label>
        <textarea
          id="conversation-message"
          rows={2}
          placeholder="Message the car assistant…"
          value={active.text}
          aria-describedby="conversation-composer-help"
          onChange={(event) =>
            flow.setText(active.sessionId, event.target.value)
          }
          onCompositionStart={() => {
            composing.current = true;
          }}
          onCompositionEnd={() => {
            composing.current = false;
          }}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing &&
              !composing.current &&
              event.keyCode !== 229
            ) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <Button
          type="submit"
          aria-label="Send message"
          disabled={busy || !session || !serviceReady}
        >
          Send
        </Button>
        <p id="conversation-composer-help">
          {active.text.length}/4,000 · Enter sends · Shift+Enter for a new line
        </p>
      </form>
    </div>
  );
}
