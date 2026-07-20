import React from "react";
import type { AgentSuggestionBase } from "../api/agentReview";
import { MATURITY_LEVEL_LABEL, STRATEGIC_RELEVANCE_LABEL } from "../api/business";
import type { MaturityLevel, StrategicRelevance } from "../api/business";

/** Business Capabilities adapter's `renderDetail` override for the generic
 * SuggestionCard (ADP-SPEC-039 US2). Renders reclassify_strategic_relevance /
 * set_maturity_level as a distinct current -> suggested transition instead of
 * the generic field-list fallback; other suggestion types fall through to
 * that default (return null here).
 */

export interface CapabilitySuggestion extends AgentSuggestionBase {
  type: string;
  capability_id: string | null;
  strategic_relevance?: StrategicRelevance | null;
  previous_strategic_relevance?: StrategicRelevance | null;
  maturity_level?: MaturityLevel | null;
  previous_maturity_level?: MaturityLevel | null;
  duplicate_of_capability_id?: string | null;
  domain_id?: string | null;
  proposed_name?: string | null;
  proposed_description?: string | null;
  proposed_level?: 1 | 2 | 3 | null;
  proposed_parent_id?: string | null;
}

export function renderCapabilitySuggestionDetail(
  suggestion: CapabilitySuggestion,
): React.ReactNode {
  if (suggestion.type === "reclassify_strategic_relevance") {
    return (
      <TransitionRow
        label="Strategic relevance"
        from={
          suggestion.previous_strategic_relevance != null
            ? STRATEGIC_RELEVANCE_LABEL[suggestion.previous_strategic_relevance]
            : "Unclassified"
        }
        to={
          suggestion.strategic_relevance != null
            ? STRATEGIC_RELEVANCE_LABEL[suggestion.strategic_relevance]
            : "Unclassified"
        }
      />
    );
  }

  if (suggestion.type === "set_maturity_level") {
    return (
      <TransitionRow
        label="Maturity level"
        from={
          suggestion.previous_maturity_level != null
            ? MATURITY_LEVEL_LABEL[suggestion.previous_maturity_level]
            : "Not assessed"
        }
        to={
          suggestion.maturity_level != null
            ? MATURITY_LEVEL_LABEL[suggestion.maturity_level]
            : "Not assessed"
        }
      />
    );
  }

  if (suggestion.type === "flag_capability_for_removal") {
    return (
      <div style={{ fontSize: 12, color: "var(--crit)", marginBottom: 8 }}>
        <strong>Flagged for removal:</strong> capability {suggestion.capability_id}
      </div>
    );
  }

  if (suggestion.type === "propose_new_capability") {
    return (
      <div style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 8 }}>
        <div style={{ marginBottom: 4 }}>
          <strong>Proposed capability:</strong>{" "}
          <span style={{ color: "var(--accent-2)", fontWeight: 600 }}>
            {suggestion.proposed_name}
          </span>{" "}
          <span style={{ fontSize: 10, color: "var(--ink-3)" }}>
            (L{suggestion.proposed_level}
            {suggestion.proposed_parent_id ? `, parent ${suggestion.proposed_parent_id}` : ""})
          </span>
        </div>
        {suggestion.proposed_description && <div>{suggestion.proposed_description}</div>}
      </div>
    );
  }

  return null;
}

function TransitionRow({ label, from, to }: { label: string; from: string; to: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--ink-2)", marginBottom: 8 }}>
      <strong>{label}:</strong>
      <span style={{ color: "var(--ink-3)", textDecoration: "line-through" }}>{from}</span>
      <span aria-hidden="true">→</span>
      <span style={{ color: "var(--accent-2)", fontWeight: 600 }}>{to}</span>
    </div>
  );
}
