// 925-strategy-compliance-linkage (COMPLY-05). Mirrors ObjectiveDesignLinkEditor.test.tsx's
// vi.mock(hooks-module) convention, adapted for the plain control-id text input (no flat
// "list all Controls" hook exists to populate a dropdown from).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveControlLinkEditor from "./ObjectiveControlLinkEditor";
import * as strategyApi from "../api/strategy";
import type { StrategicObjective } from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

const OBJECTIVE: StrategicObjective = {
  id: "obj-1",
  theme_id: "t1",
  owner: "Owner",
  statement: "GDPR Art. 32 readiness",
  metric_name: null,
  target_value: null,
  target_unit: null,
  direction: null,
  fiscal_year: 2026,
  period: "Q1",
  capability_ids: [],
  value_stream_ids: [],
  design_ids: [],
  application_ids: [],
  control_ids: ["CTRL-1"],
  status: "proposed",
  status_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useLinkObjectiveControl.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveControl>);
  mockedStrategyApi.useUnlinkObjectiveControl.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveControl>);
});

describe("ObjectiveControlLinkEditor", () => {
  it("lists currently-linked controls with a Remove action", () => {
    render(<ObjectiveControlLinkEditor objective={OBJECTIVE} />);

    expect(screen.getByText("CTRL-1")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
  });

  it("shows 'No controls linked yet' when there are none", () => {
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: [] }} />);

    expect(screen.getByText("No controls linked yet.")).toBeTruthy();
  });

  it("calls the link hook with the entered control id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "CTRL-2");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith("CTRL-2", expect.anything());
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith("CTRL-1", expect.anything());
  });

  it("shows a confirmation once linking succeeds", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useLinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "CTRL-2");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText(/Linked "CTRL-2"/)).toBeTruthy();
  });

  it("shows a confirmation once unlinking succeeds", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useUnlinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(screen.getByText(/Removed "CTRL-1"/)).toBeTruthy();
  });

  it("surfaces a 409 as 'Already linked'", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onError?.({ message: "conflict", status: 409 }));
    mockedStrategyApi.useLinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "CTRL-1");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText("Already linked")).toBeTruthy();
  });

  it("surfaces a 404 as 'No such control'", async () => {
    const mutate = vi.fn((_id, opts) => opts?.onError?.({ message: "not found", status: 404 }));
    mockedStrategyApi.useLinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "does-not-exist");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText("No such control")).toBeTruthy();
  });
});
