import React, { useState } from "react";
import { useDeleteCapability, useUpdateCapability } from "../api/business";
import type { BusinessCapability } from "../api/business";
import CapabilityForm from "./CapabilityForm";
import DesignLinkEditor from "./DesignLinkEditor";

interface CapabilityNodeProps {
  capability: BusinessCapability;
  children: React.ReactNode;
}

const LEVEL_COLORS: Record<number, string> = {
  1: "#1168BD",
  2: "#047857",
  3: "#7C3AED",
};

const LEVEL_LABELS: Record<number, string> = { 1: "L1", 2: "L2", 3: "L3" };

export default function CapabilityNode({ capability, children }: CapabilityNodeProps): React.ReactElement {
  const [expanded, setExpanded] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(capability.name);
  const [addingChild, setAddingChild] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [showLinks, setShowLinks] = useState(false);

  const update = useUpdateCapability(capability.id);
  const deleteCap = useDeleteCapability();

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

  return (
    <div style={{ marginLeft: indent }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 8px",
          borderRadius: 4,
          background: "#fff",
          border: "1px solid #E5E7EB",
          marginBottom: 3,
        }}
      >
        {/* Expand/collapse toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          style={{ background: "none", border: "none", cursor: hasChildren ? "pointer" : "default", fontSize: 11, color: "#9CA3AF", padding: "0 2px", minWidth: 14 }}
        >
          {hasChildren ? (expanded ? "▾" : "▸") : " "}
        </button>

        {/* Level badge */}
        <span style={{ fontSize: 10, fontWeight: 700, color: LEVEL_COLORS[capability.level], background: `${LEVEL_COLORS[capability.level]}15`, padding: "1px 5px", borderRadius: 3, minWidth: 20, textAlign: "center" }}>
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
              style={{ flex: 1, padding: "2px 6px", fontSize: 13, border: "1px solid #93C5FD", borderRadius: 3 }}
            />
            <button onClick={handleSaveEdit} style={actionBtn}>✓</button>
            <button onClick={() => { setEditing(false); setEditName(capability.name); }} style={actionBtn}>×</button>
          </>
        ) : (
          <>
            <span style={{ flex: 1, fontSize: 13, color: "#111827" }}>
              {capability.name}
              {capability.level === 1 && capability.domain_name && (
                <span style={{ marginLeft: 6, fontSize: 10, background: "#e3f2fd", color: "#0d47a1", padding: "1px 5px", borderRadius: 8, fontWeight: 500 }}>
                  {capability.domain_name}
                </span>
              )}
            </span>
            <button onClick={() => setEditing(true)} title="Edit" style={actionBtn}>✎</button>
            {canAddChild && (
              <button onClick={() => setAddingChild(!addingChild)} title="Add child capability" style={{ ...actionBtn, color: "#047857" }}>+</button>
            )}
            <button
              onClick={() => setShowLinks(!showLinks)}
              title="Linked designs"
              style={{ ...actionBtn, color: showLinks ? "#1168BD" : "#6B7280", fontSize: 11 }}
            >
              Links
            </button>
            <button onClick={handleDelete} title="Delete" style={{ ...actionBtn, color: "#B91C1C" }}>🗑</button>
          </>
        )}
      </div>

      {deleteError && (
        <div style={{ marginLeft: 20, marginBottom: 4, padding: "4px 10px", background: "#FEE2E2", border: "1px solid #FECACA", borderRadius: 4, fontSize: 12, color: "#B91C1C" }}>
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
            background: "#F0F9FF",
            border: "1px solid #BAE6FD",
            borderRadius: 4,
          }}
        >
          <p style={{ fontSize: 11, fontWeight: 600, color: "#0369A1", margin: "0 0 0.25rem" }}>
            Supporting Designs
          </p>
          <DesignLinkEditor entityType="capability" entityId={capability.id} />
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
  color: "#6B7280",
  padding: "1px 5px",
  borderRadius: 3,
};
