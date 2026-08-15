import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TechCapTree, { buildTechCapTree } from "./TechCapTree";
import * as applicationApi from "../api/application";
import type { TechnicalCapability } from "../api/application";

vi.mock("../api/application");

const mockedApplicationApi = vi.mocked(applicationApi);

function techCap(partial: Partial<TechnicalCapability> & { id: string; name: string; level: number }): TechnicalCapability {
  return {
    parent_id: null,
    description: null,
    created_at: "2024-01-01T00:00:00Z",
    strategic_relevance: null,
    ...partial,
  };
}

describe("buildTechCapTree", () => {
  it("returns empty array for empty input", () => {
    expect(buildTechCapTree([])).toEqual([]);
  });

  it("returns single root with no children", () => {
    const result = buildTechCapTree([techCap({ id: "a", name: "A", level: 1 })]);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("a");
    expect(result[0].children).toHaveLength(0);
  });

  it("nests a child under its parent", () => {
    const items: TechnicalCapability[] = [
      techCap({ id: "root", name: "Root", level: 1 }),
      techCap({ id: "child", name: "Child", level: 2, parent_id: "root" }),
    ];
    const tree = buildTechCapTree(items);
    expect(tree).toHaveLength(1);
    expect(tree[0].children).toHaveLength(1);
    expect(tree[0].children[0].id).toBe("child");
  });

  it("nests 3 levels correctly", () => {
    const items: TechnicalCapability[] = [
      techCap({ id: "l1", name: "L1", level: 1 }),
      techCap({ id: "l2", name: "L2", level: 2, parent_id: "l1" }),
      techCap({ id: "l3", name: "L3", level: 3, parent_id: "l2" }),
    ];
    const tree = buildTechCapTree(items);
    expect(tree[0].children[0].children[0].id).toBe("l3");
  });

  it("sorts siblings alphabetically by name at every level", () => {
    const items: TechnicalCapability[] = [
      techCap({ id: "b", name: "Bravo", level: 1 }),
      techCap({ id: "a", name: "Alpha", level: 1 }),
      techCap({ id: "c", name: "Charlie", level: 1 }),
      techCap({ id: "b2", name: "Zulu Child", level: 2, parent_id: "b" }),
      techCap({ id: "a2", name: "Echo Child", level: 2, parent_id: "b" }),
    ];
    const tree = buildTechCapTree(items);
    expect(tree.map((n) => n.id)).toEqual(["a", "b", "c"]);
    const bravo = tree.find((n) => n.id === "b")!;
    expect(bravo.children.map((n) => n.id)).toEqual(["a2", "b2"]);
  });

  it("handles orphaned nodes by excluding them from the tree", () => {
    const items: TechnicalCapability[] = [
      techCap({ id: "root", name: "Root", level: 1 }),
      techCap({ id: "orphan", name: "Orphan", level: 2, parent_id: "nonexistent" }),
    ];
    const tree = buildTechCapTree(items);
    expect(tree).toHaveLength(1);
    expect(tree[0].children).toHaveLength(0);
  });

  it("builds multiple independent roots", () => {
    const items: TechnicalCapability[] = [
      techCap({ id: "a", name: "A", level: 1 }),
      techCap({ id: "b", name: "B", level: 1 }),
    ];
    const tree = buildTechCapTree(items);
    expect(tree).toHaveLength(2);
    expect(tree.map((n) => n.id)).toEqual(["a", "b"]);
  });
});

describe("TechCapTree component", () => {
  const CAPS: TechnicalCapability[] = [
    techCap({ id: "root-a", name: "Cloud Platform", level: 1 }),
    techCap({ id: "child-a", name: "Container Orchestration", level: 2, parent_id: "root-a" }),
  ];

  let createMutateAsync: ReturnType<typeof vi.fn>;
  let updateMutate: ReturnType<typeof vi.fn>;
  let deleteMutate: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    createMutateAsync = vi.fn().mockResolvedValue(techCap({ id: "new", name: "New Cap", level: 1 }));
    updateMutate = vi.fn();
    deleteMutate = vi.fn();

    mockedApplicationApi.useTechCaps.mockReturnValue({
      data: { items: CAPS, total: CAPS.length },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof applicationApi.useTechCaps>);
    mockedApplicationApi.useCreateTechCap.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: createMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof applicationApi.useCreateTechCap>);
    mockedApplicationApi.useUpdateTechCap.mockReturnValue({
      mutate: updateMutate,
      isPending: false,
    } as unknown as ReturnType<typeof applicationApi.useUpdateTechCap>);
    mockedApplicationApi.useDeleteTechCap.mockReturnValue({
      mutate: deleteMutate,
      isPending: false,
    } as unknown as ReturnType<typeof applicationApi.useDeleteTechCap>);

    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("renders the tree with both root and child capabilities", () => {
    render(<TechCapTree />);
    expect(screen.getByText("Cloud Platform")).toBeTruthy();
    expect(screen.getByText("Container Orchestration")).toBeTruthy();
  });

  it("shows the singular/plural capability count correctly", () => {
    render(<TechCapTree />);
    expect(screen.getByText("2 technical capabilities across all levels")).toBeTruthy();
  });

  it("creates a root capability via the + Root form", async () => {
    const user = userEvent.setup();
    render(<TechCapTree />);

    await user.click(screen.getByText("+ Root"));
    await user.type(screen.getByPlaceholderText("Capability name *"), "Data Platform");
    await user.click(screen.getByText("Save"));

    expect(createMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Data Platform", parent_id: null }),
    );
  });

  it("creates a child capability under an existing node via + child", async () => {
    const user = userEvent.setup();
    render(<TechCapTree />);

    // Both root-a (L1) and child-a (L2) can take children (level < 3); the
    // root's own "+ child" button renders first.
    await user.click(screen.getAllByText("+ child")[0]);
    await user.type(screen.getByPlaceholderText("Capability name *"), "Kubernetes");
    await user.click(screen.getByText("Save"));

    expect(createMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Kubernetes", parent_id: "root-a" }),
    );
  });

  it("edits an existing capability's name inline", async () => {
    const user = userEvent.setup();
    render(<TechCapTree />);

    const editButtons = screen.getAllByTitle("Edit");
    await user.click(editButtons[0]);

    const nameInput = screen.getByDisplayValue("Cloud Platform");
    await user.clear(nameInput);
    await user.type(nameInput, "Cloud Infrastructure");
    await user.click(screen.getByTitle("Save"));

    expect(updateMutate).toHaveBeenCalledWith(
      { id: "root-a", body: { name: "Cloud Infrastructure", description: null } },
      expect.anything(),
    );
  });

  it("cancels an inline edit without saving", async () => {
    const user = userEvent.setup();
    render(<TechCapTree />);

    await user.click(screen.getAllByTitle("Edit")[0]);
    const nameInput = screen.getByDisplayValue("Cloud Platform");
    await user.clear(nameInput);
    await user.type(nameInput, "Should Not Save");
    await user.click(screen.getByTitle("Cancel"));

    expect(updateMutate).not.toHaveBeenCalled();
    expect(screen.getByText("Cloud Platform")).toBeTruthy();
  });

  it("changes strategic relevance via the select", async () => {
    const user = userEvent.setup();
    render(<TechCapTree />);

    const selects = screen.getAllByTitle("Strategic relevance");
    await user.selectOptions(selects[0], "1");

    expect(updateMutate).toHaveBeenCalledWith({ id: "root-a", body: { strategic_relevance: 1 } });
  });

  it("deletes a capability after confirmation", async () => {
    const user = userEvent.setup();
    render(<TechCapTree />);

    const deleteButtons = screen.getAllByText("✕");
    await user.click(deleteButtons[0]);

    expect(window.confirm).toHaveBeenCalled();
    expect(deleteMutate).toHaveBeenCalledWith("root-a");
  });

  it("shows an empty state with no capabilities defined", () => {
    mockedApplicationApi.useTechCaps.mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof applicationApi.useTechCaps>);

    render(<TechCapTree />);
    expect(screen.getByText(/No technical capabilities defined/)).toBeTruthy();
  });
});
