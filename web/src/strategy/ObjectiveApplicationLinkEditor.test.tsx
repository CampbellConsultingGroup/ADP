// ADP-d8u.2: mirrors ObjectiveDesignLinkEditor.test.tsx's vi.mock(hooks-module)
// convention exactly.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveApplicationLinkEditor from "./ObjectiveApplicationLinkEditor";
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
  design_ids: [],
  application_ids: ["app-1"],
  control_ids: [],
  status: "proposed",
  status_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useApplicationsForLinking.mockReturnValue({
    data: {
      items: [
        { id: "app-1", name: "Claims CRM" },
        { id: "app-2", name: "Fraud Detection" },
      ],
      total: 2,
    },
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

describe("ObjectiveApplicationLinkEditor", () => {
  it("lists currently-linked applications with a Remove action", () => {
    render(<ObjectiveApplicationLinkEditor objective={OBJECTIVE} />);

    expect(screen.getByText("Claims CRM")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
    expect(screen.queryAllByText("Fraud Detection")).toHaveLength(1);
  });

  it("offers a filtered dropdown excluding already-linked applications", () => {
    render(<ObjectiveApplicationLinkEditor objective={OBJECTIVE} />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.textContent);
    expect(optionLabels).toContain("Fraud Detection");
    expect(optionLabels).not.toContain("Claims CRM");
  });

  it("calls the link hook with the selected application id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveApplication.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveApplication>);

    const user = userEvent.setup();
    render(<ObjectiveApplicationLinkEditor objective={OBJECTIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "app-2");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith("app-2", expect.anything());
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkObjectiveApplication.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveApplication>);

    const user = userEvent.setup();
    render(<ObjectiveApplicationLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith("app-1", expect.anything());
  });

  it("shows a confirmation once linking succeeds (bug found live, 2026-08-14)", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useLinkObjectiveApplication.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveApplication>);

    const user = userEvent.setup();
    render(<ObjectiveApplicationLinkEditor objective={OBJECTIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "app-2");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText(/Linked "Fraud Detection"/)).toBeTruthy();
  });

  it("shows a confirmation once unlinking succeeds", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useUnlinkObjectiveApplication.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveApplication>);

    const user = userEvent.setup();
    render(<ObjectiveApplicationLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(screen.getByText(/Removed "Claims CRM"/)).toBeTruthy();
  });
});
