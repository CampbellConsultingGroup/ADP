// 919-insights-dashboard: mirrors this session's established vi.mock(hooks-module)
// convention (e.g. StrategyHeatMap.test.tsx).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApplicationsHeatMap from "./ApplicationsHeatMap";
import * as portfolioApi from "../api/portfolio";
import type { ApplicationHeatmapResponse } from "../api/portfolio";

vi.mock("../api/portfolio");

const mockedPortfolioApi = vi.mocked(portfolioApi);

const HEATMAP_OPEN: ApplicationHeatmapResponse = {
  items: [
    {
      id: "app-01", name: "Policy Admin System", health_score: 4,
      business_criticality: 5, time_classification: "Invest", cost: null,
    },
    {
      id: "app-02", name: "Legacy Claims Batch", health_score: null,
      business_criticality: 2, time_classification: "Eliminate", cost: null,
    },
  ],
  cost_permitted: false,
};

const HEATMAP_WITH_COST: ApplicationHeatmapResponse = {
  items: [
    {
      id: "app-01", name: "Policy Admin System", health_score: 4,
      business_criticality: 5, time_classification: "Invest", cost: 350000,
    },
    {
      id: "app-02", name: "Legacy Claims Batch", health_score: 2,
      business_criticality: 2, time_classification: "Eliminate", cost: 90000,
    },
  ],
  cost_permitted: true,
};

function mockData(data: ApplicationHeatmapResponse) {
  mockedPortfolioApi.useApplicationsHeatmap.mockReturnValue({
    data,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof portfolioApi.useApplicationsHeatmap>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockData(HEATMAP_OPEN);
});

describe("ApplicationsHeatMap (US1 — default health-score coloring)", () => {
  it("renders one cell per application, labeled by name", () => {
    render(<ApplicationsHeatMap />);

    expect(screen.getByText("Policy Admin System")).toBeTruthy();
    expect(screen.getByText("Legacy Claims Batch")).toBeTruthy();
    expect(screen.getByText("2 applications")).toBeTruthy();
  });

  it("renders an unscored application with a distinct 'Unclassified' label", () => {
    render(<ApplicationsHeatMap />);

    expect(screen.getByText("Unclassified")).toBeTruthy();
  });

  it("shows an empty-state message when there are zero applications", () => {
    mockData({ items: [], cost_permitted: false });

    render(<ApplicationsHeatMap />);

    expect(screen.getByText(/No applications in the portfolio yet/)).toBeTruthy();
  });
});

describe("ApplicationsHeatMap (US2 — dimension selector + cost gating)", () => {
  it("does not offer 'cost' as a dimension when cost_permitted is false", () => {
    render(<ApplicationsHeatMap />);

    expect(screen.queryByText(/Color by: Cost/)).toBeNull();
  });

  it("offers and applies 'cost' as a dimension when cost_permitted is true", async () => {
    mockData(HEATMAP_WITH_COST);
    const user = userEvent.setup();
    render(<ApplicationsHeatMap />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "cost");

    expect(screen.getByText("$350,000")).toBeTruthy();
    expect(screen.getByText("$90,000")).toBeTruthy();
  });

  it("switches the rendered value label when the dimension changes", async () => {
    const user = userEvent.setup();
    render(<ApplicationsHeatMap />);

    // Default (health score): app-01 shows "4"
    expect(screen.getByText("4")).toBeTruthy();

    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "time_classification");

    expect(screen.getByText("Invest")).toBeTruthy();
    expect(screen.getByText("Eliminate")).toBeTruthy();
  });
});
