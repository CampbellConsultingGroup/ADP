// 944-agent-traceability (ADP-12x, US2): an agent's derived compliance status and its mappings.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as complianceApi from "../api/compliance";
import AgentCompliance from "./AgentCompliance";

vi.mock("../api/compliance");
const api = vi.mocked(complianceApi);

function mapping(control_id: string, compliance_status: complianceApi.ComplianceStatus, evidence_ref: string | null = null) {
  return {
    control_id, target_type: "agent" as const, target_id: "ag-1", compliance_status, evidence_ref,
    assessed_at: null, assessed_by: null, created_at: "2026-11-16T00:00:00Z",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.useAllControls.mockReturnValue({
    byId: new Map([
      ["c1", { id: "c1", framework_id: "fw", framework_name: "EU AI Act", code: "Art. 50", title: "Transparency", depth: 0 }],
    ]),
    isLoading: false,
  });
});

describe("AgentCompliance", () => {
  it("shows the derived status and each mapping with its control and framework", () => {
    api.useAgentComplianceMappings.mockReturnValue({
      data: { items: [mapping("c1", "partial", "DPIA-7"), mapping("c-unknown", "compliant")], total: 2, status: "partial" },
      isLoading: false,
    } as never);
    render(<AgentCompliance agentId="ag-1" />);
    expect(screen.getByText("Derived status")).toBeTruthy();
    expect(screen.getAllByText("Partial")).toHaveLength(2);
    expect(screen.getByText(/EU AI Act/)).toBeTruthy();
    expect(screen.getByText(/Art. 50 Transparency/)).toBeTruthy();
    expect(screen.getByText(/evidence DPIA-7/)).toBeTruthy();
    // A control not in the cache falls back to its id.
    expect(screen.getByText(/c-unknown/)).toBeTruthy();
  });

  it("says when no controls are mapped", () => {
    api.useAgentComplianceMappings.mockReturnValue({
      data: { items: [], total: 0, status: "not_assessed" },
      isLoading: false,
    } as never);
    render(<AgentCompliance agentId="ag-1" />);
    expect(screen.getByText("No controls mapped.")).toBeTruthy();
    expect(screen.getByText("Not assessed")).toBeTruthy();
  });
});
