// ADP-d8u.1 (T024, extended in T031 with edit/delete cases).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveDetail from "./ObjectiveDetail";
import * as strategyApi from "../api/strategy";
import * as businessApi from "../api/business";
import type { StrategicObjective } from "../api/strategy";

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
