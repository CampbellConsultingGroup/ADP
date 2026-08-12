// ADP-SPEC-054 T017: round-trip coverage for c4Adapter.ts's Element[]/Relationship[] <->
// DiagramModel mapping, mirroring families.test.ts's/c4.test.ts's normalize-and-compare pattern.
import { describe, expect, it } from "vitest";
import {
  diagramEdgeToRelationshipCreate,
  diagramNodeToElementCreate,
  diagramNodeToElementUpdate,
  elementsToC4Model,
  kindForNode,
} from "./c4Adapter";
import type { Element, Relationship } from "../types";
import type { DiagramNode } from "../diagrams/core/model/diagram-model";

const ELEMENTS: Element[] = [
  { id: "ELM-001", name: "Customer", kind: "person" },
  { id: "ELM-002", name: "Payments Service", kind: "system" },
  { id: "ELM-003", name: "Web App", kind: "container" },
  { id: "ELM-004", name: "Checkout Component", kind: "component" },
];
const RELATIONSHIPS: Relationship[] = [
  { id: "REL-001", source: "ELM-001", target: "ELM-002", label: "Uses" },
  { id: "REL-002", source: "ELM-002", target: "ELM-003", label: "Routes to" },
  { id: "REL-003", source: "ELM-003", target: "ELM-004", label: "Contains" },
];

describe("elementsToC4Model: level filtering (data-model.md's level table)", () => {
  it("Context level shows only person + system elements and their relationship", () => {
    const model = elementsToC4Model(ELEMENTS, RELATIONSHIPS, "context");
    expect(model.nodes.map((n) => n.id).sort()).toEqual(["ELM-001", "ELM-002"]);
    expect(model.edges.map((e) => e.id)).toEqual(["REL-001"]);
    expect(model.diagramTypeId).toBe("c4-context");
  });

  it("Container level shows only system + container elements", () => {
    const model = elementsToC4Model(ELEMENTS, RELATIONSHIPS, "container");
    expect(model.nodes.map((n) => n.id).sort()).toEqual(["ELM-002", "ELM-003"]);
    expect(model.diagramTypeId).toBe("c4-container");
  });

  it("Component level shows only container + component elements", () => {
    const model = elementsToC4Model(ELEMENTS, RELATIONSHIPS, "component");
    expect(model.nodes.map((n) => n.id).sort()).toEqual(["ELM-003", "ELM-004"]);
    expect(model.diagramTypeId).toBe("c4-component");
  });
});

describe("elementsToC4Model: kind -> shape/role mapping", () => {
  it("maps each ElementKind to its documented shape and carries role through unchanged", () => {
    const model = elementsToC4Model(ELEMENTS, [], "context");
    const customer = model.nodes.find((n) => n.id === "ELM-001")!;
    expect(customer.role).toBe("person");
    expect(customer.shape).toBe("circle");
  });

  it("seeds supplied positions and auto-generates the rest", () => {
    const model = elementsToC4Model(ELEMENTS, [], "context", { "ELM-001": { x: 500, y: 500 } });
    const customer = model.nodes.find((n) => n.id === "ELM-001")!;
    expect(customer.position).toEqual({ x: 500, y: 500 });
    const system = model.nodes.find((n) => n.id === "ELM-002")!;
    expect(system.position).not.toEqual({ x: 500, y: 500 });
  });
});

describe("reverse mapping: DiagramModel -> Element/Relationship payloads", () => {
  it("a node with a role set maps back to that exact kind (research.md Decision 6)", () => {
    const node: DiagramNode = { id: "n1", label: "Customer", shape: "circle", role: "person", position: { x: 0, y: 0 } };
    expect(kindForNode(node)).toBe("person");
    expect(diagramNodeToElementCreate(node)).toEqual({ kind: "person", name: "Customer" });
  });

  it("a toolbar-added node with no role falls back to the shape convention", () => {
    const node: DiagramNode = { id: "n2", label: "New Thing", shape: "rectangle", position: { x: 0, y: 0 } };
    expect(kindForNode(node)).toBe("system");
  });

  it("a cylinder/stadium shape (DSL-text-only, Db/Queue variants) narrows to its plain base role, never lost data (research.md Decision 6)", () => {
    const node: DiagramNode = { id: "n3", label: "Orders DB", shape: "cylinder", role: "system", position: { x: 0, y: 0 } };
    expect(kindForNode(node)).toBe("system");
  });

  it("maps a renamed node to an ElementUpdate payload", () => {
    const node: DiagramNode = { id: "n1", label: "Renamed", shape: "circle", role: "person", position: { x: 0, y: 0 } };
    expect(diagramNodeToElementUpdate(node)).toEqual({ name: "Renamed" });
  });

  it("maps an edge to a RelationshipCreate payload", () => {
    const edge = { id: "e1", sourceId: "ELM-001", targetId: "ELM-002", label: "Uses" };
    expect(diagramEdgeToRelationshipCreate(edge)).toEqual({ source: "ELM-001", target: "ELM-002", label: "Uses" });
  });
});
