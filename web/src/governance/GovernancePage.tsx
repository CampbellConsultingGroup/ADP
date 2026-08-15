import React, { useState } from "react";
import type { AppView } from "../shell";
import { Button } from "../ui";
import DesignStatusTab from "./DesignStatusTab";
import ComplianceTab from "./ComplianceTab";
import ActivityFeedTab from "./ActivityFeedTab";

type TabId = "status" | "compliance" | "activity";

const TABS: { id: TabId; label: string }[] = [
  { id: "status", label: "Design Status" },
  { id: "compliance", label: "Compliance" },
  { id: "activity", label: "Activity Feed" },
];

interface GovernancePageProps {
  onNavigate: (view: AppView) => void;
  onSelectDesign: (id: string) => void;
}

export default function GovernancePage({
  onNavigate,
  onSelectDesign,
}: GovernancePageProps): React.ReactElement {
  const [activeTab, setActiveTab] = useState<TabId>("status");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", marginBottom: 20 }}>
          <Button size="sm" onClick={() => onNavigate("portfolio")} style={{ marginRight: 16 }}>← APM</Button>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--ink)" }}>
            Governance Report
          </h2>
        </div>

        {/* Tab bar */}
        <div style={{ display: "flex", borderBottom: "2px solid var(--border)", marginBottom: 20 }}>
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              style={{
                padding: "8px 20px",
                border: "none",
                borderBottom: activeTab === id ? "2px solid var(--accent)" : "2px solid transparent",
                backgroundColor: "transparent",
                color: activeTab === id ? "var(--accent)" : "var(--ink-3)",
                fontSize: 14,
                fontWeight: activeTab === id ? 600 : 400,
                cursor: "pointer",
                marginBottom: -2,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "status" && (
          <DesignStatusTab onSelectDesign={onSelectDesign} onNavigate={onNavigate} />
        )}
        {activeTab === "compliance" && (
          <ComplianceTab onSelectDesign={onSelectDesign} onNavigate={onNavigate} />
        )}
        {activeTab === "activity" && <ActivityFeedTab />}
      </div>
    </div>
  );
}
