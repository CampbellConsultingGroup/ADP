import React from "react";
import { usePortfolioSummary } from "../api/portfolio";
import { LIFECYCLE_TONE, LIFECYCLE_LABEL } from "./lifecycle";

interface PortfolioSummaryHeaderProps {
  onStatusSelect: (status: string | null) => void;
}

const ORDER = ["draft", "proposed", "current", "deprecated", "decommissioned"];

export default function PortfolioSummaryHeader({
  onStatusSelect,
}: PortfolioSummaryHeaderProps): React.ReactElement {
  const { data, isLoading } = usePortfolioSummary();

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0" }}>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} style={{ width: 80, height: 32, borderRadius: 8, background: "var(--surface-3)" }} />
        ))}
      </div>
    );
  }

  if (!data) return <></>;

  return (
    <div
      style={{
        display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8,
        padding: "12px 0", borderBottom: "1px solid var(--border)", marginBottom: 16,
      }}
    >
      <span style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginRight: 4 }}>
        {data.total_designs} designs
      </span>

      {ORDER.map((key) => {
        const count = data.by_status[key] ?? 0;
        if (count === 0) return null;
        return (
          <button
            key={key}
            onClick={() => onStatusSelect(key)}
            title={`Filter by ${LIFECYCLE_LABEL[key]}`}
            className={`ui-badge ${LIFECYCLE_TONE[key]}`}
            style={{ cursor: "pointer", fontFamily: "var(--font)", fontWeight: 600 }}
          >
            <span className="b-dot" />
            {LIFECYCLE_LABEL[key]}: {count}
          </button>
        );
      })}

      {data.overdue_review_count > 0 && (
        <span className="ui-badge warn">
          <span className="b-dot" />
          {data.overdue_review_count} overdue review{data.overdue_review_count !== 1 ? "s" : ""}
        </span>
      )}
    </div>
  );
}
