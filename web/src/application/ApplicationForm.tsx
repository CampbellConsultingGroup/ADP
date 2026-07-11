import React, { useState } from "react";
import type { Application, ApplicationCreate } from "../api/application";

interface Props {
  initial?: Application | null;
  onSave: (data: ApplicationCreate) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
}

const TIME_OPTIONS = ["", "Tolerate", "Invest", "Migrate", "Eliminate"] as const;
const R_OPTIONS = ["", "Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain", "Relocate"] as const;
const PACE_OPTIONS = ["", "Record", "Differentiation", "Innovation"] as const;

export default function ApplicationForm({ initial, onSave, onCancel, saving }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [vendor, setVendor] = useState(initial?.vendor ?? "");
  const [owner, setOwner] = useState(initial?.primary_owner ?? "");
  const [time, setTime] = useState<string>(initial?.time_classification ?? "");
  const [rStrategy, setRStrategy] = useState<string>(initial?.r_strategy ?? "");
  const [pace, setPace] = useState<string>(initial?.pace_layer ?? "");
  const [health, setHealth] = useState<string>(initial?.health_score?.toString() ?? "");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError("Name is required"); return; }
    const healthNum = health ? parseInt(health, 10) : null;
    if (healthNum !== null && (healthNum < 1 || healthNum > 5)) {
      setError("Health score must be 1–5");
      return;
    }
    setError(null);
    try {
      await onSave({
        name: name.trim(),
        description: description || null,
        vendor: vendor || null,
        primary_owner: owner || null,
        time_classification: (time || null) as ApplicationCreate["time_classification"],
        r_strategy: (rStrategy || null) as ApplicationCreate["r_strategy"],
        pace_layer: (pace || null) as ApplicationCreate["pace_layer"],
        health_score: healthNum,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  };

  const field: React.CSSProperties = { width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid #ccc", borderRadius: 4 };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12, padding: 16 }}>
      <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{initial ? "Edit Application" : "New Application"}</h3>
      {error && <div style={{ color: "#c00", fontSize: 12 }}>{error}</div>}

      <label style={{ fontSize: 12, color: "#555" }}>Name *
        <input style={field} value={name} onChange={e => setName(e.target.value)} placeholder="My Application" />
      </label>

      <label style={{ fontSize: 12, color: "#555" }}>Description
        <textarea style={{ ...field, height: 60 }} value={description} onChange={e => setDescription(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "#555" }}>Vendor
        <input style={field} value={vendor} onChange={e => setVendor(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "#555" }}>Primary Owner
        <input style={field} value={owner} onChange={e => setOwner(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "#555" }}>TIME Classification
        <select style={field} value={time} onChange={e => setTime(e.target.value)}>
          {TIME_OPTIONS.map(o => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "#555" }}>R-Strategy
        <select style={field} value={rStrategy} onChange={e => setRStrategy(e.target.value)}>
          {R_OPTIONS.map(o => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "#555" }}>Pace Layer
        <select style={field} value={pace} onChange={e => setPace(e.target.value)}>
          {PACE_OPTIONS.map(o => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "#555" }}>Health Score (1–5)
        <input style={field} type="number" min={1} max={5} value={health} onChange={e => setHealth(e.target.value)} placeholder="1–5" />
      </label>

      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={saving} style={{ padding: "6px 16px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} style={{ padding: "6px 14px", background: "#f0f0f0", border: "1px solid #ccc", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
          Cancel
        </button>
      </div>
    </form>
  );
}
