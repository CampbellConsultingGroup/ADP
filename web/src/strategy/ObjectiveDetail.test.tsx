// ADP-d8u.1 (T024, extended in T031 with edit/delete cases).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveDetail from "./ObjectiveDetail";
import * as strategyApi from "../api/strategy";
import * as businessApi from "../api/business";
import type { StrategicObjective } from "../api/strategy";
import { ApiError } from "../api/client";

vi.mock("../api/strategy");
vi.mock("../api/business");

const mockedStrategyApi = vi.mocked(strategyApi);
const mockedBusinessApi = vi.mocked(businessApi);

const OBJECTIVE: StrategicObjective = {
  id: "obj-1",
  theme_id: "t1",
  owner: "Claims Platform Team",
  statement: "Reduce claims cycle time",
  metric_name: "Claims cycle time",
  target_value: 40,
  target_unit: "%",
  direction: "decrease",
  fiscal_year: 2026,
  period: "Q3",
  capability_ids: [],
  value_stream_ids: [],
  design_ids: [],
  application_ids: [],
  status: "proposed",
  status_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useObjective.mockReturnValue({
    data: OBJECTIVE,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useObjective>);
  mockedStrategyApi.useThemes.mockReturnValue({
    data: { items: [{ id: "t1", name: "Growth", description: null, owner: null, priority: null, created_at: "2026-01-01T00:00:00Z" }], total: 1 },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useThemes>);
  mockedStrategyApi.useUpdateObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof strategyApi.useUpdateObjective>);
  mockedStrategyApi.useDeleteObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useDeleteObjective>);
  mockedStrategyApi.useObjectiveProgress.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useObjectiveProgress>);
  mockedStrategyApi.useCreateProgress.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useCreateProgress>);
  mockedStrategyApi.useUpdateProgress.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useUpdateProgress>);
  mockedStrategyApi.useAbandonObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useAbandonObjective>);
  mockedStrategyApi.useLinkObjectiveCapability.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveCapability>);
  mockedStrategyApi.useUnlinkObjectiveCapability.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveCapability>);
  mockedStrategyApi.useLinkObjectiveValueStream.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveValueStream>);
  mockedStrategyApi.useUnlinkObjectiveValueStream.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveValueStream>);
  mockedBusinessApi.useCapabilities.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof businessApi.useCapabilities>);
  mockedBusinessApi.useValueStreams.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof businessApi.useValueStreams>);
  mockedStrategyApi.useInitiatives.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useInitiatives>);
  mockedStrategyApi.useObjectiveInitiatives.mockReturnValue({
    data: { items: [], total: 0 },
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
  mockedStrategyApi.useObjectives.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useObjectives>);
  mockedStrategyApi.useObjectiveDependencies.mockReturnValue({
    data: { depends_on: [], blocks: [] },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useObjectiveDependencies>);
  mockedStrategyApi.useAddObjectiveDependency.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useAddObjectiveDependency>);
  mockedStrategyApi.useRemoveObjectiveDependency.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useRemoveObjectiveDependency>);
  mockedStrategyApi.useDesignsForLinking.mockReturnValue({
    data: { designs: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useDesignsForLinking>);
  mockedStrategyApi.useLinkObjectiveDesign.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveDesign>);
  mockedStrategyApi.useUnlinkObjectiveDesign.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveDesign>);
  mockedStrategyApi.useApplicationsForLinking.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useApplicationsForLinking>);
  mockedStrategyApi.useLinkObjectiveApplication.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveApplication>);
  mockedStrategyApi.useUnlinkObjectiveApplication.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveApplication>);
});

describe("ObjectiveDetail: status badge and progress history (ADP-d8u.5, T018)", () => {
  it("shows the status badge label for the objective's computed status", () => {
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);
    expect(screen.getByText("Not yet started")).toBeTruthy(); // OBJECTIVE.status === "proposed"
  });

  it("shows the abandoned reason when status is abandoned", () => {
    mockedStrategyApi.useObjective.mockReturnValue({
      data: { ...OBJECTIVE, status: "abandoned", status_reason: "Superseded" },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useObjective>);

    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    expect(screen.getByText("Abandoned")).toBeTruthy();
    expect(screen.getByText(/Superseded/)).toBeTruthy();
  });

  it("renders the recorded progress history", () => {
    mockedStrategyApi.useObjectiveProgress.mockReturnValue({
      data: {
        items: [
          { objective_id: "obj-1", as_of_date: "2026-08-01", actual_value: 40, note: "start", recorded_by: "jane", created_at: "" },
        ],
        total: 1,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectiveProgress>);

    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    expect(screen.getByText("2026-08-01")).toBeTruthy();
    expect(screen.getByText("40")).toBeTruthy();
    expect(screen.getByText("— start")).toBeTruthy();
  });
});

describe("ObjectiveDetail: read-only display", () => {
  it("renders the objective's core fields and both link editors", () => {
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    expect(screen.getByText("Reduce claims cycle time")).toBeTruthy();
    expect(screen.getByText(/Claims Platform Team/)).toBeTruthy();
    expect(screen.getByText(/Claims cycle time/)).toBeTruthy();
    expect(screen.getByText("No capabilities linked yet.")).toBeTruthy();
    expect(screen.getByText("No value streams linked yet.")).toBeTruthy();
  });

  it("labels the core fields clearly, distinct from the linked-entity sections (bug found live, 2026-08-14)", () => {
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    expect(screen.getByText("Owner")).toBeTruthy();
    expect(screen.getByText("Fiscal Period")).toBeTruthy();
    expect(screen.getByText("Target")).toBeTruthy();
    expect(screen.getByText(/Q3 2026/)).toBeTruthy();
  });
});

describe("ObjectiveDetail: cross-navigation (strategy screen navigation, 2026-08-14)", () => {
  it("shows the objective's own theme name, and lets you jump to it", async () => {
    const onNavigateToTheme = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} onNavigateToTheme={onNavigateToTheme} />);

    expect(screen.getByText("Theme")).toBeTruthy();
    const themeLink = screen.getByText("Growth");
    await user.click(themeLink);

    expect(onNavigateToTheme).toHaveBeenCalledWith("t1");
  });

  it("renders the theme name as plain text when no navigation handler is supplied", () => {
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    const themeText = screen.getByText("Growth");
    expect(themeText.tagName).not.toBe("BUTTON");
  });

  it("lets you jump to a linked initiative", async () => {
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

    const onNavigateToInitiative = vi.fn();
    const user = userEvent.setup();
    render(
      <ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} onNavigateToInitiative={onNavigateToInitiative} />,
    );

    await user.click(screen.getByText("Claims Automation"));

    expect(onNavigateToInitiative).toHaveBeenCalledWith("init-1");
  });
});

describe("ObjectiveDetail: edit (T031)", () => {
  it("supports editing a field and persisting it", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUpdateObjective.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useUpdateObjective>);

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.click(screen.getByText("Edit"));
    const ownerInput = screen.getByLabelText("Owner *") as HTMLInputElement;
    await user.clear(ownerInput);
    await user.type(ownerInput, "New Owner");
    await user.click(screen.getByText("Save"));

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ owner: "New Owner" }),
      expect.anything(),
    );
  });

  it("rejects saving when only some metric fields are filled in (bug found live, 2026-08-14)", async () => {
    // OBJECTIVE's fixture has all four metric fields set -- clearing just one
    // (metric name) reproduces the same partial-metric-group bug ObjectiveForm
    // had, since ObjectiveDetail's edit form duplicated the same flawed check.
    const mutate = vi.fn();
    mockedStrategyApi.useUpdateObjective.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useUpdateObjective>);

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.click(screen.getByText("Edit"));
    await user.clear(screen.getByLabelText("Metric name"));
    await user.click(screen.getByText("Save"));

    expect(mutate).not.toHaveBeenCalled();
    expect(screen.getByText(/must all be filled in together, or all left blank/i)).toBeTruthy();
  });
});

describe("ObjectiveDetail: delete (T031)", () => {
  it("supports deleting the objective", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useDeleteObjective.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useDeleteObjective>);
    vi.stubGlobal("confirm", vi.fn(() => true));

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.click(screen.getByText("Delete"));

    expect(mutate).toHaveBeenCalledWith("obj-1", expect.anything());
    vi.unstubAllGlobals();
  });
});

describe("ObjectiveDetail: abandon (ADP-d8u.5 US2, T026)", () => {
  it("prompts for a reason and calls useAbandonObjective's mutate with it", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useAbandonObjective.mockReturnValue({
      mutate,
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useAbandonObjective>);
    vi.stubGlobal("prompt", vi.fn(() => "Superseded by a broader objective"));

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.click(screen.getByText("Abandon"));

    expect(mutate).toHaveBeenCalledWith({
      status_reason: "Superseded by a broader objective",
    });
    vi.unstubAllGlobals();
  });

  it("does not call mutate when the reason prompt is cancelled", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useAbandonObjective.mockReturnValue({
      mutate,
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useAbandonObjective>);
    vi.stubGlobal("prompt", vi.fn(() => null));

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.click(screen.getByText("Abandon"));

    expect(mutate).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("does not show the Abandon action once the objective is already abandoned", () => {
    mockedStrategyApi.useObjective.mockReturnValue({
      data: { ...OBJECTIVE, status: "abandoned", status_reason: "Cancelled" },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof strategyApi.useObjective>);

    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    expect(screen.queryByText("Abandon")).toBeNull();
  });
});

describe("ObjectiveDetail: linked initiatives panel (ADP-d8u.6, T018)", () => {
  it("shows linked initiatives and supports linking a new one", async () => {
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
    const linkMutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveToInitiative.mockReturnValue({
      mutate: linkMutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveToInitiative>);

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    expect(screen.getByText("Claims Automation")).toBeTruthy();

    const select = screen.getByDisplayValue("— select initiative —");
    await user.selectOptions(select, "init-2");
    await user.click(within(select.parentElement as HTMLElement).getByText("Link"));

    expect(linkMutate).toHaveBeenCalledWith("init-2", expect.anything());
  });

  it("supports unlinking an initiative", async () => {
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
    const unlinkMutate = vi.fn();
    mockedStrategyApi.useUnlinkObjectiveFromInitiative.mockReturnValue({
      mutate: unlinkMutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveFromInitiative>);

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.click(screen.getByText("Remove"));

    expect(unlinkMutate).toHaveBeenCalledWith("init-1", expect.anything());
  });

  it("shows a confirmation once linking an initiative succeeds (bug found live, 2026-08-14)", async () => {
    mockedStrategyApi.useObjectiveInitiatives.mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectiveInitiatives>);
    mockedStrategyApi.useInitiatives.mockReturnValue({
      data: {
        items: [
          {
            id: "init-2", name: "Fraud Detection", description: null, owner: null,
            status: "planned", objective_ids: [],
            created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
          },
        ],
        total: 1,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useInitiatives>);
    const linkMutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useLinkObjectiveToInitiative.mockReturnValue({
      mutate: linkMutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveToInitiative>);

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    const select = screen.getByDisplayValue("— select initiative —");
    await user.selectOptions(select, "init-2");
    await user.click(within(select.parentElement as HTMLElement).getByText("Link"));

    expect(screen.getByText(/Linked "Fraud Detection"/)).toBeTruthy();
  });
});

describe("ObjectiveDetail: dependencies panel (ADP-d8u.6, T027)", () => {
  it("shows both depends-on and blocks directions", () => {
    mockedStrategyApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-2", theme_id: "t1", owner: "A", statement: "Launch new product line", fiscal_year: 2026, period: "Q1", status: "active", updated_at: "" },
          { id: "obj-3", theme_id: "t1", owner: "A", statement: "Expand into new market", fiscal_year: 2026, period: "Q1", status: "active", updated_at: "" },
        ],
        total: 2,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);
    mockedStrategyApi.useObjectiveDependencies.mockReturnValue({
      data: { depends_on: ["obj-2"], blocks: ["obj-3"] },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectiveDependencies>);

    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    // "Launch new product line" (obj-2) is the depends-on entry -- excluded
    // from the add-dependency select, so it appears exactly once.
    expect(screen.getByText("Launch new product line")).toBeTruthy();
    // "Expand into new market" (obj-3) is the blocks entry, and also still
    // an eligible option in the add-dependency select -- appears twice.
    expect(screen.getAllByText("Expand into new market").length).toBeGreaterThan(0);
  });

  it("surfaces the server's cycle-rejection message on a 400 response", async () => {
    mockedStrategyApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-2", theme_id: "t1", owner: "A", statement: "Launch new product line", fiscal_year: 2026, period: "Q1", status: "active", updated_at: "" },
        ],
        total: 1,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);
    const addMutate = vi.fn((_id, opts) => {
      opts.onError(
        new ApiError(400, "POST failed: 400", {
          detail: "Objective 'obj-1' cannot depend on 'obj-2' -- this would create a cycle",
        }),
      );
    });
    mockedStrategyApi.useAddObjectiveDependency.mockReturnValue({
      mutate: addMutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useAddObjectiveDependency>);

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.selectOptions(screen.getByDisplayValue("— select objective —"), "obj-2");
    await user.click(screen.getByText("Add dependency"));

    expect(screen.getByText(/would create a cycle/)).toBeTruthy();
  });

  it("supports removing a dependency", async () => {
    mockedStrategyApi.useObjectives.mockReturnValue({
      data: {
        items: [
          { id: "obj-2", theme_id: "t1", owner: "A", statement: "Launch new product line", fiscal_year: 2026, period: "Q1", status: "active", updated_at: "" },
        ],
        total: 1,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectives>);
    mockedStrategyApi.useObjectiveDependencies.mockReturnValue({
      data: { depends_on: ["obj-2"], blocks: [] },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useObjectiveDependencies>);
    const removeMutate = vi.fn();
    mockedStrategyApi.useRemoveObjectiveDependency.mockReturnValue({
      mutate: removeMutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useRemoveObjectiveDependency>);

    const user = userEvent.setup();
    render(<ObjectiveDetail objectiveId="obj-1" onBack={vi.fn()} />);

    await user.click(screen.getByText("Remove"));

    expect(removeMutate).toHaveBeenCalledWith("obj-2");
  });
});
