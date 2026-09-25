import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import seed from "../../fixtures/shared/harness-seed.json";

function resetBrowserState() {
  localStorage.clear();
  sessionStorage.clear();
  // Vitest's jsdom environment exposes this jar; clearing it also covers non-root cookie paths.
  const environment = globalThis as typeof globalThis & {
    jsdom: { cookieJar: { removeAllCookiesSync(): void } };
  };
  environment.jsdom.cookieJar.removeAllCookiesSync();
  history.replaceState(null, "", "/");
}

beforeEach(() => {
  resetBrowserState();
  vi.useFakeTimers();
  vi.setSystemTime(new Date(seed.clock_utc));
  vi.stubGlobal("fetch", () =>
    Promise.reject(new Error("UNSCRIPTED_HTTP_CALL")),
  );
  vi.spyOn(XMLHttpRequest.prototype, "open").mockImplementation(() => {
    throw new Error("LIVE_NETWORK_DISABLED_IN_UNIT_TESTS");
  });
  vi.stubGlobal(
    "WebSocket",
    class {
      constructor() {
        throw new Error("LIVE_NETWORK_DISABLED_IN_UNIT_TESTS");
      }
    },
  );
});

afterEach(() => {
  try {
    cleanup();
  } finally {
    try {
      resetBrowserState();
    } finally {
      vi.clearAllTimers();
      vi.useRealTimers();
      vi.restoreAllMocks();
      vi.unstubAllGlobals();
    }
  }
});
