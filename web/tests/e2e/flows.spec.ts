/**
 * ADP Real-Stack E2E Flow Tests
 *
 * Tests complete user flows against the running backend and real database.
 * No API mocking — every interaction hits the live system.
 *
 * Requirements:
 *   - Backend: ADP_DATABASE_URL set, ADP_AUTH_ENABLED=false, uvicorn on :8001
 *   - Frontend: VITE_AUTH_ENABLED=false, Vite dev server on :5173
 *   - ADP_WEB_URL=http://localhost:5173 env var set before running
 *
 * Run:
 *   ADP_WEB_URL=http://localhost:5173 npx playwright test --project=fullstack
 */

import { test, expect, request as playwrightRequest } from "@playwright/test";

const WEB_URL = process.env.ADP_WEB_URL ?? "";
const API_URL = process.env.ADP_API_URL ?? "http://127.0.0.1:8001";

// Unique suffix per run to avoid collisions with existing data
const RUN_ID = Date.now().toString(36).toUpperCase();

// ── Shared helpers ────────────────────────────────────────────────────────────

async function apiPost(path: string, body: unknown): Promise<{ ok: boolean; json: unknown }> {
  const ctx = await playwrightRequest.newContext({ baseURL: API_URL });
  try {
    const resp = await ctx.post(path, { data: body });
    const json = await resp.json().catch(() => null);
    return { ok: resp.ok(), json };
  } finally {
    await ctx.dispose();
  }
}

// ── Flow 1: Design creation via UI ────────────────────────────────────────────

test.describe("Design creation via UI", () => {
  test.beforeEach(() => {
    if (!WEB_URL) test.skip();
  });

  test("creates a design through the new-design form and lands on intake", async ({ page }) => {
    const title = `E2E-Create-${RUN_ID}`;

    // App.tsx's default landing view is Overview, not Designs (no client router,
    // no persisted view state) -- navigate there explicitly. Pre-existing bug
    // found while validating ADP-914.14's new canvas-v2.spec.ts against this
    // file's own pattern: page.goto alone never actually landed on Designs.
    await page.goto(WEB_URL);
    await page.getByRole("button", { name: "Designs", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Designs" })).toBeVisible({ timeout: 10_000 });

    // Open the create form (stale as "+ New Design" -- the Button component's
    // icon="plus" prop now renders the plus as a real icon, not a text prefix)
    await page.getByRole("button", { name: "New Design" }).click();
    await expect(page.getByPlaceholder(/Design title/i)).toBeVisible();

    // Fill title and submit
    await page.getByPlaceholder(/Design title/i).fill(title);
    await page.getByRole("button", { name: "Create Design" }).click();

    // After creation onSelectDesign fires → design tabs appear in NavBar
    await expect(page.getByRole("button", { name: "Knowledge" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "C4 Design" })).toBeVisible();
  });
});

// ── Flow 2: Knowledge item create → verify → delete ───────────────────────────
//
// Tests the full lifecycle that exposed the auth-header bug:
//   1. Create a knowledge item through the UI form
//   2. Verify it appears in the list
//   3. Delete it through the UI
//   4. Verify it is GONE (no stale cache, no silent 401)

test.describe("Knowledge item create → delete lifecycle", () => {
  test.describe.configure({ mode: "serial" });

  let designTitle: string;
  const itemId = `E2E-${RUN_ID}`;
  const itemTitle = `E2E Knowledge Item ${RUN_ID}`;

  test.beforeEach(() => {
    if (!WEB_URL) test.skip();
  });

  test.beforeAll(async () => {
    if (!WEB_URL) return;
    designTitle = `E2E-KB-${RUN_ID}`;
    const { ok } = await apiPost("/api/v1/designs", { title: designTitle });
    if (!ok) throw new Error(`Setup: failed to create design "${designTitle}"`);
  });

  test("creates a knowledge item via the Add Item form", async ({ page }) => {
    // App.tsx's default landing view is Overview, not Designs (no client router,
    // no persisted view state) -- navigate there explicitly. Pre-existing bug
    // found while validating ADP-914.14's new canvas-v2.spec.ts against this
    // file's own pattern: page.goto alone never actually landed on Designs.
    await page.goto(WEB_URL);
    await page.getByRole("button", { name: "Designs", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Designs" })).toBeVisible({ timeout: 10_000 });

    // Open the test design
    // DOM: span(title) → div(title+badge row) → div(flex-1) → div(design row) → button(Open)
    await page.getByText(designTitle, { exact: true }).locator("../../..").getByRole("button", { name: "Open" }).click();
    await expect(page.getByRole("button", { name: "Knowledge" })).toBeVisible({ timeout: 10_000 });

    // Navigate to Knowledge tab
    await page.getByRole("button", { name: "Knowledge" }).click();
    await expect(page.getByRole("heading", { name: "Knowledge Base" })).toBeVisible({ timeout: 10_000 });

    // Open the create form (stale as "+ Add Item", same icon-prop rename as
    // DesignsPage's "New Design" button above -- safe as a bare match since
    // KnowledgePage's own toolbar button unmounts once the form replaces it,
    // so it never coexists with the form's own "Add Item" submit button)
    await page.getByRole("button", { name: "Add Item" }).click();
    await expect(page.getByRole("heading", { name: "Add Knowledge Item" })).toBeVisible();

    // Fill in all required fields
    await page.getByPlaceholder(/PRIN-007 or PAT-012/i).fill(itemId);
    await page.getByPlaceholder(/Concise name/i).fill(itemTitle);
    await page.getByPlaceholder(/Full knowledge content/i).fill(
      "E2E automated test item — verifies create/delete lifecycle with auth headers."
    );
    await page.getByPlaceholder(/https:\/\/example.com\/source/i).fill("https://e2e.example.com");

    // Submit the form
    await page.getByRole("button", { name: "Add Item" }).click();

    // Item must appear in the list — proves the query was invalidated and re-fetched
    await expect(page.getByText(itemTitle)).toBeVisible({ timeout: 10_000 });
  });

  test("deletes the knowledge item and confirms it is removed from the list", async ({ page }) => {
    // App.tsx's default landing view is Overview, not Designs (no client router,
    // no persisted view state) -- navigate there explicitly. Pre-existing bug
    // found while validating ADP-914.14's new canvas-v2.spec.ts against this
    // file's own pattern: page.goto alone never actually landed on Designs.
    await page.goto(WEB_URL);
    await page.getByRole("button", { name: "Designs", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Designs" })).toBeVisible({ timeout: 10_000 });

    await page.getByText(designTitle, { exact: true }).locator("../../..").getByRole("button", { name: "Open" }).click();
    await page.getByRole("button", { name: "Knowledge" }).click();
    await expect(page.getByRole("heading", { name: "Knowledge Base" })).toBeVisible({ timeout: 10_000 });

    // Confirm the item is present before deletion
    await expect(page.getByText(itemTitle)).toBeVisible({ timeout: 10_000 });

    // The item title is in a <div> (title-div → flex-1-div → row-div → Delete button).
    await page.getByText(itemTitle, { exact: true }).locator("../..").getByRole("button", { name: "Delete" }).click();

    // Confirm dialog appears
    await expect(page.getByRole("heading", { name: "Delete Knowledge Item" })).toBeVisible();
    await expect(page.getByText("Are you sure you want to delete")).toBeVisible();

    // Navigate from the dialog heading up to its containing box div, then click Delete.
    // This avoids the strict-mode violation caused by ancestor divs also matching.
    await page.getByRole("heading", { name: "Delete Knowledge Item" }).locator("..").getByRole("button", { name: "Delete" }).click();

    // Dialog closes and item disappears — verifies the fix:
    // useDeleteKnowledgeItem now sends the Authorization header via apiMutation
    await expect(page.getByRole("heading", { name: "Delete Knowledge Item" })).not.toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(itemTitle)).not.toBeVisible({ timeout: 10_000 });
  });
});

// ── Flow 3: Portfolio and Governance navigation ───────────────────────────────

test.describe("Portfolio and Governance navigation", () => {
  test.beforeEach(() => {
    if (!WEB_URL) test.skip();
  });

  test("clicking Portfolio in the NavBar shows the Technologies section", async ({ page }) => {
    // App.tsx's default landing view is Overview, not Designs (no client router,
    // no persisted view state) -- navigate there explicitly. Pre-existing bug
    // found while validating ADP-914.14's new canvas-v2.spec.ts against this
    // file's own pattern: page.goto alone never actually landed on Designs.
    await page.goto(WEB_URL);
    await page.getByRole("button", { name: "Designs", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Designs" })).toBeVisible({ timeout: 10_000 });

    // exact: true -- bare "Portfolio" also substring-matches OverviewPage's
    // redesigned dashboard tiles ("Application Portfolio 18 apps", "Portfolio
    // Analysis TIME . 7R"), both visible on the landing view these tests start
    // from without navigating through Designs first.
    await page.getByRole("button", { name: "Portfolio", exact: true }).click();

    // Portfolio page shows "Technologies" heading and "Governance Report" button
    await expect(page.getByRole("heading", { name: "Technologies" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Governance Report" })).toBeVisible();
  });

  test("Governance Report button opens the three-tab governance page", async ({ page }) => {
    await page.goto(WEB_URL);
    // exact: true -- bare "Portfolio" also substring-matches OverviewPage's
    // redesigned dashboard tiles ("Application Portfolio 18 apps", "Portfolio
    // Analysis TIME . 7R"), both visible on the landing view these tests start
    // from without navigating through Designs first.
    await page.getByRole("button", { name: "Portfolio", exact: true }).click();
    await expect(page.getByRole("button", { name: "Governance Report" })).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: "Governance Report" }).click();

    // All three governance tabs must be visible
    await expect(page.getByRole("button", { name: "Design Status" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Compliance" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Activity Feed" })).toBeVisible();
  });

  test("← Portfolio back button returns to portfolio from governance", async ({ page }) => {
    await page.goto(WEB_URL);
    // exact: true -- bare "Portfolio" also substring-matches OverviewPage's
    // redesigned dashboard tiles ("Application Portfolio 18 apps", "Portfolio
    // Analysis TIME . 7R"), both visible on the landing view these tests start
    // from without navigating through Designs first.
    await page.getByRole("button", { name: "Portfolio", exact: true }).click();
    await page.getByRole("button", { name: "Governance Report" }).click();
    await expect(page.getByRole("button", { name: "Design Status" })).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: "← Portfolio" }).click();

    await expect(page.getByRole("heading", { name: "Technologies" })).toBeVisible({ timeout: 10_000 });
  });

  // Renamed from "Portfolio tab in NavBar stays highlighted when on governance
  // page" -- that assumed an older information architecture where Governance
  // was reachable only as a Portfolio sub-view, so the NavBar special-cased
  // Portfolio's active style to also apply on the governance page. Governance
  // is now its own top-level ARCHITECTURE nav item (AppShell.tsx), reachable
  // directly from the rail as well as via Portfolio's "Governance Report"
  // button -- confirmed live that AppShell's NavItem active check is a plain
  // `current === def.view` equality with no such special case anymore, so
  // "Governance" (not "Portfolio") is the item that highlights either way.
  test("Governance tab in NavBar is highlighted when reached via Portfolio's Governance Report button", async ({ page }) => {
    await page.goto(WEB_URL);
    // exact: true -- bare "Portfolio" also substring-matches OverviewPage's
    // redesigned dashboard tiles ("Application Portfolio 18 apps", "Portfolio
    // Analysis TIME . 7R"), both visible on the landing view these tests start
    // from without navigating through Designs first.
    await page.getByRole("button", { name: "Portfolio", exact: true }).click();
    await page.getByRole("button", { name: "Governance Report" }).click();
    await expect(page.getByRole("button", { name: "Design Status" })).toBeVisible({ timeout: 10_000 });

    const governanceBtn = page.getByRole("button", { name: "Governance", exact: true });
    await expect(governanceBtn).toBeVisible();
    // ui.css: .shell-navitem.active { font-weight: 600 } vs the base 500.
    await expect(governanceBtn).toHaveCSS("font-weight", "600");
  });
});

// ── Flow 4: API-layer smoke (no browser, real DB) ─────────────────────────────
//
// Quick sanity checks that the new routers return 200 from a real DB.

test.describe("New-router API smoke (real DB)", () => {
  test("GET /api/v1/portfolio/summary returns 200 with total_designs", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/portfolio/summary`);
    expect(resp.status()).toBe(200);
    const body = await resp.json() as { total_designs: number };
    expect(typeof body.total_designs).toBe("number");
  });

  test("GET /api/v1/portfolio/technologies returns 200 with technologies array", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/portfolio/technologies`);
    expect(resp.status()).toBe(200);
    const body = await resp.json() as { technologies: unknown[] };
    expect(Array.isArray(body.technologies)).toBe(true);
  });

  test("GET /api/v1/governance/status returns 200 with designs array", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/governance/status`);
    expect(resp.status()).toBe(200);
    const body = await resp.json() as { designs: unknown[]; total: number };
    expect(Array.isArray(body.designs)).toBe(true);
    expect(typeof body.total).toBe("number");
  });

  test("GET /api/v1/governance/exceptions returns 200 with exceptions array", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/governance/exceptions`);
    expect(resp.status()).toBe(200);
    const body = await resp.json() as { exceptions: unknown[]; total: number };
    expect(Array.isArray(body.exceptions)).toBe(true);
  });

  test("GET /api/v1/governance/activity without dates returns 422", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/v1/governance/activity`);
    expect(resp.status()).toBe(422);
  });

  test("GET /api/v1/governance/activity with 30-day range returns 200", async ({ request }) => {
    const to = new Date().toISOString().slice(0, 10);
    const from = new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10);
    const resp = await request.get(`${API_URL}/api/v1/governance/activity?from_date=${from}&to_date=${to}`);
    expect(resp.status()).toBe(200);
    const body = await resp.json() as { entries: unknown[]; total: number; from_date: string };
    expect(Array.isArray(body.entries)).toBe(true);
    expect(body.from_date).toBe(from);
  });
});

// ── Flow 6: Business Capabilities Agent Review button (ADP-SPEC-039) ─────────

test.describe("Business Capabilities Agent Review button", () => {
  test.beforeEach(() => {
    if (!WEB_URL) test.skip();
  });

  test("a capability row shows a working Review button that triggers a review", async ({ page }) => {
    // A real LLM call (if configured) can take longer than the config's 15s
    // default test timeout -- give this one enough room for that path too.
    test.setTimeout(45_000);

    const capName = `E2E-AgentReview-${RUN_ID}`;
    const created = await apiPost("/api/v1/business/capabilities", {
      name: capName,
      level: 1,
    });
    expect(created.ok).toBe(true);

    // App.tsx's default landing view is Overview, not Designs (no client router,
    // no persisted view state) -- navigate there explicitly. Pre-existing bug
    // found while validating ADP-914.14's new canvas-v2.spec.ts against this
    // file's own pattern: page.goto alone never actually landed on Designs.
    await page.goto(WEB_URL);
    await page.getByRole("button", { name: "Designs", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Designs" })).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: "Business", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Business Architecture" })).toBeVisible({ timeout: 10_000 });

    const row = page.getByText(capName, { exact: true }).locator("../..");
    await expect(row).toBeVisible({ timeout: 10_000 });

    const reviewButton = row.getByRole("button", { name: /Review/ });
    await expect(reviewButton).toBeVisible();
    await reviewButton.click();

    // Opens the AgentReviewButton panel with its own trigger button.
    const triggerButton = row.getByRole("button", { name: /Ask the business architecture expert/ });
    await expect(triggerButton).toBeVisible({ timeout: 10_000 });
    await triggerButton.click();

    // Whether or not a real LLM key is configured in this environment, the
    // operation must reach a terminal state (empty/with-suggestions/failed) --
    // proves the full trigger/poll round trip works end to end either way.
    await expect(
      row.getByText("No suggestions.")
        .or(row.getByText(/Review failed:/))
        .or(row.getByRole("button", { name: /^Accept$/i }))
    ).toBeVisible({ timeout: 30_000 });
  });
});
