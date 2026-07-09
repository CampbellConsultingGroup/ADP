import React, { useState } from "react";
import { useGovernanceStatus, type DesignGovernanceRecord } from "../api/governance";
import type { AppView } from "../shell";

const LIFECYCLE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  draft:          { bg: "#F3F4F6", text: "#374151", label: "Draft" },
  proposed:       { bg: "#DBEAFE", text: "#1E40AF", label: "Proposed" },
  current:        { bg: "#D1FAE5", text: "#065F46", label: "Current" },
  deprecated:     { bg: "#FEF3C7", text: "#92400E", label: "Deprecated" },
  decommissioned: { bg: "#FEE2E2", text: "#991B1B", label: "Decommissioned" },
};

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
      style={{ padding: "8px 12px", textAlign: "left", cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", fontSize: 13, fontWeight: 600, color: "#374151", borderBottom: "2px solid #E5E7EB" }}
    >
      {label} {sortKey === col ? (sortAsc ? "↑" : "↓") : ""}
    </th>
  );

  if (isLoading) {
    return (
      <div>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{ height: 48, backgroundColor: "#F3F4F6", borderRadius: 6, marginBottom: 6, animation: "pulse 1.5s infinite" }} />
        ))}
      </div>
    );
  }

  if (sorted.length === 0) {
    return <p style={{ color: "#6B7280", fontSize: 14 }}>No designs found.</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ backgroundColor: "#F9FAFB" }}>
            <SortBtn col="title" label="Design" />
            <SortBtn col="last_activity" label="Last Activity" />
            <SortBtn col="audit_count" label="Activity Count" />
            <SortBtn col="accepted_recommendations" label="Accepted Recs" />
            <SortBtn col="reasoning_record_count" label="Reasoning Records" />
            <th style={{ padding: "8px 12px", borderBottom: "2px solid #E5E7EB" }} />
          </tr>
        </thead>
        <tbody>
          {sorted.map((d) => {
            const lc = LIFECYCLE_COLORS[d.lifecycle_status] ?? LIFECYCLE_COLORS.draft;
            return (
              <tr
                key={d.design_id}
                style={{ borderBottom: "1px solid #F3F4F6" }}
              >
                <td style={{ padding: "10px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ padding: "2px 7px", borderRadius: 10, backgroundColor: lc.bg, color: lc.text, fontSize: 11, fontWeight: 600 }}>
                      {lc.label}
                    </span>
                    <span style={{ fontWeight: 500, color: "#111827" }}>{d.title}</span>
                  </div>
                </td>
                <td style={{ padding: "10px 12px", color: "#6B7280" }}>
                  {d.last_activity
                    ? new Date(d.last_activity).toLocaleDateString()
                    : "—"}
                </td>
                <td style={{ padding: "10px 12px", textAlign: "center" }}>{d.audit_count}</td>
                <td style={{ padding: "10px 12px", textAlign: "center" }}>{d.accepted_recommendations}</td>
                <td style={{ padding: "10px 12px", textAlign: "center" }}>{d.reasoning_record_count}</td>
                <td style={{ padding: "10px 12px" }}>
                  <button
                    onClick={() => { onSelectDesign(d.design_id); onNavigate("intake"); }}
                    style={{ padding: "4px 10px", borderRadius: 6, border: "1px solid #D1D5DB", backgroundColor: "#fff", fontSize: 12, cursor: "pointer", color: "#374151" }}
                  >
                    Open
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
