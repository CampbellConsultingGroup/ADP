// ADP-d8u.1 (T015): mirrors web/src/chat/ChatPanel.test.tsx's
// vi.mock(hooks-module) convention -- mocks web/src/api/strategy.ts's
// hooks directly rather than wrapping in a QueryClientProvider.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ThemeList from "./ThemeList";
import * as strategyApi from "../api/strategy";

vi.mock("../api/strategy");

const mockedApi = vi.mocked(strategyApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useCreateTheme.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof strategyApi.useCreateTheme>);
});

describe("ThemeList (mirrors DomainList.tsx's convention)", () => {
  it("renders existing themes", () => {
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

    render(<ThemeList />);

    expect(screen.getByText("Growth")).toBeTruthy();
    expect(screen.getByText("Efficiency")).toBeTruthy();
  });

  it("supports creating a new theme", async () => {
    mockedApi.useThemes.mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);
    const mutate = vi.fn();
    mockedApi.useCreateTheme.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useCreateTheme>);

    const user = userEvent.setup();
    render(<ThemeList />);

    await user.click(screen.getByText("New Theme"));
    await user.type(screen.getByPlaceholderText("Usage-based pricing"), "Growth");
    await user.click(screen.getByText("Save"));

    expect(mutate).toHaveBeenCalledWith(
      { name: "Growth" },
      expect.anything(),
    );
  });
});
