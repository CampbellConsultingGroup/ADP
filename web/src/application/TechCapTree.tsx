import { useEffect, useState } from "react";
import type React from "react";
import type { StrategicRelevance, TechCapLifecycle, TechnicalCapability } from "../api/application";
import {
  STRATEGIC_RELEVANCE_LABEL,
  TECH_CAP_LIFECYCLES,
  TECH_CAP_LIFECYCLE_LABEL,
  isPastEndOfLife,
  useCreateTechCap,
  useDeleteTechCap,
  useTechCaps,
  useUpdateTechCap,
} from "../api/application";
import TechCapForm from "./TechCapForm";
import TechCapImpactPanel from "./TechCapImpactPanel";
import { TechCapUsedBy } from "./AppCapSummaryList";
import { useCanWriteApplications } from "./appCapNav";
import { confirmAction } from "../ui/confirm";

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
  focusId?: string | null;
}

/** 938-capability-model-analysis US2: lifecycle status and end-of-life date on the row. Writers
 *  edit them in place (saved immediately, like strategic relevance); readers see a chip. */
function LifecycleControls({ node }: { node: TechCapTreeNode }): React.ReactElement {
  const canWrite = useCanWriteApplications();
  const updateCap = useUpdateTechCap();
  const past = isPastEndOfLife(node);
  const flag = past ? (
    <span
      title={`End-of-life date ${node.end_of_life_date} has passed`}
      style={{ fontSize: 10, color: "var(--crit)", whiteSpace: "nowrap" }}
    >
      ⚠ past end of life
    </span>
  ) : null;
  if (!canWrite) {
    return (
      <>
        <span aria-label="Lifecycle" style={{ fontSize: 10, color: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 3, padding: "0 4px" }}>
          {TECH_CAP_LIFECYCLE_LABEL[node.lifecycle_status]}
          {node.end_of_life_date ? ` · EOL ${node.end_of_life_date}` : ""}
        </span>
        {flag}
      </>
    );
  }
  const control: React.CSSProperties = {
    fontSize: 10, color: "var(--ink-2)", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 3px",
  };
  return (
    <>
      <select
        aria-label={`Lifecycle of ${node.name}`}
        value={node.lifecycle_status}
        onChange={(e) => updateCap.mutate({ id: node.id, body: { lifecycle_status: e.target.value as TechCapLifecycle } })}
        style={control}
      >
        {TECH_CAP_LIFECYCLES.map((s) => (
          <option key={s} value={s}>{TECH_CAP_LIFECYCLE_LABEL[s]}</option>
        ))}
      </select>
      <input
        type="date"
        aria-label={`End-of-life date of ${node.name}`}
        title="End-of-life date (optional)"
        value={node.end_of_life_date ?? ""}
        onChange={(e) => updateCap.mutate({ id: node.id, body: { end_of_life_date: e.target.value || null } })}
        style={{ ...control, width: 112 }}
      />
      {flag}
    </>
  );
}

function TechCapNode({ node, depth, focusId }: NodeProps) {
  const [expanded, setExpanded] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(node.name);
  const [editDescription, setEditDescription] = useState(node.description ?? "");
  const createCap = useCreateTechCap();
  const deleteCap = useDeleteTechCap();
  const updateCap = useUpdateTechCap();

  const handleDelete = async () => {
    if (!(await confirmAction(`Delete "${node.name}"? This also removes any child capabilities.`))) return;
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

  const focused = focusId === node.id;
  return (
    <div style={{ marginLeft: depth * 14 }} data-tech-cap-row={node.id}>
      <div
        style={{
          display: "flex", alignItems: "center", gap: 6, padding: "3px 0", borderRadius: 4,
          background: focused ? "var(--accent-wash, #e8f1f8)" : undefined,
        }}
      >
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
            <LifecycleControls node={node} />
            <span style={{ fontSize: 10, color: "var(--ink-3)" }}>L{node.level}</span>
            <button onClick={() => setEditing(true)} title="Edit" style={actionBtn}>✎</button>
            {node.level < 3 && (
              <button onClick={() => setAdding(a => !a)} style={{ fontSize: 10, color: "var(--accent)", background: "none", border: "none", cursor: "pointer" }}>+ child</button>
            )}
            <button onClick={handleDelete} style={{ fontSize: 10, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
          </>
        )}
      </div>
      {/* 937-application-capabilities: application capabilities map to technical L2/L3 only. */}
      {node.level >= 2 && <TechCapUsedBy tcId={node.id} />}
      {/* 938-capability-model-analysis US3: what this capability's end of life affects. */}
      <TechCapImpactPanel tcId={node.id} />
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
        <TechCapNode key={child.id} node={child} depth={depth + 1} focusId={focusId} />
      ))}
    </div>
  );
}

export default function TechCapTree({ focusId = null }: { focusId?: string | null } = {}) {
  const { data, isLoading, error } = useTechCaps();
  const [addingRoot, setAddingRoot] = useState(false);
  const createCap = useCreateTechCap();
  const loaded = !!data;

  // 938-capability-model-analysis: opened from an analysis list -- scroll to the row.
  useEffect(() => {
    if (!focusId || !loaded) return;
    document.querySelector(`[data-tech-cap-row="${focusId}"]`)?.scrollIntoView?.({ block: "center" });
  }, [focusId, loaded]);

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
        <TechCapNode key={root.id} node={root} depth={0} focusId={focusId} />
      ))}
    </div>
  );
}
