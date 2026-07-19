import React, { useState } from "react";
import type { AgentSuggestionBase } from "../api/agentReview";
import { useAgentReviewStatus, useSubmitAgentReview } from "../api/agentReview";
import SuggestionCard from "./SuggestionCard";

/** Generic "trigger an Agent Review + show its suggestions" button (ADP-SPEC-039).
 *
 * Self-contained: manages its own operation lifecycle (trigger -> poll ->
 * render suggestions) so a consuming screen just drops this in with a
 * basePath. Parameterized by adapter via basePath and an optional
 * renderDetail passthrough to SuggestionCard for adapter-specific rendering.
 */

interface Props<S extends AgentSuggestionBase = AgentSuggestionBase> {
  basePath: string;
  label?: string;
  renderDetail?: (suggestion: S) => React.ReactNode;
}

export default function AgentReviewButton<S extends AgentSuggestionBase = AgentSuggestionBase>({
  basePath,
  label = "Review with AI",
  renderDetail,
}: Props<S>): React.ReactElement {
  const [operationId, setOperationId] = useState<string | null>(null);
  const submit = useSubmitAgentReview(basePath);
  const { data } = useAgentReviewStatus<S>(basePath, operationId);

  const running = data?.status === "pending" || data?.status === "running";
  const busy = submit.isPending || running;

  const handleClick = async () => {
    const result = await submit.mutateAsync();
    setOperationId(result.operation_id);
  };

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={busy}
        style={{
          fontSize: 12, padding: "4px 10px", borderRadius: 4, cursor: busy ? "not-allowed" : "pointer",
          background: "var(--accent-wash)", color: "var(--accent-2)", border: "1px solid var(--accent)",
        }}
      >
        {busy ? "Reviewing…" : label}
      </button>

      {data?.status === "failed" && (
        <div className="ui-alert crit" style={{ marginTop: 8 }}>
          Review failed: {data.error_description ?? "Unknown error"}
        </div>
      )}

      {data?.status === "completed" && data.suggestions.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 8 }}>No suggestions.</div>
      )}

      {data?.status === "completed" && data.suggestions.length > 0 && operationId && (
        <div style={{ marginTop: 8 }}>
          {data.suggestions.map((s) => (
            <SuggestionCard
              key={s.suggestion_id}
              suggestion={s}
              basePath={basePath}
              operationId={operationId}
              renderDetail={renderDetail}
            />
          ))}
        </div>
      )}
    </div>
  );
}
