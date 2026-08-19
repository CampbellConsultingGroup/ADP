import React, { useState } from "react";
import type { SolutionOption } from "../api/recommend";

interface RejectDialogProps {
  option: SolutionOption;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
  isPending: boolean;
}

export default function RejectDialog({ option, onConfirm, onCancel, isPending }: RejectDialogProps): React.ReactElement {
  const [reason, setReason] = useState("");
  const canConfirm = !isPending && reason.trim().length > 0;

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "32px 16px", boxSizing: "border-box" }}>
      {/* maxHeight + flex column keeps Cancel/Confirm reachable on short viewports — mirrors the AcceptDialog fix */}
      <div style={{ background: "var(--surface)", borderRadius: 8, padding: 24, maxWidth: 500, width: "90%", maxHeight: "100%", display: "flex", flexDirection: "column", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 700, flexShrink: 0 }}>Reject Recommendation</h3>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--ink-3)", flexShrink: 0 }}>
          Option #{option.rank}: <strong>{option.title}</strong>
        </p>

        <div style={{ overflowY: "auto", minHeight: 0 }}>
          <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--ink-2)", fontWeight: 600 }}>
            Rejection reason <span style={{ color: "var(--crit)" }}>*</span>
          </p>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain why this option is not suitable (required)..."
            rows={4}
            style={{
              width: "100%",
              padding: "8px 10px",
              fontSize: 13,
              borderRadius: 6,
              border: "1px solid var(--border)",
              resize: "vertical",
              boxSizing: "border-box",
              fontFamily: "inherit",
            }}
          />
          <p style={{ margin: "4px 0 16px", fontSize: 12, color: "var(--ink-3)" }}>
            Your reason will be saved to the knowledge base as an anti-pattern to inform future recommendations.
          </p>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, flexShrink: 0, paddingTop: 12, marginTop: 4, borderTop: "1px solid var(--border)" }}>
          <button
            onClick={onCancel}
            disabled={isPending}
            style={{ padding: "8px 18px", background: "var(--surface)", color: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason.trim())}
            disabled={!canConfirm}
            style={{ padding: "8px 18px", background: canConfirm ? "var(--crit)" : "var(--border)", color: "#fff", border: "none", borderRadius: 4, cursor: canConfirm ? "pointer" : "not-allowed", fontSize: 14, fontWeight: 600 }}
          >
            {isPending ? "Rejecting..." : "Confirm Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}
