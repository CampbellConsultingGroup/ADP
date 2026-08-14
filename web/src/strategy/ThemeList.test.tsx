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
  mockedApi.useUpdateTheme.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof strategyApi.useUpdateTheme>);
  mockedApi.useDeleteTheme.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useDeleteTheme>);
  mockedApi.useObjectives.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useObjectives>);
});

describe("ThemeList (mirrors DomainList.tsx's convention)", () => {
  it("renders existing themes", () => {
    mockedApi.useThemes.mockReturnValue({
      data: {
        items: [
          { id: "t1", name: "Growth", description: null, owner: null, priority: null, created_at: "2026-01-01T00:00:00Z" },
          { id: "t2", name: "Efficiency", description: null, owner: null, priority: null, created_at: "2026-01-01T00:00:00Z" },
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

describe("ThemeList: description/owner/priority (ADP-d8u.5, T034)", () => {
  const THEME_WITH_METADATA = {
    id: "t1",
    name: "Digital Channels",
    description: "Customer-facing digital experience",
    owner: "jane.architect",
    priority: 2,
    created_at: "2026-01-01T00:00:00Z",
  };

  it("displays description, owner, and priority when present", () => {
    mockedApi.useThemes.mockReturnValue({
      data: { items: [THEME_WITH_METADATA], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);

    render(<ThemeList />);

    expect(screen.getByText("Customer-facing digital experience")).toBeTruthy();
    expect(screen.getByText(/jane.architect/)).toBeTruthy();
    expect(screen.getByText(/Priority 2/)).toBeTruthy();
  });

  it("supports editing a theme's description/owner/priority", async () => {
    mockedApi.useThemes.mockReturnValue({
      data: { items: [THEME_WITH_METADATA], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);
    const mutate = vi.fn();
    mockedApi.useUpdateTheme.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useUpdateTheme>);

    const user = userEvent.setup();
    render(<ThemeList />);

    await user.click(screen.getByText("Edit"));
    const priorityInput = screen.getByLabelText(/Priority/) as HTMLInputElement;
    await user.clear(priorityInput);
    await user.type(priorityInput, "1");
    await user.click(screen.getByText("Save"));

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ priority: 1 }),
      expect.anything(),
    );
  });

  it("deletes an unreferenced theme", async () => {
    mockedApi.useThemes.mockReturnValue({
      data: { items: [THEME_WITH_METADATA], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);
    const mutate = vi.fn();
    mockedApi.useDeleteTheme.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useDeleteTheme>);
    vi.stubGlobal("confirm", vi.fn(() => true));

    const user = userEvent.setup();
    render(<ThemeList />);

    await user.click(screen.getByText("Delete"));

    expect(mutate).toHaveBeenCalledWith("t1", expect.anything());
    vi.unstubAllGlobals();
  });

  it("shows an objective count per theme, and lets you jump to that theme's objectives (strategy screen navigation, 2026-08-14)", async () => {
    mockedApi.useThemes.mockReturnValue({
      data: { items: [THEME_WITH_METADATA], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);
    mockedApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-1", theme_id: "t1", owner: "A", statement: "Reduce cycle time", fiscal_year: 2026, period: "Q1", status: "proposed", updated_at: "" },
          { id: "obj-2", theme_id: "t1", owner: "A", statement: "Improve retention", fiscal_year: 2026, period: "Q1", status: "proposed", updated_at: "" },
        ],
        total: 2,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);

    const onNavigateToObjectives = vi.fn();
    const user = userEvent.setup();
    render(<ThemeList onNavigateToObjectives={onNavigateToObjectives} />);

    const link = screen.getByText("2 objectives");
    await user.click(link);

    expect(onNavigateToObjectives).toHaveBeenCalledWith("t1");
  });

  it("shows a zero objective count as plain text when no objectives are linked", () => {
    mockedApi.useThemes.mockReturnValue({
      data: { items: [THEME_WITH_METADATA], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);

    render(<ThemeList onNavigateToObjectives={vi.fn()} />);

    expect(screen.getByText("0 objectives")).toBeTruthy();
  });

  it("scrolls the matching row into view and marks it focused when focusThemeId is set (mirrors CapabilityTree's focusCapabilityId precedent)", () => {
    Element.prototype.scrollIntoView = vi.fn();
    mockedApi.useThemes.mockReturnValue({
      data: { items: [THEME_WITH_METADATA], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);

    render(<ThemeList focusThemeId="t1" />);

    const node = document.getElementById("theme-t1");
    expect(node).toBeTruthy();
    expect(node!.scrollIntoView).toHaveBeenCalled();
    expect(node!.getAttribute("data-focused")).toBe("true");
  });

  it("surfaces a clear message when deleting a still-referenced theme is blocked (409)", async () => {
    mockedApi.useThemes.mockReturnValue({
      data: { items: [THEME_WITH_METADATA], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useThemes>);
    mockedApi.useDeleteTheme.mockReturnValue({
      mutate: (
        _id: string,
        opts: { onError: (err: Error & { status?: number }) => void },
      ) => opts.onError(Object.assign(new Error("DELETE failed: 409"), { status: 409 })),
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useDeleteTheme>);
    vi.stubGlobal("confirm", vi.fn(() => true));

    const user = userEvent.setup();
    render(<ThemeList />);

    await user.click(screen.getByText("Delete"));

    expect(screen.getByText(/still assigned to at least one objective/)).toBeTruthy();
    vi.unstubAllGlobals();
  });
});
