import React, { useState } from "react";
import type { TechCapLifecycle, TechnicalCapability, TechnicalCapabilityCreate } from "../api/application";
import { TECH_CAP_LIFECYCLES, TECH_CAP_LIFECYCLE_LABEL } from "../api/application";

interface Props {
  parent?: TechnicalCapability | null;
  onSave: (data: TechnicalCapabilityCreate) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
}

export default function TechCapForm({ parent, onSave, onCancel, saving }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [lifecycle, setLifecycle] = useState<TechCapLifecycle>("current");
  const [endOfLife, setEndOfLife] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError("Name is required"); return; }
    setError(null);
    try {
      await onSave({
        name: name.trim(),
        description: description || null,
        parent_id: parent?.id ?? null,
        lifecycle_status: lifecycle,
        end_of_life_date: endOfLife || null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  };

  const field: React.CSSProperties = { width: "100%", padding: "5px 8px", fontSize: 12, border: "1px solid var(--border)", borderRadius: 4 };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 8, padding: "10px 12px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 6 }}>
      {parent && <div style={{ fontSize: 11, color: "var(--ink-3)" }}>Under: {parent.name} (L{parent.level})</div>}
      {error && <div style={{ fontSize: 11, color: "var(--crit)" }}>{error}</div>}
      <input style={field} value={name} onChange={e => setName(e.target.value)} placeholder="Capability name *" autoFocus />
      <input style={field} value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)" />
      <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 11, color: "var(--ink-3)" }}>
        <label style={{ display: "flex", gap: 4, alignItems: "center" }}>
          Lifecycle
          <select style={{ ...field, width: "auto" }} value={lifecycle} onChange={e => setLifecycle(e.target.value as TechCapLifecycle)}>
            {TECH_CAP_LIFECYCLES.map(s => <option key={s} value={s}>{TECH_CAP_LIFECYCLE_LABEL[s]}</option>)}
          </select>
        </label>
        <label style={{ display: "flex", gap: 4, alignItems: "center" }}>
          End of life
          <input type="date" style={{ ...field, width: "auto" }} value={endOfLife} onChange={e => setEndOfLife(e.target.value)} />
        </label>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <button type="submit" disabled={saving} style={{ fontSize: 11, padding: "4px 12px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer" }}>
          {saving ? "…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} style={{ fontSize: 11, padding: "4px 10px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer" }}>
          Cancel
        </button>
      </div>
    </form>
  );
}
