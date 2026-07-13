# Implementation Plan: Playwright End-to-End Test Suite

**Branch**: `013-playwright-e2e` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)

## Summary

Add `@playwright/test` as the test runner, create two E2E test files (`api.spec.ts` for API tests using Playwright's `request` context, `workspace.spec.ts` for browser tests using Chromium), generate a stable fixture `model-v1.json` for import round-trip testing, update `playwright.config.ts`, and install Chromium. All API tests run without a database and pass against the server on port 8001. Browser tests require Chromium + Vite dev server.

## Technical Context

**Language/Version**: TypeScript 5.x (existing web/ stack)
**Primary Framework**: `@playwright/test` v1.47+ (new devDependency); `playwright` v1.47 browser lib already installed
**Test types**: (1) API tests via `request` context — no browser launched, fast; (2) browser tests via `page` + Chromium
**Target server**: ADP API at `http://localhost:8001` (env `ADP_API_URL`); Vite at `http://localhost:5173` (env `ADP_WEB_URL`)
**No backend changes**: TypeScript-only; zero Python code changes
**New files**: `api.spec.ts`, updated `workspace.spec.ts`, `model-v1.json` fixture, updated `playwright.config.ts`

## Constitution Check

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-04 | ART-IV | E2E tests prove acceptance criteria against real app | ✅ This spec IS the QG-04 E2E layer |
| QG-05 | ART-IV, ART-XIII | Contract tests assert JSON field shapes, not just status codes | ✅ api.spec.ts asserts specific fields |
| QG-08 | ART-V | No secrets in test output or committed files | ✅ No auth tokens; only ADP_API_URL env var |

**N/A**: All other gates — this spec adds tests only, no production code changes.

## Project Structure

```text
web/
├── package.json                    # + @playwright/test devDependency
├── playwright.config.ts            # Updated: two projects (api, browser); ADP_API_URL baseURL
└── tests/e2e/
    ├── fixtures/
    │   └── model-v1.json           # Stable model fixture for import tests
    ├── api.spec.ts                 # NEW: US1-US3 API tests (request context, no browser)
    └── workspace.spec.ts           # REPLACED: US4 browser tests (Chromium)
```

## New Dependencies

| Package | Version | Purpose | Added to |
|---------|---------|---------|----------|
| `@playwright/test` | `^1.47.0` | Playwright test runner (distinct from playwright browser lib) | `web/package.json` devDependencies |
