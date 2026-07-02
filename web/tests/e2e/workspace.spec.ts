/**
 * ADP C4 Workspace Browser Tests (ADP-SPEC-013 US4)
 *
 * Uses Playwright's `page` fixture with Chromium.
 * Uses `page.route()` to mock API responses so the tests don't need a real database.
 *
 * REQUIRES: ADP_WEB_URL env var pointing to a running Vite dev server.
 * If ADP_WEB_URL is not set, all tests are skipped (not a CI failure).
 *
 * Setup:
 *   cd web && npm run dev          # Start Vite on http://localhost:5173
 *   ADP_WEB_URL=http://localhost:5173 npx playwright test --project=browser
 */

import { test, expect, type Page } from "@playwright/test";

const WEB_URL = process.env.ADP_WEB_URL;

const MOCK_DESIGN = {
  id: "E2E-D001",
  schema_version: "1.0.0",
  title: "E2E Test Design",
  elements: [
    { id: "ELM-001", name: "API Gateway", kind: "container", satisfies: [], provenance: null },
    { id: "ELM-002", name: "User", kind: "person", satisfies: [], provenance: null },
  ],
  relationships: [],
  requirements: [],
  options: [],
  findings: [],
  verdicts: [],
  audit_log: [],
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
};

const MOCK_LAYOUT = {
  design_id: "E2E-D001",
  level: "container",
  positions: {
    "ELM-001": { x: 100, y: 100 },
    "ELM-002": { x: 300, y: 100 },
  },
};

const MOCK_THEME = {
  version: "1.0.1",
  locked: true,
  styles: {
    person:    { fill: "#08427B", stroke: "#073B6F", color: "#ffffff", shape: "actor", font_size: 14, font_weight: "normal" },
    system:    { fill: "#1168BD", stroke: "#0E5FA3", color: "#ffffff", shape: "box", font_size: 14, font_weight: "bold" },
    container: { fill: "#2874A6", stroke: "#236898", color: "#ffffff", shape: "box", font_size: 13, font_weight: "normal" },
    component: { fill: "#85BBE0", stroke: "#78A8CC", color: "#000000", shape: "box", font_size: 12, font_weight: "normal" },
  },
  relationship_style: { stroke: "#707070", stroke_width: 1.5, arrow_end: "open" },
};

async function mockApis(page: Page): Promise<void> {
  // IMPORTANT: Use a regex matching /api/v1/ to avoid intercepting Vite source
  // files like /src/api/designs.ts — those must be served as TypeScript modules.
  // Glob patterns like **/api/** would incorrectly match /src/api/* source paths.
  await page.route(/\/api\/v1\//, (route) => {
    const url = route.request().url();

    if (url.includes("/designs/E2E-D001/layout/")) {
      const level = url.split("/").pop() ?? "container";
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...MOCK_LAYOUT, level }) });
    } else if (url.includes("/theme/c4")) {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_THEME) });
    } else if (url.includes("/designs/E2E-D001")) {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_DESIGN) });
    } else {
      // All other /api/v1/ calls — return empty 200 to prevent loading errors
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    }
  });
}

test.describe("C4 Workspace — Browser Tests", () => {
  test.beforeEach(({ page: _page }, testInfo) => {
    if (!WEB_URL) {
      testInfo.skip(true, "ADP_WEB_URL not set — skipping browser tests");
    }
  });

  test("workspace page loads with mocked design and canvas is visible", async ({ page }) => {
    await mockApis(page);
    await page.goto(`${WEB_URL}/designs/E2E-D001`);
    await expect(page).toHaveTitle(/ADP/);
    // The canvas Add Element button must appear once the design loads
    await expect(page.getByText("+ Add Element")).toBeVisible({ timeout: 10_000 });
  });

  test("level toggle shows all three C4 levels", async ({ page }) => {
    await mockApis(page);
    await page.goto(`${WEB_URL}/designs/E2E-D001`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("button", { name: "Context" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Container" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Component" })).toBeVisible();
  });

  test("clicking Add Element shows element kind and name inputs", async ({ page }) => {
    await mockApis(page);
    await page.goto(`${WEB_URL}/designs/E2E-D001`);
    await page.getByText("+ Add Element").click();
    await expect(page.getByPlaceholder("Element name")).toBeVisible({ timeout: 2_000 });
    await expect(page.locator("select")).toBeVisible();
  });

  test("level toggle switches the active level highlighting", async ({ page }) => {
    await mockApis(page);
    await page.goto(`${WEB_URL}/designs/E2E-D001`);
    await expect(page.getByRole("button", { name: "Context" })).toBeVisible({ timeout: 10_000 });

    // Click Context — should become active (different background)
    await page.getByRole("button", { name: "Context" }).click();
    const contextBtn = page.getByRole("button", { name: "Context" });
    const bg = await contextBtn.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    // Active button has non-white background (the ADP design uses blue #1168BD for active)
    expect(bg).not.toBe("rgb(255, 255, 255)");
  });
});
