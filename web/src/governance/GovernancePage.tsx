import React from "react";
import type { AppView } from "../shell";
import DesignStatusTab from "./DesignStatusTab";
import ComplianceTab from "./ComplianceTab";
import ActivityFeedTab from "./ActivityFeedTab";
import ArchitectureHealthTab from "./ArchitectureHealthTab";
import { Tabs } from "../ui/Tabs";
import { PageHeader } from "../ui/primitives";
import { useHashParam } from "../shell/routing";

type TabId = "status" | "compliance" | "activity" | "health";

const TABS: { id: TabId; label: string }[] = [
  { id: "status", label: "Design Status" },
  // ADP-blp.54: was "Compliance", the same word as the separate Compliance screen
  // (frameworks and controls). This tab lists design validation findings.
  { id: "compliance", label: "Design Validation" },
  { id: "activity", label: "Activity Feed" },
  // 939-governance-architecture-health: pattern conformance + capability findings.
  { id: "health", label: "Architecture Health" },
];

interface GovernancePageProps {
  onNavigate: (view: AppView) => void;
  onSelectDesign: (id: string) => void;
  /** 939: opens an adoption on the Patterns screen. */
  onOpenAdoption?: (id: string) => void;
}

export default function GovernancePage({
  onNavigate,
  onSelectDesign,
  onOpenAdoption,
}: GovernancePageProps): React.ReactElement {
  // ADP-blp.68: the tab is in the URL (?tab=...).
  const [activeTab, setActiveTab] = useHashParam<TabId>(
    "tab",
    ["status", "compliance", "activity", "health"],
    "status",
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <PageHeader
          title="Governance"
          lede="Design status, validation findings, the audit trail and architecture health."
        />

        <Tabs label="Governance report" tabs={TABS} active={activeTab} onChange={setActiveTab} />

        {/* Tab content */}
        {activeTab === "status" && (
          <DesignStatusTab onSelectDesign={onSelectDesign} onNavigate={onNavigate} />
        )}
        {activeTab === "compliance" && (
          <ComplianceTab onSelectDesign={onSelectDesign} onNavigate={onNavigate} />
        )}
        {activeTab === "activity" && <ActivityFeedTab />}
        {activeTab === "health" && (
          <ArchitectureHealthTab onOpenAdoption={onOpenAdoption ?? (() => onNavigate("patterns"))} />
        )}
      </div>
    </div>
  );
}
