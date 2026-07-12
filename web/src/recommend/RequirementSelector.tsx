import React, { useEffect, useState } from "react";
import { useRequirements, type RequirementKind } from "../api/intake";

interface RequirementSelectorProps {
  designId: string;
  onSubmit: (ids: string[]) => void;
  isPending: boolean;
}

const KIND_COLORS: Record<RequirementKind, string> = {
  functional: "var(--accent)",
  non_functional: "var(--biz)",
  constraint: "var(--tec)",
  driver: "var(--good)",
};

export default function RequirementSelector({ designId, onSubmit, isPending }: RequirementSelectorProps): React.ReactElement {
  const { data } = useRequirements(designId);
  const requirements = data?.requirements ?? [];
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Default: all selected
  useEffect(() => {
    if (requirements.length > 0) {
      setSelected(new Set(requirements.map((r) => r.id)));
    }
  }, [requirements.length]);

  if (requirements.length === 0) {
    return (
      <div style={{ padding: 16, background: "var(--warn-wash)", borderRadius: 6, border: "1px solid var(--warn)", fontSize: 13, color: "var(--warn)" }}>
        No confirmed requirements yet. <strong>Add requirements via the Intake screen</strong> to get recommendations.
      </div>
    );
  }

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div style={{ marginBottom: 16, padding: 14, background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-2)", marginBottom: 10 }}>
        Requirements to include ({selected.size}/{requirements.length} selected)
      </div>
      {requirements.map((req) => (
        <label key={req.id} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={selected.has(req.id)}
            onChange={() => toggle(req.id)}
            style={{ flexShrink: 0 }}
          />
          <span style={{ background: KIND_COLORS[req.kind as RequirementKind] ?? "var(--ink-3)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 5px", borderRadius: 3 }}>
            {req.id}
          </span>
          <span style={{ fontSize: 13, color: "var(--ink-2)" }}>{req.title}</span>
        </label>
      ))}
      <button
        disabled={selected.size === 0 || isPending}
        onClick={() => onSubmit(Array.from(selected))}
        style={{
          marginTop: 10, padding: "8px 18px",
          background: selected.size > 0 && !isPending ? "var(--accent)" : "var(--border)",
          color: "#fff", border: "none", borderRadius: 4,
          cursor: selected.size > 0 && !isPending ? "pointer" : "not-allowed",
          fontSize: 14, fontWeight: 600,
        }}
      >
        {isPending ? "Generating..." : "Get Recommendations"}
      </button>
    </div>
  );
}
