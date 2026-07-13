import React, { useState } from "react";
import { useGovernanceStatus, type DesignGovernanceRecord } from "../api/governance";
import type { AppView } from "../shell";
import { Button, StatusBadge } from "../ui";
import { LIFECYCLE_TONE, LIFECYCLE_LABEL } from "../portfolio/lifecycle";

type SortKey = keyof Pick<
  DesignGovernanceRecord,
  "title" | "last_activity" | "audit_count" | "accepted_recommendations" | "reasoning_record_count"
>;

interface DesignStatusTabProps {
  onSelectDesign: (id: string) => void;
  onNavigate: (view: AppView) => void;
}

export default function DesignStatusTab({
  onSelectDesign,
  onNavigate,
}: DesignStatusTabProps): React.ReactElement {
  const { data, isLoading } = useGovernanceStatus();
  const [sortKey, setSortKey] = useState<SortKey>("last_activity");
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const sorted = [...(data?.designs ?? [])].sort((a, b) => {
    const av = a[sortKey] ?? "";
    const bv = b[sortKey] ?? "";
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortAsc ? cmp : -cmp;
  });

  const SortBtn = ({ col, label }: { col: SortKey; label: string }) => (
    <th
      onClick={() => handleSort(col)}
      style={{ padding: "8px 12px", textAlign: "left", cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", fontSize: 13, fontWeight: 600, color: "var(--ink-2)", borderBottom: "2px solid var(--border)" }}
    >
      {label} {sortKey === col ? (sortAsc ? "↑" : "↓") : ""}
    </th>
  );

  if (isLoading) {
    return (
      <div>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{ height: 48, backgroundColor: "var(--surface-2)", borderRadius: 6, marginBottom: 6, animation: "pulse 1.5s infinite" }} />
        ))}
      </div>
    );
  }

  if (sorted.length === 0) {
    return <p style={{ color: "var(--ink-3)", fontSize: 14 }}>No designs found.</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ backgroundColor: "var(--surface-2)" }}>
            <SortBtn col="title" label="Design" />
            <SortBtn col="last_activity" label="Last Activity" />
            <SortBtn col="audit_count" label="Activity Count" />
            <SortBtn col="accepted_recommendations" label="Accepted Recs" />
            <SortBtn col="reasoning_record_count" label="Reasoning Records" />
            <th style={{ padding: "8px 12px", borderBottom: "2px solid var(--border)" }} />
          </tr>
        </thead>
        <tbody>
          {sorted.map((d) => {
            return (
              <tr
                key={d.design_id}
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <td style={{ padding: "10px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <StatusBadge tone={LIFECYCLE_TONE[d.lifecycle_status] ?? "neutral"}>
                      {LIFECYCLE_LABEL[d.lifecycle_status] ?? d.lifecycle_status}
                    </StatusBadge>
                    <span style={{ fontWeight: 500, color: "var(--ink)" }}>{d.title}</span>
                  </div>
                </td>
                <td style={{ padding: "10px 12px", color: "var(--ink-3)" }}>
                  {d.last_activity
                    ? new Date(d.last_activity).toLocaleDateString()
                    : "—"}
                </td>
                <td style={{ padding: "10px 12px", textAlign: "center" }}>{d.audit_count}</td>
                <td style={{ padding: "10px 12px", textAlign: "center" }}>{d.accepted_recommendations}</td>
                <td style={{ padding: "10px 12px", textAlign: "center" }}>{d.reasoning_record_count}</td>
                <td style={{ padding: "10px 12px" }}>
                  <Button size="sm" onClick={() => { onSelectDesign(d.design_id); onNavigate("intake"); }}>Open</Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
