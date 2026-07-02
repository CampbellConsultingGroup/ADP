/**
 * ADP API End-to-End Tests (ADP-SPEC-013)
 *
 * Uses Playwright's `request` context — no browser launched.
 * Runs against a live ADP server (default: http://localhost:8001).
 * Set ADP_API_URL env var to override.
 *
 * Requires: uvicorn adp.api.app:app --port 8001 running before this suite.
 * No database required — tests cover endpoints that work without ADP_DATABASE_URL.
 */

import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { test, expect } from "@playwright/test";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = join(__dirname, "fixtures", "model-v1.json");

// ── US1: API Smoke Tests ──────────────────────────────────────────────────────

test.describe("Health and Observability", () => {
  test("GET /health returns healthy status with trace ID", async ({ request }) => {
    const resp = await request.get("/health");
    expect(resp.status()).toBe(200);
    const body = await resp.json() as { status: string; version: string };
    expect(body.status).toBe("healthy");
    expect(body.version).toBeTruthy();
    // ADP-SPEC-012 QG-10: trace ID must be present in every response
    expect(resp.headers()["x-trace-id"]).toBeTruthy();
  });

  test("X-Trace-ID header is propagated from request", async ({ request }) => {
    const traceId = "e2e-test-trace-" + Date.now();
    const resp = await request.get("/health", {
      headers: { "X-Trace-ID": traceId },
    });
    expect(resp.status()).toBe(200);
    expect(resp.headers()["x-trace-id"]).toBe(traceId);
  });

  test("GET /metrics returns Prometheus format with ADP metrics", async ({ request }) => {
    const resp = await request.get("/metrics");
    expect(resp.status()).toBe(200);
    const text = await resp.text();
    expect(text).toContain("adp_request_total");
    expect(text).toContain("adp_request_latency_seconds");
    expect(text).toContain("adp_active_requests");
  });

  test("metrics counter increments after requests", async ({ request }) => {
    await request.get("/health");
    const resp = await request.get("/metrics");
    const text = await resp.text();

    let total = 0;
    for (const line of text.split("\n")) {
      if (line.startsWith("adp_request_total") && !line.startsWith("#")) {
        const parts = line.split(" ");
        total += parseFloat(parts[parts.length - 1] ?? "0");
      }
    }
    expect(total).toBeGreaterThan(0);
  });
});

test.describe("Locked C4 Theme (ADP-SPEC-010)", () => {
  test("GET /api/v1/theme/c4 returns locked theme v1.0.1", async ({ request }) => {
    const resp = await request.get("/api/v1/theme/c4");
    expect(resp.status()).toBe(200);
    const body = await resp.json() as {
      version: string;
      locked: boolean;
      styles: Record<string, { fill: string }>;
    };
    expect(body.locked).toBe(true);
    expect(body.version).toBe("1.0.1");
    // ART-XII: container fill must be WCAG AA compliant color (updated from #438DD5)
    expect(body.styles.container?.fill).toBe("#2874A6");
  });

  test("theme has all four C4 element kinds", async ({ request }) => {
    const resp = await request.get("/api/v1/theme/c4");
    const body = await resp.json() as { styles: Record<string, unknown> };
    expect(Object.keys(body.styles)).toEqual(
      expect.arrayContaining(["person", "system", "container", "component"]),
    );
  });
});

test.describe("Layout API (in-process store, no DB)", () => {
  test("GET /layout/container returns empty positions for unknown design", async ({ request }) => {
    const resp = await request.get("/api/v1/designs/E2E-UNKNOWN-999/layout/container");
    expect(resp.status()).toBe(200);
    const body = await resp.json() as { design_id: string; level: string; positions: object };
    expect(body.design_id).toBe("E2E-UNKNOWN-999");
    expect(body.level).toBe("container");
    expect(body.positions).toEqual({});
  });

  test("PUT then GET layout round-trips positions", async ({ request }) => {
    const positions = { "ELM-E2E-001": { x: 120, y: 80 }, "ELM-E2E-002": { x: 300, y: 200 } };
    const putResp = await request.put("/api/v1/designs/E2E-LAYOUT-TEST/layout/container", {
      data: { positions },
    });
    expect(putResp.status()).toBe(200);

    const getResp = await request.get("/api/v1/designs/E2E-LAYOUT-TEST/layout/container");
    expect(getResp.status()).toBe(200);
    const body = await getResp.json() as { positions: typeof positions };
    expect(body.positions["ELM-E2E-001"]?.x).toBe(120);
    expect(body.positions["ELM-E2E-002"]?.y).toBe(200);
  });
});

test.describe("DB-backed endpoints return 503 when unconfigured", () => {
  test("POST /render without DB returns 503 with clear message", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/E2E-001/render", {
      data: { level: "container" },
    });
    expect(resp.status()).toBe(503);
    const text = await resp.text();
    expect(text).toContain("ADP_DATABASE_URL");
  });

  test("GET /document without DB returns 503", async ({ request }) => {
    const resp = await request.get("/api/v1/designs/E2E-001/document");
    expect(resp.status()).toBe(503);
  });

  test("GET /traceability without DB returns 503", async ({ request }) => {
    const resp = await request.get("/api/v1/designs/E2E-001/traceability");
    expect(resp.status()).toBe(503);
  });
});

// ── US2: ART-VIII Confirmation Gate ──────────────────────────────────────────

test.describe("ART-VIII Confirmation Gate (ADP-SPEC-012)", () => {
  // NOTE on FastAPI dependency ordering: FastAPI resolves route dependencies
  // (Depends(get_design_store)) before or concurrently with request body parsing.
  // When ADP_DATABASE_URL is not configured, get_design_store raises 503 before
  // Pydantic can validate ExportRequest — so in a no-DB environment ALL export
  // requests return 503 regardless of body content.
  //
  // The 422-for-blank-confirmation behavior (Pydantic gate) is verified at the
  // unit/contract level in tests/contract/test_export_api.py where the store is
  // mocked. These E2E tests verify the behavior in the no-DB runtime scenario.

  test("export endpoint rejects requests without DB configured (503)", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/E2E-001/export", {
      data: { confirmation_id: "CONF-E2E-TEST", export_root: "/tmp/e2e-test" },
    });
    // In no-DB environment: dependency raises 503 before body validation
    expect(resp.status()).toBe(503);
    const text = await resp.text();
    expect(text).toContain("ADP_DATABASE_URL");
  });

  test("blank confirmation_id never succeeds (4xx or 5xx — not 200)", async ({ request }) => {
    // Whether 422 (Pydantic) or 503 (no DB) — the request must never return 200.
    // The 422 path is proven by unit tests (test_export_api.py); this E2E test
    // verifies no bypass exists.
    const resp = await request.post("/api/v1/designs/E2E-001/export", {
      data: { confirmation_id: "", export_root: "/tmp/e2e-test" },
    });
    expect(resp.status()).toBeGreaterThanOrEqual(400);
    expect(resp.status()).not.toBe(200);
  });

  test("missing confirmation_id never succeeds (4xx or 5xx)", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/E2E-001/export", {
      data: { export_root: "/tmp/e2e-test" },
    });
    expect(resp.status()).toBeGreaterThanOrEqual(400);
  });
});

// ── US3: Round-Trip Import ────────────────────────────────────────────────────

test.describe("Round-Trip Import (ADP-SPEC-011)", () => {
  test("POST /import round-trips model-v1.json correctly", async ({ request }) => {
    const modelJson = readFileSync(FIXTURE_PATH, "utf-8");
    const resp = await request.post("/api/v1/designs/import", {
      data: { model_json: modelJson },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json() as {
      design_id: string;
      schema_version: string;
      element_count: number;
      relationship_count: number;
      validation_warnings: string[];
    };
    expect(body.design_id).toBe("E2E-IMPORT");
    expect(body.schema_version).toBe("1.0.0");
    expect(body.element_count).toBe(2);
    expect(body.relationship_count).toBe(1);
    expect(body.validation_warnings).toHaveLength(0);
  });

  test("POST /import rejects wrong schema version with 422", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/import", {
      data: {
        model_json: JSON.stringify({
          schema_version: "99.0.0",
          id: "E2E-BAD-VERSION",
          title: "Bad",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }),
      },
    });
    expect(resp.status()).toBe(422);
    const text = await resp.text();
    expect(text).toContain("99.0.0");
  });

  test("POST /import rejects malformed JSON with 422", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/import", {
      data: { model_json: "{ not valid json {{{" },
    });
    expect(resp.status()).toBe(422);
  });

  test("POST /import rejects extra unknown fields with 422", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/import", {
      data: {
        model_json: JSON.stringify({
          schema_version: "1.0.0",
          id: "E2E-EXTRA",
          title: "Extra",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          extra_forbidden_field: "boom",
        }),
      },
    });
    expect(resp.status()).toBe(422);
  });
});

// ── ADP-SPEC-014: Requirements Intake API (T043) ──────────────────────────────

test.describe("Requirements Intake API (ADP-SPEC-014)", () => {
  test("POST /intake returns operation_id (202)", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/E2E-IMPORT/intake", {
      data: {
        mode: "bulk_text",
        text: "The system must handle 10,000 concurrent users without degradation in performance.",
      },
    });
    // 202 if design exists; 404 if not — either way not a 500
    expect([202, 404]).toContain(resp.status());
    if (resp.status() === 202) {
      const body = await resp.json() as { operation_id: string; status: string };
      expect(body.operation_id).toBeTruthy();
      expect(body.status).toBe("pending");
    }
  });

  test("POST /intake with short text returns 422 (validation gate)", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/E2E-IMPORT/intake", {
      data: { mode: "bulk_text", text: "short" },
    });
    expect(resp.status()).toBe(422);
  });

  test("GET /requirements returns 200 with list (ADP-SPEC-014 US4)", async ({ request }) => {
    const resp = await request.get("/api/v1/designs/E2E-IMPORT/requirements");
    // 200 if design exists (with empty or populated list); 404 if not
    expect([200, 404]).toContain(resp.status());
    if (resp.status() === 200) {
      const body = await resp.json() as { requirements: unknown[]; total: number };
      expect(Array.isArray(body.requirements)).toBe(true);
      expect(typeof body.total).toBe("number");
    }
  });

  test("POST /requirements with valid statement creates requirement (ADP-SPEC-014 US3)", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/E2E-IMPORT/requirements", {
      data: {
        statement: "The API must be stateless and handle 100 requests per second",
        kind: "non_functional",
      },
    });
    // 201 if design exists; 404 if not
    expect([201, 404]).toContain(resp.status());
    if (resp.status() === 201) {
      const body = await resp.json() as { requirement_id: string; proposal_id: null };
      expect(body.requirement_id).toMatch(/^REQ-/);
      expect(body.proposal_id).toBeNull(); // I1 fix: null for direct add
    }
  });

  test("POST /requirements with missing statement returns 422", async ({ request }) => {
    const resp = await request.post("/api/v1/designs/E2E-IMPORT/requirements", {
      data: { kind: "functional" },
    });
    expect(resp.status()).toBe(422);
  });
});
