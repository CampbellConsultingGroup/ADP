import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useCapabilities, useOrphanReport } from "../api/business";
import type { BusinessCapability } from "../api/business";
import type { DiagramSeed } from "../diagrams/generators";
import CapabilityNode from "./CapabilityNode";
import CapabilityForm from "./CapabilityForm";
import AgentReviewButton from "../agent-review/AgentReviewButton";
import { renderCapabilitySuggestionDetail } from "./agentReviewDetail";
import ChatButton from "../chat/ChatButton";
import ChatPanel from "../chat/ChatPanel";

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

function renderTree(
  nodes: CapabilityTreeNode[],
  orphanIds: Set<string>,
  onGenerateDiagram?: (seed: DiagramSeed) => void,
): React.ReactElement[] {
  return nodes.map((node) => (
    <CapabilityNode
      key={node.id}
      capability={node}
      onGenerateDiagram={onGenerateDiagram}
      isOrphan={orphanIds.has(node.id)}
    >
      {renderTree(node.children, orphanIds, onGenerateDiagram)}
    </CapabilityNode>
  ));
}

export interface CapabilityTreeProps {
  /** ADP-914.7: opens the Diagrams screen pre-filled with a flowchart
   *  generated from a capability's own subtree. `CapabilityNode` itself
   *  calls generateFromCapabilitySubtree() on click and passes the finished
   *  DiagramSeed up through this callback unchanged -- CapabilityTree only
   *  threads it through, it never touches a raw CapabilityTreeNode itself. */
  onGenerateDiagram?: (seed: DiagramSeed) => void;
}

export default function CapabilityTree({ onGenerateDiagram }: CapabilityTreeProps): React.ReactElement {
  const { data, isLoading, error } = useCapabilities();
  const { data: orphanData } = useOrphanReport();
  const [showRootForm, setShowRootForm] = useState(false);
  const [showPortfolioReview, setShowPortfolioReview] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [orphansOnly, setOrphansOnly] = useState(false);
  const queryClient = useQueryClient();

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading capabilities…</div>;
  if (error) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load capabilities: {error.message}</div>;

  const items = data?.items ?? [];
  const orphanIds = new Set((orphanData?.orphan_capabilities ?? []).map((c) => c.id));
  // FR-006: filtering to orphans only prunes the tree to just orphaned
  // nodes -- a capability whose only orphaned descendant is nested several
  // levels down surfaces as its own root, rather than dragging its whole
  // (non-orphaned) ancestor chain along just for context.
  const visibleItems = orphansOnly ? items.filter((c) => orphanIds.has(c.id)) : items;
  const tree = buildTree(visibleItems);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} capability{items.length !== 1 ? "ies" : "y"} across all levels
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setOrphansOnly(!orphansOnly)}
            title="Show only capabilities with no strategic-objective linkage"
            style={{
              padding: "6px 14px",
              background: orphansOnly ? "var(--warn-wash)" : "var(--surface)",
              color: orphansOnly ? "var(--warn)" : "var(--ink-2)",
              border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600,
            }}
          >
            {orphansOnly ? "Showing orphans only" : "Show orphans only"}
          </button>
          <ChatButton active={showChat} onToggle={() => setShowChat(!showChat)} label="Chat" />
          <button
            onClick={() => setShowPortfolioReview(!showPortfolioReview)}
            title="Ask the business architecture expert to review the entire capability portfolio for gaps and redundancies"
            style={{
              padding: "6px 14px", background: showPortfolioReview ? "var(--accent-wash)" : "var(--surface)",
              color: showPortfolioReview ? "var(--accent-2)" : "var(--ink-2)",
              border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600,
            }}
          >
            Review Portfolio
          </button>
          <button
            onClick={() => setShowRootForm(!showRootForm)}
            style={{ padding: "6px 14px", background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600 }}
          >
            + Add Strategic Capability
          </button>
        </div>
      </div>

      {showChat && (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 4,
          }}
        >
          <ChatPanel basePath="/api/v1/chat" onClose={() => setShowChat(false)} />
        </div>
      )}

      {showPortfolioReview && (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 4,
          }}
        >
          <AgentReviewButton
            basePath="/api/v1/business/capabilities/agent-review"
            label="Ask the business architecture expert to review the portfolio"
            renderDetail={renderCapabilitySuggestionDetail}
            onAccepted={() => queryClient.invalidateQueries({ queryKey: ["business-capabilities"] })}
          />
        </div>
      )}

      {showRootForm && (
        <CapabilityForm
          parentId={null}
          level={1}
          onDone={() => setShowRootForm(false)}
          onCancel={() => setShowRootForm(false)}
        />
      )}

      {tree.length === 0 && !showRootForm && orphansOnly && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No capabilities with missing strategic linkage.
        </div>
      )}

      {tree.length === 0 && !showRootForm && !orphansOnly && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          The capability model is empty. Click "Add Strategic Capability" to create the first Level 1 capability.
        </div>
      )}

      {renderTree(tree, orphanIds, onGenerateDiagram)}
    </div>
  );
}
