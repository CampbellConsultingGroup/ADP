import { useState } from "react";
import type { UsageType } from "../api/application";
import { useTechCaps, useAppTechCapLinks, useCreateAppTechCapLink, useDeleteAppTechCapLink } from "../api/application";

interface Props { appId: string; }

const USAGE_TYPES: UsageType[] = ["provides", "consumes"];

export default function TechCapLinkEditor({ appId }: Props) {
  const { data: links } = useAppTechCapLinks(appId);
  const { data: caps } = useTechCaps();
  const createLink = useCreateAppTechCapLink(appId);
  const deleteLink = useDeleteAppTechCapLink(appId);
  const [selectedTcId, setSelectedTcId] = useState("");
  const [usageType, setUsageType] = useState<UsageType>("provides");
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const handleLink = async () => {
    if (!selectedTcId) return;
    try {
      await createLink.mutateAsync({ tech_cap_id: selectedTcId, usage_type: usageType });
      setSelectedTcId("");
    } catch {
      showToast("Already linked or failed");
    }
  };

  const provides = links?.items.filter(l => l.usage_type === "provides") ?? [];
  const consumes = links?.items.filter(l => l.usage_type === "consumes") ?? [];

  return (
    <div>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Technical Capabilities</h4>
      {toast && <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 6 }}>{toast}</div>}
      {["provides", "consumes"].map(ut => {
        const group = ut === "provides" ? provides : consumes;
        return (
          <div key={ut} style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-3)", textTransform: "uppercase", marginBottom: 3 }}>{ut}</div>
            {group.length === 0 && <div style={{ fontSize: 11, color: "var(--ink-3)" }}>None</div>}
            {group.map(link => (
              <div key={`${link.tech_cap_id}-${link.usage_type}`} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                <span style={{ flex: 1, fontSize: 13 }}>{link.tech_cap_name}</span>
                <button onClick={() => deleteLink.mutate({ tcId: link.tech_cap_id, usageType: link.usage_type })} style={{ fontSize: 11, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
              </div>
            ))}
          </div>
        );
      })}
      {(caps?.items.length ?? 0) > 0 && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
          <select value={selectedTcId} onChange={e => setSelectedTcId(e.target.value)} style={{ flex: 1, fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 }}>
            <option value="">— Tech capability —</option>
            {caps?.items.map(c => <option key={c.id} value={c.id}>{c.name} (L{c.level})</option>)}
          </select>
          <select value={usageType} onChange={e => setUsageType(e.target.value as UsageType)} style={{ fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 }}>
            {USAGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={handleLink} style={{ fontSize: 12, padding: "4px 10px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer" }}>Link</button>
        </div>
      )}
    </div>
  );
}
