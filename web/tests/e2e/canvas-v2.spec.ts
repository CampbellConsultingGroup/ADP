/**
 * C4 Design View (canvas-v2) — Real-Stack Browser Tests (ADP-914.14)
 *
 * Real backend + real database, no route mocking — mirrors flows.spec.ts's
 * "fullstack" pattern rather than the deleted workspace.spec.ts's mocked-API
 * one: the app has no client-side router (App.tsx is a single useState<AppView>
 * state machine, confirmed via package.json having no react-router dependency),
 * so the old test's `page.goto("${WEB_URL}/designs/E2E-D001")` direct-URL
 * navigation never actually worked against real app behavior. Every screen is
 * reached by clicking through the nav, same as every other real-stack spec.
 *
 * Covers the three scenarios ADP-914.14 asks for: level toggle, add-element,
 * select-and-inspect — the same ground the deleted workspace.spec.ts covered
 * for the legacy C4Canvas, now for its replacement (ADP-SPEC-054).
 *
 * Requirements:
 *   - Backend: ADP_DATABASE_URL set, ADP_AUTH_ENABLED=false, uvicorn on :8001
 *   - Frontend: VITE_AUTH_ENABLED=false, Vite dev server on :5173
 *   - ADP_WEB_URL=http://localhost:5173 env var set before running
 *
 * Run:
 *   ADP_WEB_URL=http://localhost:5173 npx playwright test --project=canvas-v2
 */

import { test, expect, request as playwrightRequest, type Page } from "@playwright/test";

const WEB_URL = process.env.ADP_WEB_URL ?? "";
const API_URL = process.env.ADP_API_URL ?? "http://127.0.0.1:8001";

const RUN_ID = Date.now().toString(36).toUpperCase();

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

// Seeds a design with one element of each ElementKind, so level-toggle
// assertions have real cross-level data to check (mirrors c4-filter.ts's
// C4_LEVEL_KINDS table: context=person+system, container=system+container,
// component=container+component).
async function seedDesign(title: string): Promise<string> {
  const created = await apiPost("/api/v1/designs", { title });
  if (!created.ok) throw new Error(`Setup: failed to create design "${title}"`);
  const designId = (created.json as { id: string }).id;

  for (const kind of ["person", "system", "container", "component"] as const) {
    const el = await apiPost(`/api/v1/designs/${designId}/elements`, {
      kind,
      name: `E2E ${kind}`,
    });
    if (!el.ok) throw new Error(`Setup: failed to create ${kind} element`);
  }
  return designId;
}

async function openDesign(page: Page, designTitle: string): Promise<void> {
  // App.tsx's default landing view is Overview, not Designs (no client router,
  // no persisted view state) -- navigate there explicitly rather than assuming
  // page.goto lands on the Designs list.
  await page.goto(WEB_URL);
  await page.getByRole("button", { name: "Designs", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Designs" })).toBeVisible({ timeout: 10_000 });
  await page.getByText(designTitle, { exact: true })
    .locator("../../..")
    .getByRole("button", { name: "Open" })
    .click();
  await expect(page.getByRole("button", { name: "C4 Design" })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "C4 Design" }).click();
  await expect(page.getByRole("heading", { name: designTitle })).toBeVisible({ timeout: 10_000 });
}

test.describe("C4 Design View — level toggle (FR-006)", () => {
  const designTitle = `E2E-CanvasV2-Levels-${RUN_ID}`;

  test.beforeAll(async () => {
    if (!WEB_URL) return;
    await seedDesign(designTitle);
  });

  test.beforeEach(({}, testInfo) => {
    if (!WEB_URL) testInfo.skip(true, "ADP_WEB_URL not set — skipping browser tests");
  });

  test("Context level shows only person + system nodes", async ({ page }) => {
    await openDesign(page, designTitle);
    // Context is the default level on open.
    await expect(page.getByTestId(`node-ELM-001`)).toBeVisible({ timeout: 10_000 }); // person
    await expect(page.getByTestId(`node-ELM-002`)).toBeVisible(); // system
    await expect(page.getByTestId(`node-ELM-003`)).not.toBeVisible(); // container
    await expect(page.getByTestId(`node-ELM-004`)).not.toBeVisible(); // component
  });

  test("Container level shows only system + container nodes", async ({ page }) => {
    await openDesign(page, designTitle);
    await page.getByRole("button", { name: "Container", exact: true }).click();
    await expect(page.getByTestId(`node-ELM-002`)).toBeVisible({ timeout: 10_000 }); // system
    await expect(page.getByTestId(`node-ELM-003`)).toBeVisible(); // container
    await expect(page.getByTestId(`node-ELM-001`)).not.toBeVisible(); // person
  });

  test("Component level shows only container + component nodes", async ({ page }) => {
    await openDesign(page, designTitle);
    await page.getByRole("button", { name: "Component", exact: true }).click();
    await expect(page.getByTestId(`node-ELM-003`)).toBeVisible({ timeout: 10_000 }); // container
    await expect(page.getByTestId(`node-ELM-004`)).toBeVisible(); // component
    await expect(page.getByTestId(`node-ELM-002`)).not.toBeVisible(); // system
  });
});

test.describe("C4 Design View — add element (FR-002, SC-001)", () => {
  let designId: string;
  const designTitle = `E2E-CanvasV2-Add-${RUN_ID}`;

  test.beforeAll(async () => {
    if (!WEB_URL) return;
    designId = await seedDesign(designTitle);
  });

  test.beforeEach(({}, testInfo) => {
    if (!WEB_URL) testInfo.skip(true, "ADP_WEB_URL not set — skipping browser tests");
  });

  test("clicking Add Rectangle creates a real, persisted element", async ({ page }) => {
    await openDesign(page, designTitle);
    await page.getByTestId("add-shape-rectangle").click();

    // Reconcile.ts fires the real POST .../elements call and swaps the
    // client-side temp id for the server-assigned ELM-NNN id -- the Elements
    // picker (.ui-list) is the simplest place to observe that round trip
    // completed, scoped there since "New Node" also appears in the canvas SVG
    // label and the DSL panel's serialized text.
    const picker = page.locator(".ui-list");
    await expect(picker.getByText("New Node")).toBeVisible({ timeout: 10_000 });

    // Confirm it's really persisted server-side (not just optimistic client
    // state) via a direct API read -- App.tsx has no client router / persisted
    // view state, so a page.reload() can't be used to re-verify this in place,
    // it just resets straight back to the Overview landing view.
    const ctx = await playwrightRequest.newContext({ baseURL: API_URL });
    try {
      const resp = await ctx.get(`/api/v1/designs/${designId}`);
      const design = (await resp.json()) as { elements: { name: string }[] };
      expect(design.elements.some((e) => e.name === "New Node")).toBe(true);
    } finally {
      await ctx.dispose();
    }
  });
});

test.describe("C4 Design View — select and inspect (FR-008, ADP-SPEC-029)", () => {
  const designTitle = `E2E-CanvasV2-Inspect-${RUN_ID}`;

  test.beforeAll(async () => {
    if (!WEB_URL) return;
    await seedDesign(designTitle);
  });

  test.beforeEach(({}, testInfo) => {
    if (!WEB_URL) testInfo.skip(true, "ADP_WEB_URL not set — skipping browser tests");
  });

  test("selecting an element in the picker opens InspectionPanel with a Technology section", async ({ page }) => {
    await openDesign(page, designTitle);
    await page.getByTestId("element-row-ELM-002").click(); // the seeded "system" element

    await expect(page.getByText("[system]")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "Technology" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add", exact: true })).toBeVisible();
  });
});
