import React from "react";
import type { PortfolioDesignSummary } from "../api/portfolio";
import { Button, StatusBadge } from "../ui";
import { LIFECYCLE_TONE, LIFECYCLE_LABEL } from "./lifecycle";

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
          <div key={i} style={{ height: 56, background: "var(--surface-3)", borderRadius: 8, marginBottom: 8 }} />
        ))}
      </div>
    );
  }

  if (designs.length === 0) {
    return <p style={{ color: "var(--ink-3)", fontSize: 14, padding: "16px 0" }}>No designs match these filters.</p>;
  }

  return (
    <div>
      {designs.map((d) => (
        <div
          key={d.id}
          style={{
            display: "flex", alignItems: "center", gap: 12, padding: "10px 12px",
            borderRadius: 8, border: "1px solid var(--border)", marginBottom: 8, background: "var(--surface)",
          }}
        >
          <StatusBadge tone={LIFECYCLE_TONE[d.lifecycle_status] ?? "neutral"}>
            {LIFECYCLE_LABEL[d.lifecycle_status] ?? d.lifecycle_status}
          </StatusBadge>

          <span style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{d.title}</span>

          {d.overdue_review && <StatusBadge tone="warn">Review overdue</StatusBadge>}

          {d.primary_technology && (
            <span style={{ padding: "2px 9px", borderRadius: 12, background: "var(--surface-2)", border: "1px solid var(--border)", color: "var(--ink-2)", fontSize: 12 }}>
              {d.primary_technology}
            </span>
          )}

          <span style={{ fontSize: 12, color: "var(--ink-3)", whiteSpace: "nowrap" }}>{d.element_count} elements</span>

          <Button size="sm" onClick={() => onSelectDesign(d.id)}>Open</Button>
        </div>
      ))}
    </div>
  );
}
