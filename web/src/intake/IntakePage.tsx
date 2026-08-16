import React, { useState } from "react";
import type { AppView } from "../shell";
import IntakeTextForm from "./IntakeTextForm";
import RequirementsList from "./RequirementsList";
import LLMSettings from "./LLMSettings";
import BusinessContextPanel from "../business/BusinessContextPanel";
import CapabilityGapPanel from "./CapabilityGapPanel";

interface IntakePageProps {
  // null until a design exists -- Intake is always reachable directly (it's
  // where a design starts, per explicit product decision), not gated on one
  // being selected first. IntakeTextForm creates the design on first submit.
  designId: string | null;
  onNavigate: (view: AppView) => void;
  // Bubbles a design created during this Intake session up to the caller
  // (e.g. App.tsx's currentDesignId) so the rest of the app picks it up.
  onDesignCreated?: (designId: string) => void;
}

type Tab = "intake" | "settings";

export default function IntakePage({ designId, onNavigate, onDesignCreated }: IntakePageProps): React.ReactElement {
  const [activeTab, setActiveTab] = useState<Tab>("intake");
  // Set after a successful submit, cleared on the next edit -- IntakeTextForm
  // resets its own fields, so this is just a transient confirmation banner.
  const [justSubmitted, setJustSubmitted] = useState<{ requirementCount: number; capabilityCount: number } | null>(null);

  const TABS: { id: Tab; label: string }[] = [
    { id: "intake", label: "Intake" },
    { id: "settings", label: "⚙ LLM Settings" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "Arial, sans-serif" }}>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Tabs + form */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ display: "flex", gap: 0, borderBottom: "2px solid var(--border)", flexShrink: 0, background: "var(--surface)" }}>
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: "10px 20px", background: "none", border: "none", cursor: "pointer",
                  fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
                  color: activeTab === tab.id ? "var(--accent)" : "var(--ink-3)",
                  borderBottom: activeTab === tab.id ? "2px solid var(--accent)" : "2px solid transparent",
                  marginBottom: -2,
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
            {activeTab === "intake" && (
              <div>
                <IntakeTextForm
                  designId={designId}
                  onDesignCreated={onDesignCreated}
                  onSubmitted={(requirementCount, capabilityCount) =>
                    setJustSubmitted({ requirementCount, capabilityCount })
                  }
                />

                {justSubmitted !== null && (
                  <div className="ui-alert good" style={{ marginTop: 16 }}>
                    ✓ Intake saved — business problem and desired outcome recorded
                    {justSubmitted.requirementCount > 0 &&
                      `, ${justSubmitted.requirementCount} requirement${justSubmitted.requirementCount !== 1 ? "s" : ""} added`}
                    {justSubmitted.capabilityCount > 0 &&
                      `, ${justSubmitted.capabilityCount} business capabilit${justSubmitted.capabilityCount !== 1 ? "ies" : "y"} linked`}
                    .
                  </div>
                )}
              </div>
            )}

            {activeTab === "settings" && <LLMSettings />}
          </div>
        </div>

        {/* Right sidebar: Confirmed Requirements + business context */}
        <div style={{ flex: 1, borderLeft: "1px solid var(--border)", overflowY: "auto", background: "var(--surface-2)" }}>
          {designId ? (
            <>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 14, color: "var(--good)", display: "flex", alignItems: "center", gap: 6 }}>
                <span>✓</span> Confirmed Requirements
              </div>
              <RequirementsList designId={designId} />

              {/* Business context — capabilities and value streams linked to this design (ADP-SPEC-034) */}
              <div style={{ padding: "0 16px 16px" }}>
                <BusinessContextPanel designId={designId} onNavigate={onNavigate} />
                <CapabilityGapPanel designId={designId} />
              </div>
            </>
          ) : (
            <div style={{ padding: 16, fontSize: 13, color: "var(--ink-3)" }}>
              Confirmed requirements and business context appear here once the design starts.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
