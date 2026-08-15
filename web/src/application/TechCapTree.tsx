import { useState } from "react";
import type React from "react";
import type { StrategicRelevance, TechnicalCapability } from "../api/application";
import { STRATEGIC_RELEVANCE_LABEL, useCreateTechCap, useDeleteTechCap, useTechCaps, useUpdateTechCap } from "../api/application";
import TechCapForm from "./TechCapForm";

export interface TechCapTreeNode extends TechnicalCapability {
  children: TechCapTreeNode[];
}

/** Assemble a flat list of technical capabilities into a nested tree, with
 *  siblings at every level (L1/L2/L3) sorted alphabetically by name --
 *  explicit rather than relying on the backend's incidental (level, name)
 *  query order happening to line up with display order. Mirrors the same
 *  hardening CapabilityTree.tsx's own buildTree() applies for Business
 *  Capabilities (bug report, 2026-08-15 / ADP-am7), applied here
 *  proactively rather than waiting for the same class of bug to resurface. */
export function buildTechCapTree(items: TechnicalCapability[]): TechCapTreeNode[] {
  const byId = new Map<string, TechCapTreeNode>();
  const roots: TechCapTreeNode[] = [];

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
  const sortByName = (nodes: TechCapTreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    for (const n of nodes) sortByName(n.children);
  };
  sortByName(roots);

  return roots;
}

const actionBtn: React.CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontSize: 11,
  color: "var(--ink-3)",
  padding: "1px 4px",
};

interface NodeProps {
  node: TechCapTreeNode;
  depth: number;
}

function TechCapNode({ node, depth }: NodeProps) {
  const [expanded, setExpanded] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(node.name);
  const [editDescription, setEditDescription] = useState(node.description ?? "");
  const createCap = useCreateTechCap();
  const deleteCap = useDeleteTechCap();
  const updateCap = useUpdateTechCap();

  const handleDelete = async () => {
    if (!confirm(`Delete "${node.name}"? This also removes any child capabilities.`)) return;
    deleteCap.mutate(node.id);
  };

  const handleRelevanceChange = (value: string) => {
    const strategic_relevance = value === "" ? null : (Number(value) as StrategicRelevance);
    updateCap.mutate({ id: node.id, body: { strategic_relevance } });
  };

  const handleSaveEdit = () => {
    if (!editName.trim()) return;
    updateCap.mutate(
      { id: node.id, body: { name: editName.trim(), description: editDescription.trim() || null } },
      { onSuccess: () => setEditing(false) },
    );
  };

  const handleCancelEdit = () => {
    setEditing(false);
    setEditName(node.name);
    setEditDescription(node.description ?? "");
  };

  return (
    <div style={{ marginLeft: depth * 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 0" }}>
        {node.children.length > 0 && (
          <button onClick={() => setExpanded(e => !e)} style={{ fontSize: 10, background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", padding: 0, minWidth: 12 }}>
            {expanded ? "▾" : "▸"}
          </button>
        )}
        {node.children.length === 0 && <span style={{ minWidth: 12 }} />}

        {editing ? (
          <>
            <input
              autoFocus
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSaveEdit(); if (e.key === "Escape") handleCancelEdit(); }}
              style={{ flex: 1, fontSize: 13, padding: "2px 6px", border: "1px solid var(--accent)", borderRadius: 3 }}
            />
            <input
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="Description (optional)"
              onKeyDown={(e) => { if (e.key === "Enter") handleSaveEdit(); if (e.key === "Escape") handleCancelEdit(); }}
              style={{ flex: 1, fontSize: 12, padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 3 }}
            />
            <button onClick={handleSaveEdit} title="Save" style={actionBtn}>✓</button>
            <button onClick={handleCancelEdit} title="Cancel" style={actionBtn}>×</button>
          </>
        ) : (
          <>
            <span style={{ fontSize: 13, flex: 1 }}>{node.name}</span>
            <select
              value={node.strategic_relevance ?? ""}
              onChange={(e) => handleRelevanceChange(e.target.value)}
              title="Strategic relevance"
              style={{ fontSize: 10, color: "var(--ink-2)", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 3px" }}
            >
              <option value="">Unclassified</option>
              {([1, 2, 3] as const).map((v) => (
                <option key={v} value={v}>{STRATEGIC_RELEVANCE_LABEL[v]}</option>
              ))}
            </select>
            <span style={{ fontSize: 10, color: "var(--ink-3)" }}>L{node.level}</span>
            <button onClick={() => setEditing(true)} title="Edit" style={actionBtn}>✎</button>
            {node.level < 3 && (
              <button onClick={() => setAdding(a => !a)} style={{ fontSize: 10, color: "var(--accent)", background: "none", border: "none", cursor: "pointer" }}>+ child</button>
            )}
            <button onClick={handleDelete} style={{ fontSize: 10, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
          </>
        )}
      </div>
      {adding && (
        <div style={{ marginLeft: 14 }}>
          <TechCapForm
            parent={node}
            onSave={async (data) => { await createCap.mutateAsync(data); setAdding(false); }}
            onCancel={() => setAdding(false)}
            saving={createCap.isPending}
          />
        </div>
      )}
      {expanded && node.children.map(child => (
        <TechCapNode key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export default function TechCapTree() {
  const { data, isLoading, error } = useTechCaps();
  const [addingRoot, setAddingRoot] = useState(false);
  const createCap = useCreateTechCap();

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading technical capabilities…</div>;
  if (error) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load technical capabilities: {error.message}</div>;

  const items = data?.items ?? [];
  const tree = buildTechCapTree(items);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} technical capabilit{items.length !== 1 ? "ies" : "y"} across all levels
        </span>
        <button onClick={() => setAddingRoot(a => !a)} style={{ fontSize: 11, color: "var(--accent)", background: "none", border: "1px solid var(--accent)", borderRadius: 4, padding: "2px 8px", cursor: "pointer" }}>
          + Root
        </button>
      </div>
      {addingRoot && (
        <TechCapForm
          onSave={async (data) => { await createCap.mutateAsync(data); setAddingRoot(false); }}
          onCancel={() => setAddingRoot(false)}
          saving={createCap.isPending}
        />
      )}
      {tree.length === 0 && !addingRoot && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No technical capabilities defined. Click "+ Root" to create the first Level 1 capability.
        </div>
      )}
      {tree.map(root => (
        <TechCapNode key={root.id} node={root} depth={0} />
      ))}
    </div>
  );
}
