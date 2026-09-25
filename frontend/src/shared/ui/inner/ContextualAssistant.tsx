import type { ReactNode } from "react";
import { CinemaIcon } from "../CinemaIcon";

export function ContextualAssistant({
  count,
  ready,
  preview,
  onVerify,
  onInspect,
  onOpen,
  children,
}: {
  count: number;
  ready: boolean;
  preview: boolean;
  onVerify: () => void;
  onInspect: () => void;
  onOpen?: () => void;
  children: ReactNode;
}) {
  return (
    <aside className="comparison-context" aria-label="Comparison support">
      <section
        className="inner-assistant"
        aria-labelledby="comparison-assistant-title"
      >
        <div className="inner-assistant-heading">
          <span className="inner-assistant-mark">
            <CinemaIcon kind="spark" />
          </span>
          <div>
            <h2 id="comparison-assistant-title">dubizzle car assistant</h2>
            <p>
              {preview
                ? "Design preview"
                : onOpen
                  ? "Continue in your conversation panel"
                  : "Not connected in this view"}
            </p>
          </div>
        </div>
        <div className="inner-assistant-response">
          <p className="inner-eyebrow">Your comparison</p>
          <p>
            {count
              ? `${count} selected ${count === 1 ? "car" : "cars"}. ${ready ? "Start with the details that still need checking." : "Source details are not currently loaded."}`
              : "Choose your first car. Its source details will appear here for you to compare."}
          </p>
          <span>Missing information and conflicting claims stay visible.</span>
        </div>
        <div className="inner-assistant-actions">
          <button type="button" onClick={onVerify} disabled={!ready}>
            <CinemaIcon kind="source" />
            Show facts to verify
            <CinemaIcon kind="arrow" />
          </button>
          <button type="button" onClick={onInspect} disabled={!ready}>
            <CinemaIcon kind="search" />
            Inspect selected listings
            <CinemaIcon kind="arrow" />
          </button>
        </div>
        {onOpen && !preview ? (
          <div className="inner-assistant-actions">
            <button type="button" onClick={onOpen}>
              Open car-shopping conversation
              <CinemaIcon kind="arrow" />
            </button>
            <p>
              Choose an exact car as context in the panel. Opening sends
              nothing.
            </p>
          </div>
        ) : (
          <>
            <label
              className="inner-composer-label"
              htmlFor="comparison-assistant-input"
            >
              Ask about these cars
            </label>
            <div className="inner-assistant-composer">
              <input
                id="comparison-assistant-input"
                disabled
                placeholder="Conversation unavailable"
                aria-describedby="comparison-assistant-status"
              />
              <button
                type="button"
                disabled
                aria-label="Send unavailable: conversation is not connected"
              >
                <CinemaIcon kind="arrow" />
              </button>
            </div>
            <p
              className="inner-assistant-status"
              id="comparison-assistant-status"
            >
              Use the source actions above to inspect these cars.
            </p>
          </>
        )}
      </section>
      <section
        className="inner-next-actions"
        aria-labelledby="comparison-next-title"
      >
        <p className="inner-eyebrow">Continue with perspective</p>
        <h2 id="comparison-next-title">Next steps</h2>
        {children}
      </section>
    </aside>
  );
}
