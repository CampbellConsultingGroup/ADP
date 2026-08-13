import { defineConfig, devices } from "@playwright/test";

const API_URL = process.env.ADP_API_URL ?? "http://127.0.0.1:8001";
const WEB_URL = process.env.ADP_WEB_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: "list",
  timeout: 15_000,

  projects: [
    {
      name: "api",
      testMatch: "**/api.spec.ts",
      use: {
        baseURL: API_URL,
        // No browser needed for API tests
      },
    },
    {
      // Real-stack flows: browser + real API + real DB, no mocking.
      // Requires ADP_AUTH_ENABLED=false (backend) and VITE_AUTH_ENABLED=false (frontend).
      // Set ADP_WEB_URL=http://localhost:5173 before running.
      name: "fullstack",
      testMatch: "**/flows.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: WEB_URL,
      },
    },
    {
      // ADP-914.14: C4 Design View (canvas-v2) real-stack coverage, split into its
      // own project (same real-backend requirements as "fullstack") so it can be
      // run standalone via --project=canvas-v2.
      name: "canvas-v2",
      testMatch: "**/canvas-v2.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: WEB_URL,
      },
    },
  ],
});
