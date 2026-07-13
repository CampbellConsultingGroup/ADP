import React, { useState } from "react";
import { useCapabilities } from "../api/business";
import type { BusinessCapability } from "../api/business";
import CapabilityNode from "./CapabilityNode";
import CapabilityForm from "./CapabilityForm";

export interface CapabilityTreeNode extends BusinessCapability {
  children: CapabilityTreeNode[];
}

/** Assemble a flat list of capabilities into a nested tree, sorted by position. */
export function buildTree(items: BusinessCapability[]): CapabilityTreeNode[] {
  const byId = new Map<string, CapabilityTreeNode>();
  const roots: CapabilityTreeNode[] = [];

  // First pass: create node objects
  for (const item of items) {
    byId.set(item.id, { ...item, children: [] });
  }

  // Second pass: link children to parents
  for (const node of byId.values()) {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else if (!node.parent_id) {
      roots.push(node);
    }
  }

  // Sort all levels by position
  const sortByPosition = (nodes: CapabilityTreeNode[]) => {
    nodes.sort((a, b) => a.position - b.position);
    for (const n of nodes) sortByPosition(n.children);
  };
  sortByPosition(roots);

  return roots;
}

function renderTree(nodes: CapabilityTreeNode[]): React.ReactElement[] {
  return nodes.map((node) => (
    <CapabilityNode key={node.id} capability={node}>
      {renderTree(node.children)}
    </CapabilityNode>
  ));
}

export default function CapabilityTree(): React.ReactElement {
  const { data, isLoading, error } = useCapabilities();
  const [showRootForm, setShowRootForm] = useState(false);

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading capabilities…</div>;
  if (error) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load capabilities: {error.message}</div>;

  const items = data?.items ?? [];
  const tree = buildTree(items);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} capability{items.length !== 1 ? "ies" : "y"} across all levels
        </span>
        <button
          onClick={() => setShowRootForm(!showRootForm)}
          style={{ padding: "6px 14px", background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600 }}
        >
          + Add Strategic Capability
        </button>
      </div>

      {showRootForm && (
        <CapabilityForm
          parentId={null}
          level={1}
          onDone={() => setShowRootForm(false)}
          onCancel={() => setShowRootForm(false)}
        />
      )}

      {tree.length === 0 && !showRootForm && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          The capability model is empty. Click "Add Strategic Capability" to create the first Level 1 capability.
        </div>
      )}

      {renderTree(tree)}
    </div>
  );
}
