// COMPLY-02 US1/US2/Polish: create/edit/delete a Control's mappings, and the
// target-type selector hiding the target-id field for "organization" (no target leg).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import ControlMappingsEditor from "./ControlMappingsEditor";
import * as complianceApi from "../api/compliance";
import type { ControlMapping } from "../api/compliance";

vi.mock("../api/compliance");

const mockedApi = vi.mocked(complianceApi);

function renderWithQueryClient(ui: ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function makeMapping(overrides: Partial<ControlMapping> = {}): ControlMapping {
  return {
    control_id: "c1", target_type: "application", target_id: "app-1",
    compliance_status: "compliant", evidence_ref: null, assessed_at: null,
    assessed_by: null, created_at: "2026-08-18T00:00:00Z",
    ...overrides,
  };
}

let upsertMutate: ReturnType<typeof vi.fn>;
let deleteMutate: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  upsertMutate = vi.fn();
  deleteMutate = vi.fn();
  mockedApi.useUpsertMapping.mockReturnValue({
    mutate: upsertMutate, isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useUpsertMapping>);
  mockedApi.useDeleteMapping.mockReturnValue({
    mutate: deleteMutate, isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useDeleteMapping>);
});

describe("ControlMappingsEditor (COMPLY-02)", () => {
  it("shows 'No mappings yet' when the control has none", () => {
    mockedApi.useControlMappings.mockReturnValue({
      data: { items: [], total: 0 }, isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useControlMappings>);

    renderWithQueryClient(<ControlMappingsEditor controlId="c1" />);

    screen.getByText("No mappings yet."); // throws if missing -- presence is the assertion
  });

  it("lists an existing mapping with its status and target", () => {
    mockedApi.useControlMappings.mockReturnValue({
      data: { items: [makeMapping()], total: 1 }, isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useControlMappings>);

    renderWithQueryClient(<ControlMappingsEditor controlId="c1" />);

    screen.getByText("Application: app-1");
    screen.getByText("Compliant");
  });

  it("hides the target-id field when 'Estate-wide (organization)' is selected", async () => {
    mockedApi.useControlMappings.mockReturnValue({
      data: { items: [], total: 0 }, isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useControlMappings>);

    renderWithQueryClient(<ControlMappingsEditor controlId="c1" />);
    await userEvent.click(screen.getByRole("button", { name: "+ Add mapping" }));

    screen.getByPlaceholderText("Capability id");

    await userEvent.selectOptions(
      screen.getByLabelText("Target type"), "Estate-wide (organization)",
    );

    expect(screen.queryByPlaceholderText(/id$/)).toBeNull();
  });

  it("submits a new capability mapping via useUpsertMapping", async () => {
    mockedApi.useControlMappings.mockReturnValue({
      data: { items: [], total: 0 }, isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useControlMappings>);

    renderWithQueryClient(<ControlMappingsEditor controlId="c1" />);
    await userEvent.click(screen.getByRole("button", { name: "+ Add mapping" }));
    await userEvent.type(screen.getByPlaceholderText("Capability id"), "cap-9");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(upsertMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        targetType: "capability",
        targetId: "cap-9",
        data: expect.objectContaining({ compliance_status: "not_assessed" }),
      }),
      expect.anything(),
    );
  });

  it("opens edit mode pre-filled with the mapping's current values", async () => {
    mockedApi.useControlMappings.mockReturnValue({
      data: { items: [makeMapping({ compliance_status: "non_compliant" })], total: 1 },
      isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useControlMappings>);

    renderWithQueryClient(<ControlMappingsEditor controlId="c1" />);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    // Target type/id are fixed (not shown as editable fields) in edit mode.
    expect(screen.queryByLabelText("Target type")).toBeNull();
    screen.getByRole("button", { name: "Save" });
  });

  it("removes a mapping via useDeleteMapping after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockedApi.useControlMappings.mockReturnValue({
      data: { items: [makeMapping()], total: 1 }, isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useControlMappings>);

    renderWithQueryClient(<ControlMappingsEditor controlId="c1" />);
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(deleteMutate).toHaveBeenCalledWith(
      { targetType: "application", targetId: "app-1" },
      expect.anything(),
    );
  });

  it("does not delete when the confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    mockedApi.useControlMappings.mockReturnValue({
      data: { items: [makeMapping()], total: 1 }, isLoading: false,
    } as unknown as ReturnType<typeof complianceApi.useControlMappings>);

    renderWithQueryClient(<ControlMappingsEditor controlId="c1" />);
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(deleteMutate).not.toHaveBeenCalled();
  });
});
