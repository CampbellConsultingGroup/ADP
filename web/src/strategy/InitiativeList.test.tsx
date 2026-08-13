// ADP-d8u.6 (T018): mirrors ThemeList.test.tsx's vi.mock(hooks-module)
// convention -- mocks web/src/api/strategy.ts's hooks directly rather than
// wrapping in a QueryClientProvider.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InitiativeList from "./InitiativeList";
import * as strategyApi from "../api/strategy";

vi.mock("../api/strategy");

const mockedApi = vi.mocked(strategyApi);

const INITIATIVE = {
  id: "init-1",
  name: "Claims Automation",
  description: "Automate first-notice-of-loss intake",
  owner: "jane",
  status: "in_progress" as const,
  objective_ids: ["obj-1", "obj-2"],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useCreateInitiative.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof strategyApi.useCreateInitiative>);
  mockedApi.useUpdateInitiative.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof strategyApi.useUpdateInitiative>);
  mockedApi.useDeleteInitiative.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useDeleteInitiative>);
});

describe("InitiativeList (mirrors ThemeList.tsx's convention)", () => {
  it("renders existing initiatives with status, description, owner, and linked-objective count", () => {
    mockedApi.useInitiatives.mockReturnValue({
      data: { items: [INITIATIVE], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);

    render(<InitiativeList />);

    expect(screen.getByText("Claims Automation")).toBeTruthy();
    expect(screen.getByText("In progress")).toBeTruthy();
    expect(screen.getByText("Automate first-notice-of-loss intake")).toBeTruthy();
    expect(screen.getByText(/jane/)).toBeTruthy();
    expect(screen.getByText("2 linked objectives")).toBeTruthy();
  });

  it("supports creating a new initiative", async () => {
    mockedApi.useInitiatives.mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);
    const mutate = vi.fn();
    mockedApi.useCreateInitiative.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useCreateInitiative>);

    const user = userEvent.setup();
    render(<InitiativeList />);

    await user.click(screen.getByText("New Initiative"));
    await user.type(
      screen.getByPlaceholderText("Claims Automation Rollout"),
      "Fraud Detection Pilot",
    );
    await user.click(screen.getByText("Save"));

    expect(mutate).toHaveBeenCalledWith({ name: "Fraud Detection Pilot" }, expect.anything());
  });

  it("supports editing an initiative's status", async () => {
    mockedApi.useInitiatives.mockReturnValue({
      data: { items: [INITIATIVE], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);
    const mutate = vi.fn();
    mockedApi.useUpdateInitiative.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useUpdateInitiative>);

    const user = userEvent.setup();
    render(<InitiativeList />);

    await user.click(screen.getByText("Edit"));
    await user.selectOptions(screen.getByLabelText(/Status/), "blocked");
    await user.click(screen.getByText("Save"));

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ status: "blocked" }),
      expect.anything(),
    );
  });

  it("deletes an initiative unconditionally, even with linked objectives", async () => {
    mockedApi.useInitiatives.mockReturnValue({
      data: { items: [INITIATIVE], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);
    const mutate = vi.fn();
    mockedApi.useDeleteInitiative.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useDeleteInitiative>);
    vi.stubGlobal("confirm", vi.fn(() => true));

    const user = userEvent.setup();
    render(<InitiativeList />);

    await user.click(screen.getByText("Delete"));

    expect(mutate).toHaveBeenCalledWith("init-1");
    vi.unstubAllGlobals();
  });
});
