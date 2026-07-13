import React from "react";
import type { ProposalResponse } from "../api/intake";
import ProposalCard from "./ProposalCard";

interface ProposalsListProps {
  proposals: ProposalResponse[];
  designId: string;
  operationId: string;
}

export default function ProposalsList({ proposals, designId, operationId }: ProposalsListProps): React.ReactElement {
  if (proposals.length === 0) {
    return (
      <div style={{ padding: 16, color: "var(--ink-3)", fontSize: 13, fontStyle: "italic", textAlign: "center" }}>
        No requirements could be extracted — try the structured form.
      </div>
    );
  }
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 10 }}>
        Extracted Proposals ({proposals.length})
      </h3>
      {proposals.map((p) => (
        <ProposalCard key={p.proposal_id} proposal={p} designId={designId} operationId={operationId} />
      ))}
    </div>
  );
}
