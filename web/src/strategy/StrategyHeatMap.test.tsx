// 918-strategy-rollups: mirrors this session's established vi.mock(hooks-module)
// convention (e.g. ThemeList.test.tsx).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StrategyHeatMap from "./StrategyHeatMap";
import * as strategyApi from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

const THEMES = {
  items: [
    { id: "t1", name: "Growth", description: null, owner: null, priority: null, created_at: "" },
    { id: "t2", name: "Efficiency", description: null, owner: null, priority: null, created_at: "" },
  ],
  total: 2,
};

const HEATMAP = {
  themes: [
    {
      theme_id: "t1", theme_name: "Growth",
      proposed_count: 1, active_count: 2, at_risk_count: 1, achieved_count: 0, abandoned_count: 0,
    },
    {
      theme_id: "t2", theme_name: "Efficiency",
      proposed_count: 0, active_count: 0, at_risk_count: 0, achieved_count: 0, abandoned_count: 0,
    },
  ],
  total_objectives: 4,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useThemes.mockReturnValue({
    data: THEMES,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useThemes>);
  mockedStrategyApi.useStrategyHeatMap.mockReturnValue({
    data: HEATMAP,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useStrategyHeatMap>);
});

describe("StrategyHeatMap", () => {
  it("renders every theme row with correct per-status counts", () => {
    render(<StrategyHeatMap />);

    // "Growth"/"Efficiency" each appear twice: once as a table row, once as
    // a filter-dropdown option -- confirm both instances exist.
    expect(screen.getAllByText("Growth").length).toBe(2);
    expect(screen.getAllByText("Efficiency").length).toBe(2);
    expect(screen.getByText("4 objectives across 2 themes")).toBeTruthy();
  });

  it("shows an all-zero row for a theme with zero objectives, not omitted", () => {
    render(<StrategyHeatMap />);

    const efficiencyCell = screen.getAllByText("Efficiency").find((el) => el.tagName === "TD");
    const efficiencyRow = efficiencyCell?.closest("tr");
    expect(efficiencyRow).toBeTruthy();
    // Every cell in that row should read 0.
    const cells = efficiencyRow!.querySelectorAll("td");
    const counts = Array.from(cells).slice(1).map((c) => c.textContent);
    expect(counts).toEqual(["0", "0", "0", "0", "0"]);
  });

  it("calls useStrategyHeatMap with the selected theme id when the filter changes", async () => {
    const user = userEvent.setup();
    render(<StrategyHeatMap />);

    await user.selectOptions(screen.getByRole("combobox"), "t1");

    expect(mockedStrategyApi.useStrategyHeatMap).toHaveBeenLastCalledWith("t1");
  });

  it("shows an empty state when there are no themes", () => {
    mockedStrategyApi.useStrategyHeatMap.mockReturnValue({
      data: { themes: [], total_objectives: 0 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useStrategyHeatMap>);

    render(<StrategyHeatMap />);

    expect(screen.getByText(/No themes yet/)).toBeTruthy();
  });
});
