import { describe, it, expect } from "vitest";
import { buildTree } from "./CapabilityTree";
import type { BusinessCapability } from "../api/business";

function cap(partial: Partial<BusinessCapability> & { id: string; name: string; level: 1 | 2 | 3 }): BusinessCapability {
  return {
    parent_id: null,
    description: null,
    position: 0,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    domain_id: null,
    domain_name: null,
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
