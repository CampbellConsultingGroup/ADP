// 939-governance-architecture-health: Governance -> Architecture Health (tiles, Patterns, Capabilities).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as businessApi from "../api/business";
import * as patternsApi from "../api/patterns";
import * as capAnalysisApi from "../api/capAnalysis";
import * as orgApi from "../api/organization";
import type { CapabilityOrgFindings } from "../api/organization";
import type { Adoption, ConformanceStatus } from "../api/patterns";
import type { CapabilityFindings, CapabilityRollup, LifecycleBand } from "../api/capAnalysis";
import { CapabilityNavContext } from "../application/appCapNav";
import ArchitectureHealthTab from "./ArchitectureHealthTab";

vi.mock("../api/patterns", async (orig) => ({
  ...(await orig<typeof import("../api/patterns")>()),
  useAdoptions: vi.fn(),
}));
vi.mock("../api/business", async (orig) => ({
  ...(await orig<typeof import("../api/business")>()),
  useCapabilities: vi.fn(),
}));
vi.mock("../api/capAnalysis", async (orig) => ({
  ...(await orig<typeof import("../api/capAnalysis")>()),
  useCapabilityRollup: vi.fn(),
  useCapabilityFindings: vi.fn(),
}));

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useCapabilityOrgFindings: vi.fn(),
}));

const pat = vi.mocked(patternsApi);
const org = vi.mocked(orgApi);
const biz = vi.mocked(businessApi);
const cap = vi.mocked(capAnalysisApi);

function adoption(id: string, name: string, status: ConformanceStatus): Adoption {
  return {
    id, pattern_key: "ea.integration.domain-event-backbone", pattern_name: "Domain Event Backbone",
    kind: "reference-architecture", name, scope_type: "business_domain", scope_ref: "d", scope_name: "E-commerce & Digital",
    member_ids: [], pinned_version: null, resolved_version: "1.1.0", pins: [], created_at: "", created_by: "", updated_at: "", status,
  };
}

const ref = (id: string, name: string, level = 3) => ({ id, name, level });
const path = [ref("b1", "Sales & Customer Transactions", 1), ref("b2", "In-Store Transaction Management", 2)];

function rollupItem(id: string, name: string, level: number, band: LifecycleBand | null): CapabilityRollup {
  return {
    capability_id: id, name, level, contributing_apps: [], excluded_retired_apps: [],
    health: { worst: null, spread: {} }, risk: null, cost: null, exposure: { worst: band, spread: {} },
  };
}

const FINDINGS: CapabilityFindings = {
  overlaps: [
    {
      business: { ...ref("b4", "Apply Promotions"), path },
      status: "needs_attention",
      reasons: [{ code: "unclassified", application_ids: ["sfcc"] }],
      applications: [
        { id: "pos", name: "Oracle Retail Xstore POS", via: [ref("ac2", "Price Rule Evaluation")] },
        { id: "sfcc", name: "Salesforce Commerce Cloud", via: [ref("ac9", "Online Promotion Evaluation")] },
      ],
    },
    // 943: an explained overlap is not counted on the tile.
    {
      business: { ...ref("b7", "Accept Payment"), path },
      status: "explained",
      reasons: [],
      applications: [
        { id: "pos", name: "Oracle Retail Xstore POS", via: [ref("ac4", "Tender Authorization")] },
        { id: "pix", name: "Pix Gateway", via: [ref("ac4", "Tender Authorization")] },
      ],
    },
  ],
  gaps: {
    business_without_app_capability: [{ ...ref("b5", "Demand Forecasting"), path: [] }, { ...ref("b6", "Replenishment"), path: [] }],
    app_capability_without_business: [{ ...ref("ac7", "Loyalty Points Accrual"), path: [] }],
    app_capability_without_application: [],
  },
  shared: [],
  shared_threshold: 3,
  redundant: [],
};

// ADP-m7x: 941's ownership / performer findings.
const fcap = (id: string, name: string, level = 3) => ({ id, name, level, path: [ref("b1", "Sales & Customer Transactions", 1)] });
const ORG_FINDINGS: CapabilityOrgFindings = {
  no_owner: [fcap("b9", "Finance", 1)],
  shared_service: [
    {
      capability: fcap("b12", "Receive Goods"),
      branches: 2,
      performers: [
        { org_unit: { id: "o1", name: "Store Operations", level: 3 }, org_unit_path: [], geographies: [], folded_into: null },
        { org_unit: { id: "o2", name: "Digital Commerce", level: 3 }, org_unit_path: [], geographies: [], folded_into: null },
      ],
    },
  ],
  unmapped: [fcap("b10", "Plan Assortment"), fcap("b11", "Forecast Demand")],
  owned_no_performer: [],
  counts: { no_owner: 1, shared_service: 1, unmapped: 2, owned_no_performer: 0, l1_l2_total: 6, l3_total: 20 },
} as CapabilityOrgFindings;

function ok<T>(data: T) {
  return { data, isLoading: false, error: null } as never;
}

function seed() {
  pat.useAdoptions.mockReturnValue(
    ok({
      items: [
        adoption("a1", "E-commerce & Digital — mesh migration", "non_conformant"),
        adoption("a2", "Marketing & Loyalty — event backbone", "conformant"),
        adoption("a3", "E-commerce & Digital — event backbone", "non_conformant"),
        adoption("a4", "Claims — event backbone", "indeterminate"),
        adoption("a5", "Billing — event backbone", "not_applicable"),
      ],
      total: 5,
    }),
  );
  cap.useCapabilityRollup.mockReturnValue(
    ok({
      as_of: "2026-11-15", risk_available: true, cost_available: true,
      items: [
        rollupItem("b1", "Sales & Customer Transactions", 1, "retiring"),
        rollupItem("b3", "Process Checkout", 3, "retiring"),
        rollupItem("b4", "Apply Promotions", 3, "current"),
        rollupItem("b7", "Legacy Returns", 3, "past_end_of_life"),
      ],
    }),
  );
  cap.useCapabilityFindings.mockReturnValue(ok(FINDINGS));
  org.useCapabilityOrgFindings.mockReturnValue(ok(ORG_FINDINGS));
  const bc = (id: string, name: string, level: 1 | 2 | 3, parent_id: string | null) => ({
    id, name, level, parent_id, description: null, position: 0, created_at: "", updated_at: "",
    domain_id: null, domain_name: null, strategic_relevance: null, maturity_level: null,
  });
  biz.useCapabilities.mockReturnValue(
    ok({
      items: [
        bc("b1", "Sales & Customer Transactions", 1, null),
        bc("b2", "In-Store Transaction Management", 2, "b1"),
        bc("b3", "Process Checkout", 3, "b2"),
        bc("b7", "Legacy Returns", 3, "b2"),
      ],
      total: 4,
    }),
  );
}

const tile = (label: string) => screen.getByRole("group", { name: label });

beforeEach(() => {
  vi.clearAllMocks();
  seed();
});

describe("ArchitectureHealthTab tiles (US1)", () => {
  it("shows the five derived counts", () => {
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(within(tile("Non-conformant adoptions")).getByText("2")).toBeTruthy();
    expect(within(tile("Indeterminate adoptions")).getByText("1")).toBeTruthy();
    expect(within(tile("Exposed capabilities")).getByText("2")).toBeTruthy();
    expect(within(tile("Overlaps")).getByText("1")).toBeTruthy();
    expect(within(tile("Overlaps")).getByText("1 explained")).toBeTruthy();
    expect(within(tile("Gaps")).getByText("3")).toBeTruthy();
  });

  it("shows the organization findings as tiles (ADP-m7x)", () => {
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(within(tile("No accountable owner")).getByText("1")).toBeTruthy();
    expect(within(tile("No accountable owner")).getByText("of 6 L1/L2")).toBeTruthy();
    expect(within(tile("Shared-service candidates")).getByText("1")).toBeTruthy();
    expect(within(tile("Unmapped L3s")).getByText("2")).toBeTruthy();
    expect(within(tile("Unmapped L3s")).getByText("of 20 L3")).toBeTruthy();
  });

  it("lists the organization findings and opens a capability on the Business screen (ADP-m7x)", async () => {
    const nav = { openBusinessCapability: vi.fn(), openApplication: vi.fn(), openTechnicalCapability: vi.fn() };
    render(
      <CapabilityNavContext.Provider value={nav}>
        <ArchitectureHealthTab onOpenAdoption={vi.fn()} />
      </CapabilityNavContext.Provider>,
    );
    const section = screen.getByRole("region", { name: "Organization" });
    expect(within(section).getByText("Store Operations")).toBeTruthy();
    expect(within(section).getByText("Forecast Demand")).toBeTruthy();
    await userEvent.click(within(section).getByRole("button", { name: "Plan Assortment" }));
    expect(nav.openBusinessCapability).toHaveBeenCalledWith("b10");
  });

  it("keeps the other sections when the organization findings fail (ADP-m7x)", () => {
    org.useCapabilityOrgFindings.mockReturnValue({ data: undefined, isLoading: false, error: new Error("x") } as never);
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(within(tile("Unmapped L3s")).getByText("—")).toBeTruthy();
    expect(within(tile("Overlaps")).getByText("1")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Organization" })).getByRole("alert")).toBeTruthy();
  });

  it("asks for adoption statuses and both capability analyses", () => {
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(pat.useAdoptions).toHaveBeenCalledWith(true);
    expect(cap.useCapabilityRollup).toHaveBeenCalledWith(true);
  });

  it("never shows 0 while loading", () => {
    pat.useAdoptions.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    cap.useCapabilityRollup.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    cap.useCapabilityFindings.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    org.useCapabilityOrgFindings.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    for (const label of ["Non-conformant adoptions", "Indeterminate adoptions", "Exposed capabilities", "Overlaps", "Gaps", "No accountable owner", "Shared-service candidates", "Unmapped L3s"]) {
      expect(within(tile(label)).getByText("…")).toBeTruthy();
    }
  });

  it("shows empty states when nothing needs attention", () => {
    pat.useAdoptions.mockReturnValue(ok({ items: [adoption("a2", "Marketing", "conformant")], total: 1 }));
    cap.useCapabilityRollup.mockReturnValue(ok({ as_of: "", risk_available: true, cost_available: true, items: [] }));
    cap.useCapabilityFindings.mockReturnValue(
      ok({ ...FINDINGS, overlaps: [], gaps: { business_without_app_capability: [], app_capability_without_business: [], app_capability_without_application: [] } }),
    );
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(within(tile("Non-conformant adoptions")).getByText("0")).toBeTruthy();
    expect(screen.getByText("Every adoption is conformant or not applicable.")).toBeTruthy();
    expect(screen.getByText("No business capability depends on retiring or past-end-of-life technology.")).toBeTruthy();
  });
});

describe("ArchitectureHealthTab Patterns section (US2)", () => {
  it("lists non-conformant, then indeterminate, and summarizes the rest", () => {
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    const section = screen.getByRole("region", { name: "Pattern conformance" });
    const names = within(section).getAllByRole("button").map((b) => b.textContent);
    expect(names).toEqual([
      "E-commerce & Digital — event backbone",
      "E-commerce & Digital — mesh migration",
      "Claims — event backbone",
    ]);
    expect(within(section).getByText(/1 conformant · 1 not applicable/)).toBeTruthy();
    expect(within(section).getByText(/Indeterminate can mean/)).toBeTruthy();
  });

  it("opens the adoption on the Patterns screen", async () => {
    const onOpenAdoption = vi.fn();
    render(<ArchitectureHealthTab onOpenAdoption={onOpenAdoption} />);
    await userEvent.click(screen.getByRole("button", { name: "E-commerce & Digital — mesh migration" }));
    expect(onOpenAdoption).toHaveBeenCalledWith("a1");
  });

  it("says when nothing has been adopted", () => {
    pat.useAdoptions.mockReturnValue(ok({ items: [], total: 0 }));
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(screen.getByText("No patterns have been adopted yet.")).toBeTruthy();
  });

  it("keeps the Capabilities section when the patterns source fails", () => {
    pat.useAdoptions.mockReturnValue({ data: undefined, isLoading: false, error: new Error("boom") } as never);
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(screen.getByText("Failed to load pattern conformance.")).toBeTruthy();
    expect(within(tile("Non-conformant adoptions")).getByText("—")).toBeTruthy();
    expect(screen.getByText("Process Checkout")).toBeTruthy();
  });
});

describe("ArchitectureHealthTab Capabilities section (US3)", () => {
  it("lists exposed Level 3s worst first, with band and path, and navigates", async () => {
    const nav = { openBusinessCapability: vi.fn(), openApplication: vi.fn(), openTechnicalCapability: vi.fn() };
    render(
      <CapabilityNavContext.Provider value={nav}>
        <ArchitectureHealthTab onOpenAdoption={vi.fn()} />
      </CapabilityNavContext.Provider>,
    );
    const section = screen.getByRole("region", { name: "Exposed capabilities" });
    const items = within(section).getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(items[0]).toContain("Legacy Returns");
    expect(items[0]).toContain("Past end of life");
    expect(items[1]).toContain("Process Checkout");
    expect(items[1]).toContain("Retiring");
    expect(items[1]).toContain("Sales & Customer Transactions › In-Store Transaction Management");
    await userEvent.click(within(section).getByRole("button", { name: "Process Checkout" }));
    expect(nav.openBusinessCapability).toHaveBeenCalledWith("b3");
  });

  it("renders overlaps and gaps as on Applications -> Capabilities", () => {
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    const overlaps = screen.getByLabelText("Overlaps", { selector: "[aria-label='Overlaps']:not([role=group])" });
    expect(within(overlaps).getByText("Apply Promotions")).toBeTruthy();
    expect(within(overlaps).getByText("Online Promotion Evaluation")).toBeTruthy();
    expect(screen.getByText("Demand Forecasting")).toBeTruthy();
    expect(screen.getByText("Loyalty Points Accrual")).toBeTruthy();
  });

  it("keeps the Patterns section when the capability sources fail", () => {
    cap.useCapabilityRollup.mockReturnValue({ data: undefined, isLoading: false, error: new Error("x") } as never);
    cap.useCapabilityFindings.mockReturnValue({ data: undefined, isLoading: false, error: new Error("x") } as never);
    render(<ArchitectureHealthTab onOpenAdoption={vi.fn()} />);
    expect(screen.getByText("Failed to load capability exposure.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "E-commerce & Digital — mesh migration" })).toBeTruthy();
  });
});
