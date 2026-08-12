/**
 * ADP-SPEC-054: Element[]/Relationship[] <-> DiagramModel, the transcoding layer that lets the
 * diagram tool's reused Canvas.tsx (ADP-SPEC-052) render/edit ADP's canonical architecture-design
 * records. Reuses web/src/canvas/c4-filter.ts's existing level-visibility rules unchanged
 * (data-model.md's level table) -- this file does not reimplement them.
 *
 * KIND <-> SHAPE CONVENTION (documented limitation, not a bug): Canvas.tsx's toolbar only offers
 * the 4 generic UNIVERSAL_SHAPES (rectangle/rounded-rectangle/circle/diamond) for any non-flowchart
 * family -- there is no per-family shape set to extend without editing the vendored component
 * (research.md Decision 1's same boundary). A toolbar-added node therefore carries no `role` at
 * all (confirmed: Canvas.tsx's handleAddShape calls addNode(model, { shape }), nothing else) -- so
 * this adapter assigns kind from shape by a fixed 1:1 convention below. The toolbar's own button
 * labels ("Add Rectangle", "Add Circle", ...) are generic, not C4-aware -- an architect has to
 * learn this mapping (documented in the view's own UI copy), a known, accepted limitation of
 * reusing the vendored toolbar as-is rather than building a custom C4 shape picker.
 */
import type { C4Level, Element, ElementKind, Relationship } from "../types";
import type { DiagramContainer, DiagramEdge, DiagramModel, DiagramNode, NodeShape } from "../diagrams/core/model/diagram-model";
import { filterElementsForLevel, filterRelationshipsForLevel } from "../canvas/c4-filter";

const KIND_TO_SHAPE: Record<ElementKind, NodeShape> = {
  person: "circle",
  system: "rectangle",
  container: "rounded-rectangle",
  component: "diamond",
};

/** Inverse of KIND_TO_SHAPE -- used when a node has no `role` (a toolbar-added shape). */
const SHAPE_TO_KIND: Partial<Record<NodeShape, ElementKind>> = {
  circle: "person",
  rectangle: "system",
  "rounded-rectangle": "container",
  diamond: "component",
};

const HEADER_FOR_LEVEL: Record<C4Level, string> = {
  context: "c4-context",
  container: "c4-container",
  component: "c4-component",
};

function autoPosition(index: number): { x: number; y: number } {
  return { x: (index % 5) * 200 + 40, y: Math.floor(index / 5) * 140 + 40 };
}

/**
 * Element[]/Relationship[] + C4Level -> DiagramModel, filtered to one level
 * (research.md Decision 3: `positions`, when supplied, comes from the *existing*,
 * unmodified GET /designs/{id}/layout/{level} endpoint -- not this function's concern).
 */
export function elementsToC4Model(
  elements: Element[],
  relationships: Relationship[],
  level: C4Level,
  positions: Record<string, { x: number; y: number }> = {},
): DiagramModel {
  const visibleElements = filterElementsForLevel(elements, level);
  const visibleIds = new Set(visibleElements.map((e) => e.id));
  const visibleRelationships = filterRelationshipsForLevel(relationships, visibleIds);

  const nodes: DiagramNode[] = visibleElements.map((el, index) => ({
    id: el.id,
    label: el.name,
    shape: KIND_TO_SHAPE[el.kind],
    role: el.kind,
    position: positions[el.id] ?? autoPosition(index),
  }));

  const edges: DiagramEdge[] = visibleRelationships.map((rel) => ({
    id: rel.id,
    sourceId: rel.source,
    targetId: rel.target,
    label: rel.label,
  }));

  const containers: DiagramContainer[] = [];

  return {
    diagramTypeId: HEADER_FOR_LEVEL[level],
    nodes,
    edges,
    containers,
  };
}

/** research.md Decision 6: a node's `role`, when set, always wins over its `shape` -- only a
 *  brand-new toolbar-added node (no role yet) falls back to the shape convention above. */
export function kindForNode(node: DiagramNode): ElementKind {
  if (node.role === "person" || node.role === "system" || node.role === "container" || node.role === "component") {
    return node.role;
  }
  return SHAPE_TO_KIND[node.shape] ?? "system";
}

export interface ElementCreatePayload {
  kind: ElementKind;
  name: string;
}

/** Pure mapping only -- no API call here (reconcile.ts owns firing the request). */
export function diagramNodeToElementCreate(node: DiagramNode): ElementCreatePayload {
  return { kind: kindForNode(node), name: node.label };
}

export interface ElementUpdatePayload {
  name: string;
}

export function diagramNodeToElementUpdate(node: DiagramNode): ElementUpdatePayload {
  return { name: node.label };
}

export interface RelationshipCreatePayload {
  source: string;
  target: string;
  label?: string;
}

export function diagramEdgeToRelationshipCreate(edge: DiagramEdge): RelationshipCreatePayload {
  return { source: edge.sourceId, target: edge.targetId, label: edge.label };
}
