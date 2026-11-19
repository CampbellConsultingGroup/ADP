// 919-insights-dashboard; ADP-v2n added the TIME quadrant chart.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import InsightsPage from "./InsightsPage";
import * as applicationApi from "../api/application";
import * as portfolioApi from "../api/portfolio";

vi.mock("../api/application");
vi.mock("../api/portfolio");

const mockedApplicationApi = vi.mocked(applicationApi);
const mockedPortfolioApi = vi.mocked(portfolioApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedPortfolioApi.useApplicationsHeatmap.mockReturnValue({
    data: { items: [], cost_permitted: false },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof portfolioApi.useApplicationsHeatmap>);
  mockedApplicationApi.useRationalization.mockReturnValue({
    data: { assessed: [], unassessed: [], total: 0 },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof applicationApi.useRationalization>);
});

describe("InsightsPage", () => {
  it("renders the page heading, the TIME quadrant chart and the applications heat map", () => {
    render(<InsightsPage />);

    expect(screen.getByText("Insights")).toBeTruthy();
    expect(screen.getByText("TIME quadrant")).toBeTruthy();
    expect(screen.getByText("No applications to plot yet")).toBeTruthy();
    expect(screen.getByText(/No applications in the portfolio yet/)).toBeTruthy();
  });
});
