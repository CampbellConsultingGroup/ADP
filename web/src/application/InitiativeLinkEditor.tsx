import { useState } from "react";
import {
  useInitiatives,
  useAppInitiativeLinks,
  useCreateInitiativeLink,
  useDeleteInitiativeLink,
} from "../api/application";
import type { Disposition } from "../api/application";

interface Props { appId: string; }

const DISPOSITIONS: Disposition[] = ["retire", "replace", "modernize", "invest"];

export default function InitiativeLinkEditor({ appId }: Props) {
  const { data: links } = useAppInitiativeLinks(appId);
  const { data: initiatives } = useInitiatives();
  const createLink = useCreateInitiativeLink(appId);
  const deleteLink = useDeleteInitiativeLink(appId);
  const [selectedId, setSelectedId] = useState("");
  const [disposition, setDisposition] = useState<Disposition>("modernize");
  const [toast, setToast] = useState<string | null>(null);

  const linkedIds = new Set(links?.items.map((l) => l.initiative_id) ?? []);
  const available = initiatives?.items.filter((i) => !linkedIds.has(i.id)) ?? [];

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleLink = async () => {
    if (!selectedId) return;
    try {
      await createLink.mutateAsync({ initiative_id: selectedId, planned_disposition: disposition });
      setSelectedId("");
      setDisposition("modernize");
    } catch (e) {
      showToast((e as Error).message.includes("409") ? "Already linked" : "Failed to link");
    }
  };

  return (
    <div>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Transformation Initiatives</h4>
      {toast && <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 6 }}>{toast}</div>}
      {links?.items.length === 0 && <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 8 }}>Not linked to any initiative.</div>}
      {links?.items.map((link) => (
        <div key={link.initiative_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ flex: 1, fontSize: 13 }}>{link.initiative_name}</span>
          <span style={{ fontSize: 11, background: "var(--accent-wash)", color: "var(--accent)", padding: "1px 7px", borderRadius: 10 }}>{link.planned_disposition}</span>
          <button onClick={() => deleteLink.mutate(link.initiative_id)} style={{ fontSize: 11, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
        </div>
      ))}
      {available.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
          <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} style={{ flex: 1, fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 }}>
            <option value="">— Select initiative —</option>
            {available.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
          <select value={disposition} onChange={(e) => setDisposition(e.target.value as Disposition)} style={{ fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 }}>
            {DISPOSITIONS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
          <button onClick={handleLink} style={{ fontSize: 12, padding: "4px 10px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer" }}>Link</button>
        </div>
      )}
    </div>
  );
}
