// ADP-914.7: unit tests for the two pure "generate a diagram seed from ADP's
// own business data" functions. Pure functions -- no rendering, no mocking.

import { describe, expect, it } from "vitest";
import { generateFromValueStream, generateFromCapabilitySubtree, generateFromCapabilities } from "./generators";
import type { ValueStreamDetail, ValueStreamStage, BusinessCapability } from "../api/business";
import type { CapabilityTreeNode } from "../business/CapabilityTree";

function stage(id: string, name: string, position: number): ValueStreamStage {
  return { id, value_stream_id: "vs-1", name, description: null, position };
}

function valueStream(stages: ValueStreamStage[]): ValueStreamDetail {
  return {
    id: "vs-1",
    name: "Quote to Bind",
    description: null,
    stakeholder: null,
    position: 0,
    created_at: "2026-08-11T00:00:00Z",
    updated_at: "2026-08-11T00:00:00Z",
    stages,
  };
}

describe("generateFromValueStream", () => {
  it("produces one node per stage (in position order) and sequential edges for a 3-stage value stream", () => {
    const vs = valueStream([
      stage("s3", "Bind", 2),
      stage("s1", "Intake", 0),
      stage("s2", "Underwrite", 1),
    ]);

    const seed = generateFromValueStream(vs);

    expect(seed.title).toBe("Quote to Bind");
    expect(seed.diagramType).toBe("flowchart");
    expect(seed.model.nodes).toHaveLength(3);
    expect(seed.model.nodes.map((n) => n.label)).toEqual(["Intake", "Underwrite", "Bind"]);
    expect(seed.model.edges).toHaveLength(2);

    const [n0, n1, n2] = seed.model.nodes;
    expect(seed.model.edges[0]).toMatchObject({ sourceId: n0.id, targetId: n1.id });
    expect(seed.model.edges[1]).toMatchObject({ sourceId: n1.id, targetId: n2.id });
  });

  it("produces a single node and zero edges for a 1-stage value stream", () => {
    const vs = valueStream([stage("s1", "Intake", 0)]);
    const seed = generateFromValueStream(vs);
    expect(seed.model.nodes).toHaveLength(1);
    expect(seed.model.edges).toHaveLength(0);
  });

  it("produces zero nodes and zero edges for a value stream with no stages (spec Edge Case)", () => {
    const vs = valueStream([]);
    const seed = generateFromValueStream(vs);
    expect(seed.model.nodes).toHaveLength(0);
    expect(seed.model.edges).toHaveLength(0);
    expect(seed.title).toBe("Quote to Bind");
  });
});

function capNode(id: string, name: string, children: CapabilityTreeNode[] = []): CapabilityTreeNode {
  return {
    id,
    name,
    description: null,
    level: children.length > 0 || id === "root" ? 1 : 3,
    parent_id: null,
    position: 0,
    created_at: "2026-08-11T00:00:00Z",
    updated_at: "2026-08-11T00:00:00Z",
    domain_id: null,
    domain_name: null,
    strategic_relevance: null,
    maturity_level: null,
    children,
  };
}

describe("generateFromCapabilitySubtree", () => {
  it("produces one node per capability and parent->child edges for a 3-level chain", () => {
    const grandchild = capNode("gc", "Rating Engine");
    const child = capNode("c", "Risk Assessment", [grandchild]);
    const root = capNode("root", "Underwriting", [child]);

    const seed = generateFromCapabilitySubtree(root);

    expect(seed.title).toBe("Underwriting");
    expect(seed.diagramType).toBe("flowchart");
    expect(seed.model.nodes).toHaveLength(3);
    expect(seed.model.nodes.map((n) => n.label)).toEqual(["Underwriting", "Risk Assessment", "Rating Engine"]);
    expect(seed.model.edges).toHaveLength(2);

    const [rootNode, childNode, grandchildNode] = seed.model.nodes;
    expect(seed.model.edges).toContainEqual(expect.objectContaining({ sourceId: rootNode.id, targetId: childNode.id }));
    expect(seed.model.edges).toContainEqual(expect.objectContaining({ sourceId: childNode.id, targetId: grandchildNode.id }));
  });

  it("produces a single node and zero edges for a leaf capability (spec Edge Case)", () => {
    const leaf = capNode("leaf", "Rating Engine");
    const seed = generateFromCapabilitySubtree(leaf);
    expect(seed.model.nodes).toHaveLength(1);
    expect(seed.model.edges).toHaveLength(0);
  });

  it("both direct children point to their shared parent, not to each other", () => {
    const childA = capNode("a", "Risk Assessment");
    const childB = capNode("b", "Pricing");
    const root = capNode("root", "Underwriting", [childA, childB]);

    const seed = generateFromCapabilitySubtree(root);

    expect(seed.model.nodes).toHaveLength(3);
    expect(seed.model.edges).toHaveLength(2);
    const [rootNode, aNode, bNode] = seed.model.nodes;
    expect(seed.model.edges).toContainEqual(expect.objectContaining({ sourceId: rootNode.id, targetId: aNode.id }));
    expect(seed.model.edges).toContainEqual(expect.objectContaining({ sourceId: rootNode.id, targetId: bNode.id }));
    expect(seed.model.edges.some((e) => e.sourceId === aNode.id && e.targetId === bNode.id)).toBe(false);
  });
});

function flatCap(id: string, name: string, parentId: string | null = null): BusinessCapability {
  return {
    id,
    name,
    description: null,
    level: parentId ? 2 : 1,
    parent_id: parentId,
    position: 0,
    created_at: "2026-08-14T00:00:00Z",
    updated_at: "2026-08-14T00:00:00Z",
    domain_id: null,
    domain_name: null,
    strategic_relevance: null,
    maturity_level: null,
  };
}

// 920-capability-diagram-select
describe("generateFromCapabilities", () => {
  it("produces one node per selected capability", () => {
    const selected = [
      flatCap("a", "Risk Assessment"),
      flatCap("b", "Pricing"),
      flatCap("c", "Underwriting"),
    ];

    const seed = generateFromCapabilities(selected);

    expect(seed.diagramType).toBe("flowchart");
    expect(seed.model.nodes).toHaveLength(3);
    expect(seed.model.nodes.map((n) => n.label).sort()).toEqual(["Pricing", "Risk Assessment", "Underwriting"]);
  });

  it("adds an edge only between two selected capabilities with a direct parent-child relationship", () => {
    // root -> child is a real relationship; "unrelated" shares no relationship with either.
    const root = flatCap("root", "Underwriting");
    const child = flatCap("child", "Risk Assessment", "root");
    const unrelated = flatCap("unrelated", "Merchandising");

    const seed = generateFromCapabilities([root, child, unrelated]);

    expect(seed.model.nodes).toHaveLength(3);
    expect(seed.model.edges).toHaveLength(1);
    const rootNode = seed.model.nodes.find((n) => n.label === "Underwriting")!;
    const childNode = seed.model.nodes.find((n) => n.label === "Risk Assessment")!;
    expect(seed.model.edges[0]).toMatchObject({ sourceId: rootNode.id, targetId: childNode.id });
  });

  it("does not add an edge when a selected capability's parent is not also selected (spec Edge Case)", () => {
    // child's real parent ("root") is NOT part of the selection.
    const child = flatCap("child", "Risk Assessment", "root");
    const other = flatCap("other", "Pricing");

    const seed = generateFromCapabilities([child, other]);

    expect(seed.model.nodes).toHaveLength(2);
    expect(seed.model.edges).toHaveLength(0);
  });

  it("titles a single-capability selection with that capability's own name (SC-004 parity)", () => {
    const seed = generateFromCapabilities([flatCap("a", "Risk Assessment")]);

    expect(seed.title).toBe("Risk Assessment");
    expect(seed.model.nodes).toHaveLength(1);
    expect(seed.model.edges).toHaveLength(0);
  });

  it("titles a multi-capability selection generically", () => {
    const seed = generateFromCapabilities([flatCap("a", "Risk Assessment"), flatCap("b", "Pricing")]);

    expect(seed.title).toBe("Capabilities Diagram");
  });

  it("produces zero nodes and zero edges for an empty selection", () => {
    const seed = generateFromCapabilities([]);

    expect(seed.model.nodes).toHaveLength(0);
    expect(seed.model.edges).toHaveLength(0);
  });
});
