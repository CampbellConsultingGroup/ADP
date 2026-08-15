// Regression test for a bug report (2026-08-15, "Assigning a L1 capability
// to a Domain is not working"). Root cause: the "Unassigned L1 capabilities"
// list hardcoded CapabilityRow's domainId prop to `null` instead of passing
// the domain actually being viewed -- so clicking "Assign" always called
// mutate(null) (assign to no domain, a no-op) rather than mutate(domainId).
// Mirrors CapabilityTree.test.tsx's vi.mock("../api/business") convention.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DomainDetail from "./DomainDetail";
import * as businessApi from "../api/business";
import type { DomainDetail as DomainDetailType, BusinessCapability } from "../api/business";

vi.mock("../api/business");

const mockedBusinessApi = vi.mocked(businessApi);

const DOMAIN: DomainDetailType = {
  id: "dom-1",
  name: "Human Resources",
  scope_statement: "Workforce management, payroll, and talent.",
  classification: "commodity",
  org_unit: "People",
  risk_flags: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  capabilities: [{ capability_id: "cap-assigned", name: "Talent Acquisition", level: 1 }],
};

const CAPS: BusinessCapability[] = [
  {
    id: "cap-assigned",
    name: "Talent Acquisition",
    description: null,
    level: 1,
    parent_id: null,
    position: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    domain_id: "dom-1",
    domain_name: "Human Resources",
    strategic_relevance: null,
    maturity_level: null,
  },
  {
    id: "cap-unassigned",
    name: "Diag Capability",
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
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockedBusinessApi.useDomain.mockReturnValue({
    data: DOMAIN,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof businessApi.useDomain>);
  mockedBusinessApi.useCapabilities.mockReturnValue({
    data: { items: CAPS, total: CAPS.length },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof businessApi.useCapabilities>);
  mockedBusinessApi.useUpdateDomain.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof businessApi.useUpdateDomain>);
});

describe("DomainDetail: capability assignment", () => {
  it("calls assign with the currently-viewed domain's id, not null (regression, 2026-08-15)", async () => {
    const mutate = vi.fn();
    mockedBusinessApi.useAssignCapabilityDomain.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useAssignCapabilityDomain>);

    const user = userEvent.setup();
    render(<DomainDetail domainId="dom-1" onBack={vi.fn()} />);

    // "Diag Capability" is unassigned -- its Assign button must pass "dom-1"
    // (the domain being viewed), not the hardcoded null the bug shipped.
    const row = screen.getByText("Diag Capability").closest("div")!;
    await user.click(row.querySelector("button")!);

    expect(mutate).toHaveBeenCalledWith("dom-1", expect.anything());
  });

  it("calls unassign with null when Remove is clicked on an assigned capability", async () => {
    const mutate = vi.fn();
    mockedBusinessApi.useAssignCapabilityDomain.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useAssignCapabilityDomain>);

    const user = userEvent.setup();
    render(<DomainDetail domainId="dom-1" onBack={vi.fn()} />);

    const row = screen.getByText("Talent Acquisition").closest("div")!;
    await user.click(row.querySelector("button")!);

    expect(mutate).toHaveBeenCalledWith(null, expect.anything());
  });

  it("renders assigned and unassigned capabilities in their respective sections", () => {
    mockedBusinessApi.useAssignCapabilityDomain.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useAssignCapabilityDomain>);

    render(<DomainDetail domainId="dom-1" onBack={vi.fn()} />);

    expect(screen.getByText("Assigned L1 Capabilities (1)")).toBeTruthy();
    expect(screen.getByText("Talent Acquisition")).toBeTruthy();
    expect(screen.getByText("Diag Capability")).toBeTruthy();
  });
});
