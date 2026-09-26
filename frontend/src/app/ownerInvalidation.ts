import type { OwnerSession } from "../shared/api/OwnerSession";

type InvalidationChannel = Pick<
  BroadcastChannel,
  "addEventListener" | "removeEventListener" | "postMessage" | "close"
>;

/** Integration seam: attach once in the later owner boundary; no private payloads. */
export function bindOwnerInvalidation(
  owner: OwnerSession,
  revalidate: () => Promise<unknown>,
  target: Window,
  channel?: InvalidationChannel,
) {
  let disposed = false;
  let checking = false;
  let checkAgain = false;
  const check = async () => {
    if (disposed) return;
    if (checking) {
      checkAgain = true;
      return;
    }
    checking = true;
    try {
      await revalidate();
    } catch {
      /* Explicit invalidation still hides private state before rechecking. */
    } finally {
      checking = false;
      if (checkAgain && !disposed) {
        checkAgain = false;
        void check();
      }
    }
  };
  const focus = () => {
    void check();
  };
  const hide = () => {
    owner.invalidate();
  };
  const show = (event: PageTransitionEvent) => {
    if (event.persisted) focus();
  };
  const message = (event: MessageEvent<unknown>) => {
    if (event.data === "invalidate") {
      owner.invalidate();
      void check();
    }
  };
  target.addEventListener("focus", focus);
  target.addEventListener("pagehide", hide);
  target.addEventListener("pageshow", show);
  channel?.addEventListener("message", message);
  return {
    notifyOtherTabs() {
      channel?.postMessage("invalidate");
    },
    dispose() {
      disposed = true;
      target.removeEventListener("focus", focus);
      target.removeEventListener("pagehide", hide);
      target.removeEventListener("pageshow", show);
      channel?.removeEventListener("message", message);
      channel?.close();
    },
  };
}
