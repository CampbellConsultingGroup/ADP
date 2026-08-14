// ADP-d8u.6. Mirrors InitiativeObjectiveLinkEditor.test.tsx's vi.mock(hooks-
// module) convention, adapted for ObjectiveInitiativeLinkEditor's shape
// (linked set comes from the reverse-lookup useObjectiveInitiatives query,
// not an inline field on the objective).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveInitiativeLinkEditor from "./ObjectiveInitiativeLinkEditor";
import * as strategyApi from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useInitiatives.mockReturnValue({
    data: {
      items: [
        {
          id: "init-1", name: "Claims Automation", description: null, owner: null,
          status: "in_progress", objective_ids: ["obj-1"],
          created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "init-2", name: "Fraud Detection", description: null, owner: null,
          status: "planned", objective_ids: [],
          created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 2,
    },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useInitiatives>);
  mockedStrategyApi.useObjectiveInitiatives.mockReturnValue({
    data: {
      items: [
        {
          id: "init-1", name: "Claims Automation", description: null, owner: null,
          status: "in_progress", objective_ids: ["obj-1"],
          created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
    },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useObjectiveInitiatives>);
  mockedStrategyApi.useLinkObjectiveToInitiative.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveToInitiative>);
  mockedStrategyApi.useUnlinkObjectiveFromInitiative.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveFromInitiative>);
});

describe("ObjectiveInitiativeLinkEditor", () => {
  it("lists currently-linked initiatives with a Remove action", () => {
    render(<ObjectiveInitiativeLinkEditor objectiveId="obj-1" />);

    expect(screen.getByText("Claims Automation")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
    expect(screen.queryAllByText("Fraud Detection")).toHaveLength(1); // dropdown only
  });

  it("calls the link hook with the selected initiative id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveToInitiative.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveToInitiative>);

    const user = userEvent.setup();
    render(<ObjectiveInitiativeLinkEditor objectiveId="obj-1" />);

    await user.selectOptions(screen.getByRole("combobox"), "init-2");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith("init-2", expect.anything());
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkObjectiveFromInitiative.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveFromInitiative>);

    const user = userEvent.setup();
    render(<ObjectiveInitiativeLinkEditor objectiveId="obj-1" />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith("init-1", expect.anything());
  });

  it("renders linked initiative names as plain text when no navigation handler is supplied", () => {
    render(<ObjectiveInitiativeLinkEditor objectiveId="obj-1" />);

    const name = screen.getByText("Claims Automation");
    expect(name.tagName).not.toBe("BUTTON");
  });

  it("lets you jump to a linked initiative when onNavigateToInitiative is supplied (strategy screen navigation, 2026-08-14)", async () => {
    const onNavigateToInitiative = vi.fn();
    const user = userEvent.setup();
    render(
      <ObjectiveInitiativeLinkEditor objectiveId="obj-1" onNavigateToInitiative={onNavigateToInitiative} />,
    );

    await user.click(screen.getByText("Claims Automation"));

    expect(onNavigateToInitiative).toHaveBeenCalledWith("init-1");
  });
});
