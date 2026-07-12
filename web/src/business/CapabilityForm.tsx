import React, { useState } from "react";
import { useCreateCapability } from "../api/business";
import type { BusinessCapabilityCreate } from "../api/business";

interface CapabilityFormProps {
  parentId: string | null;
  level: 1 | 2 | 3;
  onDone: () => void;
  onCancel: () => void;
}

export default function CapabilityForm({ parentId, level, onDone, onCancel }: CapabilityFormProps): React.ReactElement {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useCreateCapability();

  const levelLabels: Record<number, string> = { 1: "Strategic (L1)", 2: "Operational (L2)", 3: "Granular (L3)" };

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    const body: BusinessCapabilityCreate = { name: name.trim(), description: description.trim() || null, level, parent_id: parentId };
    create.mutate(body, { onSuccess: onDone });
  }

  return (
    <form onSubmit={handleSubmit} style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 6, padding: 12, marginTop: 6 }}>
      <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 8 }}>New {levelLabels[level]} capability</div>
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Capability name"
        style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4, marginBottom: 6, boxSizing: "border-box" }}
      />
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4, marginBottom: 8, boxSizing: "border-box" }}
      />
      {create.isError && (
        <div style={{ fontSize: 12, color: "var(--crit)", marginBottom: 6 }}>{create.error?.message}</div>
      )}
      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
        <button type="button" onClick={onCancel} style={{ padding: "5px 12px", fontSize: 13, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer" }}>
          Cancel
        </button>
        <button
          type="submit"
          disabled={!name.trim() || create.isPending}
          style={{ padding: "5px 12px", fontSize: 13, background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4, cursor: name.trim() ? "pointer" : "not-allowed", opacity: name.trim() ? 1 : 0.5 }}
        >
          {create.isPending ? "Adding…" : "Add"}
        </button>
      </div>
    </form>
  );
}
