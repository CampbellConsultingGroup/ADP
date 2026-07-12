import React, { useState } from "react";
import { useCreateValueStream, useUpdateValueStream } from "../api/business";
import type { ValueStream } from "../api/business";

interface ValueStreamFormProps {
  existing?: ValueStream;
  onDone: () => void;
  onCancel: () => void;
}

export default function ValueStreamForm({ existing, onDone, onCancel }: ValueStreamFormProps): React.ReactElement {
  const [name, setName] = useState(existing?.name ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [stakeholder, setStakeholder] = useState(existing?.stakeholder ?? "");

  const create = useCreateValueStream();
  const update = useUpdateValueStream(existing?.id ?? "");
  const isPending = create.isPending || update.isPending;
  const error = create.error ?? update.error;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const body = { name: name.trim(), description: description.trim() || null, stakeholder: stakeholder.trim() || null };
    if (existing) {
      update.mutate(body, { onSuccess: onDone });
    } else {
      create.mutate(body, { onSuccess: onDone });
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 6, padding: 16, marginBottom: 12 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>{existing ? "Edit Value Stream" : "New Value Stream"}</div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 3 }}>Name *</label>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Order to Cash"
          style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4, boxSizing: "border-box" }}
        />
      </div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 3 }}>Target Stakeholder</label>
        <input
          value={stakeholder}
          onChange={(e) => setStakeholder(e.target.value)}
          placeholder="Customer"
          style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4, boxSizing: "border-box" }}
        />
      </div>
      <div style={{ marginBottom: 10 }}>
        <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 3 }}>Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description"
          rows={2}
          style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4, resize: "vertical", boxSizing: "border-box" }}
        />
      </div>
      {error && <div style={{ fontSize: 12, color: "var(--crit)", marginBottom: 8 }}>{error.message}</div>}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" onClick={onCancel} style={{ padding: "6px 14px", fontSize: 13, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer" }}>
          Cancel
        </button>
        <button
          type="submit"
          disabled={!name.trim() || isPending}
          style={{ padding: "6px 14px", fontSize: 13, background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4, cursor: name.trim() ? "pointer" : "not-allowed", opacity: name.trim() ? 1 : 0.5 }}
        >
          {isPending ? "Saving…" : existing ? "Save Changes" : "Create"}
        </button>
      </div>
    </form>
  );
}
