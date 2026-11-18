import React, { useCallback, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useCapabilities, useOrphanReport } from "../api/business";
import type { BusinessCapability } from "../api/business";
import { generateFromCapabilities } from "../diagrams/generators";
import type { DiagramSeed } from "../diagrams/generators";
import CapabilityNode from "./CapabilityNode";
import CapabilityForm from "./CapabilityForm";
import AgentReviewButton from "../agent-review/AgentReviewButton";
import { renderCapabilitySuggestionDetail } from "./agentReviewDetail";
import ChatButton from "../chat/ChatButton";
import ChatPanel from "../chat/ChatPanel";
import { QK } from "../api/queryKeys";

export interface CapabilityTreeNode extends BusinessCapability {
  children: CapabilityTreeNode[];
}

/** Assemble a flat list of capabilities into a nested tree, with siblings at
 *  every level (L1/L2/L3) sorted alphabetically by name -- not by `position`
 *  (mostly all 0, an unused legacy field with no editing UI), which gave no
 *  real ordering and let ties fall back to whatever row order Postgres
 *  happened to return, silently reshuffling after an unrelated edit updated
 *  a row (bug report, 2026-08-15). Name is stable under edits to any other
 *  attribute, so the displayed order no longer moves around. */
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

  // Sort all levels alphabetically by name
  const sortByName = (nodes: CapabilityTreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    for (const n of nodes) sortByName(n.children);
  };
  sortByName(roots);

  return roots;
}

/** Every id in a node's subtree, the node's own included. */
function subtreeIds(node: CapabilityTreeNode, into: Map<string, string[]>): string[] {
  const ids = [node.id, ...node.children.flatMap((c) => subtreeIds(c, into))];
  into.set(node.id, ids);
  return ids;
}

interface TreeContext {
  orphanIds: Set<string>;
  focusCapabilityId: string | null | undefined;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  /** Subtree ids by node, and a number that changes when the tree or the orphan set does. */
  subtree: Map<string, string[]>;
  epoch: number;
}

// ADP-blp.38: a row is memoised on `revision`, which names everything in its subtree that
// its rendered children depend on. Ticking one checkbox used to re-render every row.
function renderTree(nodes: CapabilityTreeNode[], ctx: TreeContext): React.ReactElement[] {
  return nodes.map((node) => {
    const ids = ctx.subtree.get(node.id) ?? [node.id];
    const selectedBelow = ids.filter((id) => ctx.selectedIds.has(id)).join(",");
    const focusBelow = ctx.focusCapabilityId && ids.includes(ctx.focusCapabilityId) ? ctx.focusCapabilityId : "";
    return (
      <CapabilityNode
        key={node.id}
        capability={node}
        isOrphan={ctx.orphanIds.has(node.id)}
        focused={ctx.focusCapabilityId === node.id}
        selected={ctx.selectedIds.has(node.id)}
        onToggleSelect={ctx.onToggleSelect}
        revision={`${ctx.epoch}|${focusBelow}|${selectedBelow}`}
      >
        {renderTree(node.children, ctx)}
      </CapabilityNode>
    );
  });
}

export interface CapabilityTreeProps {
  /** 920-capability-diagram-select US1: opens the Diagrams screen pre-filled
   *  with a flowchart generated from the currently checked capabilities (the
   *  "Generate Diagram from Selected" toolbar action, replacing the old
   *  per-row single-capability button -- FR-006). */
  onGenerateDiagram?: (seed: DiagramSeed) => void;
  /** 043-capability-heat-map US3: when set, the matching node scrolls into
   *  view and briefly highlights -- the drill-through target from
   *  CapabilityHeatMap, since no separate capability detail screen exists
   *  (research.md Decision 3). Every row is expanded by default already, so
   *  no ancestor-expansion step is needed here. */
  focusCapabilityId?: string | null;
}

export default function CapabilityTree({ onGenerateDiagram, focusCapabilityId }: CapabilityTreeProps): React.ReactElement {
  const { data, isLoading, error } = useCapabilities();
  const { data: orphanData } = useOrphanReport();
  const [showRootForm, setShowRootForm] = useState(false);
  const [showPortfolioReview, setShowPortfolioReview] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [orphansOnly, setOrphansOnly] = useState(false);
  // 920-capability-diagram-select US1: component-local, transient selection
  // state (research.md Decision 1) -- naturally resets when this component
  // unmounts on tab switch (BusinessPage.tsx conditionally renders it).
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // ADP-blp.38: the tree, the orphan set and the subtree index are rebuilt only when the data
  // changes, not on every render (a checkbox, a form opening).
  const items = useMemo(() => data?.items ?? [], [data]);
  const orphanIds = useMemo(
    () => new Set((orphanData?.orphan_capabilities ?? []).map((c) => c.id)),
    [orphanData],
  );
  const epoch = useRef(0);
  const { tree, subtree, treeEpoch } = useMemo(() => {
    // FR-006: filtering to orphans only prunes the tree to just orphaned
    // nodes -- a capability whose only orphaned descendant is nested several
    // levels down surfaces as its own root, rather than dragging its whole
    // (non-orphaned) ancestor chain along just for context.
    const visibleItems = orphansOnly ? items.filter((c) => orphanIds.has(c.id)) : items;
    const built = buildTree(visibleItems);
    const index = new Map<string, string[]>();
    built.forEach((root) => subtreeIds(root, index));
    epoch.current += 1;
    return { tree: built, subtree: index, treeEpoch: epoch.current };
  }, [items, orphanIds, orphansOnly]);

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading capabilities…</div>;
  if (error) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load capabilities: {error.message}</div>;

  function handleGenerateFromSelected() {
    const selected = items.filter((c) => selectedIds.has(c.id));
    onGenerateDiagram?.(generateFromCapabilities(selected));
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} capability{items.length !== 1 ? "ies" : "y"} across all levels
          {/* 920-capability-diagram-select US2: visible selection count. */}
          {selectedIds.size > 0 && <> · {selectedIds.size} selected</>}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          {selectedIds.size > 0 && (
            <button
              onClick={() => setSelectedIds(new Set())}
              title="Clear the current selection"
              style={{
                padding: "6px 14px",
                background: "var(--surface)",
                color: "var(--ink-2)",
                border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600,
              }}
            >
              Clear selection
            </button>
          )}
          <button
            onClick={handleGenerateFromSelected}
            disabled={selectedIds.size === 0}
            title="Generate a diagram from the checked capabilities and their hierarchy relationships"
            style={{
              padding: "6px 14px",
              background: selectedIds.size === 0 ? "var(--surface)" : "var(--accent)",
              color: selectedIds.size === 0 ? "var(--ink-3)" : "#fff",
              border: "1px solid var(--border)", borderRadius: 4,
              cursor: selectedIds.size === 0 ? "not-allowed" : "pointer",
              fontSize: 13, fontWeight: 600,
            }}
          >
            Generate Diagram from Selected
          </button>
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
            style={{ padding: "6px 14px", background: "var(--accent)", color: "var(--accent-ink)", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600 }}
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
            onAccepted={() => queryClient.invalidateQueries({ queryKey: [QK.businessCapabilities] })}
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

      {renderTree(tree, {
        orphanIds, focusCapabilityId, selectedIds, onToggleSelect: toggleSelect, subtree, epoch: treeEpoch,
      })}
    </div>
  );
}
