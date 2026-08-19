// COMPLY-01 US3: client-side delete-scope disclosure for a framework (research.md D3) —
// the confirm message names the total control count computed from the already-fetched tree.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import FrameworkDetail from "./FrameworkDetail";
import * as complianceApi from "../api/compliance";
import type { ControlNode, RegulatoryFrameworkDetail } from "../api/compliance";

vi.mock("../api/compliance");

const mockedApi = vi.mocked(complianceApi);

function renderWithQueryClient(ui: ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const FRAMEWORK_BASE = {
  id: "f1", name: "GDPR", jurisdiction: "EU", authority: "European Commission",
  version: "2016/679", effective_date: null, source_url: null,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

let deleteMutate: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  deleteMutate = vi.fn();
  mockedApi.useUpdateFramework.mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useUpdateFramework>);
  mockedApi.useDeleteFramework.mockReturnValue({
    mutate: deleteMutate, isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useDeleteFramework>);
  mockedApi.useCreateControl.mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useCreateControl>);
  mockedApi.useUpdateControl.mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useUpdateControl>);
  mockedApi.useDeleteControl.mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useDeleteControl>);
  // COMPLY-04: every test in this file renders FrameworkDetail, which now always calls
  // useFrameworkRollup -- default to "no data yet" so pre-existing tests above are unaffected;
  // the rollup-specific describe block below overrides this per test.
  mockedApi.useFrameworkRollup.mockReturnValue({
    data: undefined, isLoading: false,
  } as unknown as ReturnType<typeof complianceApi.useFrameworkRollup>);
  // 925-strategy-compliance-linkage: "Linked Objectives" read-only line, empty by default.
  mockedApi.useControlObjectives.mockReturnValue({
    data: { items: [], total: 0 },
  } as unknown as ReturnType<typeof complianceApi.useControlObjectives>);
});

describe("FrameworkDetail (COMPLY-01 US3 — delete scope disclosure)", () => {
  it("confirms with the total control count across every level before deleting", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const child: ControlNode = {
      id: "c2", framework_id: "f1", parent_id: "c1", code: "Art. 5(1)(a)", title: "X",
      description: null, position: 0, created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z", children: [],
    };
    const parent: ControlNode = {
      id: "c1", framework_id: "f1", parent_id: null, code: "Art. 5", title: "Principles",
      description: null, position: 0, created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z", children: [child],
    };
    const detail: RegulatoryFrameworkDetail = { ...FRAMEWORK_BASE, controls: [parent] };
    mockedApi.useFramework.mockReturnValue({
      data: detail, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useFramework>);

    renderWithQueryClient(<FrameworkDetail frameworkId="f1" onBack={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Delete Framework" }));

    expect(confirmSpy).toHaveBeenCalledWith(
      "Deleting 'GDPR' will also remove 2 control(s) recorded under it. Continue?",
    );
    expect(deleteMutate).not.toHaveBeenCalled();
  });

  it("calls delete and navigates back when the confirmation is accepted", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onBack = vi.fn();
    const detail: RegulatoryFrameworkDetail = { ...FRAMEWORK_BASE, controls: [] };
    mockedApi.useFramework.mockReturnValue({
      data: detail, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useFramework>);
    deleteMutate.mockImplementation((_id, opts) => opts?.onSuccess?.());

    renderWithQueryClient(<FrameworkDetail frameworkId="f1" onBack={onBack} />);

    await userEvent.click(screen.getByRole("button", { name: "Delete Framework" }));

    expect(deleteMutate).toHaveBeenCalledWith("f1", expect.anything());
    expect(onBack).toHaveBeenCalled();
  });
});

describe("FrameworkDetail (security review finding, 923-derived-compliance-status — source_url rendering)", () => {
  it("renders the Source link for an https source_url", () => {
    const detail: RegulatoryFrameworkDetail = {
      ...FRAMEWORK_BASE, source_url: "https://example.com/reg", controls: [],
    };
    mockedApi.useFramework.mockReturnValue({
      data: detail, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useFramework>);

    renderWithQueryClient(<FrameworkDetail frameworkId="f1" onBack={vi.fn()} />);

    const link = screen.getByRole("link", { name: "Source" });
    expect(link.getAttribute("href")).toBe("https://example.com/reg");
  });

  it("does not render a link for a javascript: source_url (defense-in-depth backstop)", () => {
    // The backend now rejects this at write time (adp.compliance.models), but this asserts
    // the frontend never trusts already-stored data blindly either.
    const detail: RegulatoryFrameworkDetail = {
      ...FRAMEWORK_BASE, source_url: "javascript:alert(document.cookie)", controls: [],
    };
    mockedApi.useFramework.mockReturnValue({
      data: detail, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useFramework>);

    renderWithQueryClient(<FrameworkDetail frameworkId="f1" onBack={vi.fn()} />);

    expect(screen.queryByRole("link", { name: "Source" })).toBeNull();
  });
});

describe("FrameworkDetail (COMPLY-04 US1 — coverage rollup)", () => {
  it("renders all five status-bucket counts", () => {
    const detail: RegulatoryFrameworkDetail = { ...FRAMEWORK_BASE, controls: [] };
    mockedApi.useFramework.mockReturnValue({
      data: detail, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useFramework>);
    mockedApi.useFrameworkRollup.mockReturnValue({
      data: {
        framework_id: "f1",
        entity_counts: {
          compliant_count: 2, partial_count: 4, non_compliant_count: 1,
          not_assessed_count: 0, not_applicable_count: 3,
        },
        organization_status: null,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useFrameworkRollup>);

    renderWithQueryClient(<FrameworkDetail frameworkId="f1" onBack={vi.fn()} />);

    screen.getByText("2");
    screen.getByText("Compliant");
    screen.getByText("1");
    screen.getByText("Non-compliant");
    screen.getByText("3");
    screen.getByText("Not applicable");
    screen.getByText("4");
    screen.getByText("Partial");
  });

  it("renders the estate-wide obligation line only when present", () => {
    const detail: RegulatoryFrameworkDetail = { ...FRAMEWORK_BASE, controls: [] };
    mockedApi.useFramework.mockReturnValue({
      data: detail, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useFramework>);
    mockedApi.useFrameworkRollup.mockReturnValue({
      data: {
        framework_id: "f1",
        entity_counts: {
          compliant_count: 0, partial_count: 0, non_compliant_count: 0,
          not_assessed_count: 0, not_applicable_count: 0,
        },
        organization_status: "partial",
      },
      isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useFrameworkRollup>);

    renderWithQueryClient(<FrameworkDetail frameworkId="f1" onBack={vi.fn()} />);

    screen.getByText("Estate-wide obligation:");
    screen.getByText("Partial", { selector: "strong" });
  });

  it("does not render an obligation line when organization_status is null", () => {
    const detail: RegulatoryFrameworkDetail = { ...FRAMEWORK_BASE, controls: [] };
    mockedApi.useFramework.mockReturnValue({
      data: detail, isLoading: false, error: null,
    } as unknown as ReturnType<typeof complianceApi.useFramework>);
    mockedApi.useFrameworkRollup.mockReturnValue({
      data: {
        framework_id: "f1",
        entity_counts: {
          compliant_count: 0, partial_count: 0, non_compliant_count: 0,
          not_assessed_count: 0, not_applicable_count: 0,
        },
        organization_status: null,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useFrameworkRollup>);

    renderWithQueryClient(<FrameworkDetail frameworkId="f1" onBack={vi.fn()} />);

    expect(screen.queryByText("Estate-wide obligation:")).toBeNull();
  });
});
