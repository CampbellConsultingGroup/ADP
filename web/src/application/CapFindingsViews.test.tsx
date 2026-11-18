// 938-capability-model-analysis US5: overlaps, gaps and shared views.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import * as capAnalysisApi from "../api/capAnalysis";
import type { CapabilityFindings } from "../api/capAnalysis";
import CapFindingsViews from "./CapFindingsViews";

vi.mock("../api/capAnalysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/capAnalysis")>()),
  useCapabilityFindings: vi.fn(),
}));

const api = vi.mocked(capAnalysisApi);
const ref = (id: string, name: string, level = 3) => ({ id, name, level });
const path = [ref("b1", "Sales", 1), ref("b2", "In-Store", 2)];

const FINDINGS: CapabilityFindings = {
  overlaps: [
    {
      business: { ...ref("b4", "Apply Promotions"), path },
      status: "needs_attention",
      reasons: [{ code: "unclassified", application_ids: ["commerce"] }],
      applications: [
        {
          id: "commerce", name: "Commerce Cloud", via: [ref("ac9", "Online Promotion Evaluation")],
          mappings: [{ via: ref("ac9", "Online Promotion Evaluation"), rationale: null, geography: null, hint: null }],
        },
        {
          id: "pos", name: "Store POS", via: [ref("ac2", "Price Rule Evaluation")],
          mappings: [{ via: ref("ac2", "Price Rule Evaluation"), rationale: "target", geography: null, hint: "TIME says Migrate" }],
        },
      ],
    },
    {
      business: { ...ref("b6", "Accept Payment"), path },
      status: "explained",
      reasons: [],
      applications: [
        {
          id: "pos", name: "Store POS", via: [ref("ac4", "Tender Authorization")],
          mappings: [{ via: ref("ac4", "Tender Authorization"), rationale: "target", geography: null, hint: null }],
        },
        {
          id: "pix", name: "Pix Gateway", via: [ref("ac4", "Tender Authorization")],
          mappings: [{ via: ref("ac4", "Tender Authorization"), rationale: "tactical", geography: { id: "br", name: "Brazil", code: "BR" }, hint: null }],
        },
      ],
    },
  ],
  redundant: [
    {
      business: { ...ref("b4", "Apply Promotions"), path },
      entries: [
        {
          application: { id: "old", name: "Old Promo Engine", time_classification: "Invest", r_strategy: "Retain" },
          app_capability: { ...ref("ac9", "Online Promotion Evaluation"), path: [] },
          geography: { id: "eu", name: "Europe", code: null },
          hint: "TIME says Invest",
        },
      ],
    },
    {
      business: null,
      entries: [
        {
          application: { id: "x", name: "Orphan Tool", time_classification: null, r_strategy: null },
          app_capability: { ...ref("ac8", "Loose Capability"), path: [] },
          geography: null,
          hint: null,
        },
      ],
    },
  ],
  gaps: {
    business_without_app_capability: [{ ...ref("b5", "Process Returns"), path }],
    app_capability_without_business: [{ ...ref("ac7", "Loyalty Points Accrual"), path: [] }],
    app_capability_without_application: [],
  },
  shared: [{ app_capability: { ...ref("ac3", "Customer Lookup"), path: [] }, business: [ref("x", "A"), ref("y", "B"), ref("z", "C")], count: 3 }],
  shared_threshold: 3,
};

function mockFindings(data: CapabilityFindings) {
  api.useCapabilityFindings.mockReturnValue({ data, isLoading: false, error: null } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFindings(FINDINGS);
});

describe("CapFindingsViews", () => {
  it("lists overlaps with each application and the capability it acts through", () => {
    render(<CapFindingsViews mode="overlaps" />);
    const view = screen.getByLabelText("Overlaps");
    expect(within(view).getByText("Apply Promotions")).toBeTruthy();
    expect(within(view).getByText("Commerce Cloud")).toBeTruthy();
    expect(within(view).getByText("Online Promotion Evaluation")).toBeTruthy();
    expect(within(view).getByText("Price Rule Evaluation")).toBeTruthy();
  });

  it("splits overlaps into needs attention (first) and explained, with reasons and each mapping's rationale (943)", () => {
    render(<CapFindingsViews mode="overlaps" />);
    const needs = screen.getByRole("region", { name: "Needs attention (1)" });
    const explained = screen.getByRole("region", { name: "Explained (1)" });
    expect(needs.compareDocumentPosition(explained) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(needs).getByText("Apply Promotions")).toBeTruthy();
    expect(within(needs).getByText("Unclassified: Commerce Cloud")).toBeTruthy();
    expect(within(needs).getByText(/TIME says Migrate/)).toBeTruthy();
    expect(within(explained).getByText("Accept Payment")).toBeTruthy();
    expect(within(explained).getByText("Tactical")).toBeTruthy();
    expect(within(explained).getByText(/Brazil/)).toBeTruthy();
  });

  it.each([
    [{ code: "redundant" as const, application_ids: ["commerce"] }, "Redundant: Commerce Cloud"],
    [{ code: "no_target" as const, application_ids: [] }, "No target"],
    [{ code: "competing_targets" as const, application_ids: ["commerce", "pos"] }, "Competing targets: Commerce Cloud, Store POS"],
  ])("labels the %o reason", (reason, text) => {
    mockFindings({ ...FINDINGS, overlaps: [{ ...FINDINGS.overlaps[0], reasons: [reason] }] });
    render(<CapFindingsViews mode="overlaps" />);
    expect(screen.getByText(text)).toBeTruthy();
  });

  it("lists redundant mappings by business capability, with TIME / 7R and the hint (943)", async () => {
    render(<CapFindingsViews mode="redundant" />);
    const view = screen.getByLabelText("Redundant");
    expect(within(view).getByText("Old Promo Engine")).toBeTruthy();
    expect(within(view).getByText(/TIME Invest · 7R Retain/)).toBeTruthy();
    expect(within(view).getByText(/TIME says Invest/)).toBeTruthy();
    expect(within(view).getByText(/Europe/)).toBeTruthy();
    expect(within(view).getByText("Not linked to a business capability")).toBeTruthy();
    expect(within(view).getByRole("link", { name: "Online Promotion Evaluation" }).getAttribute("href"))
      .toBe("#/applications/capabilities/ac9");
  });

  it("says when nothing is marked redundant", () => {
    mockFindings({ ...FINDINGS, redundant: [] });
    render(<CapFindingsViews mode="redundant" />);
    expect(screen.getByText(/No mapping is marked redundant/)).toBeTruthy();
  });

  it("shows the three gap lists with paths and empty states", () => {
    render(<CapFindingsViews mode="gaps" />);
    expect(screen.getByRole("region", { name: "Business capabilities with no application capability" })).toBeTruthy();
    expect(screen.getByText("Process Returns")).toBeTruthy();
    expect(screen.getAllByText(/Sales › In-Store/).length).toBeGreaterThan(0);
    expect(screen.getByText("Loyalty Points Accrual")).toBeTruthy();
    expect(screen.getByText("Every Level 3 application capability is realized by an application.")).toBeTruthy();
  });

  it("labels shared as informational", () => {
    render(<CapFindingsViews mode="shared" />);
    expect(screen.getByText(/Informational, not a problem/)).toBeTruthy();
    expect(screen.getByText("Customer Lookup")).toBeTruthy();
    expect(screen.getByText(/supports 3/)).toBeTruthy();
  });

  it("shows empty states", () => {
    mockFindings({ ...FINDINGS, overlaps: [], shared: [] });
    const { rerender } = render(<CapFindingsViews mode="overlaps" />);
    expect(screen.getByText("No business capability is realized by more than one application.")).toBeTruthy();
    rerender(<CapFindingsViews mode="shared" />);
    expect(screen.getByText(/No application capability supports 3 or more/)).toBeTruthy();
  });

  it("links every item to its own screen", () => {
    render(<CapFindingsViews mode="overlaps" />);
    const href = (el: HTMLElement) => el.getAttribute("href");
    expect(href(screen.getByRole("link", { name: "Apply Promotions" }))).toBe("#/business/b4");
    expect(href(screen.getAllByRole("link", { name: "Store POS" })[0])).toBe("#/applications/pos");
    expect(href(screen.getByRole("link", { name: "Price Rule Evaluation" }))).toBe("#/applications/capabilities/ac2");
  });
});
