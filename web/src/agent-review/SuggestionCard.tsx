import React, { useState } from "react";
import type { AgentSuggestionBase } from "../api/agentReview";
import { useAcceptSuggestion, useRejectSuggestion } from "../api/agentReview";

/** Generic review card for one Agent Review suggestion (ADP-SPEC-039).
 *
 * Renders the adapter-agnostic envelope (rationale, citations, advisory
 * gating, accept/reject) always. Adapter-specific "what's actually being
 * suggested" fields (any keys beyond AgentSuggestionBase) render as a plain
 * field list here -- individual adapters may pass a `renderDetail` override
 * for nicer, type-specific presentation as their suggestion types land.
 */

const BASE_FIELDS = new Set(["suggestion_id", "rationale", "citations", "advisory", "status", "type"]);

interface Props<S extends AgentSuggestionBase = AgentSuggestionBase> {
  suggestion: S;
  basePath: string;
  operationId: string;
  renderDetail?: (suggestion: S) => React.ReactNode;
  /** Called after a successful accept -- lets the adapter refresh whatever
   * data the suggestion just wrote to (e.g. the capabilities list), since
   * this card only knows about the review operation, not the adapter's
   * underlying entity data. */
  onAccepted?: () => void;
}

export default function SuggestionCard<S extends AgentSuggestionBase = AgentSuggestionBase>({
  suggestion,
  basePath,
  operationId,
  renderDetail,
  onAccepted,
}: Props<S>): React.ReactElement {
  const [advisoryAcknowledged, setAdvisoryAcknowledged] = useState(false);
  const accept = useAcceptSuggestion(basePath, operationId);
  const reject = useRejectSuggestion(basePath, operationId);

  const isPending = suggestion.status !== "pending";
  const canAccept = !isPending && !accept.isPending && !reject.isPending && (!suggestion.advisory || advisoryAcknowledged);

  const extraFields = Object.entries(suggestion as Record<string, unknown>).filter(
    ([key, value]) => !BASE_FIELDS.has(key) && value !== null && value !== undefined,
  );

  return (
    <div style={cardStyle}>
      {suggestion.advisory && (
        <div style={{ fontSize: 10, fontWeight: 700, color: "var(--warn)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          ⚠ Advisory — unverified citation
        </div>
      )}

      <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--ink)" }}>{suggestion.rationale}</p>

      {renderDetail?.(suggestion) ?? (
        extraFields.length > 0 && (
          <ul style={{ margin: "0 0 8px", padding: "0 0 0 14px" }}>
            {extraFields.map(([key, value]) => (
              <li key={key} style={{ fontSize: 12, color: "var(--ink-2)" }}>
                <strong>{key}</strong>: {String(value)}
              </li>
            ))}
          </ul>
        )
      )}

      {suggestion.citations.length > 0 && (
        <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 8 }}>
          Citations: {suggestion.citations.map((c) => `${c.entity_type}:${c.entity_id}`).join(", ")}
        </div>
      )}

      {suggestion.advisory && suggestion.status === "pending" && (
        <label style={{ display: "flex", gap: 6, alignItems: "flex-start", fontSize: 12, color: "var(--warn)", marginBottom: 8, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={advisoryAcknowledged}
            onChange={(e) => setAdvisoryAcknowledged(e.target.checked)}
            style={{ marginTop: 2 }}
          />
          I understand this suggestion cites an unverified reference and accept additional review responsibility.
        </label>
      )}

      {suggestion.status === "pending" ? (
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() =>
              accept.mutate(
                { suggestionId: suggestion.suggestion_id, advisoryAcknowledged },
                { onSuccess: () => onAccepted?.() },
              )
            }
            disabled={!canAccept}
            style={{ ...btnStyle, background: canAccept ? "var(--good)" : "var(--border)", color: "#fff", cursor: canAccept ? "pointer" : "not-allowed" }}
          >
            {accept.isPending ? "Accepting…" : "Accept"}
          </button>
          <button
            onClick={() => reject.mutate({ suggestionId: suggestion.suggestion_id })}
            disabled={reject.isPending || accept.isPending}
            style={{ ...btnStyle, background: "var(--surface)", color: "var(--ink-2)", border: "1px solid var(--border)" }}
          >
            {reject.isPending ? "Rejecting…" : "Reject"}
          </button>
        </div>
      ) : (
        <div style={{ fontSize: 12, fontWeight: 600, color: suggestion.status === "accepted" ? "var(--good)" : "var(--ink-3)" }}>
          {suggestion.status === "accepted" ? "✓ Accepted" : "✕ Rejected"}
        </div>
      )}
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  padding: "10px 12px",
  background: "var(--surface-2)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  marginBottom: 8,
};

const btnStyle: React.CSSProperties = {
  padding: "5px 14px",
  fontSize: 13,
  border: "none",
  borderRadius: 4,
  fontFamily: "inherit",
};
