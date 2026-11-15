// 043-capability-heat-map: mirrors this session's established vi.mock(hooks-module)
// convention (e.g. web/src/insights/ApplicationsHeatMap.test.tsx, 919-insights-dashboard).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CapabilityHeatMap from "./CapabilityHeatMap";
import * as businessApi from "../api/business";
import type { BusinessCapability } from "../api/business";
import * as capAnalysisApi from "../api/capAnalysis";
import type { CapabilityRollup, CapabilityRollupResponse } from "../api/capAnalysis";

vi.mock("../api/business");
vi.mock("../api/capAnalysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/capAnalysis")>()),
  useCapabilityRollup: vi.fn(),
}));

const mockedBusinessApi = vi.mocked(businessApi);
const mockedCapAnalysis = vi.mocked(capAnalysisApi);

const CAPABILITIES: BusinessCapability[] = [
  {
    id: "cap-1", name: "Underwriting", description: null, level: 1, parent_id: null, position: 0,
    created_at: "", updated_at: "", domain_id: null, domain_name: null,
    strategic_relevance: 1, maturity_level: 4,
  },
  {
    id: "cap-2", name: "Risk Assessment", description: null, level: 2, parent_id: "cap-1", position: 0,
    created_at: "", updated_at: "", domain_id: null, domain_name: null,
    strategic_relevance: 2, maturity_level: null,
  },
  {
    id: "cap-3", name: "Rating Engine", description: null, level: 3, parent_id: "cap-2", position: 0,
    created_at: "", updated_at: "", domain_id: null, domain_name: null,
    strategic_relevance: null, maturity_level: 2,
  },
];

function mockCapabilities(items: BusinessCapability[]) {
  mockedBusinessApi.useCapabilities.mockReturnValue({
    data: { items, total: items.length },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof businessApi.useCapabilities>);
}

function spread(entries: Record<string, number>): Record<string, number> {
  return entries;
}

function rollupItem(id: string, name: string, level: number, over: Partial<CapabilityRollup> = {}): CapabilityRollup {
  return {
    capability_id: id,
    name,
    level,
    contributing_apps: [],
    excluded_retired_apps: [],
    health: { worst: null, spread: spread({ no_data: 1 }) },
    risk: { worst: null, spread: spread({ no_data: 1 }) },
    cost: { total_tco: null, apps_without_cost: 0 },
    exposure: { worst: null, spread: spread({ no_data: 1 }) },
    ...over,
  };
}

const ROLLUP: CapabilityRollupResponse = {
  as_of: "2026-11-15",
  risk_available: true,
  cost_available: true,
  items: [
    rollupItem("cap-1", "Underwriting", 1, {
      health: { worst: 2, spread: spread({ "2": 1 }) },
      risk: { worst: "high", spread: spread({ high: 1 }) },
      cost: { total_tco: "1000.00", apps_without_cost: 0 },
      exposure: { worst: "retiring", spread: spread({ retiring: 1 }) },
      contributing_apps: [{ id: "pos", name: "Store POS", via: [{ id: "ac-1", name: "Basket Calculation", level: 3 }] }],
    }),
    rollupItem("cap-2", "Risk Assessment", 2, {
      health: { worst: 2, spread: spread({ "2": 1 }) },
      exposure: { worst: "retiring", spread: spread({ retiring: 1 }) },
    }),
    rollupItem("cap-3", "Rating Engine", 3, {
      health: { worst: 2, spread: spread({ "2": 1 }) },
      risk: { worst: "high", spread: spread({ high: 1 }) },
      cost: { total_tco: "1000.00", apps_without_cost: 0 },
      exposure: { worst: "retiring", spread: spread({ retiring: 1 }) },
      contributing_apps: [{ id: "pos", name: "Store POS", via: [{ id: "ac-1", name: "Basket Calculation", level: 3 }] }],
      excluded_retired_apps: [{ id: "old", name: "Legacy Till" }],
    }),
  ],
};

function mockRollup(data: CapabilityRollupResponse | undefined) {
  mockedCapAnalysis.useCapabilityRollup.mockReturnValue({
    data,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof capAnalysisApi.useCapabilityRollup>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockCapabilities(CAPABILITIES);
  mockRollup(ROLLUP);
});

describe("CapabilityHeatMap (US1 — default maturity coloring)", () => {
  it("renders every capability exactly once", () => {
    render(<CapabilityHeatMap />);

    expect(screen.getByText("Underwriting")).toBeTruthy();
    expect(screen.getByText("Risk Assessment")).toBeTruthy();
    expect(screen.getByText("Rating Engine")).toBeTruthy();
  });

  it("shows a distinct 'Unclassified' label for a capability with no maturity level", () => {
    render(<CapabilityHeatMap />);

    const cell = screen.getByText("Risk Assessment").closest("[title]");
    expect(cell?.getAttribute("title")).toContain("Unclassified");
  });

  it("renders a legend for the current metric", () => {
    render(<CapabilityHeatMap />);

    const legend = screen.getByRole("list", { name: "Legend" });
    expect(within(legend).getByText("Advanced")).toBeTruthy(); // maturity level 4 label
  });

  it("surfaces a capability's full name and exact value via hover title, without navigating", () => {
    render(<CapabilityHeatMap />);

    const cell = screen.getByText("Underwriting").closest("[title]");
    expect(cell?.getAttribute("title")).toContain("Underwriting");
    expect(cell?.getAttribute("title")).toContain("Advanced");
  });

  it("shows an empty-state message when there are zero capabilities", () => {
    mockCapabilities([]);

    render(<CapabilityHeatMap />);

    expect(screen.getByText(/No business capabilities/i)).toBeTruthy();
  });
});

describe("CapabilityHeatMap (US2 — strategic relevance metric)", () => {
  it("recolors and relabels cells when the metric selector switches to strategic relevance", async () => {
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "strategic_relevance");

    // cap-1: strategic_relevance 1 = "Strategic"
    const cap1Cell = screen.getByText("Underwriting").closest("[title]");
    expect(cap1Cell?.getAttribute("title")).toContain("Strategic");
    // cap-3: strategic_relevance null = "Unclassified"
    const cap3Cell = screen.getByText("Rating Engine").closest("[title]");
    expect(cap3Cell?.getAttribute("title")).toContain("Unclassified");
  });

  it("treats unclassified per-metric, not as a fixed property of the capability", async () => {
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);

    // cap-2 is unclassified for maturity (default) but classified (Core) for strategic relevance.
    let cell = screen.getByText("Risk Assessment").closest("[title]");
    expect(cell?.getAttribute("title")).toContain("Unclassified");

    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "strategic_relevance");

    cell = screen.getByText("Risk Assessment").closest("[title]");
    expect(cell?.getAttribute("title")).toContain("Core");
  });
});

describe("CapabilityHeatMap (US3 — drill-through)", () => {
  it("invokes onDrillThrough with the clicked capability's id", async () => {
    const onDrillThrough = vi.fn();
    const user = userEvent.setup();
    render(<CapabilityHeatMap onDrillThrough={onDrillThrough} />);

    await user.click(screen.getByText("Rating Engine"));

    expect(onDrillThrough).toHaveBeenCalledWith("cap-3");
  });
});

describe("CapabilityHeatMap (938 — capability model roll-ups)", () => {
  const titleOf = (name: string) => screen.getByText(name).closest("[title]")?.getAttribute("title") ?? "";

  it("does not request the roll-up until a roll-up metric is chosen, then keeps it", async () => {
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);
    expect(mockedCapAnalysis.useCapabilityRollup).toHaveBeenLastCalledWith(false);

    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "health");
    expect(mockedCapAnalysis.useCapabilityRollup).toHaveBeenLastCalledWith(true);

    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "maturity_level");
    expect(mockedCapAnalysis.useCapabilityRollup).toHaveBeenLastCalledWith(true);
  });

  it("colours by application health with the worst value, spread and contributing apps", async () => {
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "health");

    expect(titleOf("Underwriting")).toContain("Health 2");
    expect(titleOf("Underwriting")).toContain("1 leaf at health 2");
    expect(titleOf("Rating Engine")).toContain("Store POS (via Basket Calculation)");
    expect(titleOf("Rating Engine")).toContain("Excluded (retired): Legacy Till");
    expect(within(screen.getByRole("list", { name: "Legend" })).getByText("No data")).toBeTruthy();
  });

  it("shows the cell detail when a cell is focused", async () => {
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "health");
    (screen.getByText("Rating Engine").closest("[data-heatmap-cell]") as HTMLElement).focus();

    const detail = await screen.findByLabelText("Cell detail");
    expect(within(detail).getByText(/Store POS/)).toBeTruthy();
    expect(within(detail).getByText(/Legacy Till/)).toBeTruthy();
  });

  it("shows risk bands, cost totals and technology exposure", async () => {
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);
    const select = screen.getByRole("combobox", { name: "Color by" });

    await user.selectOptions(select, "risk");
    expect(titleOf("Rating Engine")).toContain("High risk");

    await user.selectOptions(select, "cost");
    expect(titleOf("Rating Engine")).toMatch(/\$1,000/);
    expect(screen.getByText(/not allocated across capabilities/)).toBeTruthy();

    await user.selectOptions(select, "exposure");
    expect(titleOf("Risk Assessment")).toContain("Retiring");
  });

  it("shows no-data cells distinctly", async () => {
    mockRollup({ ...ROLLUP, items: [rollupItem("cap-3", "Rating Engine", 3)] });
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "health");
    expect(titleOf("Rating Engine")).toContain("No data");
  });

  it("marks cost and risk as not available to callers without access, with no figures", async () => {
    mockRollup({
      ...ROLLUP,
      risk_available: false,
      cost_available: false,
      items: ROLLUP.items.map((i) => ({ ...i, risk: null, cost: null })),
    });
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "health");

    const cost = screen.getByRole("option", { name: /Application cost/ }) as HTMLOptionElement;
    const risk = screen.getByRole("option", { name: /Application risk/ }) as HTMLOptionElement;
    expect(cost.disabled).toBe(true);
    expect(cost.textContent).toContain("not available to you");
    expect(risk.disabled).toBe(true);
    expect(screen.queryByText(/\$1,000/)).toBeNull();
  });
});

describe("CapabilityHeatMap (938 — spread wording)", () => {
  it("counts leaves on parents and apps on Level 3s", async () => {
    mockRollup({
      ...ROLLUP,
      items: [
        rollupItem("cap-1", "Underwriting", 1, { health: { worst: 2, spread: { "2": 4, no_data: 1 } } }),
        rollupItem("cap-3", "Rating Engine", 3, { health: { worst: 2, spread: { "2": 1, "4": 2, no_data: 0 } } }),
      ],
    });
    const user = userEvent.setup();
    render(<CapabilityHeatMap />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Color by" }), "health");
    const title = (n: string) => screen.getByText(n).closest("[title]")?.getAttribute("title") ?? "";
    expect(title("Underwriting")).toContain("4 leaves at health 2 · 1 leaf no data");
    expect(title("Rating Engine")).toContain("1 app at health 2 · 2 apps at health 4");
  });
});
