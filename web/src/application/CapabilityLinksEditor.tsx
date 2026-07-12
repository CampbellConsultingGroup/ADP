import { useState } from "react";
import { useCapabilities } from "../api/business";
import { useAppCapLinks, useCreateAppCapLink, useDeleteAppCapLink } from "../api/application";

interface Props { appId: string; }

export default function CapabilityLinksEditor({ appId }: Props) {
  const { data: links } = useAppCapLinks(appId);
  const { data: caps } = useCapabilities();
  const createLink = useCreateAppCapLink(appId);
  const deleteLink = useDeleteAppCapLink(appId);
  const [selectedCapId, setSelectedCapId] = useState("");
  const [fitScore, setFitScore] = useState("3");
  const [toast, setToast] = useState<string | null>(null);

  const linkedIds = new Set(links?.items.map(l => l.capability_id) ?? []);
  const available = caps?.items.filter(c => !linkedIds.has(c.id)) ?? [];

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleLink = async () => {
    if (!selectedCapId) return;
    const score = parseInt(fitScore, 10);
    if (score < 1 || score > 5) { showToast("Fit score must be 1–5"); return; }
    try {
      await createLink.mutateAsync({ capability_id: selectedCapId, fit_score: score });
      setSelectedCapId("");
      setFitScore("3");
    } catch (e) {
      showToast((e as Error).message.includes("409") ? "Already linked" : "Failed to link");
    }
  };

  return (
    <div>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Business Capabilities</h4>
      {toast && <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 6 }}>{toast}</div>}
      {links?.items.length === 0 && <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 8 }}>No linked capabilities.</div>}
      {links?.items.map(link => (
        <div key={link.capability_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ flex: 1, fontSize: 13 }}>{link.capability_name}</span>
          <span style={{ fontSize: 11, background: "var(--accent-wash)", color: "var(--accent)", padding: "1px 7px", borderRadius: 10 }}>fit {link.fit_score}/5</span>
          <button onClick={() => deleteLink.mutate(link.capability_id)} style={{ fontSize: 11, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
        </div>
      ))}
      {available.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
          <select value={selectedCapId} onChange={e => setSelectedCapId(e.target.value)} style={{ flex: 1, fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 }}>
            <option value="">— Select capability —</option>
            {available.map(c => <option key={c.id} value={c.id}>{c.name} (L{c.level})</option>)}
          </select>
          <input type="number" min={1} max={5} value={fitScore} onChange={e => setFitScore(e.target.value)} style={{ width: 50, fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)", borderRadius: 4 }} title="Fit score 1–5" />
          <button onClick={handleLink} style={{ fontSize: 12, padding: "4px 10px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer" }}>Link</button>
        </div>
      )}
    </div>
  );
}
