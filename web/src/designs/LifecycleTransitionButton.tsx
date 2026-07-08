/**
 * LifecycleTransitionButton — dropdown for advancing a design through its lifecycle (ADP-SPEC-030).
 * Client-side transition graph mirrors the backend for UX; server validates authoritatively.
 */
import React, { useState } from "react";
import { useTransitionLifecycle } from "../api/designs";

interface LifecycleTransitionButtonProps {
  designId: string;
  currentStatus: string;
}

// Mirrors VALID_TRANSITIONS in src/adp/api/routers/lifecycle.py
const VALID_TRANSITIONS: Record<string, { label: string; value: string }[]> = {
  draft:         [{ label: "Propose", value: "proposed" }],
  proposed:      [{ label: "Mark Current", value: "current" }, { label: "Return to Draft", value: "draft" }],
  current:       [{ label: "Deprecate", value: "deprecated" }],
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
      <button
        onClick={() => setOpen(o => !o)}
        style={{ padding: "4px 10px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
      >
        Transition ▾
      </button>

      {open && !pending && (
        <div style={{ position: "absolute", right: 0, top: "100%", marginTop: 2, background: "#fff", border: "1px solid #E5E7EB", borderRadius: 6, boxShadow: "0 4px 12px rgba(0,0,0,0.1)", zIndex: 100, minWidth: 180 }}>
          {transitions.map(t => (
            <button
              key={t.value}
              onClick={() => { setPending(t.value); }}
              style={{ display: "block", width: "100%", padding: "8px 14px", textAlign: "left", background: "none", border: "none", cursor: "pointer", fontSize: 13, color: "#111827" }}
            >
              {t.label}
            </button>
          ))}
          <button onClick={() => setOpen(false)} style={{ display: "block", width: "100%", padding: "6px 14px", textAlign: "left", background: "none", border: "none", cursor: "pointer", fontSize: 12, color: "#9CA3AF" }}>
            Cancel
          </button>
        </div>
      )}

      {pending && (
        <div style={{ position: "absolute", right: 0, top: "100%", marginTop: 2, background: "#fff", border: "1px solid #E5E7EB", borderRadius: 6, boxShadow: "0 4px 12px rgba(0,0,0,0.1)", zIndex: 100, width: 260, padding: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10, color: "#111827" }}>
            Transition to <span style={{ color: "#1168BD" }}>{pending}</span>
          </div>

          {(DATE_FIELDS[pending] ?? []).map(df => (
            <div key={df.key} style={{ marginBottom: 8 }}>
              <label style={{ fontSize: 11, color: "#6B7280", display: "block", marginBottom: 3 }}>{df.label}</label>
              <input type="date" value={dateValue} onChange={e => setDateValue(e.target.value)}
                style={{ width: "100%", padding: "5px 8px", fontSize: 12, borderRadius: 4, border: "1px solid #D1D5DB", boxSizing: "border-box" }} />
            </div>
          ))}

          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 11, color: "#6B7280", display: "block", marginBottom: 3 }}>Note (optional, max 500 chars)</label>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} maxLength={500}
              style={{ width: "100%", padding: "5px 8px", fontSize: 12, borderRadius: 4, border: "1px solid #D1D5DB", resize: "vertical", boxSizing: "border-box", fontFamily: "inherit" }} />
          </div>

          {mutation.isError && (
            <div style={{ fontSize: 12, color: "#DC2626", marginBottom: 8 }}>{mutation.error?.message}</div>
          )}

          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={handleConfirm} disabled={mutation.isPending}
              style={{ flex: 1, padding: "6px 0", background: mutation.isPending ? "#D1D5DB" : "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: mutation.isPending ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 600 }}>
              {mutation.isPending ? "Saving…" : "Confirm"}
            </button>
            <button onClick={() => { setPending(null); setNote(""); setDateValue(""); }}
              style={{ flex: 1, padding: "6px 0", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 12 }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
