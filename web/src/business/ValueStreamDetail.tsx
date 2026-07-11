import React, { useState } from "react";
import { useDeleteValueStream, useValueStream } from "../api/business";
import ValueStreamStageEditor from "./ValueStreamStageEditor";
import ValueStreamForm from "./ValueStreamForm";
import DesignLinkEditor from "./DesignLinkEditor";

interface ValueStreamDetailProps {
  vsId: string;
  onBack: () => void;
}

export default function ValueStreamDetail({ vsId, onBack }: ValueStreamDetailProps): React.ReactElement {
  const { data: vs, isLoading, error } = useValueStream(vsId);
  const deleteMut = useDeleteValueStream();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (isLoading) return <div style={{ padding: 20, color: "#6B7280", fontSize: 14 }}>Loading…</div>;
  if (error || !vs) return <div style={{ padding: 14, background: "#FEE2E2", borderRadius: 6, fontSize: 13, color: "#B91C1C" }}>Failed to load value stream.</div>;

  function handleDelete() {
    deleteMut.mutate(vsId, { onSuccess: onBack });
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 13, color: "#6B7280", padding: "4px 0" }}>
          ← Back
        </button>
      </div>

      {editing ? (
        <ValueStreamForm existing={vs} onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />
      ) : (
        <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <h2 style={{ margin: "0 0 4px", fontSize: 18, fontWeight: 700, color: "#111827" }}>{vs.name}</h2>
              {vs.stakeholder && (
                <span style={{ fontSize: 12, background: "#DBEAFE", color: "#1D4ED8", padding: "2px 8px", borderRadius: 10, fontWeight: 600 }}>
                  Stakeholder: {vs.stakeholder}
                </span>
              )}
              {vs.description && (
                <p style={{ margin: "8px 0 0", fontSize: 13, color: "#374151" }}>{vs.description}</p>
              )}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={() => setEditing(true)} style={outlineBtn}>Edit</button>
              <button onClick={() => setConfirmDelete(true)} style={{ ...outlineBtn, color: "#B91C1C", borderColor: "#FECACA" }}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete && (
        <div style={{ padding: 12, background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 6, marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: "#B91C1C" }}>Delete "{vs.name}" and all its stages? This cannot be undone.</span>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={handleDelete} disabled={deleteMut.isPending} style={{ padding: "4px 12px", fontSize: 13, background: "#B91C1C", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
              {deleteMut.isPending ? "Deleting…" : "Yes, delete"}
            </button>
            <button onClick={() => setConfirmDelete(false)} style={{ padding: "4px 12px", fontSize: 13, background: "#fff", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer" }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Stages */}
      <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 16, marginBottom: 16 }}>
        <ValueStreamStageEditor vsId={vsId} stages={vs.stages} />
      </div>

      {/* Supporting Designs */}
      <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 16 }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 600, color: "#111827" }}>Supporting Designs</h3>
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "#6B7280" }}>
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
  background: "#fff",
  border: "1px solid #D1D5DB",
  borderRadius: 4,
  cursor: "pointer",
  color: "#374151",
};
