/**
 * ADP-SPEC-054 (research.md Decision 5): diffs a previous and a new DiagramModel (Canvas.tsx's
 * onChange callback only ever hands back the WHOLE model -- there is no finer-grained per-action
 * signal without modifying the vendored component) and fires exactly the granular backend call
 * that matches whatever actually changed, rather than ever replacing the whole design at once.
 *
 * Containers are never reconciled to the backend at all (research.md Decision 1 -- boundary
 * grouping is descoped; any DiagramContainer a user creates exists only in-session).
 * Positions are never part of this diff either (research.md Decision 3 -- layout continues to
 * flow through the existing, separate GET/PUT .../layout/{level} endpoints, debounced, wired up
 * independently in C4DesignView.tsx).
 */
import type { DiagramModel } from "../diagrams/core/model/diagram-model";
import {
  diagramEdgeToRelationshipCreate,
  diagramNodeToElementCreate,
  diagramNodeToElementUpdate,
} from "./c4Adapter";

export interface ReconcileMutations {
  createElement: (body: ReturnType<typeof diagramNodeToElementCreate>) => Promise<{ id: string }>;
  updateElement: (elementId: string, body: ReturnType<typeof diagramNodeToElementUpdate>) => Promise<void>;
  deleteElement: (elementId: string) => Promise<void>;
  createRelationship: (body: ReturnType<typeof diagramEdgeToRelationshipCreate>) => Promise<{ id: string }>;
  deleteRelationship: (relationshipId: string) => Promise<void>;
}

export type ReconcileIdReplacement = { kind: "node" | "edge"; tempId: string; realId: string };

/**
 * Applies the diff between `previous` and `next` via `mutations`, returning the list of
 * temp-id -> real-id replacements the caller must apply to its own model state (a controlled
 * update -- the same mechanism DiagramEditorPage.tsx already uses when applyDsl replaces the
 * whole model on load).
 */
export async function reconcile(
  previous: DiagramModel,
  next: DiagramModel,
  mutations: ReconcileMutations,
): Promise<ReconcileIdReplacement[]> {
  const prevNodeIds = new Set(previous.nodes.map((n) => n.id));
  const nextNodeIds = new Set(next.nodes.map((n) => n.id));
  const prevEdgeIds = new Set(previous.edges.map((e) => e.id));
  const nextEdgeIds = new Set(next.edges.map((e) => e.id));

  const removedNodeIds = new Set(previous.nodes.filter((n) => !nextNodeIds.has(n.id)).map((n) => n.id));

  // Removed relationships -- skip any whose endpoint was ALSO removed in this same diff: the
  // backend's DELETE element endpoint already cascades that relationship away server-side, so an
  // explicit delete here would be redundant (and would 404 against an already-gone entity).
  for (const edge of previous.edges) {
    if (nextEdgeIds.has(edge.id)) continue;
    const cascaded = removedNodeIds.has(edge.sourceId) || removedNodeIds.has(edge.targetId);
    if (!cascaded) {
      await mutations.deleteRelationship(edge.id);
    }
  }

  // Removed elements.
  for (const node of previous.nodes) {
    if (!nextNodeIds.has(node.id)) {
      await mutations.deleteElement(node.id);
    }
  }

  const replacements: ReconcileIdReplacement[] = [];

  // Added elements -- create, then record the temp -> real id replacement.
  for (const node of next.nodes) {
    if (!prevNodeIds.has(node.id)) {
      const created = await mutations.createElement(diagramNodeToElementCreate(node));
      replacements.push({ kind: "node", tempId: node.id, realId: created.id });
    }
  }

  // Renamed elements -- same id, present in both, label changed.
  for (const node of next.nodes) {
    if (!prevNodeIds.has(node.id)) continue;
    const prevNode = previous.nodes.find((n) => n.id === node.id);
    if (prevNode && prevNode.label !== node.label) {
      await mutations.updateElement(node.id, diagramNodeToElementUpdate(node));
    }
  }

  // Added relationships -- create, then record the temp -> real id replacement.
  for (const edge of next.edges) {
    if (!prevEdgeIds.has(edge.id)) {
      const created = await mutations.createRelationship(diagramEdgeToRelationshipCreate(edge));
      replacements.push({ kind: "edge", tempId: edge.id, realId: created.id });
    }
  }

  return replacements;
}

/** Applies id replacements (from `reconcile`'s return value) to a model, producing a new model
 *  with every temporary Canvas-generated id swapped for its real backend id. */
export function applyIdReplacements(model: DiagramModel, replacements: ReconcileIdReplacement[]): DiagramModel {
  if (replacements.length === 0) return model;
  const nodeMap = new Map(replacements.filter((r) => r.kind === "node").map((r) => [r.tempId, r.realId]));
  const edgeMap = new Map(replacements.filter((r) => r.kind === "edge").map((r) => [r.tempId, r.realId]));
  if (nodeMap.size === 0 && edgeMap.size === 0) return model;

  return {
    ...model,
    nodes: model.nodes.map((n) => (nodeMap.has(n.id) ? { ...n, id: nodeMap.get(n.id)! } : n)),
    edges: model.edges.map((e) => ({
      ...e,
      id: edgeMap.get(e.id) ?? e.id,
      sourceId: nodeMap.get(e.sourceId) ?? e.sourceId,
      targetId: nodeMap.get(e.targetId) ?? e.targetId,
    })),
  };
}
