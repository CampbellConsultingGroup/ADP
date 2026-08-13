import React, { useState } from "react";
import { useValueStreams, useOrphanReport } from "../api/business";
import ValueStreamForm from "./ValueStreamForm";

interface ValueStreamListProps {
  onSelect: (vsId: string) => void;
}

export default function ValueStreamList({ onSelect }: ValueStreamListProps): React.ReactElement {
  const { data, isLoading, error } = useValueStreams();
  const { data: orphanData } = useOrphanReport();
  const [creating, setCreating] = useState(false);
  const [orphansOnly, setOrphansOnly] = useState(false);

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading value streams…</div>;
  if (error) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load value streams: {error.message}</div>;

  const items = data?.items ?? [];
  const orphanIds = new Set((orphanData?.orphan_value_streams ?? []).map((v) => v.id));
  const visibleItems = orphansOnly ? items.filter((v) => orphanIds.has(v.id)) : items;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} value stream{items.length !== 1 ? "s" : ""}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setOrphansOnly(!orphansOnly)}
            title="Show only value streams with no strategic-objective linkage"
            style={{
              padding: "6px 14px",
              background: orphansOnly ? "var(--warn-wash)" : "var(--surface)",
              color: orphansOnly ? "var(--warn)" : "var(--ink-2)",
              border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600,
            }}
          >
            {orphansOnly ? "Showing orphans only" : "Show orphans only"}
          </button>
          <button
            onClick={() => setCreating(!creating)}
            style={{ padding: "6px 14px", background: "var(--good)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600 }}
          >
            + Create Value Stream
          </button>
        </div>
      </div>

      {creating && (
        <ValueStreamForm onDone={() => setCreating(false)} onCancel={() => setCreating(false)} />
      )}

      {visibleItems.length === 0 && !creating && orphansOnly && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No value streams with missing strategic linkage.
        </div>
      )}

      {visibleItems.length === 0 && !creating && !orphansOnly && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No value streams defined yet. Click "Create Value Stream" to add the first one.
        </div>
      )}

      {visibleItems.map((vs) => (
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
            {orphanIds.has(vs.id) && (
              <span
                title="Not referenced by any strategic objective"
                style={{ marginLeft: 6, fontSize: 11, background: "var(--warn-wash)", color: "var(--warn)", padding: "1px 7px", borderRadius: 8, fontWeight: 600 }}
              >
                no strategic linkage
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
