// 940-org-units-geography US1: the org unit tree (enterprise > division > function), mirroring
// 937's AppCapTree: alphabetical siblings, "+ child" only below level 3, server rules shown verbatim.

import { useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { OrgUnit } from "../api/organization";
import { ORG_UNIT_KIND_LABEL, useCreateOrgUnit } from "../api/organization";

export interface OrgUnitNode extends OrgUnit {
  children: OrgUnitNode[];
}

export function buildOrgUnitTree(items: OrgUnit[]): OrgUnitNode[] {
  const byId = new Map<string, OrgUnitNode>();
  for (const i of items) byId.set(i.id, { ...i, children: [] });
  const roots: OrgUnitNode[] = [];
  for (const n of byId.values()) {
    if (n.parent_id && byId.has(n.parent_id)) byId.get(n.parent_id)!.children.push(n);
    else if (!n.parent_id) roots.push(n);
  }
  const sort = (ns: OrgUnitNode[]) => {
    ns.sort((a, b) => a.name.localeCompare(b.name));
    ns.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

const linkBtn: React.CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontSize: 11,
  color: "var(--accent)",
  padding: "1px 4px",
};

export function NewOrgUnitForm({ parentId, onDone }: { parentId: string | null; onDone: (id?: string) => void }): React.ReactElement {
  const create = useCreateOrgUnit();
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
        aria-label="New org unit name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onDone();
        }}
        placeholder={parentId ? "Child org unit name" : "Enterprise name"}
        style={{ flex: 1, fontSize: 13, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 3 }}
      />
      <button type="submit" disabled={create.isPending || !name.trim()} style={linkBtn}>
        Add
      </button>
      <button type="button" onClick={() => onDone()} style={{ ...linkBtn, color: "var(--ink-3)" }}>
        Cancel
      </button>
      {error && (
        <span role="alert" style={{ fontSize: 11, color: "var(--crit)" }}>
          {error}
        </span>
      )}
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
  node: OrgUnitNode;
  depth: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
  canWrite: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const [adding, setAdding] = useState(false);
  const selected = node.id === selectedId;
  return (
    <div style={{ marginLeft: depth * 14 }} data-org-unit-row={node.id}>
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
            style={{ fontSize: 10, background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", padding: 0, minWidth: 12 }}
          >
            {expanded ? "▾" : "▸"}
          </button>
        ) : (
          <span style={{ minWidth: 12 }} />
        )}
        <button
          onClick={() => onSelect(node.id)}
          aria-current={selected ? "true" : undefined}
          style={{ flex: 1, textAlign: "left", fontSize: 13, background: "none", border: "none", cursor: "pointer", color: "var(--ink)", padding: 0, fontWeight: selected ? 600 : 400 }}
        >
          {node.name}
        </button>
        {node.application_count > 0 && (
          <span style={{ fontSize: 10, color: "var(--ink-3)" }} title="Applications owned">
            {node.application_count} app{node.application_count === 1 ? "" : "s"}
          </span>
        )}
        <span style={{ fontSize: 10, color: "var(--ink-3)" }}>{ORG_UNIT_KIND_LABEL[node.kind]}</span>
        {canWrite && node.level < 3 && (
          <button onClick={() => setAdding((a) => !a)} style={{ ...linkBtn, fontSize: 10 }} aria-label={`Add child to ${node.name}`}>
            + child
          </button>
        )}
      </div>
      {adding && (
        <div style={{ marginLeft: 18 }}>
          <NewOrgUnitForm parentId={node.id} onDone={() => setAdding(false)} />
        </div>
      )}
      {expanded &&
        node.children.map((c) => (
          <Node key={c.id} node={c} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} canWrite={canWrite} />
        ))}
    </div>
  );
}

export default function OrgUnitTree({
  items,
  selectedId,
  onSelect,
  canWrite,
}: {
  items: OrgUnit[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  canWrite: boolean;
}): React.ReactElement {
  const [addingRoot, setAddingRoot] = useState(false);
  const tree = buildOrgUnitTree(items);
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} org unit{items.length === 1 ? "" : "s"}
        </span>
        {canWrite && (
          <button
            onClick={() => setAddingRoot((a) => !a)}
            style={{ fontSize: 11, color: "var(--accent)", background: "none", border: "1px solid var(--accent)", borderRadius: 4, padding: "2px 8px", cursor: "pointer" }}
          >
            + Enterprise
          </button>
        )}
      </div>
      {addingRoot && <NewOrgUnitForm parentId={null} onDone={() => setAddingRoot(false)} />}
      {tree.length === 0 && !addingRoot && (
        <div style={{ padding: 28, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No org units yet.{canWrite ? ' Click "+ Enterprise" to start the organization model.' : ""}
        </div>
      )}
      {tree.map((r) => (
        <Node key={r.id} node={r} depth={0} selectedId={selectedId} onSelect={onSelect} canWrite={canWrite} />
      ))}
    </div>
  );
}
