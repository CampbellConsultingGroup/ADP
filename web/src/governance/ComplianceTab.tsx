import React from "react";
import { useComplianceExceptions } from "../api/governance";
import type { AppView } from "../shell";

interface ComplianceTabProps {
  onSelectDesign: (id: string) => void;
  onNavigate: (view: AppView) => void;
}

export default function ComplianceTab({
  onSelectDesign,
  onNavigate,
}: ComplianceTabProps): React.ReactElement {
  const { data, isLoading } = useComplianceExceptions();

  if (isLoading) {
    return (
      <div>
        {[1, 2].map((i) => (
          <div key={i} style={{ height: 64, backgroundColor: "#F3F4F6", borderRadius: 8, marginBottom: 8, animation: "pulse 1.5s infinite" }} />
        ))}
      </div>
    );
  }

  const exceptions = data?.exceptions ?? [];

  if (exceptions.length === 0) {
    return (
      <div style={{ padding: "24px 0", textAlign: "center" }}>
        <p style={{ color: "#059669", fontWeight: 600, fontSize: 15 }}>
          ✓ No compliance exceptions — all designs are clean.
        </p>
      </div>
    );
  }

  return (
    <div>
      {exceptions.map((ex) => (
        <div
          key={`${ex.design_id}-${ex.finding_id}`}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "12px 14px",
            borderRadius: 8,
            border: "1px solid #E5E7EB",
            marginBottom: 8,
            backgroundColor: "#fff",
          }}
        >
          {/* Severity badge */}
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 12,
              backgroundColor: ex.severity === "FAIL" ? "#FEE2E2" : "#FEF3C7",
              color: ex.severity === "FAIL" ? "#991B1B" : "#92400E",
              fontSize: 12,
              fontWeight: 700,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            {ex.severity}
          </span>

          {/* Main content */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 500, fontSize: 14, color: "#111827", marginBottom: 2 }}>
              {ex.finding_summary}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "#6B7280" }}>{ex.title}</span>
              {ex.source && (
                <span style={{ fontSize: 11, color: "#9CA3AF", fontFamily: "monospace" }}>
                  {ex.source}
                </span>
              )}
            </div>
          </div>

          {/* Open button */}
          <button
            onClick={() => { onSelectDesign(ex.design_id); onNavigate("intake"); }}
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              border: "1px solid #D1D5DB",
              backgroundColor: "#fff",
              fontSize: 12,
              cursor: "pointer",
              color: "#374151",
              flexShrink: 0,
            }}
          >
            Open
          </button>
        </div>
      ))}
    </div>
  );
}
