// ADP-d8u.1 (T023): same shape as ObjectiveCapabilityLinkEditor.test.tsx,
// substituting value streams.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveValueStreamLinkEditor from "./ObjectiveValueStreamLinkEditor";
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
  owner: "Owner",
  statement: "Statement",
  metric_name: null,
  target_value: null,
  target_unit: null,
  direction: null,
  fiscal_year: 2026,
  period: "Q1",
  capability_ids: [],
  value_stream_ids: ["vs-1"],
  design_ids: [],
  application_ids: [],
  status: "proposed",
  status_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedBusinessApi.useValueStreams.mockReturnValue({
    data: {
      items: [
        { id: "vs-1", name: "Claim to Payout" },
        { id: "vs-2", name: "Quote to Bind" },
      ],
      total: 2,
    },
    isLoading: false,
  } as unknown as ReturnType<typeof businessApi.useValueStreams>);
  mockedStrategyApi.useLinkObjectiveValueStream.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveValueStream>);
  mockedStrategyApi.useUnlinkObjectiveValueStream.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveValueStream>);
});

describe("ObjectiveValueStreamLinkEditor", () => {
  it("lists currently-linked value streams with a Remove action", () => {
    render(<ObjectiveValueStreamLinkEditor objective={OBJECTIVE} />);

    expect(screen.getByText("Claim to Payout")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
  });

  it("offers a filtered dropdown excluding already-linked value streams", () => {
    render(<ObjectiveValueStreamLinkEditor objective={OBJECTIVE} />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.textContent);
    expect(optionLabels).toContain("Quote to Bind");
    expect(optionLabels).not.toContain("Claim to Payout");
  });

  it("calls the link hook with the selected value stream id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveValueStream.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveValueStream>);

    const user = userEvent.setup();
    render(<ObjectiveValueStreamLinkEditor objective={OBJECTIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "vs-2");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith("vs-2", expect.anything());
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkObjectiveValueStream.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveValueStream>);

    const user = userEvent.setup();
    render(<ObjectiveValueStreamLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith("vs-1", expect.anything());
  });

  it("shows a confirmation once linking succeeds (bug found live, 2026-08-14)", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useLinkObjectiveValueStream.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveValueStream>);

    const user = userEvent.setup();
    render(<ObjectiveValueStreamLinkEditor objective={OBJECTIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "vs-2");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText(/Linked "Quote to Bind"/)).toBeTruthy();
  });

  it("shows a confirmation once unlinking succeeds", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useUnlinkObjectiveValueStream.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveValueStream>);

    const user = userEvent.setup();
    render(<ObjectiveValueStreamLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(screen.getByText(/Removed "Claim to Payout"/)).toBeTruthy();
  });
});
