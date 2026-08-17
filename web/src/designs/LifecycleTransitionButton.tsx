/**
 * LifecycleTransitionButton — dropdown for advancing a design through its lifecycle (ADP-SPEC-030).
 * Client-side transition graph mirrors the backend for UX; server validates authoritatively.
 */
import React, { useState } from "react";
import { useTransitionLifecycle } from "../api/designs";
import { Button } from "../ui";

interface LifecycleTransitionButtonProps {
  designId: string;
  currentStatus: string;
}

// Mirrors VALID_TRANSITIONS in src/adp/api/routers/lifecycle.py
const VALID_TRANSITIONS: Record<string, { label: string; value: string }[]> = {
  draft:         [{ label: "Propose", value: "proposed" }],
  proposed:      [{ label: "Mark Current", value: "current" }, { label: "Return to Draft", value: "draft" }],
  current:       [{ label: "Deprecate", value: "deprecated" }, { label: "Mark Complete", value: "complete" }],
  complete:      [{ label: "Deprecate", value: "deprecated" }, { label: "Reinstate as Current", value: "current" }],
  deprecated:    [{ label: "Decommission", value: "decommissioned" }, { label: "Reinstate as Current", value: "current" }],
  decommissioned: [],
};

const DATE_FIELDS: Record<string, { key: string; label: string }[]> = {
  proposed:       [{ key: "proposed_date", label: "Proposed date (optional)" }],
  current:        [{ key: "current_since", label: "Live since (optional)" }],
  decommissioned: [{ key: "retirement_date", label: "Retirement date (optional)" }],
};

export default function LifecycleTransitionButton({
  designId,
  currentStatus,
}: LifecycleTransitionButtonProps): React.ReactElement {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [dateValue, setDateValue] = useState("");
  const mutation = useTransitionLifecycle(designId);

  const transitions = VALID_TRANSITIONS[currentStatus] ?? [];
  if (transitions.length === 0) return <></>;

  const handleConfirm = () => {
    if (!pending) return;
    const dateFields = DATE_FIELDS[pending] ?? [];
    const body: Record<string, string | null> = { status: pending };
    if (note.trim()) body.note = note.trim();
    if (dateValue && dateFields.length > 0) {
      body[dateFields[0].key] = new Date(dateValue).toISOString();
    }
    mutation.mutate(body as unknown as Parameters<ReturnType<typeof useTransitionLifecycle>["mutate"]>[0], {
      onSuccess: () => { setOpen(false); setPending(null); setNote(""); setDateValue(""); },
    });
  };

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <Button size="sm" onClick={() => setOpen((o) => !o)}>Transition ▾</Button>

      {open && !pending && (
        <div className="ui-menu" style={{ right: 0, top: "100%", marginTop: 4, minWidth: 180 }}>
          {transitions.map((t) => (
            <button key={t.value} className="ui-menu-item" onClick={() => setPending(t.value)}>
              {t.label}
            </button>
          ))}
          <button className="ui-menu-item muted" onClick={() => setOpen(false)}>Cancel</button>
        </div>
      )}

      {pending && (
        <div className="ui-menu" style={{ right: 0, top: "100%", marginTop: 4, width: 260, padding: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10, color: "var(--ink)" }}>
            Transition to <span style={{ color: "var(--accent)" }}>{pending}</span>
          </div>

          {(DATE_FIELDS[pending] ?? []).map((df) => (
            <div key={df.key} style={{ marginBottom: 8 }}>
              <label className="ui-label">{df.label}</label>
              <input type="date" className="ui-input" value={dateValue} onChange={(e) => setDateValue(e.target.value)} />
            </div>
          ))}

          <div style={{ marginBottom: 10 }}>
            <label className="ui-label">Note (optional, max 500 chars)</label>
            <textarea className="ui-textarea" value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500} />
          </div>

          {mutation.isError && (
            <div style={{ fontSize: 12, color: "var(--crit)", marginBottom: 8 }}>{mutation.error?.message}</div>
          )}

          <div style={{ display: "flex", gap: 6 }}>
            <Button variant="primary" size="sm" style={{ flex: 1 }} onClick={handleConfirm} disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Confirm"}
            </Button>
            <Button size="sm" style={{ flex: 1 }} onClick={() => { setPending(null); setNote(""); setDateValue(""); }}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
