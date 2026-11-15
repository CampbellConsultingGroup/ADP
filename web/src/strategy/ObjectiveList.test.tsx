// ADP-d8u.1 (T031): mirrors web/src/business/ValueStreamList.tsx's
// convention (list + inline embedded create form + onSelect).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveList from "./ObjectiveList";
import * as strategyApi from "../api/strategy";

vi.mock("../api/strategy");

const mockedApi = vi.mocked(strategyApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useThemes.mockReturnValue({
    data: { items: [{ id: "t1", name: "Growth", created_at: "2026-01-01T00:00:00Z" }], total: 1 },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useThemes>);
  mockedApi.useCreateObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof strategyApi.useCreateObjective>);
});

describe("ObjectiveList", () => {
  it("renders multiple objectives with summary info", () => {
    mockedApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-1", theme_id: "t1", owner: "Owner A", statement: "Statement A", fiscal_year: 2026, period: "Q1", updated_at: "2026-01-01T00:00:00Z" },
          { id: "obj-2", theme_id: "t1", owner: "Owner B", statement: "Statement B", fiscal_year: 2026, period: "Q2", updated_at: "2026-01-01T00:00:00Z" },
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);

    render(<ObjectiveList onSelect={vi.fn()} />);

    expect(screen.getByText("Statement A")).toBeTruthy();
    expect(screen.getByText("Statement B")).toBeTruthy();
    expect(screen.getByText(/Owner A/)).toBeTruthy();
  });

  it("narrows the list to filterThemeId, with a clear-filter action (strategy screen navigation, 2026-08-14)", async () => {
    mockedApi.useThemes.mockReturnValue({
      data: {
        items: [
          { id: "t1", name: "Growth", created_at: "2026-01-01T00:00:00Z" },
          { id: "t2", name: "Efficiency", created_at: "2026-01-01T00:00:00Z" },
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);
    mockedApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-1", theme_id: "t1", owner: "Owner A", statement: "Statement A", fiscal_year: 2026, period: "Q1", updated_at: "2026-01-01T00:00:00Z" },
          { id: "obj-2", theme_id: "t2", owner: "Owner B", statement: "Statement B", fiscal_year: 2026, period: "Q2", updated_at: "2026-01-01T00:00:00Z" },
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);

    const onClearThemeFilter = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveList onSelect={vi.fn()} filterThemeId="t1" onClearThemeFilter={onClearThemeFilter} />);

    expect(screen.getByText("Statement A")).toBeTruthy();
    expect(screen.queryByText("Statement B")).toBeNull();
    expect(screen.getByText(/in theme .Growth./)).toBeTruthy();

    await user.click(screen.getByText("Clear filter"));
    expect(onClearThemeFilter).toHaveBeenCalled();
  });

  it("calls onSelect when an objective is clicked", async () => {
    mockedApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-1", theme_id: "t1", owner: "Owner A", statement: "Statement A", fiscal_year: 2026, period: "Q1", updated_at: "2026-01-01T00:00:00Z" },
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);

    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveList onSelect={onSelect} />);

    await user.click(screen.getByText("Statement A"));
    expect(onSelect).toHaveBeenCalledWith("obj-1");
  });

  // ── ADP-3fg: each objective's Theme is visible (and navigable) from the list ──────
  function twoThemesTwoObjectives() {
    mockedApi.useThemes.mockReturnValue({
      data: {
        items: [
          { id: "t1", name: "Growth", created_at: "2026-01-01T00:00:00Z" },
          { id: "t2", name: "Efficiency", created_at: "2026-01-01T00:00:00Z" },
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);
    mockedApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-1", theme_id: "t1", owner: "Owner A", statement: "Statement A", fiscal_year: 2026, period: "Q1", updated_at: "2026-01-01T00:00:00Z" },
          { id: "obj-2", theme_id: "t2", owner: "Owner B", statement: "Statement B", fiscal_year: 2026, period: "Q2", updated_at: "2026-01-01T00:00:00Z" },
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);
  }

  it("shows each objective's theme on its row", () => {
    twoThemesTwoObjectives();
    render(<ObjectiveList onSelect={vi.fn()} />);
    const rowA = screen.getByText("Statement A").closest("[data-objective-row]") as HTMLElement;
    const rowB = screen.getByText("Statement B").closest("[data-objective-row]") as HTMLElement;
    expect(within(rowA).getByText("Growth")).toBeTruthy();
    expect(within(rowB).getByText("Efficiency")).toBeTruthy();
  });

  it("jumps to the theme without opening the objective", async () => {
    twoThemesTwoObjectives();
    const onSelect = vi.fn();
    const onNavigateToTheme = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveList onSelect={onSelect} onNavigateToTheme={onNavigateToTheme} />);
    await user.click(screen.getByRole("button", { name: "Efficiency" }));
    expect(onNavigateToTheme).toHaveBeenCalledWith("t2");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("falls back to the theme id when the theme is not loaded", () => {
    mockedApi.useThemes.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false, error: null } as unknown as ReturnType<typeof strategyApi.useThemes>);
    mockedApi.useObjectives.mockReturnValue({
      data: { items: [{ id: "obj-1", theme_id: "t-missing", owner: "O", statement: "S", fiscal_year: 2026, period: "Q1", updated_at: "2026-01-01T00:00:00Z" }], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);
    render(<ObjectiveList onSelect={vi.fn()} />);
    expect(screen.getByText("t-missing")).toBeTruthy();
  });

  it("filters by theme from a dropdown", async () => {
    twoThemesTwoObjectives();
    const onThemeFilterChange = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<ObjectiveList onSelect={vi.fn()} onThemeFilterChange={onThemeFilterChange} />);
    await user.selectOptions(screen.getByLabelText("Filter by theme"), "t2");
    expect(onThemeFilterChange).toHaveBeenCalledWith("t2");
    rerender(<ObjectiveList onSelect={vi.fn()} filterThemeId="t2" onThemeFilterChange={onThemeFilterChange} />);
    expect(screen.queryByText("Statement A")).toBeNull();
    expect(screen.getByText("Statement B")).toBeTruthy();
    expect((screen.getByLabelText("Filter by theme") as HTMLSelectElement).value).toBe("t2");
    await user.selectOptions(screen.getByLabelText("Filter by theme"), "");
    expect(onThemeFilterChange).toHaveBeenLastCalledWith(null);
  });
});
