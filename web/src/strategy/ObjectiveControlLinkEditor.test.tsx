// 925-strategy-compliance-linkage (COMPLY-05); ADP-w7z: pick a framework, then choosing a
// control links it at once (like the Capabilities screen's dropdowns).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveControlLinkEditor from "./ObjectiveControlLinkEditor";
import * as complianceApi from "../api/compliance";
import type { RegulatoryFrameworkDetail } from "../api/compliance";
import * as strategyApi from "../api/strategy";
import type { StrategicObjective } from "../api/strategy";

vi.mock("../api/strategy");
vi.mock("../api/compliance", async (orig) => ({
  ...(await orig<typeof import("../api/compliance")>()),
  useFrameworks: vi.fn(),
  useFramework: vi.fn(),
  useAllControls: vi.fn(),
}));

const mockedStrategyApi = vi.mocked(strategyApi);
const mockedCompliance = vi.mocked(complianceApi);

const ctl = (id: string, code: string, title: string, children: RegulatoryFrameworkDetail["controls"] = []) => ({
  id, framework_id: "fw-1", parent_id: null, code, title, description: null, position: 0,
  created_at: "", updated_at: "", children,
});
const GDPR = {
  id: "fw-1", name: "GDPR", jurisdiction: "EU", authority: "EU", version: "", effective_date: null,
  source_url: null, status: "in_force", created_at: "", updated_at: "",
  controls: [ctl("CTRL-1", "Art. 5", "Principles", [ctl("CTRL-2", "Art. 5(1)(f)", "Integrity and confidentiality")]), ctl("CTRL-3", "Art. 32", "Security of processing")],
} as RegulatoryFrameworkDetail;

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
  mockedCompliance.useFrameworks.mockReturnValue({ data: { items: [GDPR], total: 1 }, isLoading: false } as never);
  mockedCompliance.useFramework.mockImplementation(
    (id: string | null) => ({ data: id === "fw-1" ? GDPR : undefined, isLoading: false }) as never,
  );
  mockedCompliance.useAllControls.mockReturnValue({
    byId: new Map(complianceApi.flattenControls(GDPR).map((c) => [c.id, c])),
    isLoading: false,
  });
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

    expect(screen.getByText("Art. 5 — Principles")).toBeTruthy();
    expect(screen.getByText("GDPR", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
  });

  it("shows 'No controls linked yet' when there are none", () => {
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: [] }} />);

    expect(screen.getByText("No controls linked yet.")).toBeTruthy();
  });

  it("links a control as soon as it is chosen, with no separate Link button (ADP-w7z)", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={OBJECTIVE} />);

    expect(screen.queryByRole("button", { name: "Link" })).toBeNull();
    expect(screen.queryByLabelText("Control")).toBeNull();
    await user.selectOptions(screen.getByLabelText("Framework"), "fw-1");
    const options = Array.from((screen.getByLabelText("Control") as HTMLSelectElement).options).map((o) => o.value);
    expect(options).toEqual(["", "CTRL-2", "CTRL-3"]); // CTRL-1 is already linked; children follow parents
    await user.selectOptions(screen.getByLabelText("Control"), "CTRL-3");

    expect(mutate).toHaveBeenCalledWith("CTRL-3", expect.anything());
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

    await user.selectOptions(screen.getByLabelText("Framework"), "fw-1");
    await user.selectOptions(screen.getByLabelText("Control"), "CTRL-3");

    expect(screen.getByText(/Linked "Art. 32 — Security of processing"/)).toBeTruthy();
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

    expect(screen.getByText(/Removed "Art. 5 — Principles"/)).toBeTruthy();
  });

  it.each([
    [409, "Already linked"],
    [404, "No such control"],
  ])("surfaces a %i as '%s' and resets the dropdown", async (status, text) => {
    const mutate = vi.fn((_id, opts) => opts?.onError?.({ message: "x", status }));
    mockedStrategyApi.useLinkObjectiveControl.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveControl>);

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: [] }} />);

    await user.selectOptions(screen.getByLabelText("Framework"), "fw-1");
    await user.selectOptions(screen.getByLabelText("Control"), "CTRL-3");

    expect(screen.getByText(text)).toBeTruthy();
    expect((screen.getByLabelText("Control") as HTMLSelectElement).value).toBe("");
  });

  it("says when a chosen framework has no controls yet", async () => {
    const empty = { ...GDPR, id: "fw-2", name: "DORA", controls: [] } as RegulatoryFrameworkDetail;
    mockedCompliance.useFrameworks.mockReturnValue({ data: { items: [GDPR, empty], total: 2 }, isLoading: false } as never);
    mockedCompliance.useFramework.mockImplementation(
      (id: string | null) => ({ data: id === "fw-2" ? empty : GDPR, isLoading: false }) as never,
    );

    const user = userEvent.setup();
    render(<ObjectiveControlLinkEditor objective={OBJECTIVE} />);
    await user.selectOptions(screen.getByLabelText("Framework"), "fw-2");

    expect(screen.getByText("This framework has no controls yet.")).toBeTruthy();
  });

  it("falls back to the raw id for a control it cannot find", () => {
    render(<ObjectiveControlLinkEditor objective={{ ...OBJECTIVE, control_ids: ["gone"] }} />);
    expect(screen.getByText("gone")).toBeTruthy();
  });
});
