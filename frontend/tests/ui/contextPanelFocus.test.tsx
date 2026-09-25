import { useRef, useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ContextPanel } from "../../src/app/ContextPanel";
import { CinemaHeader } from "../../src/shared/ui/CinemaHeader";
import { MemoryRouter } from "react-router";

vi.mock("../../src/app/ServicesProvider", () => ({
  useIdentity: () => ({ epoch: 0 }),
  useServices: () => {
    throw new Error("Help panel must not access services");
  },
}));

function Fixture({ showOpener = true, revision = 0, mobileHeader = false }) {
  const [open, setOpen] = useState(false);
  const original = useRef<HTMLElement | null>(null);
  return (
    <>
      <h1 id="page-heading" tabIndex={-1}>
        Browse revision {revision}
      </h1>
      {mobileHeader && (
        <MemoryRouter>
          <CinemaHeader
            count={0}
            path="/"
            onHelp={() => {
              original.current = document.activeElement as HTMLElement;
              setOpen(true);
            }}
          />
        </MemoryRouter>
      )}
      {showOpener && !mobileHeader && (
        <button
          onClick={(event) => {
            original.current = event.currentTarget;
            setOpen(true);
          }}
        >
          Open help
        </button>
      )}
      <ContextPanel
        kind={open ? "help" : null}
        close={() => setOpen(false)}
        opener={() => original.current}
        inner
        openIdentity={() => {}}
      />
    </>
  );
}

const flush = () =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });

async function openPanel(narrow: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: narrow,
      media: "(max-width: 959px)",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  const view = render(<Fixture />);
  const opener = screen.getByRole("button", { name: "Open help" });
  opener.focus();
  fireEvent.click(opener);
  await flush();
  const close = screen.getByRole("button", { name: "Close" });
  expect(close).toHaveFocus();
  return { ...view, opener, close };
}

describe("ContextPanel focus regression; native traversal needs browser proof", () => {
  test.each(["Close", "Escape"])(
    "mobile Help keeps the visible Menu as the %s return target",
    async (method) => {
      vi.stubGlobal(
        "ResizeObserver",
        class {
          observe() {}
          disconnect() {}
        },
      );
      vi.stubGlobal(
        "matchMedia",
        vi.fn(() => ({
          matches: true,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
        })),
      );
      render(<Fixture mobileHeader />);
      fireEvent.click(screen.getByRole("button", { name: "Menu" }));
      const help = screen.getByRole("button", { name: "Help" });
      help.focus();
      fireEvent.click(help);
      await flush();
      const close = screen.getByRole("button", { name: "Close" });
      if (method === "Close") fireEvent.click(close);
      else fireEvent.keyDown(close, { key: "Escape", code: "Escape" });
      await flush();
      expect(screen.getByRole("button", { name: "Menu" })).toHaveFocus();
      expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute(
        "aria-expanded",
        "false",
      );
      expect(document.querySelector("#main-navigation")).toHaveAttribute(
        "data-open",
        "false",
      );
    },
  );
  test.each([false, true])(
    "Tab defaults are preserved wide and trapped narrow: narrow=%s",
    async (narrow) => {
      const { close } = await openPanel(narrow);
      // The help panel has one tabbable control, so both edges are exercised.
      expect(fireEvent.keyDown(close, { key: "Tab", code: "Tab" })).toBe(
        !narrow,
      );
      expect(
        fireEvent.keyDown(close, { key: "Tab", code: "Tab", shiftKey: true }),
      ).toBe(!narrow);
    },
  );

  test.each([false, true])(
    "Close restores the connected opener with native scrolling: narrow=%s",
    async (narrow) => {
      const { opener, close } = await openPanel(narrow);
      const focus = vi.spyOn(opener, "focus");
      fireEvent.click(close);
      await flush();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(opener).toHaveFocus();
      expect(focus).toHaveBeenLastCalledWith();
    },
  );

  test.each([false, true])(
    "Escape after opener removal focuses the heading with native scrolling: narrow=%s",
    async (narrow) => {
      const { rerender, opener, close } = await openPanel(narrow);
      rerender(<Fixture showOpener={false} />);
      expect(opener.isConnected).toBe(false);
      const heading = document.getElementById("page-heading")!;
      const focus = vi.spyOn(heading, "focus");
      fireEvent.keyDown(close, { key: "Escape", code: "Escape" });
      await flush();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(heading).toHaveFocus();
      expect(focus).toHaveBeenLastCalledWith();
    },
  );

  test.each([false, true])(
    "Passive shell rerender does not steal panel focus: narrow=%s",
    async (narrow) => {
      const { rerender, close } = await openPanel(narrow);
      rerender(<Fixture revision={1} />);
      await flush();
      expect(close).toHaveFocus();
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    },
  );
});
