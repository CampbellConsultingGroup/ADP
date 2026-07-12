import React, { useState } from "react";
import type { ProposalResponse, RequirementKind } from "../api/intake";
import { useConfirmProposal, useRejectProposal } from "../api/intake";
import { Button } from "../ui";
import { KIND_HUE, kindLabel } from "./kinds";

interface ProposalCardProps {
  proposal: ProposalResponse;
  designId: string;
  operationId: string;
}

export default function ProposalCard({ proposal, designId, operationId }: ProposalCardProps): React.ReactElement {
  const [editing, setEditing] = useState(false);
  const [editedText, setEditedText] = useState(proposal.draft_statement);
  const confirm = useConfirmProposal(designId, operationId);
  const reject = useRejectProposal(designId, operationId);

  const isActioned = proposal.status !== "pending";
  const isPending = confirm.isPending || reject.isPending;

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 10, background: "var(--surface)", opacity: isActioned ? 0.6 : 1 }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
        <span style={{ background: KIND_HUE[proposal.kind as RequirementKind] ?? "var(--ink-3)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4 }}>
          {kindLabel(proposal.kind)}
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{Math.round(proposal.confidence * 100)}% confidence</span>
        {isActioned && <span style={{ fontSize: 11, color: "var(--ink-2)", fontWeight: 700 }}>{proposal.status.toUpperCase()}</span>}
      </div>

      {editing ? (
        <textarea
          aria-label="Edit requirement statement"
          className="ui-textarea"
          value={editedText}
          onChange={(e) => setEditedText(e.target.value)}
          style={{ minHeight: 60 }}
        />
      ) : (
        <div style={{ fontSize: 13, color: "var(--ink)", marginBottom: 8 }}>{proposal.draft_statement}</div>
      )}

      {/* Source excerpt — SC-005: ALWAYS visible, never hidden */}
      <blockquote role="blockquote" style={{ margin: "8px 0", padding: "6px 10px", background: "var(--surface-2)", borderLeft: "3px solid var(--border-strong)", fontSize: 12, color: "var(--ink-2)", fontStyle: "italic" }}>
        Source: “{proposal.source_excerpt}”
      </blockquote>

      {!isActioned && (
        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center" }}>
          <Button variant="primary" size="sm" disabled={isPending}
            onClick={() => confirm.mutate({ proposalId: proposal.proposal_id, editedStatement: null })}>
            {confirm.isPending ? "…" : "Confirm"}
          </Button>
          {!editing ? (
            <Button size="sm" disabled={isPending} onClick={() => setEditing(true)}>Edit &amp; Confirm</Button>
          ) : (
            <Button variant="primary" size="sm" disabled={isPending || !editedText.trim()}
              onClick={() => confirm.mutate({ proposalId: proposal.proposal_id, editedStatement: editedText.trim() })}>
              Confirm Edit
            </Button>
          )}
          <Button variant="danger" size="sm" disabled={isPending}
            onClick={() => reject.mutate({ proposalId: proposal.proposal_id })}>
            Reject
          </Button>
          {editing && <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>}
        </div>
      )}
      {(confirm.isError || reject.isError) && (
        <div style={{ marginTop: 6, fontSize: 12, color: "var(--crit)" }}>
          {String((confirm.error || reject.error)?.message ?? "Action failed")}
        </div>
      )}
    </div>
  );
}
