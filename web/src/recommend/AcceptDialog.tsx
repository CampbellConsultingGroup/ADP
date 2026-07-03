import React, { useState } from "react";
import type { SolutionOption, AcceptOptionRequest } from "../api/recommend";

interface AcceptDialogProps {
  option: SolutionOption;
  designId: string;
  onConfirm: (req: AcceptOptionRequest) => void;
  onCancel: () => void;
  isPending: boolean;
}

export default function AcceptDialog({ option, onConfirm, onCancel, isPending }: AcceptDialogProps): React.ReactElement {
  const [advisoryChecked, setAdvisoryChecked] = useState(false);

  const canConfirm = !isPending && (!option.advisory || advisoryChecked);

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div style={{ background: "#fff", borderRadius: 8, padding: 24, maxWidth: 500, width: "90%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 700 }}>Accept Recommendation</h3>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "#6B7280" }}>
          Option #{option.rank}: <strong>{option.title}</strong>
        </p>

        {option.proposed_elements.length > 0 && (
          <div style={{ marginBottom: 16, padding: 12, background: "#F8FAFC", borderRadius: 6, border: "1px solid #E5E7EB" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#6B7280", marginBottom: 8 }}>
              This will add {option.proposed_elements.length} element{option.proposed_elements.length !== 1 ? "s" : ""} to the design:
            </div>
            {option.proposed_elements.map((el, i) => (
              <div key={i} style={{ fontSize: 13, color: "#374151", marginBottom: 4 }}>
                • <strong>[{el.kind}]</strong> {el.name}
                {el.description && <span style={{ color: "#6B7280" }}> — {el.description}</span>}
              </div>
            ))}
          </div>
        )}

        <p style={{ fontSize: 12, color: "#9CA3AF", marginBottom: 16 }}>
          These elements can be edited on the canvas after acceptance.
        </p>

        {/* Advisory acknowledgement checkbox — required for advisory options (ART-VII) */}
        {option.advisory && (
          <div style={{ marginBottom: 16, padding: 12, background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 6 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#92400E", marginBottom: 8 }}>⚠ Advisory Warning</div>
            <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={advisoryChecked}
                onChange={(e) => setAdvisoryChecked(e.target.checked)}
                style={{ marginTop: 2, flexShrink: 0 }}
              />
              <span style={{ fontSize: 13, color: "#78350F" }}>
                I understand this option lacks full knowledge-base grounding and accept additional review responsibility before implementation.
              </span>
            </label>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button
            onClick={onCancel}
            disabled={isPending}
            style={{ padding: "8px 18px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm({ confirmation_id: `CONFIRM-${option.option_id}`, advisory_acknowledged: advisoryChecked })}
            disabled={!canConfirm}
            style={{ padding: "8px 18px", background: canConfirm ? "#166534" : "#D1D5DB", color: "#fff", border: "none", borderRadius: 4, cursor: canConfirm ? "pointer" : "not-allowed", fontSize: 14, fontWeight: 600 }}
          >
            {isPending ? "Accepting..." : "Confirm Accept"}
          </button>
        </div>
      </div>
    </div>
  );
}
