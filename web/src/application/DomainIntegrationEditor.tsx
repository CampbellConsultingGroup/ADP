import React, { useState } from "react";
import type { IntegrationDir } from "../api/application";
import { useAppDomainIntegrations, useCreateAppDomainIntegration, useDeleteAppDomainIntegration } from "../api/application";
import { useDomains } from "../api/business";

const DIRECTIONS: IntegrationDir[] = ["inbound", "outbound", "bidirectional"];
const DIR_ICON: Record<IntegrationDir, string> = { inbound: "←", outbound: "→", bidirectional: "↔" };

interface Props { appId: string; }

export default function DomainIntegrationEditor({ appId }: Props) {
  const { data: integrations } = useAppDomainIntegrations(appId);
  const { data: domains } = useDomains();
  const createIntegration = useCreateAppDomainIntegration(appId);
  const deleteIntegration = useDeleteAppDomainIntegration(appId);
  const [domainId, setDomainId] = useState("");
  const [intType, setIntType] = useState("API");
  const [direction, setDirection] = useState<IntegrationDir>("inbound");
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const handleCreate = async () => {
    try {
      await createIntegration.mutateAsync({ domain_id: domainId || null, integration_type: intType, direction });
      setDomainId("");
    } catch {
      showToast("Failed to create integration");
    }
  };

  const field: React.CSSProperties = { fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 };

  return (
    <div>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Domain Integrations</h4>
      {toast && <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 6 }}>{toast}</div>}
      {integrations?.items.length === 0 && <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 8 }}>No domain integrations.</div>}
      {integrations?.items.map(item => (
        <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 13 }}>{DIR_ICON[item.direction]}</span>
          <span style={{ flex: 1, fontSize: 13 }}>{item.domain_name ?? "External"}</span>
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{item.integration_type}</span>
          <button onClick={() => deleteIntegration.mutate(item.id)} style={{ fontSize: 11, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select value={domainId} onChange={e => setDomainId(e.target.value)} style={{ ...field, flex: 1 }}>
          <option value="">External / no domain</option>
          {domains?.items.map((d: { id: string; name: string }) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <input value={intType} onChange={e => setIntType(e.target.value)} placeholder="Type" style={{ ...field, width: 80 }} />
        <select value={direction} onChange={e => setDirection(e.target.value as IntegrationDir)} style={field}>
          {DIRECTIONS.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <button onClick={handleCreate} style={{ fontSize: 12, padding: "4px 10px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer" }}>Add</button>
      </div>
    </div>
  );
}
