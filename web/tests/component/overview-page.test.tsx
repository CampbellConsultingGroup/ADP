/**
 * Component tests for the Overview landing dashboard — ADP-SPEC-037.
 *
 * Covers FR-006 (Overview is the default view), FR-007 (KPIs are fetched live
 * from the API, never hard-coded), and FR-009 (error affordance on query
 * failure; empty states when data is absent).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

import App from "../../src/App";
import OverviewPage from "../../src/overview/OverviewPage";
import { mockFetch, renderWithQuery } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// Every GET the Overview hooks issue. Distinctive totals so we can assert the
// rendered figures come from the response, not a constant.
const OK_ROUTES: Record<string, unknown> = {
  "GET /api/v1/applications": { items: [], total: 42 },
  "GET /api/v1/technical-capabilities": { items: [], total: 6 },
  "GET /api/v1/integrations": { items: [], total: 11 },
  "GET /api/v1/business/capabilities": { items: [], total: 23 },
  "GET /api/v1/business/value-streams": { items: [], total: 5 },
  "GET /api/v1/business/domains": { items: [], total: 3 },
  "GET /api/v1/portfolio/summary": { by_status: { current: 2, proposed: 1, draft: 1 }, total_designs: 17 },
  "GET /api/v1/knowledge": { items: [], total: 8 },
  "GET /api/v1/strategy/summary": {
    total_objectives: 9,
    total_themes: 3,
    linked_count: 6,
    unlinked_count: 3,
    current_period_count: 4,
    upcoming_count: 3,
    past_due_count: 2,
  },
  // 924-compliance-rollup-reporting
  "GET /api/v1/compliance/summary": {
    framework_count: 4,
    coverage_percent: 75,
    at_risk_count: 1,
  },
};

const ERROR_TEXT = /Some metrics failed to load/;

describe("OverviewPage", () => {
  it("is the default landing view rendered inside the shell (FR-006)", async () => {
    mockFetch(OK_ROUTES);
    renderWithQuery(<App />);
    // The Overview landing heading is shown with no navigation performed.
    expect(await screen.findByText("Architecture at a glance")).toBeTruthy();
  });

  it("fetches its KPIs live from the API (FR-007)", async () => {
    const calls = mockFetch(OK_ROUTES);
    renderWithQuery(<OverviewPage onNavigate={vi.fn()} />);

    await waitFor(() => {
      const urls = calls.map((c) => c.url);
      expect(urls).toContain("/api/v1/portfolio/summary");
      expect(urls).toContain("/api/v1/applications");
    });
    // Every recorded call is a read — the dashboard never mutates.
    expect(calls.every((c) => c.method === "GET")).toBe(true);
  });

  it("renders values sourced from the API responses (FR-007)", async () => {
    mockFetch(OK_ROUTES);
    renderWithQuery(<OverviewPage onNavigate={vi.fn()} />);
    // total_designs (17) and applications total (42) come straight from the mocks.
    expect((await screen.findAllByText("17")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("42").length).toBeGreaterThan(0);
  });

  it("shows an error affordance when a query fails (FR-009)", async () => {
    mockFetch({ ...OK_ROUTES, "GET /api/v1/portfolio/summary": [500, { detail: "boom" }] });
    renderWithQuery(<OverviewPage onNavigate={vi.fn()} />);
    expect(await screen.findByText(ERROR_TEXT)).toBeTruthy();
  });

  it("shows empty-state placeholders without an error when data is absent (FR-009)", async () => {
    // All endpoints succeed but carry no totals → figures fall back to "—".
    const empty = Object.fromEntries(Object.keys(OK_ROUTES).map((k) => [k, {}]));
    mockFetch(empty);
    renderWithQuery(<OverviewPage onNavigate={vi.fn()} />);

    expect(await screen.findByText("Architecture at a glance")).toBeTruthy();
    await waitFor(() => expect(screen.getAllByText("—").length).toBeGreaterThan(0));
    expect(screen.queryByText(ERROR_TEXT)).toBeNull();
  });

  it("navigates into a domain view when a tile is activated (FR-008)", async () => {
    mockFetch(OK_ROUTES);
    const onNavigate = vi.fn();
    renderWithQuery(<OverviewPage onNavigate={onNavigate} />);

    const tile = (await screen.findByText("Application Portfolio")).closest("button");
    expect(tile).toBeTruthy();
    fireEvent.click(tile as HTMLButtonElement);
    expect(onNavigate).toHaveBeenCalledWith("applications");
  });
});
