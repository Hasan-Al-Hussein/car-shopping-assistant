import { StrictMode, useRef } from "react";
import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { startScrollReveals } from "../../src/shared/ui/scrollReveal";
import { useScrollReveal } from "../../src/shared/ui/useScrollReveal";

describe("V8 progressive scroll motion", () => {
  let intersect: IntersectionObserverCallback;
  let mutation: MutationCallback;
  let changeMotion: (() => void) | undefined;
  const observe = vi.fn(),
    unobserve = vi.fn(),
    disconnect = vi.fn();
  const mutationDisconnect = vi.fn();
  const animations: {
    cancel: ReturnType<typeof vi.fn>;
    onfinish: (() => void) | null;
  }[] = [];
  const animate = vi.fn<
    (
      frames: Keyframe[] | PropertyIndexedKeyframes | null,
      options?: number | KeyframeAnimationOptions,
    ) => Animation
  >(() => {
    const result = { cancel: vi.fn(), onfinish: null };
    animations.push(result);
    return result as unknown as Animation;
  });
  const cleanups: (() => void)[] = [];
  let root: HTMLDivElement;
  let originalAnimate: PropertyDescriptor | undefined;
  let reduced = false;

  beforeEach(() => {
    root = document.createElement("div");
    document.body.append(root);
    reduced = false;
    animations.length = 0;
    changeMotion = undefined;
    [observe, unobserve, disconnect, mutationDisconnect, animate].forEach(
      (mock) => mock.mockClear(),
    );
    originalAnimate = Object.getOwnPropertyDescriptor(
      Element.prototype,
      "animate",
    );
    Object.defineProperty(Element.prototype, "animate", {
      configurable: true,
      writable: true,
      value: animate,
    });
    vi.stubGlobal("matchMedia", () => ({
      get matches() {
        return reduced;
      },
      addEventListener: (_name: string, callback: () => void) => {
        changeMotion = callback;
      },
      removeEventListener: vi.fn(),
    }));
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          intersect = callback;
        }
        observe = observe;
        unobserve = unobserve;
        disconnect = disconnect;
      },
    );
    vi.stubGlobal(
      "MutationObserver",
      class {
        constructor(callback: MutationCallback) {
          mutation = callback;
        }
        observe = vi.fn();
        disconnect = mutationDisconnect;
      },
    );
  });
  afterEach(() => {
    cleanups.splice(0).forEach((cleanup) => cleanup());
    root.remove();
    if (originalAnimate)
      Object.defineProperty(Element.prototype, "animate", originalAnimate);
    else Reflect.deleteProperty(Element.prototype, "animate");
  });
  function card(key: string, top = window.innerHeight + 80) {
    const element = document.createElement("article");
    element.dataset.reveal = key;
    const button = document.createElement("button");
    button.textContent = "View car";
    element.append(button);
    vi.spyOn(element, "getBoundingClientRect").mockReturnValue({
      top,
      bottom: top + 200,
      height: 200,
    } as DOMRect);
    root.append(element);
    return element;
  }
  function enter(element: HTMLElement) {
    intersect(
      [
        {
          target: element,
          isIntersecting: true,
          boundingClientRect: element.getBoundingClientRect(),
          intersectionRatio: 1,
          intersectionRect: element.getBoundingClientRect(),
          rootBounds: null,
          time: 0,
        },
      ],
      {} as IntersectionObserver,
    );
  }
  function start(seen = new Set<string>(), restoring = false) {
    const cleanup = startScrollReveals(root, seen, restoring);
    cleanups.push(cleanup);
    return cleanup;
  }

  test("reveals initial visible results and below-fold cards while keeping past content static", () => {
    const visible = card("visible", 50),
      above = card("above", -250),
      below = card("below");
    start();
    expect(observe).toHaveBeenCalledWith(below);
    expect(observe).toHaveBeenCalledWith(visible);
    expect(observe).not.toHaveBeenCalledWith(above);
    expect(visible.getAttribute("style")).toBeNull();
    expect(above.getAttribute("aria-hidden")).toBeNull();
    expect(animate).not.toHaveBeenCalled();
    enter(visible);
    expect(animate).toHaveBeenCalledOnce();
  });
  test("reveals each exact card once, with bounded opacity/translation and no hidden fill", () => {
    const element = card("snapshot/car-12"),
      seen = new Set<string>();
    start(seen);
    enter(element);
    enter(element);
    expect(animate).toHaveBeenCalledOnce();
    const [frames, options] = animate.mock.calls[0]!;
    const entrance = (frames as Keyframe[])[0]!;
    expect(Number(entrance.opacity)).toBeGreaterThan(0);
    expect(Number(entrance.opacity)).toBeLessThanOrEqual(1);
    expect(Object.keys(entrance).sort()).toEqual(["opacity", "transform"]);
    expect((options as KeyframeAnimationOptions).duration).toBeLessThanOrEqual(
      700,
    );
    expect(options).toEqual(expect.objectContaining({ fill: "none" }));
    animations[0]!.onfinish?.();
    expect(animations[0]!.cancel).toHaveBeenCalledOnce();
    expect(seen.has("snapshot/car-12")).toBe(true);
  });
  test("focus bypasses a waiting reveal and cancels an active one without moving focus", () => {
    const waiting = card("waiting"),
      active = card("active");
    start();
    const waitingButton = waiting.querySelector("button")!;
    waitingButton.focus();
    enter(waiting);
    expect(animate).not.toHaveBeenCalled();
    enter(active);
    const activeButton = active.querySelector("button")!;
    activeButton.focus();
    expect(animations[0]!.cancel).toHaveBeenCalledOnce();
    expect(activeButton).toHaveFocus();
  });
  test("reduced motion at entry leaves content available without an observer", () => {
    reduced = true;
    const element = card("reduced");
    start();
    expect(observe).not.toHaveBeenCalled();
    expect(element).toBeVisible();
    expect(element.querySelector("button")).toBeEnabled();
  });
  test("a live reduced-motion change cancels animation and disconnects both observers", () => {
    const element = card("active");
    start();
    enter(element);
    reduced = true;
    changeMotion?.();
    expect(animations[0]!.cancel).toHaveBeenCalledOnce();
    expect(disconnect).toHaveBeenCalled();
    expect(mutationDisconnect).toHaveBeenCalled();
  });
  test("restored history and missing animation support keep the static fallback", () => {
    const element = card("restored");
    start(new Set(), true);
    expect(observe).not.toHaveBeenCalled();
    Reflect.deleteProperty(Element.prototype, "animate");
    start();
    expect(observe).not.toHaveBeenCalled();
    expect(element).toBeVisible();
  });
  test("missing observer support leaves content visible and controls enabled", () => {
    const element = card("no-observer");
    vi.stubGlobal("IntersectionObserver", undefined);
    expect(() => start()).not.toThrow();
    expect(observe).not.toHaveBeenCalled();
    expect(element).toBeVisible();
    expect(element.querySelector("button")).toBeEnabled();
  });
  test("late data can reveal once; unmount cancels animations and prevents stale callbacks", () => {
    const cleanup = start();
    const element = card("late-result", 50);
    mutation(
      [{ addedNodes: [element] } as unknown as MutationRecord],
      {} as MutationObserver,
    );
    expect(observe).toHaveBeenCalledWith(element);
    enter(element);
    cleanup();
    enter(element);
    expect(animate).toHaveBeenCalledOnce();
    expect(animations[0]!.cancel).toHaveBeenCalledOnce();
    expect(disconnect).toHaveBeenCalled();
  });
  test("animation failure preserves enabled controls and does not escape into the page", () => {
    const element = card("failed-animation");
    animate.mockImplementationOnce(() => {
      throw new Error("Animation unavailable");
    });
    start();
    expect(() => enter(element)).not.toThrow();
    expect(element).toBeVisible();
    expect(element.querySelector("button")).toBeEnabled();
  });
  test("initial POP still enhances scroll under StrictMode, but Back never replays it", () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      top: window.innerHeight + 80,
    } as DOMRect);
    function Surface({
      visit,
      restoring,
    }: {
      visit: string;
      restoring: boolean;
    }) {
      const reference = useRef<HTMLDivElement>(null);
      useScrollReveal(reference, visit, restoring);
      return (
        <div ref={reference}>
          <article data-reveal="car">
            <button>View car</button>
          </article>
        </div>
      );
    }
    const view = render(
      <StrictMode>
        <Surface visit="initial" restoring />
      </StrictMode>,
    );
    expect(observe).toHaveBeenCalled();
    view.rerender(
      <StrictMode>
        <Surface visit="next" restoring={false} />
      </StrictMode>,
    );
    observe.mockClear();
    view.rerender(
      <StrictMode>
        <Surface visit="initial" restoring />
      </StrictMode>,
    );
    expect(observe).not.toHaveBeenCalled();
  });
});
