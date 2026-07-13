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
  const [acceptanceReason, setAcceptanceReason] = useState("");

  const canConfirm = !isPending && (!option.advisory || advisoryChecked);

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div style={{ background: "var(--surface)", borderRadius: 8, padding: 24, maxWidth: 500, width: "90%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 700 }}>Accept Recommendation</h3>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--ink-3)" }}>
          Option #{option.rank}: <strong>{option.title}</strong>
        </p>

        {option.proposed_elements.length > 0 && (
          <div style={{ marginBottom: 16, padding: 12, background: "var(--surface-2)", borderRadius: 6, border: "1px solid var(--border)" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", marginBottom: 8 }}>
              This will add {option.proposed_elements.length} element{option.proposed_elements.length !== 1 ? "s" : ""} to the design:
            </div>
            {option.proposed_elements.map((el, i) => (
              <div key={i} style={{ fontSize: 13, color: "var(--ink-2)", marginBottom: 4 }}>
                • <strong>[{el.kind}]</strong> {el.name}
                {el.description && <span style={{ color: "var(--ink-3)" }}> — {el.description}</span>}
              </div>
            ))}
          </div>
        )}

        <p style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 16 }}>
          These elements can be edited on the canvas after acceptance.
        </p>

        {/* ADP-SPEC-019: optional acceptance reason saved to KB */}
        <div style={{ marginBottom: 16 }}>
          <p style={{ margin: "0 0 6px", fontSize: 13, color: "var(--ink-2)", fontWeight: 600 }}>
            Acceptance reason <span style={{ color: "var(--ink-3)", fontWeight: 400 }}>(optional)</span>
          </p>
          <textarea
            value={acceptanceReason}
            onChange={(e) => setAcceptanceReason(e.target.value)}
            placeholder="Why are you accepting this recommendation? (stored in knowledge base)"
            rows={3}
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
        </div>

        {/* Advisory acknowledgement checkbox — required for advisory options (ART-VII) */}
        {option.advisory && (
          <div style={{ marginBottom: 16, padding: 12, background: "var(--warn-wash)", border: "1px solid var(--warn)", borderRadius: 6 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--warn)", marginBottom: 8 }}>⚠ Advisory Warning</div>
            <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={advisoryChecked}
                onChange={(e) => setAdvisoryChecked(e.target.checked)}
                style={{ marginTop: 2, flexShrink: 0 }}
              />
              <span style={{ fontSize: 13, color: "var(--warn)" }}>
                I understand this option lacks full knowledge-base grounding and accept additional review responsibility before implementation.
              </span>
            </label>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button
            onClick={onCancel}
            disabled={isPending}
            style={{ padding: "8px 18px", background: "var(--surface)", color: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm({
              confirmation_id: `CONFIRM-${option.option_id}`,
              advisory_acknowledged: advisoryChecked,
              acceptance_reason: acceptanceReason.trim() || undefined,
            })}
            disabled={!canConfirm}
            style={{ padding: "8px 18px", background: canConfirm ? "var(--good)" : "var(--border)", color: "#fff", border: "none", borderRadius: 4, cursor: canConfirm ? "pointer" : "not-allowed", fontSize: 14, fontWeight: 600 }}
          >
            {isPending ? "Accepting..." : "Confirm Accept"}
          </button>
        </div>
      </div>
    </div>
  );
}
