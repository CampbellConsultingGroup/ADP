import { useEffect, useState } from "react";
import { useApplicationQuality, useUpdateApplicationQuality } from "../api/application";
import type { ApplicationQualityMetricUpdate } from "../api/application";
import { Loading, Button, Field } from "../ui/primitives";
import { useUnsavedChanges } from "../ui/unsaved";

/** APM US8 — quality & performance signals. Manual/advisory: never overrides health_score. */

interface Props { appId: string; }


export default function QualityPanel({ appId }: Props) {
  const { data: quality, isLoading, error } = useApplicationQuality(appId);
  const updateQuality = useUpdateApplicationQuality(appId);

  const [uptimePct, setUptimePct] = useState("");
  const [incidentsYtd, setIncidentsYtd] = useState("");
  const [satisfactionScore, setSatisfactionScore] = useState("");
  const [perfNote, setPerfNote] = useState("");
  const [ticketVolume30d, setTicketVolume30d] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  // ADP-blp.63: any edit in the panel counts as unsaved until it is saved or reloaded.
  const [touched, setTouched] = useState(false);
  useUnsavedChanges(touched);

  useEffect(() => {
    if (!quality) return;
    setTouched(false);
    setUptimePct(quality.uptime_pct ?? "");
    setIncidentsYtd(quality.incidents_ytd?.toString() ?? "");
    setSatisfactionScore(quality.satisfaction_score?.toString() ?? "");
    setPerfNote(quality.perf_note ?? "");
    setTicketVolume30d(quality.ticket_volume_30d?.toString() ?? "");
  }, [quality]);

  if (isLoading) return <Loading />;
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
      setTouched(false);
      showToast("Saved");
    } catch {
      showToast("Save failed");
    }
  };

  return (
    <div className="ui-form-stack" style={{ maxWidth: 460 }} onChange={() => setTouched(true)}>
      <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Quality &amp; Performance</h4>
      <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
        Manual signals — advisory only, never overrides Health score.
      </div>
      {toast && <div style={{ fontSize: 11, color: toast === "Saved" ? "var(--ink-2)" : "var(--crit)" }}>{toast}</div>}

      <Field label="Uptime %">
        {(c) => (
          <input className="ui-input" {...c} type="number" min={0} max={100} step={0.01} value={uptimePct} onChange={(e) => setUptimePct(e.target.value)} placeholder="e.g. 99.95" />
        )}
      </Field>

      <Field label="Incidents (YTD)">
        {(c) => (
          <input className="ui-input" {...c} type="number" min={0} step={1} value={incidentsYtd} onChange={(e) => setIncidentsYtd(e.target.value)} />
        )}
      </Field>

      <Field label="Satisfaction Score (1–5)">
        {(c) => (
          <input className="ui-input" {...c} type="number" min={1} max={5} step={1} value={satisfactionScore} onChange={(e) => setSatisfactionScore(e.target.value)} />
        )}
      </Field>

      <Field label="Performance Note">
        {(c) => (
          <textarea className="ui-textarea" {...c} style={{ height: 60 }} value={perfNote} onChange={(e) => setPerfNote(e.target.value)} />
        )}
      </Field>

      <Field label="Ticket Volume (30d)">
        {(c) => (
          <input className="ui-input" {...c} type="number" min={0} step={1} value={ticketVolume30d} onChange={(e) => setTicketVolume30d(e.target.value)} />
        )}
      </Field>

      <div>
        <Button variant="primary" onClick={handleSave} disabled={updateQuality.isPending}>
          {updateQuality.isPending ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  );
}
