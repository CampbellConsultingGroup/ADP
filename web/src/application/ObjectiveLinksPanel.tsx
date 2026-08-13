/** ObjectiveLinksPanel — mirrors CapabilityLinksEditor.tsx's read+link
 * pattern (ADP-d8u.2), showing/linking/unlinking the strategic objectives
 * this application realizes. Uses the application-side hook variants
 * (useLinkApplicationToObjective/useUnlinkApplicationFromObjective) since
 * this panel lives on the application, not the objective. */

import { useState } from "react";
import {
  useApplicationObjectives,
  useObjectives,
  useLinkApplicationToObjective,
  useUnlinkApplicationFromObjective,
} from "../api/strategy";

interface Props {
  appId: string;
}

export default function ObjectiveLinksPanel({ appId }: Props) {
  const { data: linked } = useApplicationObjectives(appId);
  const { data: allObjectives } = useObjectives();
  const link = useLinkApplicationToObjective(appId);
  const unlink = useUnlinkApplicationFromObjective(appId);
  const [selectedObjectiveId, setSelectedObjectiveId] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const linkedIds = new Set(linked?.items.map((o) => o.id) ?? []);
  const available = (allObjectives?.items ?? []).filter((o) => !linkedIds.has(o.id));

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleLink = async () => {
    if (!selectedObjectiveId) return;
    try {
      await link.mutateAsync(selectedObjectiveId);
      setSelectedObjectiveId("");
    } catch (e) {
      showToast((e as Error).message.includes("409") ? "Already linked" : "Failed to link");
    }
  };

  return (
    <div>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>
        Objectives Realized
      </h4>
      {toast && <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 6 }}>{toast}</div>}
      {linked?.items.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 8 }}>
          No objectives linked.
        </div>
      )}
      {linked?.items.map((objective) => (
        <div
          key={objective.id}
          style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}
        >
          <span style={{ flex: 1, fontSize: 13 }}>{objective.statement}</span>
          <button
            onClick={() => unlink.mutate(objective.id)}
            style={{
              fontSize: 11, color: "var(--crit)", background: "none", border: "none",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>
      ))}
      {available.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center" }}>
          <select
            value={selectedObjectiveId}
            onChange={(e) => setSelectedObjectiveId(e.target.value)}
            style={{
              flex: 1, fontSize: 12, padding: "4px 6px", border: "1px solid var(--border)",
              borderRadius: 4,
            }}
          >
            <option value="">— select objective —</option>
            {available.map((o) => (
              <option key={o.id} value={o.id}>{o.statement}</option>
            ))}
          </select>
          <button
            onClick={handleLink}
            style={{
              fontSize: 12, padding: "4px 10px", background: "var(--accent)",
              color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer",
            }}
          >
            Link
          </button>
        </div>
      )}
    </div>
  );
}
