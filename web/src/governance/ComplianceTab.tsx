import React from "react";
import { useComplianceExceptions } from "../api/governance";
import type { AppView } from "../shell";
import { Button, StatusBadge } from "../ui";

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
          <div key={i} style={{ height: 64, backgroundColor: "var(--surface-2)", borderRadius: 8, marginBottom: 8, animation: "pulse 1.5s infinite" }} />
        ))}
      </div>
    );
  }

  const exceptions = data?.exceptions ?? [];

  if (exceptions.length === 0) {
    return (
      <div style={{ padding: "24px 0", textAlign: "center" }}>
        <p style={{ color: "var(--good)", fontWeight: 600, fontSize: 15 }}>
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
            border: "1px solid var(--border)",
            marginBottom: 8,
            backgroundColor: "var(--surface)",
          }}
        >
          {/* Severity badge */}
          <div style={{ flexShrink: 0 }}>
            <StatusBadge tone={ex.severity === "FAIL" ? "crit" : "warn"}>{ex.severity}</StatusBadge>
          </div>

          {/* Main content */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 500, fontSize: 14, color: "var(--ink)", marginBottom: 2 }}>
              {ex.finding_summary}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "var(--ink-3)" }}>{ex.title}</span>
              {ex.source && (
                <span style={{ fontSize: 11, color: "var(--ink-3)", fontFamily: "monospace" }}>
                  {ex.source}
                </span>
              )}
            </div>
          </div>

          {/* Open button */}
          <Button size="sm" style={{ flexShrink: 0 }} onClick={() => { onSelectDesign(ex.design_id); onNavigate("intake"); }}>Open</Button>
        </div>
      ))}
    </div>
  );
}
