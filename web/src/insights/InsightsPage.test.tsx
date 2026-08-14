// 919-insights-dashboard

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import InsightsPage from "./InsightsPage";
import * as portfolioApi from "../api/portfolio";

vi.mock("../api/portfolio");

const mockedPortfolioApi = vi.mocked(portfolioApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedPortfolioApi.useApplicationsHeatmap.mockReturnValue({
    data: { items: [], cost_permitted: false },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof portfolioApi.useApplicationsHeatmap>);
});

describe("InsightsPage", () => {
  it("renders the page heading and the applications heat map", () => {
    render(<InsightsPage />);

    expect(screen.getByText("Insights")).toBeTruthy();
    expect(screen.getByText(/No applications in the portfolio yet/)).toBeTruthy();
  });
});
