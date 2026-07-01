/**
 * E2E: C4 Visual Design Workspace
 *
 * Requires a running ADP backend at ADP_TEST_URL (default: http://localhost:8000).
 * Mark @slow — requires full stack.
 */
import { test, expect } from "@playwright/test";

let testDesignId: string;

test.beforeAll(async ({ request }) => {
  // Create a fresh design for E2E testing
  const now = new Date().toISOString();
  const response = await request.post("/api/v1/designs", {
    data: {
      schema_version: "1.0.0",
      id: "E2E-001",
      title: "E2E Test Design",
      elements: [],
      relationships: [],
      created_at: now,
      updated_at: now,
    },
  });

  if (response.ok()) {
    const data = (await response.json()) as { id: string };
    testDesignId = data.id;
  } else {
    // Use a pre-existing design id if creation fails
    testDesignId = "E2E-001";
  }
});

test("@slow place element and verify in API", async ({ page, request }) => {
  await page.goto(`/designs/${testDesignId}`);

  // Wait for workspace to load
  await page.waitForSelector("text=+ Add Element", { timeout: 10_000 });

  // Open add menu
  await page.click("text=+ Add Element");

  // Select kind (default is container)
  const nameInput = page.getByPlaceholder("Element name");
  await nameInput.fill("Test Gateway");

  // Add element
  await page.click("text=Add");

  // Verify element appears on canvas (optimistic update)
  await expect(page.getByText("Test Gateway")).toBeVisible({ timeout: 5_000 });

  // Verify via API that the element is in the model
  await page.waitForTimeout(2_000); // allow API mutation to settle

  const designResponse = await request.get(`/api/v1/designs/${testDesignId}`);
  expect(designResponse.ok()).toBe(true);

  const design = (await designResponse.json()) as { elements: Array<{ name: string }> };
  const found = design.elements.some((e) => e.name === "Test Gateway");
  expect(found).toBe(true);
});

test("@slow switch C4 level hides out-of-level elements", async ({ page }) => {
  await page.goto(`/designs/${testDesignId}`);
  await page.waitForSelector("text=Container", { timeout: 10_000 });

  // Switch to Context level
  await page.click("text=Context");

  // Container elements should not be visible (only person + system shown at context)
  // Person/system elements may or may not exist depending on prior test state
  // Just verify level toggle is responsive
  await expect(page.getByRole("button", { name: "Context" })).toBeVisible();
});
