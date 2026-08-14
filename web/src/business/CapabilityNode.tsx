import React, { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { MATURITY_LEVEL_LABEL, STRATEGIC_RELEVANCE_LABEL, useDeleteCapability, useUpdateCapability } from "../api/business";
import type { MaturityLevel, StrategicRelevance } from "../api/business";
import type { CapabilityTreeNode } from "./CapabilityTree";
import { generateFromCapabilitySubtree } from "../diagrams/generators";
import type { DiagramSeed } from "../diagrams/generators";
import CapabilityForm from "./CapabilityForm";
import DesignLinkEditor from "./DesignLinkEditor";
import { LEVEL_STYLE } from "./classification";
import AgentReviewButton from "../agent-review/AgentReviewButton";
import { renderCapabilitySuggestionDetail } from "./agentReviewDetail";

interface CapabilityNodeProps {
  // ADP-914.7: widened from BusinessCapability to CapabilityTreeNode (a
  // strict superset -- all existing field access below still compiles) so
  // this node has its own full subtree on hand for "Generate Diagram"
  // (research.md Decision 1), without needing a second data-fetch/lookup.
  capability: CapabilityTreeNode;
  children: React.ReactNode;
  /** ADP-914.7: opens the Diagrams screen pre-filled with a flowchart
   *  generated from this capability's own subtree. */
  onGenerateDiagram?: (seed: DiagramSeed) => void;
  /** 918-strategy-rollups: true when this capability has zero strategic-
   *  objective linkage (spec.md FR-006). */
  isOrphan?: boolean;
  /** 043-capability-heat-map US3: true when this is the drill-through target
   *  from CapabilityHeatMap -- scrolls into view and briefly highlights
   *  (research.md Decision 3: no separate capability detail screen exists,
   *  this row already carries every detail affordance). */
  focused?: boolean;
}

const LEVEL_LABELS: Record<number, string> = { 1: "L1", 2: "L2", 3: "L3" };

export default function CapabilityNode({ capability, children, onGenerateDiagram, isOrphan, focused }: CapabilityNodeProps): React.ReactElement {
  const [expanded, setExpanded] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(capability.name);
  const [addingChild, setAddingChild] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [showLinks, setShowLinks] = useState(false);
  const [showAgentReview, setShowAgentReview] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);

  const update = useUpdateCapability(capability.id);
  const deleteCap = useDeleteCapability();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (focused) rowRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focused]);

  const hasChildren = React.Children.count(children) > 0;
  const canAddChild = capability.level < 3;
  const childLevel = (capability.level + 1) as 1 | 2 | 3;
  const indent = (capability.level - 1) * 24;

  function handleSaveEdit() {
    if (!editName.trim()) return;
    update.mutate({ name: editName.trim() }, { onSuccess: () => setEditing(false) });
  }

  function handleDelete() {
    setDeleteError(null);
    deleteCap.mutate(capability.id, {
      onError: (err) => setDeleteError(err.message),
    });
  }

  function handleRelevanceChange(value: string) {
    const strategic_relevance = value === "" ? null : (Number(value) as StrategicRelevance);
    update.mutate({ strategic_relevance });
  }

  function handleMaturityChange(value: string) {
    const maturity_level = value === "" ? null : (Number(value) as MaturityLevel);
    update.mutate({ maturity_level });
  }

  return (
    <div style={{ marginLeft: indent }}>
      <div
        id={`cap-${capability.id}`}
        ref={rowRef}
        data-focused={focused ? "true" : undefined}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 8px",
          borderRadius: 4,
          background: focused ? "var(--accent-wash)" : "var(--surface)",
          border: focused ? "1px solid var(--accent)" : "1px solid var(--border)",
          marginBottom: 3,
        }}
      >
        {/* Expand/collapse toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          style={{ background: "none", border: "none", cursor: hasChildren ? "pointer" : "default", fontSize: 11, color: "var(--ink-3)", padding: "0 2px", minWidth: 14 }}
        >
          {hasChildren ? (expanded ? "▾" : "▸") : " "}
        </button>

        {/* Level badge */}
        <span style={{ fontSize: 10, fontWeight: 700, color: LEVEL_STYLE[capability.level]?.fg, background: LEVEL_STYLE[capability.level]?.bg, padding: "1px 5px", borderRadius: 3, minWidth: 20, textAlign: "center" }}>
          {LEVEL_LABELS[capability.level]}
        </span>

        {/* Name (inline edit) */}
        {editing ? (
          <>
            <input
              autoFocus
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSaveEdit(); if (e.key === "Escape") { setEditing(false); setEditName(capability.name); } }}
              style={{ flex: 1, padding: "2px 6px", fontSize: 13, border: "1px solid var(--accent)", borderRadius: 3 }}
            />
            <button onClick={handleSaveEdit} style={actionBtn}>✓</button>
            <button onClick={() => { setEditing(false); setEditName(capability.name); }} style={actionBtn}>×</button>
          </>
        ) : (
          <>
            <span style={{ flex: 1, fontSize: 13, color: "var(--ink)" }}>
              {capability.name}
              {capability.level === 1 && capability.domain_name && (
                <span style={{ marginLeft: 6, fontSize: 10, background: "var(--accent-wash)", color: "var(--accent-2)", padding: "1px 5px", borderRadius: 8, fontWeight: 500 }}>
                  {capability.domain_name}
                </span>
              )}
              {isOrphan && (
                <span
                  title="Not referenced by any strategic objective"
                  style={{ marginLeft: 6, fontSize: 10, background: "var(--warn-wash)", color: "var(--warn)", padding: "1px 5px", borderRadius: 8, fontWeight: 500 }}
                >
                  no strategic linkage
                </span>
              )}
            </span>
            <select
              value={capability.strategic_relevance ?? ""}
              onChange={(e) => handleRelevanceChange(e.target.value)}
              title="Strategic relevance"
              style={{ fontSize: 10, color: "var(--ink-2)", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 3px" }}
            >
              <option value="">Unclassified</option>
              {([1, 2, 3] as const).map((v) => (
                <option key={v} value={v}>{STRATEGIC_RELEVANCE_LABEL[v]}</option>
              ))}
            </select>
            <select
              value={capability.maturity_level ?? ""}
              onChange={(e) => handleMaturityChange(e.target.value)}
              title="Maturity level"
              style={{ fontSize: 10, color: "var(--ink-2)", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 3px" }}
            >
              <option value="">Not assessed</option>
              {([1, 2, 3, 4, 5] as const).map((v) => (
                <option key={v} value={v}>{MATURITY_LEVEL_LABEL[v]}</option>
              ))}
            </select>
            <button onClick={() => onGenerateDiagram?.(generateFromCapabilitySubtree(capability))} title="Generate Diagram" style={actionBtn}>⛶</button>
            <button onClick={() => setEditing(true)} title="Edit" style={actionBtn}>✎</button>
            {canAddChild && (
              <button onClick={() => setAddingChild(!addingChild)} title="Add child capability" style={{ ...actionBtn, color: "var(--good)" }}>+</button>
            )}
            <button
              onClick={() => setShowLinks(!showLinks)}
              title="Linked designs"
              style={{ ...actionBtn, color: showLinks ? "var(--accent)" : "var(--ink-3)", fontSize: 11 }}
            >
              Links
            </button>
            <button
              onClick={() => setShowAgentReview(!showAgentReview)}
              title="Ask the business architecture expert to review this capability"
              style={{ ...actionBtn, color: showAgentReview ? "var(--accent)" : "var(--ink-3)", fontSize: 11 }}
            >
              Review
            </button>
            <button onClick={handleDelete} title="Delete" style={{ ...actionBtn, color: "var(--crit)" }}>Delete</button>
          </>
        )}
      </div>

      {deleteError && (
        <div style={{ marginLeft: 20, marginBottom: 4, padding: "4px 10px", background: "var(--crit-wash)", border: "1px solid var(--crit)", borderRadius: 4, fontSize: 12, color: "var(--crit)" }}>
          {deleteError}
        </div>
      )}

      {addingChild && (
        <div style={{ marginLeft: 20 }}>
          <CapabilityForm
            parentId={capability.id}
            level={childLevel}
            onDone={() => setAddingChild(false)}
            onCancel={() => setAddingChild(false)}
          />
        </div>
      )}

      {showLinks && (
        <div
          style={{
            marginLeft: 20,
            marginBottom: 6,
            padding: "8px 12px",
            background: "var(--accent-wash)",
            border: "1px solid var(--accent)",
            borderRadius: 4,
          }}
        >
          <p style={{ fontSize: 11, fontWeight: 600, color: "var(--accent-2)", margin: "0 0 0.25rem" }}>
            Supporting Designs
          </p>
          <DesignLinkEditor entityType="capability" entityId={capability.id} />
        </div>
      )}

      {showAgentReview && (
        <div
          style={{
            marginLeft: 20,
            marginBottom: 6,
            padding: "8px 12px",
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 4,
          }}
        >
          <AgentReviewButton
            basePath={`/api/v1/business/capabilities/${capability.id}/agent-review`}
            label="Ask the business architecture expert"
            renderDetail={renderCapabilitySuggestionDetail}
            onAccepted={() => queryClient.invalidateQueries({ queryKey: ["business-capabilities"] })}
          />
        </div>
      )}

      {expanded && children}
    </div>
  );
}

const actionBtn: React.CSSProperties = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  fontSize: 13,
  color: "var(--ink-3)",
  padding: "1px 5px",
  borderRadius: 3,
};
