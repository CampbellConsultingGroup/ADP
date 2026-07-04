import React, { useState } from "react";
import type { SolutionOption } from "../api/recommend";
import AcceptDialog from "./AcceptDialog";
import RejectDialog from "./RejectDialog";
import { useAcceptOption, useRejectOption } from "../api/recommend";

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
  const [showAcceptDialog, setShowAcceptDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const accept = useAcceptOption(designId, operationId);
  const reject = useRejectOption(designId, operationId);

  const isAccepted = option.status === "accepted";
  const isRejected = option.status === "rejected";
  const isSettled = isAccepted || isRejected;
  const isRequirementsOnly = option.knowledge_source === "requirements_only";

  return (
    <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, marginBottom: 16, overflow: "hidden", opacity: isSettled ? 0.7 : 1 }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", background: isAccepted ? "#F0FDF4" : isRejected ? "#FEF2F2" : "#F8FAFC", borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ background: "#1168BD", color: "#fff", fontWeight: 700, fontSize: 13, padding: "3px 10px", borderRadius: 4 }}>#{option.rank}</span>
        <span style={{ fontWeight: 600, fontSize: 15, flex: 1 }}>{option.title}</span>
        <span style={{ fontSize: 12, color: "#6B7280" }}>score: {Math.round(option.ranking_score * 100)}%</span>
        {option.advisory && !isRequirementsOnly && (
          <span style={{ background: "#FEF3C7", color: "#92400E", border: "1px solid #FDE68A", fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 4 }}>⚠ ADVISORY</span>
        )}
        {isAccepted && <span style={{ background: "#D1FAE5", color: "#065F46", fontSize: 12, fontWeight: 600, padding: "2px 8px", borderRadius: 4 }}>✓ Accepted</span>}
        {isRejected && <span style={{ background: "#FEE2E2", color: "#991B1B", fontSize: 12, fontWeight: 600, padding: "2px 8px", borderRadius: 4 }}>✗ Rejected</span>}
      </div>

      <div style={{ padding: 16 }}>
        {/* ADP-SPEC-019: requirements_only info box (blue, neutral) */}
        {isRequirementsOnly && (
          <div style={{ marginBottom: 12, padding: 10, background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 6, fontSize: 13, color: "#1E40AF" }}>
            ℹ Generated from requirements — no prior knowledge base entries were available. Accepting this option will save it to the knowledge base for future recommendations.
          </div>
        )}

        {/* Advisory warning for KB-grounded options that lack citations */}
        {option.advisory && !isRequirementsOnly && (
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
          {isRequirementsOnly
            ? "No knowledge citations — generated from requirements only"
            : option.grounded_on.length > 0
              ? `Grounded on: ${option.grounded_on.join(", ")}`
              : "No knowledge citations (advisory)"}
        </div>

        {/* Action buttons */}
        {!isSettled && (
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => setShowAcceptDialog(true)}
              disabled={accept.isPending || reject.isPending}
              style={{ padding: "8px 18px", background: "#166534", color: "#fff", border: "none", borderRadius: 4, cursor: (accept.isPending || reject.isPending) ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
            >
              {accept.isPending ? "Accepting..." : "Accept"}
            </button>
            <button
              onClick={() => setShowRejectDialog(true)}
              disabled={accept.isPending || reject.isPending}
              style={{ padding: "8px 18px", background: "#fff", color: "#991B1B", border: "1px solid #FCA5A5", borderRadius: 4, cursor: (accept.isPending || reject.isPending) ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
            >
              {reject.isPending ? "Rejecting..." : "Reject"}
            </button>
          </div>
        )}
        {accept.isError && (
          <div style={{ marginTop: 8, color: "#B91C1C", fontSize: 13 }}>
            {String(accept.error?.message ?? "Accept failed")}
          </div>
        )}
        {reject.isError && (
          <div style={{ marginTop: 8, color: "#B91C1C", fontSize: 13 }}>
            {String(reject.error?.message ?? "Reject failed")}
          </div>
        )}
      </div>

      {showAcceptDialog && (
        <AcceptDialog
          option={option}
          designId={""}
          onConfirm={(req) => {
            accept.mutate(
              { optionId: option.option_id, ...req },
              {
                onSuccess: () => {
                  setShowAcceptDialog(false);
                  onAcceptSuccess();
                },
              },
            );
          }}
          onCancel={() => setShowAcceptDialog(false)}
          isPending={accept.isPending}
        />
      )}

      {showRejectDialog && (
        <RejectDialog
          option={option}
          onConfirm={(reason) => {
            reject.mutate(
              { optionId: option.option_id, rejection_reason: reason },
              {
                onSuccess: () => {
                  setShowRejectDialog(false);
                },
              },
            );
          }}
          onCancel={() => setShowRejectDialog(false)}
          isPending={reject.isPending}
        />
      )}
    </div>
  );
}
