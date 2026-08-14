// 043-capability-heat-map: mirrors this session's established vi.mock(hooks-module)
// convention (e.g. web/src/insights/ApplicationsHeatMap.test.tsx, 919-insights-dashboard).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CapabilityHeatMap from "./CapabilityHeatMap";
import * as businessApi from "../api/business";
import type { BusinessCapability } from "../api/business";

vi.mock("../api/business");

const mockedBusinessApi = vi.mocked(businessApi);

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

beforeEach(() => {
  vi.clearAllMocks();
  mockCapabilities(CAPABILITIES);
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
