// 937-application-capabilities: the application capability catalog (L1-L3), with the derived
// "missing technical capability" badge. Mirrors TechCapTree.tsx (alphabetical siblings,
// "+ child" only below L3).

import { useState } from "react";
import type React from "react";
import type { ApplicationCapability } from "../api/appCapabilities";
import { MISSING_TECHNICAL_CAPABILITY, errorDetail, useCreateAppCapability } from "../api/appCapabilities";

export interface AppCapTreeNode extends ApplicationCapability {
  children: AppCapTreeNode[];
}

export function buildAppCapTree(items: ApplicationCapability[]): AppCapTreeNode[] {
  const byId = new Map<string, AppCapTreeNode>();
  for (const item of items) byId.set(item.id, { ...item, children: [] });
  const roots: AppCapTreeNode[] = [];
  for (const node of byId.values()) {
    if (node.parent_id && byId.has(node.parent_id)) byId.get(node.parent_id)!.children.push(node);
    else if (!node.parent_id) roots.push(node);
  }
  const sortByName = (nodes: AppCapTreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    for (const n of nodes) sortByName(n.children);
  };
  sortByName(roots);
  return roots;
}

export function MissingTechBadge(): React.ReactElement {
  return (
    <span
      title="Governance warning: this application capability has no technical capability behind it. Saving is not blocked."
      style={{
        fontSize: 10,
        color: "var(--warn, #9a6700)",
        background: "var(--warn-wash, #fff4d6)",
        border: "1px solid var(--warn, #9a6700)",
        borderRadius: 3,
        padding: "0 4px",
        whiteSpace: "nowrap",
      }}
    >
      ⚠ No technical capability
    </span>
  );
}

export function NewAppCapForm({
  parentId,
  onDone,
}: {
  parentId: string | null;
  onDone: (createdId?: string) => void;
}): React.ReactElement {
  const create = useCreateAppCapability();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const created = await create.mutateAsync({ name: name.trim(), parent_id: parentId });
      setName("");
      setError(null);
      onDone(created.id);
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  return (
    <form onSubmit={submit} style={{ display: "flex", gap: 6, alignItems: "center", margin: "4px 0" }}>
      <input
        autoFocus
        aria-label="New application capability name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape") onDone(); }}
        placeholder={parentId ? "Child capability name" : "Level 1 capability name"}
        style={{ flex: 1, fontSize: 13, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 3 }}
      />
      <button type="submit" disabled={create.isPending || !name.trim()} className="ui-btn-link">Add</button>
      <button type="button" onClick={() => onDone()} className="ui-btn-link muted">Cancel</button>
      {error && <span role="alert" style={{ fontSize: 11, color: "var(--crit)" }}>{error}</span>}
    </form>
  );
}

function Node({
  node,
  depth,
  selectedId,
  onSelect,
  canWrite,
}: {
  node: AppCapTreeNode;
  depth: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
  canWrite: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const [adding, setAdding] = useState(false);
  const selected = node.id === selectedId;
  return (
    <div style={{ marginLeft: depth * 14 }} data-app-cap-row={node.id}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "3px 4px",
          borderRadius: 4,
          background: selected ? "var(--accent-wash, #e8f1f8)" : undefined,
        }}
      >
        {node.children.length > 0 ? (
          <button
            onClick={() => setExpanded((e) => !e)}
            aria-label={expanded ? `Collapse ${node.name}` : `Expand ${node.name}`}
            className="ui-btn-plain" style={{ fontSize: 10, background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", padding: 0, minWidth: 12 }}
          >
            {expanded ? "▾" : "▸"}
          </button>
        ) : (
          <span style={{ minWidth: 12 }} />
        )}
        <button
          onClick={() => onSelect(node.id)}
          aria-current={selected ? "true" : undefined}
          className="ui-btn-plain" style={{ flex: 1, textAlign: "left", fontSize: 13, background: "none", border: "none", cursor: "pointer", color: "var(--ink)", padding: 0, fontWeight: selected ? 600 : 400 }}
        >
          {node.name}
        </button>
        {node.warnings.includes(MISSING_TECHNICAL_CAPABILITY) && <MissingTechBadge />}
        {node.level === 3 && (
          <span style={{ fontSize: 10, color: "var(--ink-3)" }} title="Business / technical / applications">
            {node.business_capability_count}·{node.technical_capability_count}·{node.realization_count}
          </span>
        )}
        <span style={{ fontSize: 10, color: "var(--ink-3)" }}>L{node.level}</span>
        {canWrite && node.level < 3 && (
          <button onClick={() => setAdding((a) => !a)} className="ui-btn-link" aria-label={`Add child to ${node.name}`}>
            + child
          </button>
        )}
      </div>
      {adding && (
        <div style={{ marginLeft: 18 }}>
          <NewAppCapForm parentId={node.id} onDone={() => setAdding(false)} />
        </div>
      )}
      {expanded &&
        node.children.map((child) => (
          <Node key={child.id} node={child} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} canWrite={canWrite} />
        ))}
    </div>
  );
}

export default function AppCapTree({
  items,
  selectedId,
  onSelect,
  canWrite,
}: {
  items: ApplicationCapability[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  canWrite: boolean;
}): React.ReactElement {
  const [addingRoot, setAddingRoot] = useState(false);
  const tree = buildAppCapTree(items);
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} application capabilit{items.length !== 1 ? "ies" : "y"} across all levels
        </span>
        {canWrite && (
          <button
            onClick={() => setAddingRoot((a) => !a)}
            className="ui-btn ui-btn-xs"
          >
            + Root
          </button>
        )}
      </div>
      {addingRoot && <NewAppCapForm parentId={null} onDone={() => setAddingRoot(false)} />}
      {tree.length === 0 && !addingRoot && (
        <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No application capabilities yet.{canWrite ? ' Click "+ Root" to create the first Level 1 capability.' : ""}
        </div>
      )}
      {tree.map((root) => (
        <Node key={root.id} node={root} depth={0} selectedId={selectedId} onSelect={onSelect} canWrite={canWrite} />
      ))}
    </div>
  );
}
