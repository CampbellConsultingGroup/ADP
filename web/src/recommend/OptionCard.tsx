import React, { useState } from "react";
import type { SolutionOption } from "../api/recommend";
import AcceptDialog from "./AcceptDialog";
import RejectDialog from "./RejectDialog";
import ReasoningPanel from "./ReasoningPanel";
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
  container: "var(--ent)",
  system: "var(--accent)",
  person: "var(--accent-2)",
  component: "var(--biz)",
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
    <div style={{ border: "1px solid var(--border)", borderRadius: 8, marginBottom: 16, overflow: "hidden", opacity: isSettled ? 0.7 : 1 }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", background: isAccepted ? "var(--good-wash)" : isRejected ? "var(--crit-wash)" : "var(--surface-2)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ background: "var(--accent)", color: "#fff", fontWeight: 700, fontSize: 13, padding: "3px 10px", borderRadius: 4 }}>#{option.rank}</span>
        <span style={{ fontWeight: 600, fontSize: 15, flex: 1 }}>{option.title}</span>
        <span style={{ fontSize: 12, color: "var(--ink-3)" }}>score: {Math.round(option.ranking_score * 100)}%</span>
        {option.advisory && !isRequirementsOnly && (
          <span style={{ background: "var(--warn-wash)", color: "var(--warn)", border: "1px solid var(--warn)", fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 4 }}>⚠ ADVISORY</span>
        )}
        {isAccepted && <span style={{ background: "var(--good-wash)", color: "var(--good)", fontSize: 12, fontWeight: 600, padding: "2px 8px", borderRadius: 4 }}>✓ Accepted</span>}
        {isRejected && <span style={{ background: "var(--crit-wash)", color: "var(--crit)", fontSize: 12, fontWeight: 600, padding: "2px 8px", borderRadius: 4 }}>✗ Rejected</span>}
      </div>

      <div style={{ padding: 16 }}>
        {/* ADP-SPEC-019: requirements_only info box (blue, neutral) */}
        {isRequirementsOnly && (
          <div style={{ marginBottom: 12, padding: 10, background: "var(--accent-wash)", border: "1px solid var(--accent)", borderRadius: 6, fontSize: 13, color: "var(--accent-2)" }}>
            ℹ Generated from requirements — no prior knowledge base entries were available. Accepting this option will save it to the knowledge base for future recommendations.
          </div>
        )}

        {/* Advisory warning for KB-grounded options that lack citations */}
        {option.advisory && !isRequirementsOnly && (
          <div style={{ marginBottom: 12, padding: 10, background: "var(--warn-wash)", border: "1px solid var(--warn)", borderRadius: 6, fontSize: 13, color: "var(--warn)" }}>
            ⚠ This option lacks full knowledge-base grounding. Additional review recommended before accepting.
          </div>
        )}

        {/* Rationale */}
        <p style={{ fontSize: 13, color: "var(--ink-2)", marginBottom: 14, lineHeight: 1.6 }}>{option.rationale}</p>

        {/* Trade-off table */}
        {option.trade_offs.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Trade-offs</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--ink-3)", fontWeight: 500, width: "35%" }}>Criterion</th>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--ink-3)", fontWeight: 500, width: "20%" }}>Stance</th>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--ink-3)", fontWeight: 500 }}>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {option.trade_offs.map((tf, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--surface-2)" }}>
                    <td style={{ padding: "5px 8px", color: "var(--ink-2)" }}>{tf.criterion}</td>
                    <td style={{ padding: "5px 8px", whiteSpace: "nowrap" }}>
                      {STANCE_ICONS[tf.stance] ?? "•"} {tf.stance.replace("_", " ")}
                    </td>
                    <td style={{ padding: "5px 8px", color: "var(--ink-3)", fontSize: 12 }}>{tf.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Proposed elements */}
        {option.proposed_elements.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Proposed Elements</div>
            {option.proposed_elements.map((el, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
                <span style={{ background: KIND_COLORS[el.kind] ?? "var(--ink-3)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 3, flexShrink: 0, marginTop: 1 }}>
                  {el.kind}
                </span>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>{el.name}</span>
                  {el.description && <span style={{ fontSize: 12, color: "var(--ink-3)", marginLeft: 8 }}>{el.description}</span>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Reasoning panel (ADP-SPEC-028) */}
        <ReasoningPanel
          option={option}
          operationId={operationId}
          designId={designId}
        />

        {/* Action buttons */}
        {!isSettled && (
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => setShowAcceptDialog(true)}
              disabled={accept.isPending || reject.isPending}
              style={{ padding: "8px 18px", background: "var(--good)", color: "#fff", border: "none", borderRadius: 4, cursor: (accept.isPending || reject.isPending) ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
            >
              {accept.isPending ? "Accepting..." : "Accept"}
            </button>
            <button
              onClick={() => setShowRejectDialog(true)}
              disabled={accept.isPending || reject.isPending}
              style={{ padding: "8px 18px", background: "var(--surface)", color: "var(--crit)", border: "1px solid var(--crit)", borderRadius: 4, cursor: (accept.isPending || reject.isPending) ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
            >
              {reject.isPending ? "Rejecting..." : "Reject"}
            </button>
          </div>
        )}
        {accept.isError && (
          <div style={{ marginTop: 8, color: "var(--crit)", fontSize: 13 }}>
            {String(accept.error?.message ?? "Accept failed")}
          </div>
        )}
        {reject.isError && (
          <div style={{ marginTop: 8, color: "var(--crit)", fontSize: 13 }}>
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
