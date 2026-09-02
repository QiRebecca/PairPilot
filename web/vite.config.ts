import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    // These route-level tests render the full application shell. Running
    // several jsdom shells in parallel makes timers and async queries flaky on
    // constrained CI runners, so execute test files deterministically.
    fileParallelism: false,
    // React 19 + jsdom startup can exceed Vitest's 5 second default when the
    // suite starts on a cold CI worker. Keep the bound tight, but leave enough
    // room for the route-level interaction assertions.
    testTimeout: 10_000,
  },
});
