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
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div style={{ background: "#fff", borderRadius: 8, padding: 24, maxWidth: 500, width: "90%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 700 }}>Reject Recommendation</h3>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "#6B7280" }}>
          Option #{option.rank}: <strong>{option.title}</strong>
        </p>

        <p style={{ margin: "0 0 8px", fontSize: 13, color: "#374151", fontWeight: 600 }}>
          Rejection reason <span style={{ color: "#DC2626" }}>*</span>
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
            border: "1px solid #D1D5DB",
            resize: "vertical",
            boxSizing: "border-box",
            fontFamily: "inherit",
          }}
        />
        <p style={{ margin: "4px 0 16px", fontSize: 12, color: "#9CA3AF" }}>
          Your reason will be saved to the knowledge base as an anti-pattern to inform future recommendations.
        </p>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button
            onClick={onCancel}
            disabled={isPending}
            style={{ padding: "8px 18px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason.trim())}
            disabled={!canConfirm}
            style={{ padding: "8px 18px", background: canConfirm ? "#991B1B" : "#D1D5DB", color: "#fff", border: "none", borderRadius: 4, cursor: canConfirm ? "pointer" : "not-allowed", fontSize: 14, fontWeight: 600 }}
          >
            {isPending ? "Rejecting..." : "Confirm Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}
