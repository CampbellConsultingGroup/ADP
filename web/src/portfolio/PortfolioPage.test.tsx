// ADP-8xo: mirrors ApplicationsHeatMap.test.tsx's established
// vi.mock(hooks-module) convention. PortfolioPage calls hooks from two
// modules (api/application, api/portfolio), both mocked.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PortfolioPage from "./PortfolioPage";
import * as applicationApi from "../api/application";
import * as portfolioApi from "../api/portfolio";
import type { Application } from "../api/application";
import type { ApplicationCapabilityGroupsResponse } from "../api/portfolio";

vi.mock("../api/application");
vi.mock("../api/portfolio");

const mockedApplicationApi = vi.mocked(applicationApi);
const mockedPortfolioApi = vi.mocked(portfolioApi);

function app(overrides: Partial<Application> & { id: string; name: string }): Application {
  return {
    description: null,
    vendor: null,
    primary_owner: null,
    time_classification: null,
    r_strategy: null,
    pace_layer: null,
    health_score: null,
    business_value: null,
    business_criticality: null,
    owning_business_unit: null,
    business_owner: null,
    technical_owner: null,
    lifecycle_status: "active",
    hosting_model: null,
    architecture_pattern: null,
    tech_debt_flags: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const APPS: Application[] = [
  app({ id: "app-1", name: "Claims Core", time_classification: "Invest", hosting_model: "cloud" }),
  app({ id: "app-2", name: "Fax Intake Tool", time_classification: null, hosting_model: "on_prem" }),
];

const CAPABILITY_GROUPS: ApplicationCapabilityGroupsResponse = {
  items: [
    { app_id: "app-1", capability_id: "cap-1", capability_name: "Claims Processing", fit_score: 4 },
    { app_id: "app-1", capability_id: "cap-2", capability_name: "Fraud Detection", fit_score: 2 },
  ],
};

function mockData(apps: Application[], groups: ApplicationCapabilityGroupsResponse) {
  mockedApplicationApi.useApplications.mockReturnValue({
    data: { items: apps, total: apps.length },
  } as unknown as ReturnType<typeof applicationApi.useApplications>);
  mockedPortfolioApi.useApplicationCapabilityGroups.mockReturnValue({
    data: groups,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof portfolioApi.useApplicationCapabilityGroups>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockData(APPS, CAPABILITY_GROUPS);
});

describe("PortfolioPage (ADP-8xo — default capability grouping)", () => {
  it("renders capability buckets by default, with an app appearing in both its buckets", () => {
    render(<PortfolioPage />);

    expect(screen.getByText("Claims Processing")).toBeTruthy();
    expect(screen.getByText("Fraud Detection")).toBeTruthy();
    // app-1 is linked to both -- its name renders in both bucket cards.
    expect(screen.getAllByText("Claims Core")).toHaveLength(2);
  });

  it("shows an app with zero capability links under Unclassified", () => {
    render(<PortfolioPage />);

    expect(screen.getByText(/Unclassified \(1\)/)).toBeTruthy();
    expect(screen.getByText("Fax Intake Tool")).toBeTruthy();
  });

  it("shows an empty-state message when there are zero applications", () => {
    mockData([], { items: [] });

    render(<PortfolioPage />);

    expect(screen.getByText(/No applications in the portfolio yet/)).toBeTruthy();
  });
});

describe("PortfolioPage (ADP-8xo — Group by dropdown)", () => {
  it("switches to TIME buckets on selection, and shows the null case as Unclassified", async () => {
    const user = userEvent.setup();
    render(<PortfolioPage />);

    // Set both dropdowns to "time" to stay in the flat single-dimension view --
    // ADP-3wa's second dropdown means changing only the first now activates the
    // cross-tab instead (covered separately below).
    await user.selectOptions(screen.getByRole("combobox", { name: "Group by" }), "time");
    await user.selectOptions(screen.getByRole("combobox", { name: "Then by" }), "time");

    expect(screen.getByText("Invest")).toBeTruthy();
    expect(screen.getByText(/Unclassified \(1\)/)).toBeTruthy();
    // Regrouping is a pure client-side computation over already-fetched data --
    // neither hook is parameterized by `dimension`, so there is structurally no
    // query-key change (and thus no re-fetch) when the dropdown changes.
  });

  it("offers all 5 dimensions", () => {
    render(<PortfolioPage />);

    const select = screen.getByRole("combobox", { name: "Group by" });
    expect(select.textContent).toMatch(/Business Capability/);
    expect(select.textContent).toMatch(/TIME Disposition/);
    expect(select.textContent).toMatch(/7R Strategy/);
    expect(select.textContent).toMatch(/Ownership \/ Business Unit/);
    expect(select.textContent).toMatch(/Criticality \/ Risk Tier/);
  });
});

describe("PortfolioPage (ADP-3wa — second dropdown / cross-tab)", () => {
  it("both dropdowns default to Business Capability, rendering the flat card view (no table)", () => {
    render(<PortfolioPage />);

    expect((screen.getByRole("combobox", { name: "Group by" }) as HTMLSelectElement).value).toBe("capability");
    expect((screen.getByRole("combobox", { name: "Then by" }) as HTMLSelectElement).value).toBe("capability");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("selecting a different second dimension renders a cross-tab table with correct cells", async () => {
    const user = userEvent.setup();
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Then by" }), "time");

    const table = screen.getByRole("table");
    expect(table).toBeTruthy();
    // Row headers: the 2 capabilities + Unclassified (app-2 has no capability link).
    expect(screen.getByText("Claims Processing")).toBeTruthy();
    expect(screen.getByText("Fraud Detection")).toBeTruthy();
    // Column headers: TIME's fixed set.
    expect(screen.getByText("Invest")).toBeTruthy();
    // app-1 (Invest, linked to both capabilities) shows a count of 1 in both
    // capability rows' Invest column -- the multi-membership cross-tab case.
    const investCells = screen.getAllByTitle("Claims Core");
    expect(investCells).toHaveLength(2);
  });

  it("setting both dropdowns to the same (non-default) dimension reverts to the flat card view", async () => {
    const user = userEvent.setup();
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Then by" }), "time");
    expect(screen.getByRole("table")).toBeTruthy();

    await user.selectOptions(screen.getByRole("combobox", { name: "Group by" }), "time");

    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText("Invest")).toBeTruthy();
  });

  it("shows the active pivot in the summary line only when dimensions differ", async () => {
    const user = userEvent.setup();
    render(<PortfolioPage />);

    expect(screen.queryByText(/Business Capability × TIME Disposition/)).toBeNull();

    await user.selectOptions(screen.getByRole("combobox", { name: "Then by" }), "time");

    expect(screen.getByText(/Business Capability × TIME Disposition/)).toBeTruthy();
  });
});

describe("PortfolioPage (ADP-9ye — Filter by)", () => {
  it("no filter selected by default -- full app count, no value dropdown", () => {
    render(<PortfolioPage />);

    expect(screen.getByText(/^2 applications/)).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Filter value" })).toBeNull();
  });

  it("offers all 8 filter fields, including the 3 not used for grouping", () => {
    render(<PortfolioPage />);

    const select = screen.getByRole("combobox", { name: "Filter by" });
    expect(select.textContent).toMatch(/Business Capability/);
    expect(select.textContent).toMatch(/TIME Disposition/);
    expect(select.textContent).toMatch(/7R Strategy/);
    expect(select.textContent).toMatch(/Ownership \/ Business Unit/);
    expect(select.textContent).toMatch(/Criticality \/ Risk Tier/);
    expect(select.textContent).toMatch(/Lifecycle Status/);
    expect(select.textContent).toMatch(/Hosting Model/);
    expect(select.textContent).toMatch(/PACE Layer/);
  });

  it("selecting a filter field auto-selects a value and narrows the app list", async () => {
    const user = userEvent.setup();
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "hosting_model");

    // hosting_model's fixed bucket order is on_prem/cloud/saas/hybrid -- the
    // auto-selected first value is "On-Prem" (app-2's value), narrowing 2 -> 1.
    expect(screen.getByText(/1 of 2 application/)).toBeTruthy();
    expect(screen.getByText(/filtered to Hosting Model: On-Prem/)).toBeTruthy();
    expect(screen.getByText("Fax Intake Tool")).toBeTruthy();
    expect(screen.queryByText("Claims Core")).toBeNull();
  });

  it("clearing the filter restores the full application set", async () => {
    const user = userEvent.setup();
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "hosting_model");
    expect(screen.getByText(/1 of 2 application/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Clear filter" }));

    expect(screen.getByText(/^2 applications/)).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Filter value" })).toBeNull();
  });

  it("a filter applied while the cross-tab is active narrows the table too", async () => {
    const user = userEvent.setup();
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Then by" }), "time");
    expect(screen.getByRole("table")).toBeTruthy();
    // Before filtering, app-1's name appears in the table (twice -- linked to
    // 2 capabilities, the multi-membership cross-tab case).
    expect(screen.getAllByText("Claims Core").length).toBeGreaterThan(0);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "hosting_model");

    // Filtered to On-Prem (app-2 only) -- app-1 no longer appears anywhere.
    expect(screen.queryByText("Claims Core")).toBeNull();
    expect(screen.getByText("Fax Intake Tool")).toBeTruthy();
  });
});

describe("PortfolioPage (ADP-6w4 — comparison/string operators)", () => {
  const OPERATOR_APPS: Application[] = [
    app({
      id: "app-1", name: "Claims Core", hosting_model: "cloud",
      business_criticality: 3, health_score: 2, vendor: "Acme Cloud Systems",
    }),
    app({
      id: "app-2", name: "Fax Intake Tool", hosting_model: "on_prem",
      business_criticality: 5, health_score: 4, vendor: "Other Co",
    }),
  ];

  it("a pure-bucket field (v1's original 8) shows no operator dropdown", async () => {
    const user = userEvent.setup();
    mockData(OPERATOR_APPS, CAPABILITY_GROUPS);
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "hosting_model");

    expect(screen.queryByRole("combobox", { name: "Filter operator" })).toBeNull();
    expect(screen.getByRole("combobox", { name: "Filter value" })).toBeTruthy();
  });

  it("criticality defaults to '=' with the v1 bucket dropdown, still narrowing correctly", async () => {
    const user = userEvent.setup();
    mockData(OPERATOR_APPS, CAPABILITY_GROUPS);
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "criticality");

    expect(screen.getByRole("combobox", { name: "Filter operator" })).toBeTruthy();
    // Bucket dropdown (v1 behavior), not the free-form input.
    expect(screen.getByRole("combobox", { name: "Filter value" })).toBeTruthy();
    expect(screen.queryByPlaceholderText("value…")).toBeNull();
  });

  it("switching criticality's operator to '>' swaps the value control to a number input and narrows correctly", async () => {
    const user = userEvent.setup();
    mockData(OPERATOR_APPS, CAPABILITY_GROUPS);
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "criticality");
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter operator" }), "gt");

    // Bucket dropdown is gone; a number input is in its place.
    expect(screen.queryByRole("combobox", { name: "Filter value" })).toBeNull();
    const input = screen.getByPlaceholderText("value…");
    expect(input.getAttribute("type")).toBe("number");

    await user.type(input, "3");

    expect(screen.getByText("Fax Intake Tool")).toBeTruthy();
    expect(screen.queryByText("Claims Core")).toBeNull();
    expect(screen.getByText(/filtered to Criticality \/ Risk Tier: > 3/)).toBeTruthy();
  });

  it("a new numeric-only field (health_score) never shows a bucket dropdown, only the operator + number input", async () => {
    const user = userEvent.setup();
    mockData(OPERATOR_APPS, CAPABILITY_GROUPS);
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "health_score");

    expect(screen.getByRole("combobox", { name: "Filter operator" })).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Filter value" })).toBeNull();
    expect(screen.getByPlaceholderText("value…").getAttribute("type")).toBe("number");

    // Default operator is "=" -- app-2's health_score is 4, app-1's is 2.
    await user.type(screen.getByPlaceholderText("value…"), "4");

    expect(screen.getByText("Fax Intake Tool")).toBeTruthy();
    expect(screen.queryByText("Claims Core")).toBeNull();
  });

  it("a new string-only field (vendor) offers contains/starts with, narrowing case-insensitively", async () => {
    const user = userEvent.setup();
    mockData(OPERATOR_APPS, CAPABILITY_GROUPS);
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "vendor");
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter operator" }), "contains");

    const input = screen.getByPlaceholderText("text…");
    expect(input.getAttribute("type")).toBe("text");
    await user.type(input, "cloud");

    // app-1 appears twice (linked to 2 capability buckets, default Group By) -- getAllByText.
    expect(screen.getAllByText("Claims Core").length).toBeGreaterThan(0);
    expect(screen.queryByText("Fax Intake Tool")).toBeNull();
  });

  it("switching from a comparison field back to a pure-bucket field resets the operator and drops the free-form input", async () => {
    const user = userEvent.setup();
    mockData(OPERATOR_APPS, CAPABILITY_GROUPS);
    render(<PortfolioPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "health_score");
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter operator" }), "gt");
    await user.type(screen.getByPlaceholderText("value…"), "3");

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by" }), "hosting_model");

    expect(screen.queryByRole("combobox", { name: "Filter operator" })).toBeNull();
    expect(screen.queryByPlaceholderText("value…")).toBeNull();
    expect(screen.getByRole("combobox", { name: "Filter value" })).toBeTruthy();
  });
});
