// 920-capability-diagram-select: first render-based test for CapabilityNode.tsx
// (previously only exercised indirectly via CapabilityTree.test.tsx). Needs a
// real QueryClientProvider since this component calls useQueryClient()
// directly, mirroring CapabilityTree.test.tsx's own renderWithQueryClient()
// helper.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import CapabilityNode from "./CapabilityNode";
import * as businessApi from "../api/business";
import * as complianceApi from "../api/compliance";
import type { CapabilityTreeNode } from "./CapabilityTree";

vi.mock("../api/business");
vi.mock("../api/compliance");

const mockedBusinessApi = vi.mocked(businessApi);
const mockedComplianceApi = vi.mocked(complianceApi);

function renderWithQueryClient(ui: ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

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

    await userEvent.click(screen.getByRole("button", { name: "Compliance" }));

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

    await userEvent.click(screen.getByRole("button", { name: "Compliance" }));

    screen.getByText("No controls mapped yet.");
  });
});
