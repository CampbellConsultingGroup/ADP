import React, { useState } from "react";
import type { AppView } from "../shell";
import type { DiagramSeed } from "../diagrams/generators";
import CapabilityTree from "./CapabilityTree";
import CapabilityHeatMap from "./CapabilityHeatMap";
import ValueStreamList from "./ValueStreamList";
import ValueStreamDetail from "./ValueStreamDetail";
import DomainList from "./DomainList";
import DomainDetail from "./DomainDetail";

type BusinessTab = "capabilities" | "heatmap" | "value-streams" | "domains";

interface BusinessPageProps {
  onNavigate: (view: AppView) => void;
  designId?: string | null;
  /** ADP-914.7: opens the Diagrams screen pre-filled with a generated diagram
   *  (from a value stream's stages or a capability's subtree). Threaded down
   *  to ValueStreamDetail (US1) and CapabilityTree (US2). */
  onGenerateDiagram?: (seed: DiagramSeed) => void;
}

export default function BusinessPage({ onGenerateDiagram }: BusinessPageProps): React.ReactElement {
  const [tab, setTab] = useState<BusinessTab>("capabilities");
  const [selectedVsId, setSelectedVsId] = useState<string | null>(null);
  const [selectedDomainId, setSelectedDomainId] = useState<string | null>(null);
  // 043-capability-heat-map US3: set when a heat-map cell is clicked; cleared
  // on any manual tab click so a later, unrelated visit to the Capabilities
  // tab doesn't carry a stale highlight forward.
  const [focusCapabilityId, setFocusCapabilityId] = useState<string | null>(null);

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
          {([["capabilities", "Capabilities"], ["heatmap", "Heat Map"], ["value-streams", "Value Streams"], ["domains", "Domains"]] as [BusinessTab, string][]).map(([t, label]) => (
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
          <CapabilityHeatMap
            onDrillThrough={(id) => {
              setFocusCapabilityId(id);
              setTab("capabilities");
            }}
          />
        )}

        {tab === "value-streams" && (
          selectedVsId
            ? <ValueStreamDetail vsId={selectedVsId} onBack={() => setSelectedVsId(null)} onGenerateDiagram={onGenerateDiagram} />
            : <ValueStreamList onSelect={setSelectedVsId} />
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
