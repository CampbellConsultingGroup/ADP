import React, { useState } from "react";
import type { Application, ApplicationIntegrationCreate, AppIntegrationType } from "../api/application";

const TYPES: AppIntegrationType[] = ["API", "event", "file", "database", "messaging", "other"];

interface Props {
  apps: Application[];
  defaultSourceId?: string;
  onSave: (data: ApplicationIntegrationCreate) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
}

export default function IntegrationForm({ apps, defaultSourceId, onSave, onCancel, saving }: Props) {
  const [sourceId, setSourceId] = useState(defaultSourceId ?? "");
  const [targetId, setTargetId] = useState("");
  const [intType, setIntType] = useState<AppIntegrationType>("API");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceId || !targetId) { setError("Source and target are required"); return; }
    if (sourceId === targetId) { setError("Source and target must be different"); return; }
    setError(null);
    try {
      await onSave({ source_app_id: sourceId, target_app_id: targetId, integration_type: intType, description: description || null });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  };

  const sel: React.CSSProperties = { padding: "5px 8px", fontSize: 12, border: "1px solid var(--border)", borderRadius: 4 };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 10, padding: 14 }}>
      <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>New Integration</h4>
      {error && <div style={{ fontSize: 11, color: "var(--crit)" }}>{error}</div>}

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Source Application *
        <select style={{ ...sel, width: "100%", marginTop: 2 }} value={sourceId} onChange={e => setSourceId(e.target.value)}>
          <option value="">— Select source —</option>
          {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Target Application *
        <select style={{ ...sel, width: "100%", marginTop: 2 }} value={targetId} onChange={e => setTargetId(e.target.value)}>
          <option value="">— Select target —</option>
          {apps.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Integration Type
        <select style={{ ...sel, width: "100%", marginTop: 2 }} value={intType} onChange={e => setIntType(e.target.value as AppIntegrationType)}>
          {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Description
        <input style={{ ...sel, width: "100%", marginTop: 2 }} value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional" />
      </label>

      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={saving} style={{ fontSize: 12, padding: "5px 14px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer" }}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} style={{ fontSize: 12, padding: "5px 12px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer" }}>
          Cancel
        </button>
      </div>
    </form>
  );
}
