import React from "react";
import { usePortfolioSummary } from "../api/portfolio";

const STATUS_CHIPS: { key: string; label: string; bg: string; text: string }[] = [
  { key: "draft",          label: "Draft",          bg: "#F3F4F6", text: "#374151" },
  { key: "proposed",       label: "Proposed",       bg: "#DBEAFE", text: "#1E40AF" },
  { key: "current",        label: "Current",        bg: "#D1FAE5", text: "#065F46" },
  { key: "deprecated",     label: "Deprecated",     bg: "#FEF3C7", text: "#92400E" },
  { key: "decommissioned", label: "Decommissioned", bg: "#FEE2E2", text: "#991B1B" },
];

interface PortfolioSummaryHeaderProps {
  onStatusSelect: (status: string | null) => void;
}

export default function PortfolioSummaryHeader({
  onStatusSelect,
}: PortfolioSummaryHeaderProps): React.ReactElement {
  const { data, isLoading } = usePortfolioSummary();

  if (isLoading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "12px 0",
        }}
      >
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{
              width: 80,
              height: 32,
              borderRadius: 8,
              backgroundColor: "#E5E7EB",
              animation: "pulse 1.5s infinite",
            }}
          />
        ))}
      </div>
    );
  }

  if (!data) return <></>;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 10,
        padding: "12px 0",
        borderBottom: "1px solid #E5E7EB",
        marginBottom: 16,
      }}
    >
      {/* Total */}
      <span style={{ fontSize: 14, fontWeight: 700, color: "#111827", marginRight: 4 }}>
        {data.total_designs} designs
      </span>

      {/* Status chips */}
      {STATUS_CHIPS.map(({ key, label, bg, text }) => {
        const count = data.by_status[key] ?? 0;
        if (count === 0) return null;
        return (
          <button
            key={key}
            onClick={() => onStatusSelect(key)}
            title={`Filter by ${label}`}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "3px 10px",
              borderRadius: 12,
              border: "none",
              backgroundColor: bg,
              color: text,
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {label}: {count}
          </button>
        );
      })}

      {/* Overdue badge */}
      {data.overdue_review_count > 0 && (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "3px 10px",
            borderRadius: 12,
            backgroundColor: "#FEF3C7",
            color: "#92400E",
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          ⚠ {data.overdue_review_count} overdue review{data.overdue_review_count !== 1 ? "s" : ""}
        </span>
      )}
    </div>
  );
}
