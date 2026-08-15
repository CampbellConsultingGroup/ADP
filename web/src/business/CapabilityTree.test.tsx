import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import CapabilityTree, { buildTree } from "./CapabilityTree";
import * as businessApi from "../api/business";
import type { BusinessCapability } from "../api/business";

vi.mock("../api/business");

const mockedBusinessApi = vi.mocked(businessApi);

// CapabilityTree.tsx calls useQueryClient() directly (for the portfolio-
// review invalidate callback) -- a real QueryClientProvider is needed,
// unlike this session's usual vi.mock(hooks-module)-only convention.
function renderWithQueryClient(ui: ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function cap(partial: Partial<BusinessCapability> & { id: string; name: string; level: 1 | 2 | 3 }): BusinessCapability {
  return {
    parent_id: null,
    description: null,
    position: 0,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    domain_id: null,
    domain_name: null,
    strategic_relevance: null,
    maturity_level: null,
    ...partial,
  };
}

describe("buildTree", () => {
  it("returns empty array for empty input", () => {
    expect(buildTree([])).toEqual([]);
  });

  it("returns single root with no children", () => {
    const result = buildTree([cap({ id: "a", name: "A", level: 1 })]);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("a");
    expect(result[0].children).toHaveLength(0);
  });

  it("nests a child under its parent", () => {
    const items: BusinessCapability[] = [
      cap({ id: "root", name: "Root", level: 1 }),
      cap({ id: "child", name: "Child", level: 2, parent_id: "root" }),
    ];
    const tree = buildTree(items);
    expect(tree).toHaveLength(1);
    expect(tree[0].children).toHaveLength(1);
    expect(tree[0].children[0].id).toBe("child");
  });

  it("nests 3 levels correctly", () => {
    const items: BusinessCapability[] = [
      cap({ id: "l1", name: "L1", level: 1 }),
      cap({ id: "l2", name: "L2", level: 2, parent_id: "l1" }),
      cap({ id: "l3", name: "L3", level: 3, parent_id: "l2" }),
    ];
    const tree = buildTree(items);
    expect(tree[0].children[0].children[0].id).toBe("l3");
  });

  it("sorts siblings alphabetically by name, ignoring position", () => {
    // position deliberately set opposite to name order -- a stale, unused
    // field with no editing UI (bug report, 2026-08-15) must not affect the
    // result.
    const items: BusinessCapability[] = [
      cap({ id: "b", name: "Bravo", level: 1, position: 1 }),
      cap({ id: "a", name: "Alpha", level: 1, position: 2 }),
      cap({ id: "c", name: "Charlie", level: 1, position: 0 }),
    ];
    const tree = buildTree(items);
    expect(tree.map((n) => n.id)).toEqual(["a", "b", "c"]);
  });

  it("handles orphaned nodes by excluding them from the tree", () => {
    const items: BusinessCapability[] = [
      cap({ id: "root", name: "Root", level: 1 }),
      cap({ id: "orphan", name: "Orphan", level: 2, parent_id: "nonexistent" }),
    ];
    const tree = buildTree(items);
    expect(tree).toHaveLength(1);
    expect(tree[0].children).toHaveLength(0);
  });

  it("builds multiple independent roots", () => {
    const items: BusinessCapability[] = [
      cap({ id: "a", name: "A", level: 1, position: 1 }),
      cap({ id: "b", name: "B", level: 1, position: 2 }),
    ];
    const tree = buildTree(items);
    expect(tree).toHaveLength(2);
    expect(tree.map((n) => n.id)).toEqual(["a", "b"]);
  });
});

describe("CapabilityTree: orphan badge and filter (918-strategy-rollups)", () => {
  const CAPS: BusinessCapability[] = [
    cap({ id: "linked", name: "Linked Cap", level: 1 }),
    cap({ id: "orphan", name: "Orphan Cap", level: 1, position: 1 }),
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockedBusinessApi.useCapabilities.mockReturnValue({
      data: { items: CAPS, total: 2 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof businessApi.useCapabilities>);
    mockedBusinessApi.useOrphanReport.mockReturnValue({
      data: { orphan_capabilities: [CAPS[1]], orphan_value_streams: [] },
    } as unknown as ReturnType<typeof businessApi.useOrphanReport>);
    mockedBusinessApi.useUpdateCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useUpdateCapability>);
    mockedBusinessApi.useDeleteCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useDeleteCapability>);
  });

  it("shows a 'no strategic linkage' badge only on the orphaned capability", () => {
    renderWithQueryClient(<CapabilityTree />);

    expect(screen.getAllByText("no strategic linkage")).toHaveLength(1);
  });

  it("toggling 'Show orphans only' narrows the tree to just orphaned capabilities", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<CapabilityTree />);

    expect(screen.getByText("Linked Cap")).toBeTruthy();
    expect(screen.getByText("Orphan Cap")).toBeTruthy();

    await user.click(screen.getByText("Show orphans only"));

    expect(screen.queryByText("Linked Cap")).toBeNull();
    expect(screen.getByText("Orphan Cap")).toBeTruthy();
  });
});

describe("CapabilityTree: focusCapabilityId scroll/highlight (043-capability-heat-map US3)", () => {
  const CAPS: BusinessCapability[] = [
    cap({ id: "a", name: "Cap A", level: 1 }),
    cap({ id: "b", name: "Cap B", level: 1, position: 1 }),
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockedBusinessApi.useCapabilities.mockReturnValue({
      data: { items: CAPS, total: 2 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof businessApi.useCapabilities>);
    mockedBusinessApi.useOrphanReport.mockReturnValue({
      data: { orphan_capabilities: [], orphan_value_streams: [] },
    } as unknown as ReturnType<typeof businessApi.useOrphanReport>);
    mockedBusinessApi.useUpdateCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useUpdateCapability>);
    mockedBusinessApi.useDeleteCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useDeleteCapability>);
    // jsdom does not implement scrollIntoView.
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("scrolls the matching node into view when focusCapabilityId is set", () => {
    renderWithQueryClient(<CapabilityTree focusCapabilityId="b" />);

    const node = document.getElementById("cap-b");
    expect(node).toBeTruthy();
    expect(node!.scrollIntoView).toHaveBeenCalled();
  });

  it("does not scroll anything when focusCapabilityId is null", () => {
    renderWithQueryClient(<CapabilityTree focusCapabilityId={null} />);

    const nodeA = document.getElementById("cap-a");
    const nodeB = document.getElementById("cap-b");
    expect(nodeA!.scrollIntoView).not.toHaveBeenCalled();
    expect(nodeB!.scrollIntoView).not.toHaveBeenCalled();
  });

  it("applies a highlight treatment only to the focused node", () => {
    renderWithQueryClient(<CapabilityTree focusCapabilityId="b" />);

    const nodeA = document.getElementById("cap-a")!;
    const nodeB = document.getElementById("cap-b")!;
    expect(nodeB.getAttribute("data-focused")).toBe("true");
    expect(nodeA.getAttribute("data-focused")).not.toBe("true");
  });
});

describe("CapabilityTree: multi-select + Generate Diagram from Selected (920-capability-diagram-select US1)", () => {
  const CAPS: BusinessCapability[] = [
    cap({ id: "root-a", name: "Underwriting", level: 1 }),
    cap({ id: "child-a", name: "Risk Assessment", level: 2, parent_id: "root-a", position: 1 }),
    cap({ id: "root-b", name: "Claims", level: 1, position: 1 }),
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockedBusinessApi.useCapabilities.mockReturnValue({
      data: { items: CAPS, total: CAPS.length },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof businessApi.useCapabilities>);
    mockedBusinessApi.useOrphanReport.mockReturnValue({
      data: { orphan_capabilities: [], orphan_value_streams: [] },
    } as unknown as ReturnType<typeof businessApi.useOrphanReport>);
    mockedBusinessApi.useUpdateCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useUpdateCapability>);
    mockedBusinessApi.useDeleteCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useDeleteCapability>);
  });

  it("disables 'Generate Diagram from Selected' when nothing is checked", () => {
    renderWithQueryClient(<CapabilityTree onGenerateDiagram={vi.fn()} />);

    const button = screen.getByText("Generate Diagram from Selected") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("generates a diagram from exactly the checked capabilities, spanning branches", async () => {
    const onGenerateDiagram = vi.fn();
    const user = userEvent.setup();
    renderWithQueryClient(<CapabilityTree onGenerateDiagram={onGenerateDiagram} />);

    // Render order (name-sorted tree walk): root-b (Claims), root-a
    // (Underwriting), child-a (Risk Assessment, nested under root-a).
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]); // root-b (Claims)
    await user.click(checkboxes[1]); // root-a (Underwriting) -- a different branch

    const button = screen.getByText("Generate Diagram from Selected") as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    await user.click(button);

    expect(onGenerateDiagram).toHaveBeenCalledTimes(1);
    const seed = onGenerateDiagram.mock.calls[0][0];
    expect(seed.model.nodes).toHaveLength(2);
    expect(seed.model.nodes.map((n: { label: string }) => n.label).sort()).toEqual(["Claims", "Underwriting"]);
    // root-a and root-b have no relationship to each other -- zero edges.
    expect(seed.model.edges).toHaveLength(0);
  });

  it("includes the hierarchy edge when a checked parent and checked child are both selected", async () => {
    const onGenerateDiagram = vi.fn();
    const user = userEvent.setup();
    renderWithQueryClient(<CapabilityTree onGenerateDiagram={onGenerateDiagram} />);

    // Render order (name-sorted tree walk): root-b (Claims), root-a
    // (Underwriting), child-a (Risk Assessment, nested under root-a).
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[1]); // root-a (Underwriting)
    await user.click(checkboxes[2]); // child-a (root-a's real child)
    await user.click(screen.getByText("Generate Diagram from Selected"));

    const seed = onGenerateDiagram.mock.calls[0][0];
    expect(seed.model.nodes).toHaveLength(2);
    expect(seed.model.edges).toHaveLength(1);
  });
});

describe("CapabilityTree: selection count and clear (920-capability-diagram-select US2)", () => {
  const CAPS: BusinessCapability[] = [
    cap({ id: "root-a", name: "Underwriting", level: 1 }),
    cap({ id: "root-b", name: "Claims", level: 1, position: 1 }),
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockedBusinessApi.useCapabilities.mockReturnValue({
      data: { items: CAPS, total: CAPS.length },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof businessApi.useCapabilities>);
    mockedBusinessApi.useOrphanReport.mockReturnValue({
      data: { orphan_capabilities: [], orphan_value_streams: [] },
    } as unknown as ReturnType<typeof businessApi.useOrphanReport>);
    mockedBusinessApi.useUpdateCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useUpdateCapability>);
    mockedBusinessApi.useDeleteCapability.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof businessApi.useDeleteCapability>);
  });

  it("shows no selection count and no Clear action when nothing is checked", () => {
    renderWithQueryClient(<CapabilityTree />);

    expect(screen.queryByText(/selected/)).toBeNull();
    expect(screen.queryByText("Clear selection")).toBeNull();
  });

  it("shows a count reflecting the number of checked capabilities", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<CapabilityTree />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    expect(screen.getByText(/2 selected/)).toBeTruthy();
  });

  it("unchecks every row and resets the count when Clear selection is used", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<CapabilityTree />);

    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);
    expect(screen.getByText(/2 selected/)).toBeTruthy();

    await user.click(screen.getByText("Clear selection"));

    expect(screen.queryByText(/selected/)).toBeNull();
    expect(checkboxes[0].checked).toBe(false);
    expect(checkboxes[1].checked).toBe(false);
  });
});
