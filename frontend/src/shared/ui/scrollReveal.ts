/** Progressive decoration only: HTML and controls are visible before this runs. */
export function startScrollReveals(
  root: HTMLElement,
  seen: Set<string>,
  restoring = false,
): () => void {
  if (
    restoring ||
    typeof IntersectionObserver === "undefined" ||
    typeof MutationObserver === "undefined" ||
    typeof window.matchMedia !== "function" ||
    typeof Element.prototype.animate !== "function"
  )
    return () => {};

  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (motion.matches || typeof motion.addEventListener !== "function")
    return () => {};
  const observed = new Set<HTMLElement>();
  const animations = new Map<HTMLElement, Animation>();
  let stopped = false;
  const cancel = (element: HTMLElement) => {
    animations.get(element)?.cancel();
    animations.delete(element);
  };
  const observer = new IntersectionObserver(
    (entries) => {
      if (stopped) return;
      let stagger = 0;
      for (const entry of entries) {
        if (!entry.isIntersecting || !(entry.target instanceof HTMLElement))
          continue;
        const element = entry.target;
        observer.unobserve(element);
        observed.delete(element);
        const key = element.dataset.reveal;
        if (!key || seen.has(key)) continue;
        seen.add(key);
        if (
          !element.isConnected ||
          motion.matches ||
          element.contains(document.activeElement)
        )
          continue;
        try {
          const animation = element.animate(
            [
              { opacity: 0.3, transform: "translateY(28px)" },
              { opacity: 1, transform: "translateY(0)" },
            ],
            {
              duration: 620,
              delay: Math.min(stagger++, 3) * 60,
              easing: "cubic-bezier(.2,.65,.3,1)",
              fill: "none",
            },
          );
          animations.set(element, animation);
          animation.onfinish = () => cancel(element);
        } catch {
          // Unsupported animation implementations keep the visible static surface.
        }
      }
    },
    { threshold: 0.08 },
  );

  const inspect = (scope: Element) => {
    const candidates = [
      ...(scope.matches("[data-reveal]") ? [scope] : []),
      ...scope.querySelectorAll<HTMLElement>("[data-reveal]"),
    ];
    for (const candidate of candidates) {
      if (!(candidate instanceof HTMLElement) || observed.has(candidate))
        continue;
      const key = candidate.dataset.reveal;
      if (!key || seen.has(key)) continue;
      const bounds = candidate.getBoundingClientRect();
      // Visible initial and asynchronously loaded results reveal too. Never hide
      // static HTML; skip already-scrolled content and focused controls.
      if (bounds.bottom <= 0 || candidate.contains(document.activeElement)) {
        seen.add(key);
        continue;
      }
      observed.add(candidate);
      observer.observe(candidate);
    }
  };
  const mutations = new MutationObserver((records) => {
    if (stopped) return;
    for (const record of records) {
      for (const node of record.addedNodes)
        if (node instanceof Element) inspect(node);
    }
    for (const element of observed) {
      if (!root.contains(element)) {
        observer.unobserve(element);
        observed.delete(element);
      }
    }
    for (const element of animations.keys())
      if (!root.contains(element)) cancel(element);
  });
  const onFocus = (event: FocusEvent) => {
    if (!(event.target instanceof Node)) return;
    for (const element of observed) {
      if (element.contains(event.target)) {
        const key = element.dataset.reveal;
        if (key) seen.add(key);
        observer.unobserve(element);
        observed.delete(element);
      }
    }
    for (const element of animations.keys())
      if (element.contains(event.target)) cancel(element);
  };
  const cleanup = () => {
    stopped = true;
    observer.disconnect();
    mutations.disconnect();
    for (const element of animations.keys()) cancel(element);
    observed.clear();
    root.removeEventListener("focusin", onFocus);
    motion.removeEventListener("change", onMotion);
  };
  const onMotion = () => {
    if (motion.matches) cleanup();
  };
  root.addEventListener("focusin", onFocus);
  motion.addEventListener("change", onMotion);
  mutations.observe(root, { childList: true, subtree: true });
  inspect(root);
  return cleanup;
}
