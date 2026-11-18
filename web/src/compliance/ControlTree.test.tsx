// COMPLY-01 US3: client-side delete-scope disclosure (research.md D3) — the
// descendant count shown in the confirm dialog is computed from the already-
// fetched tree, and cancelling issues no API call.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ControlTree from "./ControlTree";
import * as complianceApi from "../api/compliance";
import type { ControlNode } from "../api/compliance";
import { renderWithQuery as renderWithQueryClient } from "../../tests/support/apiTestUtils";

vi.mock("../api/compliance");

const mockedApi = vi.mocked(complianceApi);

function makeControl(overrides: Partial<ControlNode> = {}): ControlNode {
  return {
    id: "c1", framework_id: "f1", parent_id: null, code: "Art. 5", title: "Principles",
    description: "...", position: 0, created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z", children: [],
    ...overrides,
  };
}

let deleteMutate: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  deleteMutate = vi.fn();
  mockedApi.useCreateControl.mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useCreateControl>);
  mockedApi.useUpdateControl.mockReturnValue({
    mutate: vi.fn(), isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useUpdateControl>);
  mockedApi.useDeleteControl.mockReturnValue({
    mutate: deleteMutate, isPending: false,
  } as unknown as ReturnType<typeof complianceApi.useDeleteControl>);
  // 925-strategy-compliance-linkage: "Linked Objectives" read-only line, empty by default.
  mockedApi.useFrameworkControlObjectives.mockReturnValue({
    data: new Map(),
  } as unknown as ReturnType<typeof complianceApi.useFrameworkControlObjectives>);
});

describe("ControlTree (COMPLY-01 US3 — delete scope disclosure)", () => {
  it("shows a leaf-control confirm message with no descendant count", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const leaf = makeControl({ code: "Art. 33", children: [] });
    renderWithQueryClient(<ControlTree frameworkId="f1" controls={[leaf]} />);

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(confirmSpy).toHaveBeenCalledWith("Delete control 'Art. 33'?");
    expect(deleteMutate).not.toHaveBeenCalled();
  });

  it("shows the descendant count for a control with children", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const child = makeControl({ id: "c2", code: "Art. 5(1)(a)", parent_id: "c1", children: [] });
    const grandchild = makeControl({ id: "c3", code: "Art. 5(1)(a)(i)", parent_id: "c2", children: [] });
    const parent = makeControl({ id: "c1", code: "Art. 5", children: [{ ...child, children: [grandchild] }] });

    renderWithQueryClient(<ControlTree frameworkId="f1" controls={[parent]} />);

    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

    expect(confirmSpy).toHaveBeenCalledWith(
      "Deleting 'Art. 5' will also remove 2 descendant control(s). Continue?",
    );
    expect(deleteMutate).not.toHaveBeenCalled();
  });

  it("calls the delete mutation when the confirmation is accepted", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const leaf = makeControl({ id: "c9", code: "Art. 33", children: [] });
    renderWithQueryClient(<ControlTree frameworkId="f1" controls={[leaf]} />);

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(deleteMutate).toHaveBeenCalledWith("c9", expect.anything());
  });

  it("renders nested children indented beneath their parent", () => {
    const child = makeControl({ id: "c2", code: "Art. 5(1)(a)", parent_id: "c1", children: [] });
    const parent = makeControl({ id: "c1", code: "Art. 5", children: [child] });
    renderWithQueryClient(<ControlTree frameworkId="f1" controls={[parent]} />);

    // getByText throws if no match is found -- presence is the assertion.
    screen.getByText(/Art\. 5 —/);
    screen.getByText(/Art\. 5\(1\)\(a\) —/);
  });
});

describe("ControlTree linked objectives (ADP-blp.35)", () => {
  it("shows each control's objectives from one framework-wide query", () => {
    mockedApi.useFrameworkControlObjectives.mockReturnValue({
      data: new Map([["c1", [{ id: "o1", statement: "Reduce breach risk" }]]]),
    } as unknown as ReturnType<typeof complianceApi.useFrameworkControlObjectives>);
    const controls = [
      { id: "c1", framework_id: "fw1", parent_id: null, code: "A.1", title: "One", description: "", children: [] },
      { id: "c2", framework_id: "fw1", parent_id: null, code: "A.2", title: "Two", description: "", children: [] },
    ] as unknown as Parameters<typeof ControlTree>[0]["controls"];
    render(<ControlTree frameworkId="fw1" controls={controls} />);
    expect(screen.getByText("Regulatory driver for: Reduce breach risk")).toBeTruthy();
    expect(screen.getAllByText(/Regulatory driver for/)).toHaveLength(1);
    // Every row asks for the same framework: the query cache makes that one request.
    for (const call of mockedApi.useFrameworkControlObjectives.mock.calls) {
      expect(call[0]).toBe("fw1");
    }
  });
});
