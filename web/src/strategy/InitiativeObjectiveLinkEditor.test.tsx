// ADP-pgx. Mirrors ObjectiveCapabilityLinkEditor.test.tsx's vi.mock(hooks-
// module) convention, adapted for InitiativeObjectiveLinkEditor's simpler
// shape (linked set comes off the `initiative` prop, no reverse-lookup query).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InitiativeObjectiveLinkEditor from "./InitiativeObjectiveLinkEditor";
import * as strategyApi from "../api/strategy";
import type { StrategyInitiative } from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

const INITIATIVE: StrategyInitiative = {
  id: "init-1",
  name: "Claims Automation Rollout",
  description: null,
  owner: null,
  status: "planned",
  objective_ids: ["obj-1"],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useObjectives.mockReturnValue({
    data: {
      items: [
        { id: "obj-1", theme_id: "t1", owner: "Owner", statement: "Reduce cycle time", fiscal_year: 2026, period: "Q1", status: "proposed", updated_at: "2026-01-01T00:00:00Z" },
        { id: "obj-2", theme_id: "t1", owner: "Owner", statement: "Improve retention", fiscal_year: 2026, period: "Q1", status: "proposed", updated_at: "2026-01-01T00:00:00Z" },
      ],
      total: 2,
    },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useObjectives>);
  mockedStrategyApi.useLinkInitiativeObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeObjective>);
  mockedStrategyApi.useUnlinkInitiativeObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkInitiativeObjective>);
});

describe("InitiativeObjectiveLinkEditor", () => {
  it("lists currently-linked objectives with a Remove action", () => {
    render(<InitiativeObjectiveLinkEditor initiative={INITIATIVE} />);

    expect(screen.getByText("Reduce cycle time")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
    // "Improve retention" is not linked, so it must not appear in the linked
    // list (it belongs only in the dropdown).
    expect(screen.queryAllByText("Improve retention")).toHaveLength(1);
  });

  it("offers a filtered dropdown excluding already-linked objectives", () => {
    render(<InitiativeObjectiveLinkEditor initiative={INITIATIVE} />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.textContent);
    expect(optionLabels).toContain("Improve retention");
    expect(optionLabels).not.toContain("Reduce cycle time");
  });

  it("calls the link hook with the selected objective id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkInitiativeObjective.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeObjective>);

    const user = userEvent.setup();
    render(<InitiativeObjectiveLinkEditor initiative={INITIATIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "obj-2");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith("obj-2", expect.anything());
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkInitiativeObjective.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkInitiativeObjective>);

    const user = userEvent.setup();
    render(<InitiativeObjectiveLinkEditor initiative={INITIATIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith("obj-1", expect.anything());
  });

  it("shows a confirmation once linking succeeds", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useLinkInitiativeObjective.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeObjective>);

    const user = userEvent.setup();
    render(<InitiativeObjectiveLinkEditor initiative={INITIATIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "obj-2");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText(/Linked "Improve retention"/)).toBeTruthy();
  });

  it("shows a confirmation once unlinking succeeds", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useUnlinkInitiativeObjective.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkInitiativeObjective>);

    const user = userEvent.setup();
    render(<InitiativeObjectiveLinkEditor initiative={INITIATIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(screen.getByText(/Removed "Reduce cycle time"/)).toBeTruthy();
  });

  it("surfaces a 409 as 'Already linked'", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onError?.({ message: "conflict", status: 409 }));
    mockedStrategyApi.useLinkInitiativeObjective.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeObjective>);

    const user = userEvent.setup();
    render(<InitiativeObjectiveLinkEditor initiative={INITIATIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "obj-2");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText("Already linked")).toBeTruthy();
  });
});
