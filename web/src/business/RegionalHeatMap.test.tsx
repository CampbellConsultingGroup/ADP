// 942-regional-assessments US3: the regional heat map.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { Geography, RegionalHeatmap } from "../api/organization";
import RegionalHeatMap from "./RegionalHeatMap";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useRegionalHeatmap: vi.fn(),
  useGeographies: vi.fn(),
  useSetRegionalAssessment: vi.fn(),
  useRemoveRegionalAssessment: vi.fn(),
}));

const api = vi.mocked(orgApi);
const col = (id: string, name: string, level = 2, code: string | null = null) => ({ id, name, level, code });
const geo = (id: string, name: string, kind: Geography["kind"], code: string | null = null): Geography => ({
  id, name, code, m49: null, parent_id: null, level: kind === "global" ? 1 : kind === "region" ? 2 : 3, kind, path: [], org_unit_count: 0,
});

const HEATMAP: RegionalHeatmap = {
  columns: [col("am", "Americas"), col("eu", "Europe")],
  max_columns: 12,
  rows: [
    {
      capability: { id: "accept", name: "Accept Payment", level: 3, parent_id: "pay" },
      baseline: 3,
      region_specific: false,
      scope_needs_update: false,
      cells: [
        { geography_id: "am", state: "assessed", maturity_level: 2, note: "Pix handled locally", delta: -1 },
        { geography_id: "eu", state: "assessed", maturity_level: 5, note: null, delta: 2 },
      ],
    },
    {
      capability: { id: "esocial", name: "eSocial Reporting", level: 3, parent_id: "hr" },
      baseline: null,
      region_specific: true,
      scope_needs_update: true,
      cells: [
        { geography_id: "am", state: "not_assessed", maturity_level: null, note: null, delta: null },
        { geography_id: "eu", state: "not_applicable", maturity_level: null, note: null, delta: null },
      ],
    },
  ],
};

let save: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  save = vi.fn().mockResolvedValue({});
  api.useRegionalHeatmap.mockReturnValue({ data: HEATMAP, isLoading: false, error: null } as never);
  api.useGeographies.mockReturnValue({
    data: { items: [geo("g", "Global", "global"), geo("am", "Americas", "region"), geo("eu", "Europe", "region"), geo("br", "Brazil", "country", "BR")], total: 4 },
  } as never);
  api.useSetRegionalAssessment.mockReturnValue({ mutateAsync: save, isPending: false } as never);
  api.useRemoveRegionalAssessment.mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as never);
});

function rowOf(name: string): HTMLElement {
  return screen.getByRole("button", { name }).closest("tr") as HTMLElement;
}

describe("RegionalHeatMap", () => {
  it("shows the baseline column plus the region columns", () => {
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite />);
    const headers = within(screen.getByRole("table")).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["Capability", "Baseline", "Americas", "Europe"]);
    expect(within(rowOf("Accept Payment")).getByText("3 Established")).toBeTruthy();
  });

  it("shows scores with the label and ▲/▼ against the baseline, and the note in the title", () => {
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite />);
    const row = rowOf("Accept Payment");
    expect(within(row).getByLabelText("below baseline by 1")).toBeTruthy();
    expect(within(row).getByLabelText("above baseline by 2")).toBeTruthy();
    const am = within(row).getByRole("button", { name: /in Americas/ }).closest("td") as HTMLElement;
    expect(am.getAttribute("title")).toBe("2 · Emerging\nPix handled locally");
  });

  it("distinguishes not assessed, not applicable and scope needing an update", () => {
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite />);
    const row = rowOf("eSocial Reporting");
    expect(within(row).getAllByText("Not assessed")).toHaveLength(2); // baseline + Americas
    expect(within(row).getByText("Not applicable")).toBeTruthy();
    expect(within(row).getByText("region-specific")).toBeTruthy();
    expect(within(row).getByText("scope needs updating")).toBeTruthy();
    // A not-applicable cell can't be edited.
    expect(within(row).queryByRole("button", { name: /in Europe/ })).toBeNull();
  });

  it("styles cells with border longhands only, so a state change can't mis-style them", () => {
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite />);
    for (const td of Array.from(document.querySelectorAll("td"))) {
      expect(td.style.borderStyle === "solid" || td.style.borderStyle === "dashed").toBe(true);
      expect(td.getAttribute("style") ?? "").not.toMatch(/(^|;)\s*border:/);
    }
    const unassessed = within(rowOf("eSocial Reporting")).getAllByText("Not assessed")[1].closest("td") as HTMLElement;
    expect(unassessed.style.borderStyle).toBe("dashed");
  });

  it("adds and removes columns, and resets to regions", async () => {
    const change = vi.fn();
    render(<RegionalHeatMap columns={null} onColumnsChange={change} canWrite />);
    const add = screen.getByLabelText("Add column") as HTMLSelectElement;
    expect(Array.from(add.options).map((o) => o.textContent)).toEqual(["Add a region or country…", "Brazil (BR)"]);
    await userEvent.selectOptions(add, "br");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(change).toHaveBeenCalledWith(["am", "eu", "br"]);
    await userEvent.click(screen.getByRole("button", { name: "Remove column Europe" }));
    expect(change).toHaveBeenLastCalledWith(["am"]);
    await userEvent.click(screen.getByRole("button", { name: "Reset to regions" }));
    expect(change).toHaveBeenLastCalledWith(null);
  });

  it("disables adding at the column limit", () => {
    api.useRegionalHeatmap.mockReturnValue({ data: { ...HEATMAP, max_columns: 2 }, isLoading: false, error: null } as never);
    render(<RegionalHeatMap columns={["am", "eu"]} onColumnsChange={vi.fn()} canWrite />);
    expect((screen.getByLabelText("Add column") as HTMLSelectElement).disabled).toBe(true);
    expect(screen.getByText("At most 2 columns")).toBeTruthy();
  });

  it("lets writers record an assessment from a cell", async () => {
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite />);
    await userEvent.click(within(rowOf("eSocial Reporting")).getByRole("button", { name: /in Americas/ }));
    const form = screen.getByRole("form", { name: "Assess eSocial Reporting in Americas" });
    await userEvent.selectOptions(within(form).getByLabelText("Regional maturity"), "2");
    await userEvent.type(within(form).getByLabelText("Regional variant note"), "Manual filing");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(save).toHaveBeenCalledWith({ capabilityId: "esocial", geographyId: "am", maturity_level: 2, note: "Manual filing" });
  });

  it("is read-only for readers", () => {
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite={false} />);
    expect(screen.queryByRole("button", { name: /in Americas/ })).toBeNull();
    expect(screen.getAllByText(/Emerging/).length).toBeGreaterThan(0);
  });

  it("opens a capability from its row name", async () => {
    const open = vi.fn();
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite onOpenCapability={open} />);
    await userEvent.click(screen.getByRole("button", { name: "Accept Payment" }));
    expect(open).toHaveBeenCalledWith("accept");
  });

  it("shows loading and error states", () => {
    api.useRegionalHeatmap.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    const { unmount } = render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite />);
    expect(screen.getByText(/Loading regional heat map/)).toBeTruthy();
    unmount();
    api.useRegionalHeatmap.mockReturnValue({ data: undefined, isLoading: false, error: new Error("x") } as never);
    render(<RegionalHeatMap columns={null} onColumnsChange={vi.fn()} canWrite />);
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
