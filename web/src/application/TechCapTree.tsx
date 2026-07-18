import { useState } from "react";
import type { StrategicRelevance, TechnicalCapability } from "../api/application";
import { STRATEGIC_RELEVANCE_LABEL, useCreateTechCap, useDeleteTechCap, useUpdateTechCap } from "../api/application";
import TechCapForm from "./TechCapForm";

interface Props {
  caps: TechnicalCapability[];
}

interface NodeProps {
  cap: TechnicalCapability;
  children: TechnicalCapability[];
  allCaps: TechnicalCapability[];
  depth: number;
}

function TechCapNode({ cap, children, allCaps, depth }: NodeProps) {
  const [expanded, setExpanded] = useState(true);
  const [adding, setAdding] = useState(false);
  const createCap = useCreateTechCap();
  const deleteCap = useDeleteTechCap();
  const updateCap = useUpdateTechCap();

  const handleDelete = async () => {
    if (!confirm(`Delete "${cap.name}"? This also removes any child capabilities.`)) return;
    deleteCap.mutate(cap.id);
  };

  const handleRelevanceChange = (value: string) => {
    const strategic_relevance = value === "" ? null : (Number(value) as StrategicRelevance);
    updateCap.mutate({ id: cap.id, body: { strategic_relevance } });
  };

  return (
    <div style={{ marginLeft: depth * 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 0" }}>
        {children.length > 0 && (
          <button onClick={() => setExpanded(e => !e)} style={{ fontSize: 10, background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", padding: 0, minWidth: 12 }}>
            {expanded ? "▾" : "▸"}
          </button>
        )}
        {children.length === 0 && <span style={{ minWidth: 12 }} />}
        <span style={{ fontSize: 13, flex: 1 }}>{cap.name}</span>
        <select
          value={cap.strategic_relevance ?? ""}
          onChange={(e) => handleRelevanceChange(e.target.value)}
          title="Strategic relevance"
          style={{ fontSize: 10, color: "var(--ink-2)", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 3px" }}
        >
          <option value="">Unclassified</option>
          {([1, 2, 3] as const).map((v) => (
            <option key={v} value={v}>{STRATEGIC_RELEVANCE_LABEL[v]}</option>
          ))}
        </select>
        <span style={{ fontSize: 10, color: "var(--ink-3)" }}>L{cap.level}</span>
        {cap.level < 3 && (
          <button onClick={() => setAdding(a => !a)} style={{ fontSize: 10, color: "var(--accent)", background: "none", border: "none", cursor: "pointer" }}>+ child</button>
        )}
        <button onClick={handleDelete} style={{ fontSize: 10, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
      </div>
      {adding && (
        <div style={{ marginLeft: 14 }}>
          <TechCapForm
            parent={cap}
            onSave={async (data) => { await createCap.mutateAsync(data); setAdding(false); }}
            onCancel={() => setAdding(false)}
            saving={createCap.isPending}
          />
        </div>
      )}
      {expanded && children.map(child => (
        <TechCapNode
          key={child.id}
          cap={child}
          children={allCaps.filter(c => c.parent_id === child.id)}
          allCaps={allCaps}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

export default function TechCapTree({ caps }: Props) {
  const [addingRoot, setAddingRoot] = useState(false);
  const createCap = useCreateTechCap();
  const roots = caps.filter(c => c.parent_id === null);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Technical Capabilities</h4>
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
      {roots.length === 0 && !addingRoot && (
        <div style={{ fontSize: 12, color: "var(--ink-3)" }}>No technical capabilities defined.</div>
      )}
      {roots.map(root => (
        <TechCapNode
          key={root.id}
          cap={root}
          children={caps.filter(c => c.parent_id === root.id)}
          allCaps={caps}
          depth={0}
        />
      ))}
    </div>
  );
}
