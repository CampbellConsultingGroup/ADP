/**
 * ReasoningPanel — collapsible LLM reasoning display for a recommendation option (ADP-SPEC-028).
 *
 * Lazy: reasoning is only fetched when the user clicks "Show reasoning".
 * Immutable: staleTime=Infinity so records are never re-fetched (llm_reasoning_log is append-only).
 *
 * Displays three sections when expanded:
 *   1. Generation reasoning  (step_name = "generate")
 *   2. Trade-off analysis    (step_name = "analyze_tradeoffs")
 *   3. Knowledge citations   (option.grounded_on resolved to titles)
 */
import React, { useState } from "react";
import type { SolutionOption } from "../api/recommend";
import { useOptionReasoning } from "../api/recommend";
import KnowledgeCitationChip from "./KnowledgeCitationChip";

interface ReasoningPanelProps {
  option: SolutionOption;
  operationId: string;
  designId: string;
}

function _relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ReasoningPanel({ option, operationId }: ReasoningPanelProps): React.ReactElement {
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading } = useOptionReasoning(operationId, option.option_id, expanded);
  const records = data?.records ?? [];
  const hasRecords = !isLoading && records.length > 0;
  const noRecords = !isLoading && expanded && records.length === 0;

  const generateRecord = records.find((r) => r.step_name === "generate");
  const tradeoffRecord = records.find((r) => r.step_name === "analyze_tradeoffs");

  const isRequirementsOnly = option.knowledge_source === "requirements_only";

  return (
    <div style={{ marginBottom: 14, borderTop: "1px solid #F3F4F6", paddingTop: 12 }}>
      {/* Toggle button */}
      {noRecords ? (
        <span style={{ fontSize: 12, color: "#9CA3AF", fontStyle: "italic" }}>
          No reasoning recorded for this option
        </span>
      ) : (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            padding: "5px 12px",
            background: expanded ? "#EFF6FF" : "#fff",
            color: expanded ? "#1E40AF" : "#6B7280",
            border: `1px solid ${expanded ? "#BFDBFE" : "#D1D5DB"}`,
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          {expanded ? "▲ Hide reasoning" : "▼ Show reasoning"}
        </button>
      )}

      {/* Panel content */}
      {expanded && (
        <div style={{ marginTop: 12, padding: 16, background: "#FAFAFA", border: "1px solid #E5E7EB", borderRadius: 8 }}>

          {/* Loading skeleton */}
          {isLoading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[80, 60, 90, 50].map((w, i) => (
                <div key={i} style={{ height: 12, width: `${w}%`, background: "#E5E7EB", borderRadius: 4, animation: "pulse 1.5s infinite" }} />
              ))}
            </div>
          )}

          {/* Section 1: Generation reasoning */}
          {generateRecord && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#374151", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Generation Reasoning
                </span>
                <span style={{ fontSize: 11, background: "#E0E7FF", color: "#3730A3", padding: "1px 6px", borderRadius: 3 }}>
                  {generateRecord.model_id}
                </span>
                <span style={{ fontSize: 11, color: "#9CA3AF" }}>
                  {_relativeTime(generateRecord.created_at)}
                </span>
              </div>
              <p style={{ fontSize: 13, color: "#374151", lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap" }}>
                {generateRecord.reasoning_text}
              </p>
              <div style={{ marginTop: 6, fontSize: 11, color: "#9CA3AF" }}>
                {generateRecord.input_tokens + generateRecord.output_tokens} tokens
              </div>
            </div>
          )}

          {/* Section 2: Trade-off analysis */}
          {tradeoffRecord && (
            <div style={{ marginBottom: 16, paddingTop: generateRecord ? 12 : 0, borderTop: generateRecord ? "1px solid #E5E7EB" : "none" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                Trade-off Analysis
              </div>
              <p style={{ fontSize: 13, color: "#374151", lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap" }}>
                {tradeoffRecord.reasoning_text}
              </p>
              {tradeoffRecord.truncated && (
                <div style={{ marginTop: 6, fontSize: 11, color: "#F59E0B", fontStyle: "italic" }}>
                  [Truncated at 100,000 characters]
                </div>
              )}
            </div>
          )}

          {/* Section 3: Knowledge citations */}
          <div style={{ paddingTop: (generateRecord || tradeoffRecord) ? 12 : 0, borderTop: (generateRecord || tradeoffRecord) ? "1px solid #E5E7EB" : "none" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
              Knowledge Citations
            </div>
            {isRequirementsOnly ? (
              <div style={{ fontSize: 12, color: "#1E40AF", background: "#EFF6FF", padding: "6px 10px", borderRadius: 5 }}>
                ℹ Generated from requirements — no prior knowledge base entries were available.
              </div>
            ) : option.grounded_on.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {option.grounded_on.map((itemId, i) => (
                  <KnowledgeCitationChip key={i} itemId={String(itemId)} />
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "#9CA3AF", fontStyle: "italic" }}>
                No knowledge citations for this option
              </div>
            )}
          </div>

          {/* No records loaded but not loading */}
          {hasRecords === false && !isLoading && records.length === 0 && (
            <div style={{ fontSize: 12, color: "#9CA3AF", textAlign: "center", padding: "8px 0" }}>
              Reasoning records not yet available
            </div>
          )}
        </div>
      )}
    </div>
  );
}
