// 932-regulatory-framework-tags (ADP-bkg). Mirrors ObjectiveControlLinkEditor.test.tsx's
// vi.mock(hooks-module) convention, adapted for RiskPanel's two mocked hook modules
// (../api/application for the risk record itself, ../api/compliance for the framework list the
// picker is sourced from). No jest-dom matchers are configured in this project (tests/setup.ts) —
// assertions use plain Testing Library queries (getByText/queryByText, .checked), matching every
// other component test's own established convention (e.g. CapabilityNode.test.tsx).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RiskPanel from "./RiskPanel";
import * as applicationApi from "../api/application";
import * as complianceApi from "../api/compliance";
import type { ApplicationRisk } from "../api/application";
import type { RegulatoryFramework, RegulatoryFrameworkListResponse } from "../api/compliance";

vi.mock("../api/application");
vi.mock("../api/compliance");

const mockedApplicationApi = vi.mocked(applicationApi);
const mockedComplianceApi = vi.mocked(complianceApi);

function framework(overrides: Partial<RegulatoryFramework>): RegulatoryFramework {
  return {
    id: "FRM-1",
    name: "GDPR",
    jurisdiction: "EU",
    authority: "EDPB",
    version: "2016/679",
    effective_date: null,
    source_url: null,
    status: "in_force",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function risk(overrides: Partial<ApplicationRisk>): ApplicationRisk {
  return {
    security_posture: null,
    vulnerability_status: null,
    data_classification: null,
    regulatory_tags: [],
    dr_bc_status: null,
    end_of_life_date: null,
    end_of_support_date: null,
    updated_at: null,
    ...overrides,
  };
}

const mutateAsync = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  mockedApplicationApi.useUpdateApplicationRisk.mockReturnValue({
    mutateAsync,
    isPending: false,
  } as unknown as ReturnType<typeof applicationApi.useUpdateApplicationRisk>);
});

function mockFrameworks(items: RegulatoryFramework[]) {
  mockedComplianceApi.useFrameworks.mockReturnValue({
    data: { items, total: items.length } as RegulatoryFrameworkListResponse,
  } as unknown as ReturnType<typeof complianceApi.useFrameworks>);
}

function mockRisk(data: ApplicationRisk) {
  mockedApplicationApi.useApplicationRisk.mockReturnValue({
    data,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof applicationApi.useApplicationRisk>);
}

describe("RiskPanel — regulatory framework picker", () => {
  it("renders one checkbox per in_force/amended framework, excluding repealed/not_yet_applicable", () => {
    mockFrameworks([
      framework({ id: "FRM-1", name: "GDPR", status: "in_force" }),
      framework({ id: "FRM-2", name: "DORA", status: "amended" }),
      framework({ id: "FRM-3", name: "Old Reg", status: "repealed" }),
      framework({ id: "FRM-4", name: "Future Reg", status: "not_yet_applicable" }),
    ]);
    mockRisk(risk({ regulatory_tags: [] }));

    render(<RiskPanel appId="app-1" />);

    expect(screen.getByText("GDPR")).toBeTruthy();
    expect(screen.getByText("DORA")).toBeTruthy();
    expect(screen.queryByText("Old Reg")).toBeNull();
    expect(screen.queryByText("Future Reg")).toBeNull();
  });

  it("pre-checks frameworks already tagged on the application", () => {
    mockFrameworks([
      framework({ id: "FRM-1", name: "GDPR", status: "in_force" }),
      framework({ id: "FRM-2", name: "DORA", status: "amended" }),
    ]);
    mockRisk(risk({ regulatory_tags: ["FRM-1"] }));

    render(<RiskPanel appId="app-1" />);

    const gdpr = screen.getByRole("checkbox", { name: /GDPR/ }) as HTMLInputElement;
    const dora = screen.getByRole("checkbox", { name: /DORA/ }) as HTMLInputElement;
    expect(gdpr.checked).toBe(true);
    expect(dora.checked).toBe(false);
  });

  it("toggling checkboxes and saving submits the expected regulatory_tags array", async () => {
    const user = userEvent.setup();
    mockFrameworks([
      framework({ id: "FRM-1", name: "GDPR", status: "in_force" }),
      framework({ id: "FRM-2", name: "DORA", status: "amended" }),
    ]);
    mockRisk(risk({ regulatory_tags: [] }));
    mutateAsync.mockResolvedValue(risk({ regulatory_tags: ["FRM-2"] }));

    render(<RiskPanel appId="app-1" />);

    await user.click(screen.getByRole("checkbox", { name: /DORA/ }));
    await user.click(screen.getByRole("button", { name: /save/i }));

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ regulatory_tags: ["FRM-2"] })
    );
  });

  it("disambiguates two frameworks sharing the same name by jurisdiction and version", () => {
    mockFrameworks([
      framework({ id: "FRM-1", name: "Data Protection Act", jurisdiction: "UK", version: "2018" }),
      framework({ id: "FRM-2", name: "Data Protection Act", jurisdiction: "NG", version: "2023" }),
    ]);
    mockRisk(risk({ regulatory_tags: ["FRM-1", "FRM-2"] }));

    render(<RiskPanel appId="app-1" />);

    expect(screen.getByText("Data Protection Act (UK, 2018)")).toBeTruthy();
    expect(screen.getByText("Data Protection Act (NG, 2023)")).toBeTruthy();
  });

  it("shows the plain name (no disambiguation) when no other framework shares it", () => {
    mockFrameworks([framework({ id: "FRM-1", name: "GDPR" })]);
    mockRisk(risk({ regulatory_tags: ["FRM-1"] }));

    render(<RiskPanel appId="app-1" />);

    expect(screen.getByText("GDPR")).toBeTruthy();
  });
});
