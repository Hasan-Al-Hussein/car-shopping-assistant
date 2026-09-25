// Selected only by CSA_F03_CANARY=1; ordinary npm test excludes this file.
import { expect, test } from "vitest";
import { frozenClock } from "./fixtures";

test("intentional assertion failure", () => {
  const clock = frozenClock();
  const before = clock.now().toISOString();
  clock.advance(60);
  expect(clock.now().toISOString(), "F03_INTENTIONAL_ASSERTION_FAILURE").toBe(
    before,
  );
});
