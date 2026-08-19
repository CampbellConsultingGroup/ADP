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
  control_mappings: [],
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
  mockedApi.useObjectives.mockReturnValue({
    data: {
      items: [
        { id: "obj-1", theme_id: "t1", owner: "Owner", statement: "Reduce cycle time", fiscal_year: 2026, period: "Q1", status: "proposed", updated_at: "2026-01-01T00:00:00Z" },
        { id: "obj-2", theme_id: "t1", owner: "Owner", statement: "Improve retention", fiscal_year: 2026, period: "Q1", status: "proposed", updated_at: "2026-01-01T00:00:00Z" },
      ],
      total: 2,
    },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useObjectives>);
  mockedApi.useLinkInitiativeObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeObjective>);
  mockedApi.useUnlinkInitiativeObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkInitiativeObjective>);
  // 925-strategy-compliance-linkage: InitiativeControlMappingEditor's link/unlink mutations.
  mockedApi.useLinkInitiativeControlMapping.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeControlMapping>);
  mockedApi.useUnlinkInitiativeControlMapping.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkInitiativeControlMapping>);
});

describe("InitiativeList (mirrors ThemeList.tsx's convention)", () => {
  it("renders existing initiatives with status, description, owner, and linked-objective statements", () => {
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
    expect(screen.getByText("Reduce cycle time")).toBeTruthy();
    expect(screen.getByText("Improve retention")).toBeTruthy();
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

  it("shows the objective link editor in edit mode without submitting the name/status form (ADP-pgx)", async () => {
    const initiative = { ...INITIATIVE, objective_ids: ["obj-1"] };
    mockedApi.useInitiatives.mockReturnValue({
      data: { items: [initiative], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);
    const updateMutate = vi.fn();
    mockedApi.useUpdateInitiative.mockReturnValue({
      mutate: updateMutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useUpdateInitiative>);
    const linkMutate = vi.fn();
    mockedApi.useLinkInitiativeObjective.mockReturnValue({
      mutate: linkMutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeObjective>);

    const user = userEvent.setup();
    render(<InitiativeList />);

    await user.click(screen.getByText("Edit"));

    expect(screen.getByText("Linked Objectives")).toBeTruthy();
    expect(screen.getByText("Reduce cycle time")).toBeTruthy();

    // Three <select>s are on screen in edit mode (Status, the objective link
    // editor's own, then 925-strategy-compliance-linkage's target-type
    // select) -- the objective one is always the second, right after Status,
    // regardless of what other selects render after it.
    const comboboxes = screen.getAllByRole("combobox");
    await user.selectOptions(comboboxes[1], "obj-2");
    // Two "Link" buttons now render (objective editor, then
    // 925-strategy-compliance-linkage's control-mapping editor) -- the
    // objective editor's is first in DOM order.
    await user.click(screen.getAllByText("Link")[0]);

    expect(linkMutate).toHaveBeenCalledWith("obj-2", expect.anything());
    // Clicking Link must not have also submitted the name/status form.
    expect(updateMutate).not.toHaveBeenCalled();
  });

  it("lets you jump from a linked objective's name to its own detail view (strategy screen navigation, 2026-08-14)", async () => {
    mockedApi.useInitiatives.mockReturnValue({
      data: { items: [INITIATIVE], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);

    const onNavigateToObjective = vi.fn();
    const user = userEvent.setup();
    render(<InitiativeList onNavigateToObjective={onNavigateToObjective} />);

    await user.click(screen.getByText("Reduce cycle time"));

    expect(onNavigateToObjective).toHaveBeenCalledWith("obj-1");
  });

  it("scrolls the matching row into view and marks it focused when focusInitiativeId is set (mirrors CapabilityTree's focusCapabilityId precedent)", () => {
    Element.prototype.scrollIntoView = vi.fn();
    mockedApi.useInitiatives.mockReturnValue({
      data: { items: [INITIATIVE], total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);

    render(<InitiativeList focusInitiativeId="init-1" />);

    const node = document.getElementById("initiative-init-1");
    expect(node).toBeTruthy();
    expect(node!.scrollIntoView).toHaveBeenCalled();
    expect(node!.getAttribute("data-focused")).toBe("true");
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
