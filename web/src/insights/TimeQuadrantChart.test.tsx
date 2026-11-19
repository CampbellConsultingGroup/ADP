// ADP-v2n: TIME quadrant bubble chart on the Insights page.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import TimeQuadrantChart from "./TimeQuadrantChart";
import * as applicationApi from "../api/application";
import * as portfolioApi from "../api/portfolio";
import type { RationalizationResponse } from "../api/application";
import type { ApplicationHeatmapResponse } from "../api/portfolio";

vi.mock("../api/application");
vi.mock("../api/portfolio");

const mockedApp = vi.mocked(applicationApi);
const mockedPortfolio = vi.mocked(portfolioApi);

const RAT: RationalizationResponse = {
  assessed: [
    { app_id: "app-01", name: "Policy Admin System", business_value: 5, health_score: 4, quadrant: "invest" },
    { app_id: "app-02", name: "Legacy Claims Batch", business_value: 4, health_score: 1, quadrant: "migrate" },
  ],
  unassessed: [{ app_id: "app-03", name: "New Portal", business_value: null, health_score: 3, quadrant: null }],
  total: 3,
};

function heatmap(cost_permitted: boolean): ApplicationHeatmapResponse {
  return {
    items: [
      { id: "app-01", name: "Policy Admin System", health_score: 4, business_criticality: 5, time_classification: "Invest", cost: cost_permitted ? 350000 : null },
      // Classified Invest, but its scores put it in Migrate.
      { id: "app-02", name: "Legacy Claims Batch", health_score: 1, business_criticality: 2, time_classification: "Invest", cost: cost_permitted ? 90000 : null },
    ],
    cost_permitted,
  };
}

function mock(rat: RationalizationResponse | undefined, heat: ApplicationHeatmapResponse | undefined, extra: object = {}) {
  mockedApp.useRationalization.mockReturnValue({ data: rat, isLoading: false, error: null, ...extra } as unknown as ReturnType<typeof applicationApi.useRationalization>);
  mockedPortfolio.useApplicationsHeatmap.mockReturnValue({ data: heat, isLoading: false, error: null } as unknown as ReturnType<typeof portfolioApi.useApplicationsHeatmap>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mock(RAT, heatmap(false));
});

describe("TimeQuadrantChart", () => {
  it("draws one linked bubble per assessed application", () => {
    render(<TimeQuadrantChart />);
    const link = screen.getByRole("link", { name: /Policy Admin System/ });
    expect(link.getAttribute("href")).toContain("app-01");
    expect(screen.getByTestId("bubble-app-02")).toBeTruthy();
    expect(screen.getByText("2 applications placed by business value and technical health.", { exact: false })).toBeTruthy();
  });

  it("calls out an application whose TIME classification differs from its quadrant", () => {
    render(<TimeQuadrantChart />);
    expect(screen.getByText(/1 has a TIME classification that differs from its quadrant/)).toBeTruthy();
    expect(screen.getByTestId("bubble-app-02").getAttribute("stroke-width")).toBe("2.5");
    expect(screen.getByTestId("bubble-app-01").getAttribute("stroke-width")).toBe("1");
  });

  it("lists applications that cannot be placed", () => {
    render(<TimeQuadrantChart />);
    expect(screen.getByText(/1 not plotted/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "New Portal" })).toBeTruthy();
  });

  it("keeps bubbles one size and says why when cost is not available", () => {
    render(<TimeQuadrantChart />);
    expect(screen.getByTestId("bubble-app-01").getAttribute("r")).toBe(screen.getByTestId("bubble-app-02").getAttribute("r"));
    expect(screen.getByText(/cost is not available to you/)).toBeTruthy();
    expect(screen.queryByText(/TCO/)).toBeNull();
  });

  it("sizes bubbles by cost when the caller may read it", () => {
    mock(RAT, heatmap(true));
    render(<TimeQuadrantChart />);
    const big = Number(screen.getByTestId("bubble-app-01").getAttribute("r"));
    const small = Number(screen.getByTestId("bubble-app-02").getAttribute("r"));
    expect(big).toBeGreaterThan(small);
    expect(screen.getByRole("link", { name: /TCO \$350,000/ })).toBeTruthy();
  });

  it("shows an empty state when nothing can be placed", () => {
    mock({ assessed: [], unassessed: [], total: 0 }, heatmap(false));
    render(<TimeQuadrantChart />);
    expect(screen.getByText("No applications to plot yet")).toBeTruthy();
  });

  it("shows an error when a request fails", () => {
    mock(undefined, heatmap(false), { error: new Error("boom") });
    render(<TimeQuadrantChart />);
    expect(screen.getByText("Failed to load the TIME quadrant chart")).toBeTruthy();
  });
});
