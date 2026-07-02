import React from "react";
import { useRequirements, type RequirementKind } from "../api/intake";

interface RequirementsListProps { designId: string; }

const KIND_COLORS: Record<RequirementKind, string> = {
  functional: "#1168BD", non_functional: "#6B21A8",
  constraint: "#C2410C", driver: "#166534",
};

export default function RequirementsList({ designId }: RequirementsListProps): React.ReactElement {
  const { data, isLoading } = useRequirements(designId);
  if (isLoading) return <div style={{ padding: 8, color: "#888", fontSize: 12 }}>Loading...</div>;
  const requirements = data?.requirements ?? [];
  if (requirements.length === 0) {
    return <div style={{ padding: 12, color: "#999", fontSize: 13, fontStyle: "italic" }}>No requirements yet — use the intake form.</div>;
  }
  return (
    <div>
      {requirements.map((req) => (
        <div key={req.id} style={{ padding: "8px 12px", borderBottom: "1px solid #eee" }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
            <span style={{ background: KIND_COLORS[req.kind] ?? "#888", color: "#fff", fontSize: 10, fontWeight: "bold", padding: "2px 6px", borderRadius: 3 }}>{req.id}</span>
            <span style={{ background: "#f0f0f0", color: "#555", fontSize: 10, padding: "2px 6px", borderRadius: 3 }}>{req.kind.replace("_", " ")}</span>
          </div>
          <div style={{ fontSize: 13, color: "#333" }}>{req.title}</div>
          {req.satisfies.length > 0 && <div style={{ fontSize: 11, color: "#999", marginTop: 2 }}>Satisfied by: {req.satisfies.join(", ")}</div>}
        </div>
      ))}
    </div>
  );
}
