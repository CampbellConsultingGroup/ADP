// 920-capability-diagram-select: first render-based test for CapabilityNode.tsx
// (previously only exercised indirectly via CapabilityTree.test.tsx). Needs a
// real QueryClientProvider since this component calls useQueryClient()
// directly, mirroring CapabilityTree.test.tsx's own renderWithQueryClient()
// helper.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CapabilityNode from "./CapabilityNode";
import * as businessApi from "../api/business";
import * as complianceApi from "../api/compliance";
import * as capAnalysisApi from "../api/capAnalysis";
import type { CapabilityTreeNode } from "./CapabilityTree";
import * as agenticApi from "../api/agentic";
import { renderWithQuery as renderWithQueryClient } from "../../tests/support/apiTestUtils";

// ADP-blp.59: opening Details shows the Links section first; its editor has its own tests.
vi.mock("./DesignLinkEditor", () => ({ default: () => <div>design-links-editor</div> }));
vi.mock("../api/business");
vi.mock("../api/compliance");
vi.mock("../api/agentic");
vi.mock("../api/capAnalysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/capAnalysis")>()),
  useBusinessTechnology: vi.fn(),
}));

const mockedBusinessApi = vi.mocked(businessApi);
const mockedComplianceApi = vi.mocked(complianceApi);

const CAPABILITY: CapabilityTreeNode = {
  id: "cap-1",
  name: "Risk Assessment",
  description: null,
  level: 1,
  parent_id: null,
  position: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  domain_id: null,
  domain_name: null,
  strategic_relevance: null,
  maturity_level: null,
  children: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedBusinessApi.useUpdateCapability.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof businessApi.useUpdateCapability>);
  mockedBusinessApi.useDeleteCapability.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof businessApi.useDeleteCapability>);
});

describe("CapabilityNode (920-capability-diagram-select US1)", () => {
  it("renders a checkbox reflecting the selected prop", () => {
    renderWithQueryClient(
      <CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={vi.fn()}>
        {null}
      </CapabilityNode>,
    );

    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
  });

  it("reflects selected=true as a checked checkbox", () => {
    renderWithQueryClient(
      <CapabilityNode capability={CAPABILITY} selected={true} onToggleSelect={vi.fn()}>
        {null}
      </CapabilityNode>,
    );

    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it("calls onToggleSelect with the capability's id when the checkbox is clicked", async () => {
    const onToggleSelect = vi.fn();
    const user = userEvent.setup();
    renderWithQueryClient(
      <CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={onToggleSelect}>
        {null}
      </CapabilityNode>,
    );

    await user.click(screen.getByRole("checkbox"));

    expect(onToggleSelect).toHaveBeenCalledWith("cap-1");
  });

  it("no longer renders the old per-row Generate Diagram button (FR-006)", () => {
    renderWithQueryClient(
      <CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={vi.fn()}>
        {null}
      </CapabilityNode>,
    );

    expect(screen.queryByTitle("Generate Diagram")).toBeNull();
  });
});

describe("CapabilityNode (COMPLY-02 US3 — mapped compliance controls)", () => {
  it("shows the mapped controls list when 'Compliance' is toggled on", async () => {
    mockedComplianceApi.useCapabilityComplianceMappings.mockReturnValue({
      data: {
        items: [
          {
            control_id: "AC-2", target_type: "capability", target_id: "cap-1",
            compliance_status: "compliant", evidence_ref: null, assessed_at: null,
            assessed_by: null, created_at: "2026-08-18T00:00:00Z",
          },
        ],
      },
      isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useCapabilityComplianceMappings>);

    renderWithQueryClient(
      <CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={vi.fn()}>
        {null}
      </CapabilityNode>,
    );

    await userEvent.click(screen.getByRole("button", { name: /Details/ }));
    await userEvent.click(screen.getByRole("tab", { name: "Compliance" }));

    screen.getByText("AC-2");
    screen.getByText("compliant");
  });

  it("shows 'No controls mapped yet' when there are none", async () => {
    mockedComplianceApi.useCapabilityComplianceMappings.mockReturnValue({
      data: { items: [] }, isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useCapabilityComplianceMappings>);

    renderWithQueryClient(
      <CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={vi.fn()}>
        {null}
      </CapabilityNode>,
    );

    await userEvent.click(screen.getByRole("button", { name: /Details/ }));
    await userEvent.click(screen.getByRole("tab", { name: "Compliance" }));

    screen.getByText("No controls mapped yet.");
  });
});

describe("CapabilityNode technology dependencies (938-capability-model-analysis US4)", () => {
  const L3: CapabilityTreeNode = { ...CAPABILITY, id: "cap-3", name: "Process Checkout", level: 3, parent_id: "cap-2" };
  const mockedCapAnalysis = vi.mocked(capAnalysisApi);

  function mockDeps(items: capAnalysisApi.TechnologyDependency[]) {
    mockedCapAnalysis.useBusinessTechnology.mockReturnValue({
      data: { as_of: "2026-11-15", items },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof capAnalysisApi.useBusinessTechnology>);
  }

  it("is only on Level 3 rows, collapsed until opened", async () => {
    mockDeps([]);
    renderWithQueryClient(<CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={vi.fn()}>{null}</CapabilityNode>);
    expect(screen.queryByRole("button", { name: /Technology dependencies/ })).toBeNull();
  });

  it("lists each technical capability with its band and the application capability that links it", async () => {
    mockDeps([
      {
        technical: { id: "tc", name: "Local Data Store with Offline Sync", level: 3, path: [{ id: "t2", name: "Data Storage", level: 2 }] },
        lifecycle_status: "retiring",
        end_of_life_date: "2027-06-30",
        effective_band: "retiring",
        via_app_capability: { id: "ac", name: "Basket Calculation", level: 3 },
        via_business_capability: { id: "cap-3", name: "Process Checkout", level: 3 },
      },
    ]);
    const user = userEvent.setup();
    renderWithQueryClient(<CapabilityNode capability={L3} selected={false} onToggleSelect={vi.fn()}>{null}</CapabilityNode>);
    expect(mockedCapAnalysis.useBusinessTechnology).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /Technology dependencies/ }));
    expect(mockedCapAnalysis.useBusinessTechnology).toHaveBeenCalledWith("cap-3");
    expect(screen.getByText("Local Data Store with Offline Sync")).toBeTruthy();
    expect(screen.getByText("Retiring")).toBeTruthy();
    expect(screen.getByText("Basket Calculation")).toBeTruthy();
    expect(screen.getByText(/EOL 2027-06-30/)).toBeTruthy();
  });

  it("says when nothing is reached", async () => {
    mockDeps([]);
    const user = userEvent.setup();
    renderWithQueryClient(<CapabilityNode capability={L3} selected={false} onToggleSelect={vi.fn()}>{null}</CapabilityNode>);
    await user.click(screen.getByRole("button", { name: /Technology dependencies/ }));
    expect(screen.getByText(/No technical capability is reached/)).toBeTruthy();
  });
});


describe("CapabilityNode automated by agents (944)", () => {
  it("lists the agents that automate an L3 capability on expand", async () => {
    vi.mocked(agenticApi.useAutomatedBy).mockReturnValue({
      data: {
        items: [{
          id: "ag-1", name: "Payment Agent", lifecycle_status: "active", autonomy_level: 3,
          agentic_risk: { band: "high", factors: [], missing: [], not_considered: ["tool_side_effects"] },
        }],
        total: 1,
      },
      isLoading: false,
    } as never);
    renderWithQueryClient(<CapabilityNode capability={{ ...CAPABILITY, level: 3, parent_id: "p" }} selected={false} onToggleSelect={vi.fn()}>{null}</CapabilityNode>);
    expect(screen.queryByText("Payment Agent")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Automated by agents/ }));
    screen.getByText("Payment Agent");
    screen.getByText("High risk");
  });

  it("has no automated-by expander on L1/L2 rows", () => {
    renderWithQueryClient(<CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={vi.fn()}>{null}</CapabilityNode>);
    expect(screen.queryByRole("button", { name: /Automated by agents/ })).toBeNull();
  });
});

describe("CapabilityNode details panel (ADP-blp.59)", () => {
  it("opens one panel with a section per kind of detail, and closes it again", async () => {
    renderWithQueryClient(
      <CapabilityNode capability={CAPABILITY} selected={false} onToggleSelect={vi.fn()}>
        {null}
      </CapabilityNode>,
    );
    expect(screen.queryByRole("tablist")).toBeNull();
    const details = screen.getByRole("button", { name: /Details/ });
    expect(details.getAttribute("aria-expanded")).toBe("false");

    await userEvent.click(details);
    expect(details.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Links", "Organization", "Regions", "Compliance", "Review",
    ]);
    expect(screen.getByRole("tab", { name: "Links" }).getAttribute("aria-selected")).toBe("true");

    await userEvent.click(details);
    expect(screen.queryByRole("tablist")).toBeNull();
  });
});
