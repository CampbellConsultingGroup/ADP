// ADP-d8u.2: mirrors ObjectiveCapabilityLinkEditor.test.tsx's
// vi.mock(hooks-module) convention exactly.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveDesignLinkEditor from "./ObjectiveDesignLinkEditor";
import * as strategyApi from "../api/strategy";
import type { StrategicObjective } from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

const OBJECTIVE: StrategicObjective = {
  id: "obj-1",
  theme_id: "t1",
  owner: "Owner",
  statement: "Statement",
  metric_name: null,
  target_value: null,
  target_unit: null,
  direction: null,
  fiscal_year: 2026,
  period: "Q1",
  capability_ids: [],
  value_stream_ids: [],
  design_ids: ["DSN-001"],
  application_ids: [],
  control_ids: [],
  status: "proposed",
  status_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useDesignsForLinking.mockReturnValue({
    data: {
      designs: [
        { id: "DSN-001", title: "Payments Platform" },
        { id: "DSN-002", title: "Claims Portal" },
      ],
      total: 2,
    },
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
});

describe("ObjectiveDesignLinkEditor", () => {
  it("lists currently-linked designs with a Remove action", () => {
    render(<ObjectiveDesignLinkEditor objective={OBJECTIVE} />);

    expect(screen.getByText("Payments Platform")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
    expect(screen.queryAllByText("Claims Portal")).toHaveLength(1);
  });

  it("offers a filtered dropdown excluding already-linked designs", () => {
    render(<ObjectiveDesignLinkEditor objective={OBJECTIVE} />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.textContent);
    expect(optionLabels).toContain("Claims Portal");
    expect(optionLabels).not.toContain("Payments Platform");
  });

  it("calls the link hook with the selected design id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveDesign.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveDesign>);

    const user = userEvent.setup();
    render(<ObjectiveDesignLinkEditor objective={OBJECTIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "DSN-002");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith("DSN-002", expect.anything());
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkObjectiveDesign.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveDesign>);

    const user = userEvent.setup();
    render(<ObjectiveDesignLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith("DSN-001", expect.anything());
  });

  it("shows a confirmation once linking succeeds (bug found live, 2026-08-14)", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useLinkObjectiveDesign.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveDesign>);

    const user = userEvent.setup();
    render(<ObjectiveDesignLinkEditor objective={OBJECTIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "DSN-002");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText(/Linked "Claims Portal"/)).toBeTruthy();
  });

  it("shows a confirmation once unlinking succeeds", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useUnlinkObjectiveDesign.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveDesign>);

    const user = userEvent.setup();
    render(<ObjectiveDesignLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(screen.getByText(/Removed "Payments Platform"/)).toBeTruthy();
  });
});
