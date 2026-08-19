// COMPLY-02 US3: reverse-lookup panel for an Application's mapped Controls, incl. the
// READ_APPLICATION_GOVERNANCE 403 state (mirrors GovernancePanel.tsx's own error-handling
// shape). No pre-existing ApplicationDetail.test.tsx to extend (confirmed by direct search) --
// testing the new standalone panel directly is more proportionate than authoring a full
// ApplicationDetail test suite from scratch just to reach this one new tab.

import { describe, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import ApplicationComplianceMappings from "./ApplicationComplianceMappings";
import * as complianceApi from "../api/compliance";
import { ApiError } from "../api/client";

vi.mock("../api/compliance");

const mockedApi = vi.mocked(complianceApi);

function renderWithQueryClient(ui: ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ApplicationComplianceMappings (COMPLY-02 US3)", () => {
  it("shows a loading state", () => {
    mockedApi.useApplicationComplianceMappings.mockReturnValue({
      data: undefined, isLoading: true, error: null,
    } as unknown as ReturnType<typeof complianceApi.useApplicationComplianceMappings>);

    renderWithQueryClient(<ApplicationComplianceMappings appId="app-1" />);

    screen.getByText("Loading…");
  });

  it("shows the permission-denied message on a 403", () => {
    mockedApi.useApplicationComplianceMappings.mockReturnValue({
      data: undefined, isLoading: false,
      error: new ApiError(403, "GET .../compliance-mappings failed: 403"),
    } as unknown as ReturnType<typeof complianceApi.useApplicationComplianceMappings>);

    renderWithQueryClient(<ApplicationComplianceMappings appId="app-1" />);

    screen.getByText("You don't have permission to view compliance mappings for this application.");
  });

  it("shows a generic error message on a non-403 failure", () => {
    mockedApi.useApplicationComplianceMappings.mockReturnValue({
      data: undefined, isLoading: false,
      error: new ApiError(500, "GET .../compliance-mappings failed: 500"),
    } as unknown as ReturnType<typeof complianceApi.useApplicationComplianceMappings>);

    renderWithQueryClient(<ApplicationComplianceMappings appId="app-1" />);

    screen.getByText("Could not load compliance mappings.");
  });

  it("shows 'No controls mapped yet' when there are none", () => {
    mockedApi.useApplicationComplianceMappings.mockReturnValue({
      data: { items: [], total: 0 }, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useApplicationComplianceMappings>);

    renderWithQueryClient(<ApplicationComplianceMappings appId="app-1" />);

    screen.getByText("No controls mapped yet.");
  });

  it("lists mapped controls with their status", () => {
    mockedApi.useApplicationComplianceMappings.mockReturnValue({
      data: {
        items: [
          {
            control_id: "Art. 32", target_type: "application", target_id: "app-1",
            compliance_status: "non_compliant", evidence_ref: null, assessed_at: null,
            assessed_by: null, created_at: "2026-08-18T00:00:00Z",
          },
        ],
        total: 1,
      },
      isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useApplicationComplianceMappings>);

    renderWithQueryClient(<ApplicationComplianceMappings appId="app-1" />);

    screen.getByText("Art. 32");
    screen.getByText("non compliant");
  });
});
