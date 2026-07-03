import React, { useState } from "react";
import type { SolutionOption } from "../api/recommend";
import AcceptDialog from "./AcceptDialog";
import { useAcceptOption } from "../api/recommend";

interface OptionCardProps {
  option: SolutionOption;
  designId: string;
  operationId: string;
  onAcceptSuccess: () => void;
}

const STANCE_ICONS: Record<string, string> = {
  meets: "✅",
  partially_meets: "⚠️",
  does_not_meet: "❌",
};

const KIND_COLORS: Record<string, string> = {
  container: "#2874A6",
  system: "#1168BD",
  person: "#08427B",
  component: "#6B21A8",
};

export default function OptionCard({ option, designId, operationId, onAcceptSuccess }: OptionCardProps): React.ReactElement {
  const [showDialog, setShowDialog] = useState(false);
  const accept = useAcceptOption(designId, operationId);

  const isAccepted = option.status === "accepted";

  return (
    <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, marginBottom: 16, overflow: "hidden", opacity: isAccepted ? 0.7 : 1 }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", background: isAccepted ? "#F0FDF4" : "#F8FAFC", borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ background: "#1168BD", color: "#fff", fontWeight: 700, fontSize: 13, padding: "3px 10px", borderRadius: 4 }}>#{option.rank}</span>
        <span style={{ fontWeight: 600, fontSize: 15, flex: 1 }}>{option.title}</span>
        <span style={{ fontSize: 12, color: "#6B7280" }}>score: {Math.round(option.ranking_score * 100)}%</span>
        {option.advisory && (
          <span style={{ background: "#FEF3C7", color: "#92400E", border: "1px solid #FDE68A", fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 4 }}>⚠ ADVISORY</span>
        )}
        {isAccepted && <span style={{ background: "#D1FAE5", color: "#065F46", fontSize: 12, fontWeight: 600, padding: "2px 8px", borderRadius: 4 }}>✓ Accepted</span>}
      </div>

      <div style={{ padding: 16 }}>
        {/* Advisory warning */}
        {option.advisory && (
          <div style={{ marginBottom: 12, padding: 10, background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 6, fontSize: 13, color: "#78350F" }}>
            ⚠ This option lacks full knowledge-base grounding. Additional review recommended before accepting.
          </div>
        )}

        {/* Rationale */}
        <p style={{ fontSize: 13, color: "#374151", marginBottom: 14, lineHeight: 1.6 }}>{option.rationale}</p>

        {/* Trade-off table */}
        {option.trade_offs.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#6B7280", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Trade-offs</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #E5E7EB" }}>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "#6B7280", fontWeight: 500, width: "35%" }}>Criterion</th>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "#6B7280", fontWeight: 500, width: "20%" }}>Stance</th>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "#6B7280", fontWeight: 500 }}>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {option.trade_offs.map((tf, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #F3F4F6" }}>
                    <td style={{ padding: "5px 8px", color: "#374151" }}>{tf.criterion}</td>
                    <td style={{ padding: "5px 8px", whiteSpace: "nowrap" }}>
                      {STANCE_ICONS[tf.stance] ?? "•"} {tf.stance.replace("_", " ")}
                    </td>
                    <td style={{ padding: "5px 8px", color: "#6B7280", fontSize: 12 }}>{tf.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Proposed elements */}
        {option.proposed_elements.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#6B7280", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Proposed Elements</div>
            {option.proposed_elements.map((el, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
                <span style={{ background: KIND_COLORS[el.kind] ?? "#6B7280", color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 3, flexShrink: 0, marginTop: 1 }}>
                  {el.kind}
                </span>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>{el.name}</span>
                  {el.description && <span style={{ fontSize: 12, color: "#6B7280", marginLeft: 8 }}>{el.description}</span>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Grounding */}
        <div style={{ fontSize: 12, color: "#9CA3AF", marginBottom: 14 }}>
          {option.grounded_on.length > 0
            ? `Grounded on: ${option.grounded_on.join(", ")}`
            : "No knowledge citations (advisory)"}
        </div>

        {/* Accept button */}
        {!isAccepted && (
          <button
            onClick={() => setShowDialog(true)}
            disabled={accept.isPending}
            style={{ padding: "8px 18px", background: "#166534", color: "#fff", border: "none", borderRadius: 4, cursor: accept.isPending ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
          >
            {accept.isPending ? "Accepting..." : "Accept this option"}
          </button>
        )}
        {accept.isError && (
          <div style={{ marginTop: 8, color: "#B91C1C", fontSize: 13 }}>
            {String(accept.error?.message ?? "Accept failed")}
          </div>
        )}
      </div>

      {showDialog && (
        <AcceptDialog
          option={option}
          designId={/* unused */ ""}
          onConfirm={(req) => {
            accept.mutate(
              { optionId: option.option_id, ...req },
              {
                onSuccess: () => {
                  setShowDialog(false);
                  onAcceptSuccess();
                },
              },
            );
          }}
          onCancel={() => setShowDialog(false)}
          isPending={accept.isPending}
        />
      )}
    </div>
  );
}
