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

  it("sorts siblings by position", () => {
    const items: BusinessCapability[] = [
      cap({ id: "b", name: "B", level: 1, position: 2 }),
      cap({ id: "a", name: "A", level: 1, position: 1 }),
      cap({ id: "c", name: "C", level: 1, position: 3 }),
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
