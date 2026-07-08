import React from "react";
import type { PortfolioDesignSummary } from "../api/portfolio";

const LIFECYCLE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  draft:          { bg: "#F3F4F6", text: "#374151", label: "Draft" },
  proposed:       { bg: "#DBEAFE", text: "#1E40AF", label: "Proposed" },
  current:        { bg: "#D1FAE5", text: "#065F46", label: "Current" },
  deprecated:     { bg: "#FEF3C7", text: "#92400E", label: "Deprecated" },
  decommissioned: { bg: "#FEE2E2", text: "#991B1B", label: "Decommissioned" },
};

interface PortfolioDesignListProps {
  designs: PortfolioDesignSummary[];
  isLoading: boolean;
  onSelectDesign: (id: string) => void;
}

export default function PortfolioDesignList({
  designs,
  isLoading,
  onSelectDesign,
}: PortfolioDesignListProps): React.ReactElement {
  if (isLoading) {
    return (
      <div>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            style={{
              height: 56,
              backgroundColor: "#F3F4F6",
              borderRadius: 8,
              marginBottom: 8,
              animation: "pulse 1.5s infinite",
            }}
          />
        ))}
      </div>
    );
  }

  if (designs.length === 0) {
    return (
      <p style={{ color: "#6B7280", fontSize: 14, padding: "16px 0" }}>
        No designs match these filters.
      </p>
    );
  }

  return (
    <div>
      {designs.map((d) => {
        const lc = LIFECYCLE_COLORS[d.lifecycle_status] ?? LIFECYCLE_COLORS.draft;
        return (
          <div
            key={d.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid #E5E7EB",
              marginBottom: 8,
              backgroundColor: "#fff",
            }}
          >
            {/* Status badge */}
            <span
              style={{
                padding: "2px 8px",
                borderRadius: 12,
                backgroundColor: lc.bg,
                color: lc.text,
                fontSize: 12,
                fontWeight: 600,
                whiteSpace: "nowrap",
              }}
            >
              {lc.label}
            </span>

            {/* Title */}
            <span style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "#111827" }}>
              {d.title}
            </span>

            {/* Overdue chip */}
            {d.overdue_review && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 12,
                  backgroundColor: "#FEF3C7",
                  color: "#92400E",
                  fontSize: 12,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}
              >
                ⚠ Review overdue
              </span>
            )}

            {/* Technology tag */}
            {d.primary_technology && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 12,
                  backgroundColor: "#EDE9FE",
                  color: "#5B21B6",
                  fontSize: 12,
                }}
              >
                {d.primary_technology}
              </span>
            )}

            {/* Element count */}
            <span style={{ fontSize: 12, color: "#6B7280", whiteSpace: "nowrap" }}>
              {d.element_count} elements
            </span>

            {/* Open button */}
            <button
              onClick={() => onSelectDesign(d.id)}
              style={{
                padding: "4px 12px",
                borderRadius: 6,
                border: "1px solid #D1D5DB",
                backgroundColor: "#fff",
                color: "#374151",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              Open
            </button>
          </div>
        );
      })}
    </div>
  );
}
