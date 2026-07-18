import { useEffect, useState } from "react";
import { useApplicationQuality, useUpdateApplicationQuality } from "../api/application";
import type { ApplicationQualityMetricUpdate } from "../api/application";

/** APM US8 — quality & performance signals. Manual/advisory: never overrides health_score. */

interface Props { appId: string; }

const field: React.CSSProperties = {
  width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4,
};
const label: React.CSSProperties = { fontSize: 12, color: "var(--ink-2)" };

export default function QualityPanel({ appId }: Props) {
  const { data: quality, isLoading, error } = useApplicationQuality(appId);
  const updateQuality = useUpdateApplicationQuality(appId);

  const [uptimePct, setUptimePct] = useState("");
  const [incidentsYtd, setIncidentsYtd] = useState("");
  const [satisfactionScore, setSatisfactionScore] = useState("");
  const [perfNote, setPerfNote] = useState("");
  const [ticketVolume30d, setTicketVolume30d] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!quality) return;
    setUptimePct(quality.uptime_pct ?? "");
    setIncidentsYtd(quality.incidents_ytd?.toString() ?? "");
    setSatisfactionScore(quality.satisfaction_score?.toString() ?? "");
    setPerfNote(quality.perf_note ?? "");
    setTicketVolume30d(quality.ticket_volume_30d?.toString() ?? "");
  }, [quality]);

  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;
  if (error) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Could not load quality data.</div>;

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    const body: ApplicationQualityMetricUpdate = {
      uptime_pct: uptimePct || null,
      incidents_ytd: incidentsYtd === "" ? null : Number(incidentsYtd),
      satisfaction_score: satisfactionScore === "" ? null : Number(satisfactionScore),
      perf_note: perfNote || null,
      ticket_volume_30d: ticketVolume30d === "" ? null : Number(ticketVolume30d),
    };
    try {
      await updateQuality.mutateAsync(body);
      showToast("Saved");
    } catch {
      showToast("Save failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 460 }}>
      <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Quality &amp; Performance</h4>
      <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
        Manual signals — advisory only, never overrides Health score.
      </div>
      {toast && <div style={{ fontSize: 11, color: toast === "Saved" ? "var(--ink-2)" : "var(--crit)" }}>{toast}</div>}

      <label style={label}>Uptime %
        <input style={field} type="number" min={0} max={100} step={0.01} value={uptimePct} onChange={(e) => setUptimePct(e.target.value)} placeholder="e.g. 99.95" />
      </label>

      <label style={label}>Incidents (YTD)
        <input style={field} type="number" min={0} step={1} value={incidentsYtd} onChange={(e) => setIncidentsYtd(e.target.value)} />
      </label>

      <label style={label}>Satisfaction Score (1–5)
        <input style={field} type="number" min={1} max={5} step={1} value={satisfactionScore} onChange={(e) => setSatisfactionScore(e.target.value)} />
      </label>

      <label style={label}>Performance Note
        <textarea style={{ ...field, height: 60 }} value={perfNote} onChange={(e) => setPerfNote(e.target.value)} />
      </label>

      <label style={label}>Ticket Volume (30d)
        <input style={field} type="number" min={0} step={1} value={ticketVolume30d} onChange={(e) => setTicketVolume30d(e.target.value)} />
      </label>

      <div>
        <button
          type="button"
          onClick={handleSave}
          disabled={updateQuality.isPending}
          style={{
            padding: "6px 14px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 6,
            background: "var(--accent, #2874A6)", color: "#fff", cursor: "pointer",
          }}
        >
          {updateQuality.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
