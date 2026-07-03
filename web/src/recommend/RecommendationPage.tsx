import React, { useState } from "react";
import { useStartRecommendation, useRecommendStatus } from "../api/recommend";
import RequirementSelector from "./RequirementSelector";
import OptionCard from "./OptionCard";

interface RecommendationPageProps {
  designId: string;
  onNavigate: (view: "canvas" | "intake" | "recommend") => void;
}

type NavView = "canvas" | "intake" | "recommend";

const NAV_ITEMS: { view: NavView; label: string }[] = [
  { view: "intake", label: "Intake" },
  { view: "recommend", label: "Recommendations" },
  { view: "canvas", label: "Canvas" },
];

export default function RecommendationPage({ designId, onNavigate }: RecommendationPageProps): React.ReactElement {
  const [operationId, setOperationId] = useState<string | null>(null);
  const start = useStartRecommendation(designId);
  const { data: statusData } = useRecommendStatus(designId, operationId);

  const status = statusData?.status;
  const options = statusData?.options ?? [];

  const handleSubmit = (ids: string[]) => {
    start.mutate({ requirement_ids: ids }, {
      onSuccess: (data) => setOperationId(data.operation_id),
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Arial, sans-serif" }}>
      {/* Header with three-view nav */}
      <div style={{ display: "flex", alignItems: "center", gap: 0, padding: "0 16px", background: "#1168BD", color: "#fff", flexShrink: 0 }}>
        <span style={{ fontWeight: 700, fontSize: 15, marginRight: 20, padding: "12px 0" }}>ADP</span>
        {NAV_ITEMS.map(({ view, label }) => (
          <button
            key={view}
            onClick={() => onNavigate(view)}
            style={{
              padding: "12px 18px",
              background: view === "recommend" ? "rgba(255,255,255,0.2)" : "transparent",
              color: "#fff",
              border: "none",
              borderBottom: view === "recommend" ? "3px solid #fff" : "3px solid transparent",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: view === "recommend" ? 600 : 400,
            }}
          >
            {label}
          </button>
        ))}
        <span style={{ fontSize: 13, opacity: 0.7, marginLeft: "auto", padding: "12px 0" }}>{designId}</span>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#111827", marginBottom: 4 }}>Architecture Recommendations</h2>
        <p style={{ fontSize: 13, color: "#6B7280", marginBottom: 20 }}>
          Claude will analyse your requirements and suggest ranked architectural options grounded in your organisation's knowledge base.
        </p>

        {/* Requirement selector */}
        <RequirementSelector designId={designId} onSubmit={handleSubmit} isPending={start.isPending || status === "running"} />

        {/* Status indicators */}
        {operationId && status === "running" && (
          <div style={{ marginTop: 16, padding: 14, background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 6, fontSize: 13, color: "#1D4ED8" }}>
            ⏳ Claude is analysing your requirements and generating options...
          </div>
        )}
        {operationId && status === "failed" && (
          <div style={{ marginTop: 16, padding: 14, background: "#FEE2E2", border: "1px solid #FECACA", borderRadius: 6, fontSize: 13, color: "#B91C1C" }}>
            ✗ Generation failed: {statusData?.error_description ?? "Unknown error"}. Check LLM configuration.
          </div>
        )}

        {/* Options */}
        {operationId && status === "completed" && options.length === 0 && (
          <div style={{ marginTop: 16, padding: 14, background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 6, fontSize: 13, color: "#92400E" }}>
            No options were generated. This may be because the knowledge base is empty (all options would be advisory) or the LLM did not return structured output. Try again or check LLM settings.
          </div>
        )}
        {operationId && status === "completed" && options.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#374151", marginBottom: 14 }}>
              {statusData?.result_summary} — ranked by fit with your requirements
            </div>
            {options.map((opt) => (
              <OptionCard
                key={opt.option_id}
                option={opt}
                designId={designId}
                operationId={operationId}
                onAcceptSuccess={() => onNavigate("canvas")}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
