import React, { useState } from "react";
import { useValueStreams } from "../api/business";
import ValueStreamForm from "./ValueStreamForm";

interface ValueStreamListProps {
  onSelect: (vsId: string) => void;
}

export default function ValueStreamList({ onSelect }: ValueStreamListProps): React.ReactElement {
  const { data, isLoading, error } = useValueStreams();
  const [creating, setCreating] = useState(false);

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading value streams…</div>;
  if (error) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load value streams: {error.message}</div>;

  const items = data?.items ?? [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} value stream{items.length !== 1 ? "s" : ""}
        </span>
        <button
          onClick={() => setCreating(!creating)}
          style={{ padding: "6px 14px", background: "var(--good)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600 }}
        >
          + Create Value Stream
        </button>
      </div>

      {creating && (
        <ValueStreamForm onDone={() => setCreating(false)} onCancel={() => setCreating(false)} />
      )}

      {items.length === 0 && !creating && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No value streams defined yet. Click "Create Value Stream" to add the first one.
        </div>
      )}

      {items.map((vs) => (
        <div
          key={vs.id}
          onClick={() => onSelect(vs.id)}
          style={{
            padding: "12px 16px",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            marginBottom: 6,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 2 }}>{vs.name}</div>
            {vs.stakeholder && (
              <span style={{ fontSize: 11, background: "var(--good-wash)", color: "var(--good)", padding: "1px 7px", borderRadius: 8, fontWeight: 600 }}>
                {vs.stakeholder}
              </span>
            )}
            {vs.description && (
              <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 3 }}>{vs.description}</div>
            )}
          </div>
          <span style={{ fontSize: 12, color: "var(--ink-3)" }}>›</span>
        </div>
      ))}
    </div>
  );
}
