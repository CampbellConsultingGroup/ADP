# Feature Specification: Playwright End-to-End Test Suite

**Feature Branch**: `013-playwright-e2e`
**Created**: 2026-07-02
**Status**: Draft
**Input**: `/home/jmuir/projects/ADP/docs/013-playwright-e2e.md`

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: this spec IS the TDD deliverable for end-to-end coverage; Playwright tests are the acceptance tests that unit/contract mocks cannot replace

**ART-V (security)**: Low risk — tests run against a local server; no credentials committed.

**ART-VII (AI grounding)**: Not engaged.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Local test server process; test artifacts on disk.

**Trust boundaries crossed**: Playwright browser → localhost API server → filesystem (for export tests).

**Abuse cases**:
- Test credentials committed to source → Mitigated by using environment variables or no-auth bypass for tests; never commit `ADP_TOKEN` values
- E2E tests that write exports to production paths → Mitigated by always using `tmp_path`-equivalent temp directories; all export tests clean up after themselves

**Residual risk**: Negligible. Tests are local-only; no external network calls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — API Smoke Tests (Priority: P1)

A developer runs a single command and gets confirmation that all key ADP API endpoints respond correctly against the live server: health, theme, layout, import, document generation, and metrics. These tests do not require a database and can run against the server started with no `ADP_DATABASE_URL`.

**Why this priority**: The API smoke tests validate the end-to-end wiring of the FastAPI application — routing, middleware, telemetry, response schemas — in a way that no unit test can. They are the first gate after deployment.

**Independent Test**: Start the ADP server on port 8001; run `npx playwright test api-smoke`; assert all tests pass within 30 seconds.

**Acceptance Scenarios**:

1. **Given** the ADP server is running, **When** `GET /health` is called, **Then** the response is 200 with `{"status": "healthy"}` and the `X-Trace-ID` header is present.
2. **Given** the ADP server is running, **When** `GET /api/v1/theme/c4` is called, **Then** the response is 200 with `locked: true` and all four element kinds present, and the container fill is `#2874A6` (WCAG AA v1.0.1).
3. **Given** the ADP server is running, **When** `GET /metrics` is called, **Then** the response contains `adp_request_total`, `adp_request_latency_seconds`, and `adp_active_requests`.
4. **Given** the ADP server is running, **When** `POST /api/v1/designs/import` is called with a valid `model.json`, **Then** the response is 200 with the correct `element_count` and `design_id`.
5. **Given** the ADP server is running, **When** `GET /api/v1/designs/{id}/layout/container` is called for an unknown design ID, **Then** the response is 200 with empty `positions` (in-process store returns empty for new IDs).
6. **Given** the ADP server is running with no `ADP_DATABASE_URL`, **When** `POST /api/v1/designs/{id}/render` is called, **Then** the response is 503 with a clear "ADP_DATABASE_URL is not configured" message — not a 500.

---

### User Story 2 — ART-VIII Confirmation Gate Tests (Priority: P1)

A developer verifies that the export endpoint correctly enforces the ART-VIII human confirmation requirement — rejecting empty confirmation IDs — without needing a database.

**Why this priority**: ART-VIII is a constitutional MUST. The E2E test proves the gate works in the deployed application, not just in unit tests with mocked dependencies.

**Independent Test**: `POST /api/v1/designs/{id}/export` with blank `confirmation_id`; assert 422 from Pydantic validation; `POST` with valid non-empty `confirmation_id` but no DB → assert 503 (not 422); proves the gate fires before the DB dependency.

**Acceptance Scenarios**:

1. **Given** the server is running, **When** `POST /export` with `{"confirmation_id": "", "export_root": "/tmp"}`, **Then** response is 422 and body mentions `confirmation_id`.
2. **Given** the server is running, **When** `POST /export` with `{"confirmation_id": "CONF-TEST", "export_root": "/tmp"}`, **Then** response is 503 (DB not configured) — NOT 422 — proving the ART-VIII gate passes and the DB dependency fires next.

---

### User Story 3 — Round-Trip Import/Export Tests (Priority: P2)

A developer verifies that the import endpoint round-trips a `model.json` correctly — parsing, validating, and returning element counts — and that the wrong schema version is rejected with a clear 422.

**Why this priority**: Round-trip integrity (FR-007 in ADP-SPEC-011) requires a live API test to prove that serialization, HTTP transport, and deserialization all work together.

**Independent Test**: Serialize a known design to JSON via Python; POST it to `POST /api/v1/designs/import`; assert the response `element_count` and `design_id` match the original.

**Acceptance Scenarios**:

1. **Given** a valid `model.json` at schema version `1.0.0`, **When** posted to `/import`, **Then** 200 with correct `element_count`, `relationship_count`, and empty `validation_warnings`.
2. **Given** a `model.json` with `schema_version: "99.0.0"`, **When** posted to `/import`, **Then** 422 with detail mentioning the version mismatch.
3. **Given** malformed JSON (not valid JSON string), **When** posted to `/import`, **Then** 422 with a clear error.

---

### User Story 4 — Web Canvas Smoke Test (Priority: P2)

A developer opens the C4 workspace in a real Chromium browser via Playwright and verifies that the page loads, the level toggle renders, and the "Add Element" button is visible — without requiring a backend connection.

**Why this priority**: The web canvas is a TypeScript/React application that has its own build chain. Browser-level smoke tests catch build regressions and routing errors that no unit test can.

**Independent Test**: Run `npm run dev` (Vite dev server); launch Playwright browser; navigate to `http://localhost:5173/designs/D-001`; assert "Add Element" text and level toggle buttons are visible.

**Acceptance Scenarios**:

1. **Given** the Vite dev server is running, **When** the workspace URL is opened in Chromium, **Then** the page title contains "ADP" and the canvas container is visible.
2. **Given** the workspace is loaded, **When** the level toggle is inspected, **Then** three buttons (Context, Container, Component) are visible.
3. **Given** the workspace is loaded, **When** the "Add Element" button is clicked, **Then** an element kind dropdown and name input appear within 2 seconds.

---

### Edge Cases

- What if the ADP server is not running when tests execute? Tests must fail with a clear "connection refused" error, not a cryptic timeout — set a short `baseURL` timeout.
- What if Chromium is not installed? `npx playwright install chromium` must be run first; the test runner should emit a clear "browser not found" error, not a crash.
- What if the Vite dev server is not running for US4? US4 tests are skipped unless `ADP_WEB_URL` is set; they are not blocking CI.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Playwright test suite MUST cover all endpoints that work without a database (health, theme, metrics, layout, import) as API-level tests using Playwright's `request` context — no browser required for these.
- **FR-002**: The test suite MUST include at least one browser-level test that opens the C4 workspace and verifies the canvas renders (US4).
- **FR-003**: The ART-VIII confirmation gate MUST be verified by a dedicated E2E test that proves blank `confirmation_id` → 422 and non-blank → 503 (not a stale gate bypass).
- **FR-004**: All API tests MUST verify response schema — not just status codes — by asserting specific JSON fields.
- **FR-005**: The test suite MUST be runnable with a single command: `npx playwright test` from the `web/` directory against a running ADP server.
- **FR-006**: Tests MUST clean up any artifacts they create (e.g., temp export directories); no test state leaks between runs.

### Key Entities

- **API Test**: A Playwright test using `request` fixture to call the ADP REST API; no browser launched.
- **Browser Test**: A Playwright test using `page` fixture to interact with the web canvas in Chromium.
- **ADP_API_URL**: Environment variable pointing to the running ADP server (default: `http://localhost:8001`).
- **ADP_WEB_URL**: Environment variable pointing to the Vite dev server (default: `http://localhost:5173`); if unset, browser tests are skipped.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All API smoke tests (US1) pass against a running ADP server within 10 seconds total.
- **SC-002**: The ART-VIII gate test (US2) passes in under 2 seconds.
- **SC-003**: The import round-trip test (US3) correctly validates a 4-element design in under 5 seconds.
- **SC-004**: The web canvas smoke test (US4) loads and finds the "Add Element" button within 10 seconds in a real Chromium browser.
- **SC-005**: Running `npx playwright test` with the server down fails immediately with a clear connection error, not a hang.

## Assumptions

- **Playwright CLI**: `playwright` v1.47+ is already installed in `web/node_modules/` (added in ADP-SPEC-009). The `@playwright/test` package (the test runner) needs to be added to `web/package.json` — it is the test runner, distinct from the `playwright` browser library.
- **Chromium**: Must be installed via `npx playwright install chromium` before browser tests can run. This is a one-time setup step, not a test-time dependency.
- **Test location**: All E2E tests live in `web/tests/e2e/` alongside the existing `workspace.spec.ts` stub. The existing stub will be replaced or merged.
- **No auth**: Tests call API endpoints without Bearer tokens. Endpoints that require auth (future ADP-SPEC-003 full implementation) are explicitly skipped in the test suite.
- **Server must be started manually**: `npx playwright test` does NOT start the ADP server or Vite dev server. Both must be running before tests execute. This is documented in the RUNBOOK.
- **CI scope**: API tests (US1-US3) are designed to run in CI without a browser or database. Browser tests (US4) are optional in CI and gated by `ADP_WEB_URL`.
