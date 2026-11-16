/** All adoptions with their derived status (936 US1/US2, FR-021). */

import React, { useState } from "react";
import { useAdoptions } from "../api/patterns";
import type { DiagramSeed } from "../diagrams/generators";
import { StatusBadge } from "../ui";
import AdoptionForm from "./AdoptionForm";
import AdoptionPage from "./AdoptionPage";
import { SCOPE_LABELS, STATUS_LABELS, STATUS_TONES } from "./labels";
import { useCanManagePatterns } from "./permissions";

const cell: React.CSSProperties = { padding: "7px 10px", borderBottom: "1px solid var(--border)", fontSize: 12.5, textAlign: "left" };

export default function AdoptionsList({
  onGenerateDiagram,
  initialSelected = null,
}: {
  onGenerateDiagram?: (seed: DiagramSeed) => void;
  /** 939-governance-architecture-health: opened from Governance -> Architecture Health. */
  initialSelected?: string | null;
}) {
  const canManage = useCanManagePatterns();
  const { data, isLoading } = useAdoptions(true);
  const [selected, setSelected] = useState<string | null>(initialSelected);
  const [creating, setCreating] = useState(false);

  if (selected) {
    return <AdoptionPage adoptionId={selected} onBack={() => setSelected(null)} onGenerateDiagram={onGenerateDiagram} />;
  }
  if (creating) {
    return (
      <div style={{ padding: "16px 20px", overflow: "auto", height: "100%" }}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>Adopt a pattern</h2>
        <AdoptionForm onCreated={(a) => { setCreating(false); setSelected(a.id); }} onCancel={() => setCreating(false)} />
      </div>
    );
  }
  const items = data?.items ?? [];
  return (
    <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12, overflow: "auto", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)", flex: 1 }}>
          Where each pattern applies, and whether the estate conforms right now. Status is computed from
          the live registries every time; nothing is stored.
        </p>
        {canManage && (
          <button type="button" className="ui-btn ui-btn-primary ui-btn-sm" onClick={() => setCreating(true)}>Adopt a pattern</button>
        )}
      </div>
      {isLoading ? (
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Evaluating…</div>
      ) : items.length === 0 ? (
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No adoptions yet.</div>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>{["Adoption", "Pattern", "Scope", "Version", "Status"].map((h) => <th key={h} style={{ ...cell, color: "var(--ink-3)", fontWeight: 600 }}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id} onClick={() => setSelected(a.id)} style={{ cursor: "pointer" }}>
                <td style={cell}>
                  <button type="button" onClick={(e) => { e.stopPropagation(); setSelected(a.id); }}
                    style={{ background: "none", border: "none", padding: 0, color: "var(--accent)", cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>
                    {a.name}
                  </button>
                </td>
                <td style={cell}>{a.pattern_name ?? a.pattern_key}</td>
                <td style={cell}>{SCOPE_LABELS[a.scope_type]}{a.scope_name ? `: ${a.scope_name}` : ""}</td>
                <td style={cell}>{a.pinned_version ?? `current (${a.resolved_version ?? "none"})`}</td>
                <td style={cell}>{a.status ? <StatusBadge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</StatusBadge> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
