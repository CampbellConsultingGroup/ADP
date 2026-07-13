# Research: Playwright End-to-End Test Suite

**Branch**: `013-playwright-e2e` | **Date**: 2026-07-02

---

## Decision 1: `@playwright/test` vs `playwright` package

**Decision**: Add `@playwright/test` as the test runner. The existing `playwright` package (already in `web/package.json`) is the browser automation library; `@playwright/test` is the test framework (runner, fixtures, assertions). They are separate packages but compatible at the same version.

**Current state**: `"playwright": "^1.47.0"` is in devDependencies. `@playwright/test` is not present but is resolvable via the global `npx playwright` CLI which includes the runner.

**Chosen approach**: Add `"@playwright/test": "^1.47.0"` to `web/package.json` and install it alongside `playwright`. This allows `import { test, expect, request } from '@playwright/test'` in test files and `npx playwright test` as the runner.

---

## Decision 2: Test file structure — API tests vs browser tests

**Decision**: Two separate spec files:
- `web/tests/e2e/api.spec.ts` — Pure API tests using Playwright's `request` fixture. No browser launched. Fast (< 10s total). Runs always.
- `web/tests/e2e/workspace.spec.ts` — Browser tests using `page` fixture (Chromium). Slower. Skipped unless `ADP_WEB_URL` is set.

**Rationale**: Separating API and browser tests lets CI run the fast API tests on every push without installing Chromium, and only run browser tests on specific pipelines. The existing `workspace.spec.ts` stub (from ADP-SPEC-009) is replaced with the real implementation.

---

## Decision 3: ADP_API_URL configuration

**Decision**: Use `process.env.ADP_API_URL ?? 'http://localhost:8001'` as the base URL for API tests. The `playwright.config.ts` already has `baseURL: process.env.ADP_TEST_URL ?? 'http://localhost:8000'` — update it to use `ADP_API_URL` with default `8001` (matching the port we run on).

---

## Decision 4: Chromium installation

**Decision**: `npx playwright install chromium` is a one-time setup command documented in RUNBOOK.md. It is NOT run automatically during `npm install`. Browser tests skip gracefully if Chromium is absent (via `test.skip` guard checking `process.env.ADP_WEB_URL`).

---

## Decision 5: Design fixture for import tests

**Decision**: Generate the `model.json` fixture in Python and commit it to `web/tests/e2e/fixtures/model-v1.json`. This avoids requiring the Python runtime during TypeScript tests and makes the fixture a stable, reviewable artifact.

---

## Summary of Changes

| File | Action |
|---|---|
| `web/package.json` | Add `@playwright/test` devDependency |
| `web/playwright.config.ts` | Update baseURL to `ADP_API_URL:8001`; separate projects for API vs browser |
| `web/tests/e2e/api.spec.ts` | New: API smoke tests (US1-US3) |
| `web/tests/e2e/workspace.spec.ts` | Replace stub with real browser tests (US4) |
| `web/tests/e2e/fixtures/model-v1.json` | New: stable model fixture for import tests |
