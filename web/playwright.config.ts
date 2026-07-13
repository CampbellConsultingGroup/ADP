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
      name: "browser",
      testMatch: "**/workspace.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: WEB_URL,
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
  ],
});
