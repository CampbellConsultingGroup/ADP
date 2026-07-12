import React from "react";
import { useRequirements } from "../api/intake";
import { KIND_HUE, kindLabel } from "./kinds";

interface RequirementsListProps { designId: string; }

export default function RequirementsList({ designId }: RequirementsListProps): React.ReactElement {
  const { data, isLoading } = useRequirements(designId);
  if (isLoading) return <div style={{ padding: 8, color: "var(--ink-3)", fontSize: 12 }}>Loading…</div>;
  const requirements = data?.requirements ?? [];
  if (requirements.length === 0) {
    return <div style={{ padding: 12, color: "var(--ink-3)", fontSize: 13, fontStyle: "italic" }}>No requirements yet — use the intake form.</div>;
  }
  return (
    <div>
      {requirements.map((req) => (
        <div key={req.id} style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
            <span style={{ background: KIND_HUE[req.kind] ?? "var(--ink-3)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4 }}>{req.id}</span>
            <span style={{ background: "var(--surface-2)", border: "1px solid var(--border)", color: "var(--ink-2)", fontSize: 10, padding: "2px 6px", borderRadius: 4 }}>{kindLabel(req.kind)}</span>
          </div>
          <div style={{ fontSize: 13, color: "var(--ink)" }}>{req.title}</div>
          {req.satisfies.length > 0 && <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>Satisfied by: {req.satisfies.join(", ")}</div>}
        </div>
      ))}
    </div>
  );
}
