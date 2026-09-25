import { useEffect, useRef, type RefObject } from "react";
import { startScrollReveals } from "./scrollReveal";

export function useScrollReveal(
  root: RefObject<HTMLElement | null>,
  visitKey: string,
  restoring: boolean,
) {
  const visits = useRef(new Map<string, Set<string>>());
  const navigation = useRef({ lastKey: visitKey, hasNavigated: false });
  useEffect(() => {
    if (!root.current) return;
    if (navigation.current.lastKey !== visitKey)
      navigation.current.hasNavigated = true;
    navigation.current.lastKey = visitKey;
    let seen = visits.current.get(visitKey);
    if (!seen) {
      seen = new Set<string>();
      visits.current.set(visitKey, seen);
      if (visits.current.size > 50) {
        const first = visits.current.keys().next().value;
        if (first !== undefined) visits.current.delete(first);
      }
    }
    return startScrollReveals(
      root.current,
      seen,
      restoring && navigation.current.hasNavigated,
    );
  }, [root, visitKey, restoring]);
}
