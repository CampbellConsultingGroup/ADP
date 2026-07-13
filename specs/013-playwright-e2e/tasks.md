# Tasks: Playwright End-to-End Test Suite

**Input**: Design documents from `/specs/013-playwright-e2e/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅

**Tests**: This spec IS the test implementation. All tasks produce test files. The "test" for this spec is that `npx playwright test` passes.

**Note**: TypeScript-only spec. No Python changes. All files are in `web/`. Server must be running on port 8001 before running tests.

---

## Phase 1: Setup

- [ ] T001 Add `"@playwright/test": "^1.47.0"` to `web/package.json` devDependencies; run `npm install` in `web/`; verify `npx playwright --version` shows 1.47+
- [ ] T002 [P] Install Chromium browser: run `cd web && npx playwright install chromium`; verify `~/.cache/ms-playwright/chromium-*/chrome-linux/chrome` exists
- [ ] T003 [P] Create `web/tests/e2e/fixtures/` directory; generate `web/tests/e2e/fixtures/model-v1.json` using Python: `python3 -c "from adp.models import ArchitectureDescription, Element; import json; d=ArchitectureDescription.model_validate({'schema_version':'1.0.0','id':'E2E-IMPORT','title':'E2E Import Test','created_at':'2026-07-02T00:00:00Z','updated_at':'2026-07-02T00:00:00Z','elements':[{'id':'ELM-001','name':'API Gateway','kind':'container','satisfies':[],'provenance':None},{'id':'ELM-002','name':'Auth Service','kind':'container','satisfies':[],'provenance':None}],'requirements':[],'relationships':[{'id':'REL-001','source':'ELM-001','target':'ELM-002','label':'authenticates via'}]}); open('web/tests/e2e/fixtures/model-v1.json','w').write(d.model_dump_json(indent=2))"` from project root

**Checkpoint**: `cd web && npx playwright --version` succeeds; `web/tests/e2e/fixtures/model-v1.json` exists and is valid JSON

---

## Phase 2: Update Playwright Config

- [ ] T004 Rewrite `web/playwright.config.ts` with two separate projects: (1) `api` project — uses `request` fixture only, no browser, baseURL from `process.env.ADP_API_URL ?? 'http://localhost:8001'`; (2) `browser` project — uses Chromium, baseURL from `process.env.ADP_WEB_URL ?? 'http://localhost:5173'`; set `timeout: 10000` for API tests and `timeout: 30000` for browser tests; set `testDir: './tests/e2e'`; set `reporter: 'list'`

---

## Phase 3: US1 — API Smoke Tests

**Goal**: All no-database-required endpoints pass; response schemas verified; runs in < 10s.

- [ ] T005 [US1] Create `web/tests/e2e/api.spec.ts` with these test cases (all using `request` fixture, no browser):

  **Health and observability:**
  - `test('GET /health returns healthy status')`: call `/health`; assert 200; assert `body.status === 'healthy'`; assert response header `X-Trace-ID` is non-empty
  - `test('GET /metrics returns prometheus format')`: call `/metrics`; assert 200; assert text includes `adp_request_total`, `adp_request_latency_seconds`, `adp_active_requests`
  - `test('X-Trace-ID header propagated from request')`: call `/health` with `X-Trace-ID: test-e2e-trace`; assert response header `X-Trace-ID === 'test-e2e-trace'`

  **Theme:**
  - `test('GET /api/v1/theme/c4 returns locked theme v1.0.1')`: call `/api/v1/theme/c4`; assert 200; assert `body.locked === true`; assert `body.version === '1.0.1'`; assert `body.styles.container.fill === '#2874A6'` (WCAG AA color)
  - `test('theme has all four element kinds')`: assert all of `person`, `system`, `container`, `component` are keys in `body.styles`

  **Layout (in-process store — no DB needed):**
  - `test('GET /layout/container returns empty positions for new design')`: call `/api/v1/designs/E2E-NEW/layout/container`; assert 200; assert `body.design_id === 'E2E-NEW'`; assert `body.level === 'container'`; assert `body.positions` is an empty object `{}`

  **No-DB error responses:**
  - `test('POST /render without DB returns 503 with clear message')`: call `POST /api/v1/designs/E2E-001/render` with `{"level": "container"}`; assert 503; assert response body text includes `ADP_DATABASE_URL`
  - `test('POST /document without DB returns 503 with clear message')`: call `GET /api/v1/designs/E2E-001/document`; assert 503; assert response body text includes `ADP_DATABASE_URL`

---

## Phase 4: US2 — ART-VIII Confirmation Gate

- [ ] T006 [US2] Add to `web/tests/e2e/api.spec.ts`:
  - `test('ART-VIII: blank confirmation_id rejected with 422')`: call `POST /api/v1/designs/E2E-001/export` with `{"confirmation_id": "", "export_root": "/tmp"}`; assert 422; assert response body mentions `confirmation_id`
  - `test('ART-VIII: missing confirmation_id field rejected with 422')`: call with `{"export_root": "/tmp"}` (no confirmation_id field); assert 422
  - `test('ART-VIII: non-blank confirmation_id passes gate, hits DB 503')`: call with `{"confirmation_id": "CONF-E2E-TEST", "export_root": "/tmp"}`; assert 503 (not 422) — proves gate passed and DB dependency fired

---

## Phase 5: US3 — Round-Trip Import

- [ ] T007 [US3] Add to `web/tests/e2e/api.spec.ts`:
  - `test('POST /import round-trips model-v1.json correctly')`: read `fixtures/model-v1.json` using `fs.readFileSync`; POST to `/api/v1/designs/import` with `{"model_json": content}`; assert 200; assert `body.design_id === 'E2E-IMPORT'`; assert `body.element_count === 2`; assert `body.relationship_count === 1`; assert `body.validation_warnings` is empty array
  - `test('POST /import rejects wrong schema version')`: POST `{"model_json": JSON.stringify({schema_version: "99.0.0", id: "X", title: "T", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z"})}`; assert 422; assert response body mentions `99.0.0`
  - `test('POST /import rejects malformed JSON')`: POST `{"model_json": "not json {"}`; assert 422; assert response body mentions `Invalid JSON` or similar

---

## Phase 6: US4 — Web Canvas Browser Tests

- [ ] T008 [US4] Replace `web/tests/e2e/workspace.spec.ts` with browser tests that skip unless `ADP_WEB_URL` is set:

  ```typescript
  import { test, expect } from '@playwright/test';

  const WEB_URL = process.env.ADP_WEB_URL;

  test.describe('C4 Workspace Browser Tests', () => {
    test.skip(!WEB_URL, 'ADP_WEB_URL not set — skipping browser tests');

    test('workspace page loads and canvas is visible', async ({ page }) => {
      await page.goto(`${WEB_URL}/designs/E2E-D001`);
      await expect(page).toHaveTitle(/ADP/);
      await expect(page.getByText('+ Add Element')).toBeVisible({ timeout: 10_000 });
    });

    test('level toggle shows three C4 levels', async ({ page }) => {
      await page.goto(`${WEB_URL}/designs/E2E-D001`);
      await expect(page.getByRole('button', { name: 'Context' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Container' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Component' })).toBeVisible();
    });

    test('clicking Add Element shows input form', async ({ page }) => {
      await page.goto(`${WEB_URL}/designs/E2E-D001`);
      await page.getByText('+ Add Element').click();
      await expect(page.getByPlaceholder('Element name')).toBeVisible({ timeout: 2_000 });
    });
  });
  ```

---

## Phase 7: Polish and Run

- [ ] T009 Run `cd web && npx playwright test --project=api` against a running ADP server on port 8001; assert all API tests pass; fix any failures
- [ ] T010 [P] Run `cd web && npx playwright test --project=browser` (requires `ADP_WEB_URL=http://localhost:5173` and Vite + Chromium); document skip behavior when not set
- [ ] T011 [P] Add `"test:e2e": "playwright test"` and `"test:e2e:api": "playwright test --project=api"` scripts to `web/package.json`
- [ ] T012 [P] Add a note to RUNBOOK.md under "Running tests" section: `# E2E tests (requires running server)\ncd web && ADP_API_URL=http://localhost:8001 npx playwright test --project=api`

---

## Dependencies & Execution Order

- T001 → T002, T003 (parallel after install)
- T004 (config) must come before T005-T008 (tests reference config)
- T005 → T006 → T007 (all go into same api.spec.ts, sequential)
- T008 (browser test) independent of T005-T007
- T009-T012 (polish) after all test files written

---

## Notes

- API tests use Playwright `request` fixture — no browser launched, very fast
- Browser tests skip gracefully when `ADP_WEB_URL` is unset (not a failure, just skipped)
- `model-v1.json` fixture is generated once from Python and committed; stable across runs
- Running `npx playwright test` with the server down gives immediate "ECONNREFUSED" — not a hang
