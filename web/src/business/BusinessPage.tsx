import React, { useState } from "react";
import type { AppView } from "../shell";
import type { DiagramSeed } from "../diagrams/generators";
import CapabilityTree from "./CapabilityTree";
import CapabilityHeatMap from "./CapabilityHeatMap";
import ValueStreamList from "./ValueStreamList";
import ValueStreamDetail from "./ValueStreamDetail";
import DomainList from "./DomainList";
import DomainDetail from "./DomainDetail";
import OrganizationTab, { useCanWriteBusiness } from "./OrganizationTab";
import RegionalHeatMap from "./RegionalHeatMap";

type BusinessTab = "capabilities" | "heatmap" | "value-streams" | "domains" | "organization";

interface BusinessPageProps {
  onNavigate: (view: AppView) => void;
  designId?: string | null;
  /** ADP-914.7: opens the Diagrams screen pre-filled with a generated diagram
   *  (from a value stream's stages or a capability's subtree). Threaded down
   *  to ValueStreamDetail (US1) and CapabilityTree (US2). */
  onGenerateDiagram?: (seed: DiagramSeed) => void;
  /** 938-capability-model-analysis: opened from an analysis list elsewhere -- start on the
   *  Capabilities tab, scrolled to and highlighting this capability. */
  initialFocusCapabilityId?: string | null;
}

export default function BusinessPage({ onGenerateDiagram, initialFocusCapabilityId = null }: BusinessPageProps): React.ReactElement {
  const [tab, setTab] = useState<BusinessTab>(initialFocusCapabilityId ? "capabilities" : "domains");
  const [selectedVsId, setSelectedVsId] = useState<string | null>(null);
  const [selectedDomainId, setSelectedDomainId] = useState<string | null>(null);
  // 043-capability-heat-map US3: set when a heat-map cell is clicked; cleared
  // on any manual tab click so a later, unrelated visit to the Capabilities
  // tab doesn't carry a stale highlight forward.
  const [focusCapabilityId, setFocusCapabilityId] = useState<string | null>(initialFocusCapabilityId);
  // 942-regional-assessments: the Heat Map tab's view and the regional columns, kept here so the
  // choice survives switching tabs for the session (null = the server's default, the regions).
  const [heatmapView, setHeatmapView] = useState<"capabilities" | "regional">("capabilities");
  const [regionalColumns, setRegionalColumns] = useState<string[] | null>(null);
  const canWriteBusiness = useCanWriteBusiness();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "Arial, sans-serif" }}>

      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink)", margin: "0 0 4px" }}>Business Architecture</h2>
          <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>
            Define capabilities and value streams that ground solution architecture in business context.
          </p>
        </div>

        {/* Tab bar */}
        <div style={{ display: "flex", gap: 0, borderBottom: "2px solid var(--border)", marginBottom: 20 }}>
          {([["domains", "Domains"], ["capabilities", "Capabilities"], ["value-streams", "Value Streams"], ["heatmap", "Heat Map"], ["organization", "Organization"]] as [BusinessTab, string][]).map(([t, label]) => (
            <button
              key={t}
              onClick={() => { setTab(t); setSelectedVsId(null); setSelectedDomainId(null); setFocusCapabilityId(null); }}
              style={{
                padding: "8px 20px",
                fontSize: 14,
                fontWeight: tab === t ? 600 : 400,
                color: tab === t ? "var(--accent)" : "var(--ink-3)",
                background: "transparent",
                border: "none",
                borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent",
                cursor: "pointer",
                marginBottom: -2,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === "capabilities" && (
          <CapabilityTree onGenerateDiagram={onGenerateDiagram} focusCapabilityId={focusCapabilityId} />
        )}

        {tab === "heatmap" && (
          <>
            <div role="tablist" aria-label="Heat map view" style={{ display: "flex", gap: 6, marginBottom: 12 }}>
              {([["capabilities", "Capabilities"], ["regional", "Regional"]] as const).map(([v, text]) => (
                <button
                  key={v}
                  role="tab"
                  aria-selected={heatmapView === v}
                  onClick={() => setHeatmapView(v)}
                  style={{
                    fontSize: 12,
                    padding: "3px 10px",
                    border: "1px solid var(--border)",
                    borderRadius: 4,
                    background: heatmapView === v ? "var(--accent)" : "var(--surface)",
                    color: heatmapView === v ? "#fff" : "var(--ink-2)",
                    cursor: "pointer",
                  }}
                >
                  {text}
                </button>
              ))}
            </div>
            {heatmapView === "capabilities" ? (
              <CapabilityHeatMap
                onDrillThrough={(id) => {
                  setFocusCapabilityId(id);
                  setTab("capabilities");
                }}
              />
            ) : (
              <RegionalHeatMap
                columns={regionalColumns}
                onColumnsChange={setRegionalColumns}
                canWrite={canWriteBusiness}
                onOpenCapability={(id) => {
                  setFocusCapabilityId(id);
                  setTab("capabilities");
                }}
              />
            )}
          </>
        )}

        {tab === "value-streams" && (
          selectedVsId
            ? <ValueStreamDetail vsId={selectedVsId} onBack={() => setSelectedVsId(null)} onGenerateDiagram={onGenerateDiagram} />
            : <ValueStreamList onSelect={setSelectedVsId} />
        )}

        {/* 940-org-units-geography (ADP-55k.1) */}
        {tab === "organization" && (
          <OrganizationTab
            onOpenCapability={(id) => {
              setTab("capabilities");
              setFocusCapabilityId(id);
            }}
          />
        )}

        {tab === "domains" && (
          selectedDomainId
            ? <DomainDetail domainId={selectedDomainId} onBack={() => setSelectedDomainId(null)} />
            : <DomainList onSelect={setSelectedDomainId} />
        )}
      </div>
    </div>
  );
}
