import { useState } from "react";
import { useValueStreams } from "../api/business";
import { useAppStageLinks, useCreateAppStageLink, useDeleteAppStageLink } from "../api/application";

interface Props { appId: string; }

export default function StageLinkEditor({ appId }: Props) {
  const { data: links } = useAppStageLinks(appId);
  const { data: streams } = useValueStreams();
  const createLink = useCreateAppStageLink(appId);
  const deleteLink = useDeleteAppStageLink(appId);
  const [selectedStageId, setSelectedStageId] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const handleLink = async () => {
    if (!selectedStageId) return;
    try {
      await createLink.mutateAsync(selectedStageId);
      setSelectedStageId("");
    } catch {
      showToast("Already linked or failed");
    }
  };

  return (
    <div>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "#444" }}>Value Stream Stages</h4>
      {toast && <div style={{ fontSize: 11, color: "#c00", marginBottom: 6 }}>{toast}</div>}
      {links?.items.length === 0 && <div style={{ fontSize: 12, color: "#888", marginBottom: 8 }}>No stages linked.</div>}
      {links?.items.map(link => (
        <div key={link.stage_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ flex: 1, fontSize: 13 }}>{link.stage_name}</span>
          <button onClick={() => deleteLink.mutate(link.stage_id)} style={{ fontSize: 11, color: "#c00", background: "none", border: "none", cursor: "pointer" }}>✕</button>
        </div>
      ))}
      {(streams?.items.length ?? 0) > 0 && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
          <select value={selectedStageId} onChange={e => setSelectedStageId(e.target.value)} style={{ flex: 1, fontSize: 12, padding: "4px 6px", border: "1px solid #ccc", borderRadius: 4 }}>
            <option value="">— Select stage —</option>
            {streams?.items.map(vs => (
              <optgroup key={vs.id} label={vs.name}>
                {/* Stages need to be fetched per-VS — using stage links as the available source */}
              </optgroup>
            ))}
          </select>
          <button onClick={handleLink} disabled={!selectedStageId} style={{ fontSize: 12, padding: "4px 10px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>Link</button>
        </div>
      )}
    </div>
  );
}
