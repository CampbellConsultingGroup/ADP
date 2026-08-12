// ADP-d8u.1 (T031): mirrors web/src/business/ValueStreamList.tsx's
// convention (list + inline embedded create form + onSelect).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
