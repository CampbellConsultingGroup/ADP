import React, { useState } from "react";
import { useDeleteValueStream, useValueStream } from "../api/business";
import { generateFromValueStream } from "../diagrams/generators";
import type { DiagramSeed } from "../diagrams/generators";
import ValueStreamStageEditor from "./ValueStreamStageEditor";
import ValueStreamForm from "./ValueStreamForm";
import DesignLinkEditor from "./DesignLinkEditor";

interface ValueStreamDetailProps {
  vsId: string;
  onBack: () => void;
  /** ADP-914.7: opens the Diagrams screen pre-filled with a flowchart
   *  generated from this value stream's ordered stages. */
  onGenerateDiagram?: (seed: DiagramSeed) => void;
}

export default function ValueStreamDetail({ vsId, onBack, onGenerateDiagram }: ValueStreamDetailProps): React.ReactElement {
  const { data: vs, isLoading, error } = useValueStream(vsId);
  const deleteMut = useDeleteValueStream();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading…</div>;
  if (error || !vs) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load value stream.</div>;

  function handleDelete() {
    deleteMut.mutate(vsId, { onSuccess: onBack });
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 13, color: "var(--ink-3)", padding: "4px 0" }}>
          ← Back
        </button>
      </div>

      {editing ? (
        <ValueStreamForm existing={vs} onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />
      ) : (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <h2 style={{ margin: "0 0 4px", fontSize: 18, fontWeight: 700, color: "var(--ink)" }}>{vs.name}</h2>
              {vs.stakeholder && (
                <span style={{ fontSize: 12, background: "var(--accent-wash)", color: "var(--accent)", padding: "2px 8px", borderRadius: 10, fontWeight: 600 }}>
                  Stakeholder: {vs.stakeholder}
                </span>
              )}
              {vs.description && (
                <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--ink-2)" }}>{vs.description}</p>
              )}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={() => onGenerateDiagram?.(generateFromValueStream(vs))} style={outlineBtn}>Generate Diagram</button>
              <button onClick={() => setEditing(true)} style={outlineBtn}>Edit</button>
              <button onClick={() => setConfirmDelete(true)} style={{ ...outlineBtn, color: "var(--crit)", borderColor: "var(--crit)" }}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete && (
        <div style={{ padding: 12, background: "var(--crit-wash)", border: "1px solid var(--crit)", borderRadius: 6, marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: "var(--crit)" }}>Delete "{vs.name}" and all its stages? This cannot be undone.</span>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={handleDelete} disabled={deleteMut.isPending} style={{ padding: "4px 12px", fontSize: 13, background: "var(--crit)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
              {deleteMut.isPending ? "Deleting…" : "Yes, delete"}
            </button>
            <button onClick={() => setConfirmDelete(false)} style={{ padding: "4px 12px", fontSize: 13, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer" }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Stages */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16, marginBottom: 16 }}>
        <ValueStreamStageEditor vsId={vsId} stages={vs.stages} />
      </div>

      {/* Supporting Designs */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 16 }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>Supporting Designs</h3>
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "var(--ink-3)" }}>
          Link solution designs that support or implement this value stream.
        </p>
        <DesignLinkEditor entityType="value-stream" entityId={vsId} />
      </div>
    </div>
  );
}

const outlineBtn: React.CSSProperties = {
  padding: "5px 12px",
  fontSize: 13,
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 4,
  cursor: "pointer",
  color: "var(--ink-2)",
};
