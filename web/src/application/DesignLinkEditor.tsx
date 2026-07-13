import { useState } from "react";
import { useDesigns } from "../api/business";
import { useAppDesignLinks, useCreateAppDesignLink, useDeleteAppDesignLink } from "../api/application";

interface Props { appId: string; }

export default function DesignLinkEditor({ appId }: Props) {
  const { data: links } = useAppDesignLinks(appId);
  const { data: designs } = useDesigns();
  const createLink = useCreateAppDesignLink(appId);
  const deleteLink = useDeleteAppDesignLink(appId);
  const [selectedDesignId, setSelectedDesignId] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };
  const linkedIds = new Set(links?.items.map(l => l.design_id) ?? []);
  const available = designs?.designs.filter(d => !linkedIds.has(d.id)) ?? [];

  const handleLink = async () => {
    if (!selectedDesignId) return;
    try {
      await createLink.mutateAsync(selectedDesignId);
      setSelectedDesignId("");
    } catch {
      showToast("Already linked or design not found");
    }
  };

  return (
    <div>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Linked Designs</h4>
      {toast && <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 6 }}>{toast}</div>}
      {links?.items.length === 0 && <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 8 }}>No designs linked.</div>}
      {links?.items.map(link => {
        const design = designs?.designs.find(d => d.id === link.design_id);
        return (
          <div key={link.design_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ flex: 1, fontSize: 13 }}>{design?.title ?? link.design_id}</span>
            <button onClick={() => deleteLink.mutate(link.design_id)} style={{ fontSize: 11, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
          </div>
        );
      })}
      {available.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
          <select value={selectedDesignId} onChange={e => setSelectedDesignId(e.target.value)} style={{ flex: 1, fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 }}>
            <option value="">— Select design —</option>
            {available.map(d => <option key={d.id} value={d.id}>{d.title}</option>)}
          </select>
          <button onClick={handleLink} style={{ fontSize: 12, padding: "4px 10px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer" }}>Link</button>
        </div>
      )}
    </div>
  );
}
