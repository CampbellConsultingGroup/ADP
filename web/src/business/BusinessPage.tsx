import React, { useState } from "react";
import { NavBar, type AppView } from "../shell";
import CapabilityTree from "./CapabilityTree";
import ValueStreamList from "./ValueStreamList";
import ValueStreamDetail from "./ValueStreamDetail";
import DomainList from "./DomainList";
import DomainDetail from "./DomainDetail";

type BusinessTab = "capabilities" | "value-streams" | "domains";

interface BusinessPageProps {
  onNavigate: (view: AppView) => void;
  designId?: string | null;
}

export default function BusinessPage({ onNavigate, designId = null }: BusinessPageProps): React.ReactElement {
  const [tab, setTab] = useState<BusinessTab>("capabilities");
  const [selectedVsId, setSelectedVsId] = useState<string | null>(null);
  const [selectedDomainId, setSelectedDomainId] = useState<string | null>(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Arial, sans-serif" }}>
      <NavBar currentView="business" onNavigate={onNavigate} designId={designId} />

      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#111827", margin: "0 0 4px" }}>Business Architecture</h2>
          <p style={{ fontSize: 13, color: "#6B7280", margin: 0 }}>
            Define capabilities and value streams that ground solution architecture in business context.
          </p>
        </div>

        {/* Tab bar */}
        <div style={{ display: "flex", gap: 0, borderBottom: "2px solid #E5E7EB", marginBottom: 20 }}>
          {([["capabilities", "Capabilities"], ["value-streams", "Value Streams"], ["domains", "Domains"]] as [BusinessTab, string][]).map(([t, label]) => (
            <button
              key={t}
              onClick={() => { setTab(t); setSelectedVsId(null); setSelectedDomainId(null); }}
              style={{
                padding: "8px 20px",
                fontSize: 14,
                fontWeight: tab === t ? 600 : 400,
                color: tab === t ? "#1168BD" : "#6B7280",
                background: "transparent",
                border: "none",
                borderBottom: tab === t ? "2px solid #1168BD" : "2px solid transparent",
                cursor: "pointer",
                marginBottom: -2,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === "capabilities" && <CapabilityTree />}

        {tab === "value-streams" && (
          selectedVsId
            ? <ValueStreamDetail vsId={selectedVsId} onBack={() => setSelectedVsId(null)} />
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
