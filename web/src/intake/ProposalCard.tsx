import React, { useState } from "react";
import type { ProposalResponse, RequirementKind } from "../api/intake";
import { useConfirmProposal, useRejectProposal } from "../api/intake";

interface ProposalCardProps {
  proposal: ProposalResponse;
  designId: string;
  operationId: string;
}

const KIND_COLORS: Record<RequirementKind, string> = {
  functional: "#1168BD", non_functional: "#6B21A8",
  constraint: "#C2410C", driver: "#166534",
};

export default function ProposalCard({ proposal, designId, operationId }: ProposalCardProps): React.ReactElement {
  const [editing, setEditing] = useState(false);
  const [editedText, setEditedText] = useState(proposal.draft_statement);
  const confirm = useConfirmProposal(designId, operationId);
  const reject = useRejectProposal(designId, operationId);

  const isActioned = proposal.status !== "pending";
  const isPending = confirm.isPending || reject.isPending;

  return (
    <div style={{ border: "1px solid #e0e0e0", borderRadius: 6, padding: 12, marginBottom: 10, opacity: isActioned ? 0.6 : 1 }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <span style={{ background: KIND_COLORS[proposal.kind as RequirementKind] ?? "#888", color: "#fff", fontSize: 10, fontWeight: "bold", padding: "2px 6px", borderRadius: 3 }}>
          {proposal.kind.replace("_", " ")}
        </span>
        <span style={{ fontSize: 11, color: "#888" }}>{Math.round(proposal.confidence * 100)}% confidence</span>
        {isActioned && <span style={{ fontSize: 11, color: "#555", fontWeight: "bold" }}>{proposal.status.toUpperCase()}</span>}
      </div>

      {editing ? (
        <textarea
          aria-label="Edit requirement statement"
          value={editedText}
          onChange={(e) => setEditedText(e.target.value)}
          style={{ width: "100%", padding: 6, fontSize: 13, border: "1px solid #ccc", borderRadius: 4, resize: "vertical", minHeight: 60 }}
        />
      ) : (
        <div style={{ fontSize: 13, color: "#222", marginBottom: 8 }}>{proposal.draft_statement}</div>
      )}

      {/* Source excerpt — SC-005: ALWAYS visible, never hidden */}
      <blockquote role="blockquote" style={{ margin: "8px 0", padding: "6px 10px", background: "#f5f5f5", borderLeft: "3px solid #ccc", fontSize: 12, color: "#666", fontStyle: "italic" }}>
        Source: "{proposal.source_excerpt}"
      </blockquote>

      {!isActioned && (
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            disabled={isPending}
            onClick={() => confirm.mutate({ proposalId: proposal.proposal_id, editedStatement: null })}
            style={{ padding: "5px 12px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: isPending ? "not-allowed" : "pointer", fontSize: 13 }}
          >
            {confirm.isPending ? "..." : "Confirm"}
          </button>
          {!editing ? (
            <button
              disabled={isPending}
              onClick={() => setEditing(true)}
              style={{ padding: "5px 12px", background: "#fff", color: "#1168BD", border: "1px solid #1168BD", borderRadius: 4, cursor: isPending ? "not-allowed" : "pointer", fontSize: 13 }}
            >
              Edit & Confirm
            </button>
          ) : (
            <button
              disabled={isPending || !editedText.trim()}
              onClick={() => confirm.mutate({ proposalId: proposal.proposal_id, editedStatement: editedText.trim() })}
              style={{ padding: "5px 12px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: isPending ? "not-allowed" : "pointer", fontSize: 13 }}
            >
              Confirm Edit
            </button>
          )}
          <button
            disabled={isPending}
            onClick={() => reject.mutate({ proposalId: proposal.proposal_id })}
            style={{ padding: "5px 12px", background: "#fff", color: "#c0392b", border: "1px solid #c0392b", borderRadius: 4, cursor: isPending ? "not-allowed" : "pointer", fontSize: 13 }}
          >
            Reject
          </button>
          {editing && <button onClick={() => setEditing(false)} style={{ padding: "5px 8px", background: "none", border: "none", color: "#888", cursor: "pointer", fontSize: 12 }}>Cancel</button>}
        </div>
      )}
      {(confirm.isError || reject.isError) && (
        <div style={{ marginTop: 6, fontSize: 12, color: "#c0392b" }}>
          {String((confirm.error || reject.error)?.message ?? "Action failed")}
        </div>
      )}
    </div>
  );
}
