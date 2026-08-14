// ADP-914.7: generate a pre-filled diagram from ADP's own business-capability/
// value-stream data. Both functions are pure: (source data) -> DiagramSeed.
// They build a typed DiagramModel via the vendored diagram-core's addNode/
// addEdge -- never hand-written DSL text (spec ART-XIII).

import { createEmptyDiagramModel } from "./core/index";
import { addNode, addEdge } from "./core/model/diagram-ops";
import type { DiagramModel } from "./core/index";
import type { DiagramType } from "./api";
import type { ValueStreamDetail, BusinessCapability } from "../api/business";
import type { CapabilityTreeNode } from "../business/CapabilityTree";

export interface DiagramSeed {
  title: string;
  diagramType: DiagramType;
  model: DiagramModel;
}

/**
 * User Story 1: one node per stage (in `position` order), sequential edges
 * between consecutive stages. `addNode` assigns each node's id internally
 * (research.md Decision 2), so a stage-id -> generated-node-id map is built
 * while creating nodes, then used to resolve edges.
 */
export function generateFromValueStream(vs: ValueStreamDetail): DiagramSeed {
  let model = createEmptyDiagramModel("flowchart");
  const nodeIdByStageId = new Map<string, string>();

  const orderedStages = [...vs.stages].sort((a, b) => a.position - b.position);
  for (const stage of orderedStages) {
    model = addNode(model, { shape: "rectangle", label: stage.name });
    const created = model.nodes[model.nodes.length - 1];
    nodeIdByStageId.set(stage.id, created.id);
  }

  for (let i = 0; i < orderedStages.length - 1; i++) {
    const sourceId = nodeIdByStageId.get(orderedStages[i].id)!;
    const targetId = nodeIdByStageId.get(orderedStages[i + 1].id)!;
    model = addEdge(model, { sourceId, targetId });
  }

  return { title: vs.name, diagramType: "flowchart", model };
}

/**
 * User Story 2: one node per capability in the subtree (the selected
 * capability plus every descendant), a parent->child edge for each. Unlike
 * generateFromValueStream, no id-mapping table is needed here -- a top-down
 * recursive walk always has the parent's just-created, `addNode`-assigned id
 * on hand via the closure, since a parent is created before its children.
 */
export function generateFromCapabilitySubtree(root: CapabilityTreeNode): DiagramSeed {
  let model = createEmptyDiagramModel("flowchart");

  function addSubtree(node: CapabilityTreeNode, parentGeneratedId: string | null): void {
    model = addNode(model, { shape: "rectangle", label: node.name });
    const created = model.nodes[model.nodes.length - 1];
    if (parentGeneratedId) {
      model = addEdge(model, { sourceId: parentGeneratedId, targetId: created.id });
    }
    for (const child of node.children) {
      addSubtree(child, created.id);
    }
  }

  addSubtree(root, null);

  return { title: root.name, diagramType: "flowchart", model };
}

/**
 * 920-capability-diagram-select US1: one node per selected capability (any
 * branch/level, arbitrary combination), plus one edge for each pair of
 * *selected* capabilities that have a direct parent-child relationship --
 * research.md Decision 3's flat id-membership check (`parent_id` also in the
 * selected set), not a tree walk. A selected capability whose real parent
 * isn't also selected renders with no incoming edge (no automatic ancestor
 * inclusion, spec.md's resolved Assumption). Title: the single capability's
 * own name for a 1-item selection (SC-004 parity with
 * generateFromCapabilitySubtree's own leaf-node output), otherwise a generic
 * title (research.md Decision 4).
 */
export function generateFromCapabilities(selected: BusinessCapability[]): DiagramSeed {
  let model = createEmptyDiagramModel("flowchart");
  const nodeIdByCapabilityId = new Map<string, string>();

  for (const cap of selected) {
    model = addNode(model, { shape: "rectangle", label: cap.name });
    const created = model.nodes[model.nodes.length - 1];
    nodeIdByCapabilityId.set(cap.id, created.id);
  }

  const selectedIds = new Set(selected.map((c) => c.id));
  for (const cap of selected) {
    if (cap.parent_id && selectedIds.has(cap.parent_id)) {
      model = addEdge(model, {
        sourceId: nodeIdByCapabilityId.get(cap.parent_id)!,
        targetId: nodeIdByCapabilityId.get(cap.id)!,
      });
    }
  }

  const title = selected.length === 1 ? selected[0].name : "Capabilities Diagram";
  return { title, diagramType: "flowchart", model };
}
