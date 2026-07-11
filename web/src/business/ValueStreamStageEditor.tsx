import React, { useState } from "react";
import { useAddStage, useDeleteStage, useReorderStages, useUpdateStage } from "../api/business";
import type { ValueStreamStage } from "../api/business";
import StageCapsEditor from "./StageCapsEditor";

interface ValueStreamStageEditorProps {
  vsId: string;
  stages: ValueStreamStage[];
}

export default function ValueStreamStageEditor({ vsId, stages }: ValueStreamStageEditorProps): React.ReactElement {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [addingName, setAddingName] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  const addStage = useAddStage(vsId);
  const deleteStage = useDeleteStage(vsId);
  const reorder = useReorderStages(vsId);

  function startEdit(stage: ValueStreamStage) {
    setEditingId(stage.id);
    setEditName(stage.name);
  }

  function handleMoveUp(index: number) {
    if (index === 0) return;
    const reordered = [...stages];
    [reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]];
    reorder.mutate({ stages: reordered.map((s) => ({ id: s.id, name: s.name, description: s.description })) });
  }

  function handleMoveDown(index: number) {
    if (index === stages.length - 1) return;
    const reordered = [...stages];
    [reordered[index], reordered[index + 1]] = [reordered[index + 1], reordered[index]];
    reorder.mutate({ stages: reordered.map((s) => ({ id: s.id, name: s.name, description: s.description })) });
  }

  function handleAddStage(e: React.FormEvent) {
    e.preventDefault();
    if (!addingName.trim()) return;
    addStage.mutate({ name: addingName.trim(), position: stages.length }, {
      onSuccess: () => { setAddingName(""); setShowAdd(false); },
    });
  }

  const updateStage = useUpdateStage(vsId, editingId ?? "");

  function handleSaveEdit() {
    if (!editingId || !editName.trim()) return;
    updateStage.mutate({ name: editName.trim() }, { onSuccess: () => setEditingId(null) });
  }

  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Stages ({stages.length})
      </div>

      {stages.length === 0 && (
        <div style={{ fontSize: 13, color: "#9CA3AF", padding: "12px 0", fontStyle: "italic" }}>
          No stages yet. Add the first stage below.
        </div>
      )}

      {stages.map((stage, index) => (
        <div
          key={stage.id}
          style={{ border: "1px solid #E5E7EB", borderRadius: 4, marginBottom: 8, overflow: "hidden" }}
        >
          {/* Stage header row */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 8px", background: "#F9FAFB" }}>
            <span style={{ fontSize: 11, color: "#9CA3AF", minWidth: 20, textAlign: "right" }}>{index + 1}</span>

            {editingId === stage.id ? (
              <>
                <input
                  autoFocus
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSaveEdit(); if (e.key === "Escape") setEditingId(null); }}
                  style={{ flex: 1, padding: "3px 6px", fontSize: 13, border: "1px solid #93C5FD", borderRadius: 3 }}
                />
                <button onClick={handleSaveEdit} style={{ padding: "2px 8px", fontSize: 12, background: "#1168BD", color: "#fff", border: "none", borderRadius: 3, cursor: "pointer" }}>Save</button>
                <button onClick={() => setEditingId(null)} style={{ padding: "2px 8px", fontSize: 12, background: "#fff", border: "1px solid #D1D5DB", borderRadius: 3, cursor: "pointer" }}>×</button>
              </>
            ) : (
              <>
                <span style={{ flex: 1, fontSize: 13, color: "#111827" }}>{stage.name}</span>
                <button onClick={() => startEdit(stage)} title="Edit" style={btnStyle}>✎</button>
                <button onClick={() => handleMoveUp(index)} disabled={index === 0} title="Move up" style={{ ...btnStyle, opacity: index === 0 ? 0.3 : 1 }}>↑</button>
                <button onClick={() => handleMoveDown(index)} disabled={index === stages.length - 1} title="Move down" style={{ ...btnStyle, opacity: index === stages.length - 1 ? 0.3 : 1 }}>↓</button>
                <button
                  onClick={() => deleteStage.mutate(stage.id)}
                  title="Delete stage"
                  style={{ ...btnStyle, color: "#B91C1C" }}
                >×</button>
              </>
            )}
          </div>

          {/* Stage capabilities (ADP-SPEC-035) */}
          <div style={{ padding: "6px 12px 10px 12px", borderTop: "1px solid #F3F4F6" }}>
            <StageCapsEditor vsId={vsId} stageId={stage.id} />
          </div>
        </div>
      ))}

      {showAdd ? (
        <form onSubmit={handleAddStage} style={{ display: "flex", gap: 6, marginTop: 6 }}>
          <input
            autoFocus
            value={addingName}
            onChange={(e) => setAddingName(e.target.value)}
            placeholder="Stage name"
            style={{ flex: 1, padding: "5px 8px", fontSize: 13, border: "1px solid #D1D5DB", borderRadius: 4 }}
          />
          <button type="submit" disabled={!addingName.trim() || addStage.isPending} style={{ padding: "5px 10px", fontSize: 13, background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
            {addStage.isPending ? "…" : "Add"}
          </button>
          <button type="button" onClick={() => { setShowAdd(false); setAddingName(""); }} style={{ padding: "5px 10px", fontSize: 13, background: "#fff", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer" }}>
            Cancel
          </button>
        </form>
      ) : (
        <button onClick={() => setShowAdd(true)} style={{ marginTop: 8, padding: "5px 12px", fontSize: 13, background: "#fff", border: "1px dashed #D1D5DB", borderRadius: 4, cursor: "pointer", color: "#6B7280" }}>
          + Add Stage
        </button>
      )}
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: "2px 6px",
  fontSize: 13,
  background: "transparent",
  border: "none",
  borderRadius: 3,
  cursor: "pointer",
  color: "#374151",
};
