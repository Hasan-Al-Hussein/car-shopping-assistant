import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const canary = process.env.CSA_F03_CANARY === "1";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: canary
      ? ["tests/harness/failure.canary.ts"]
      : [
          "tests/harness/**/*.test.{ts,tsx}",
          "tests/ui/**/*.test.{ts,tsx}",
          "src/**/*.test.{ts,tsx}",
        ],
    maxWorkers: 1,
    fileParallelism: false,
    isolate: true,
    testTimeout: 3000,
    passWithNoTests: false,
  },
});
