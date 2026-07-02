import React, { useState } from "react";
import { useIntakeStatus } from "../api/intake";
import IntakeTextForm from "./IntakeTextForm";
import StructuredForm from "./StructuredForm";
import ProposalsList from "./ProposalsList";
import RequirementsList from "./RequirementsList";
import LLMSettings from "./LLMSettings";

interface IntakePageProps {
  designId: string;
  onBack: () => void;
}

type Tab = "bulk" | "form" | "settings";

export default function IntakePage({ designId, onBack }: IntakePageProps): React.ReactElement {
  const [activeTab, setActiveTab] = useState<Tab>("bulk");
  const [operationId, setOperationId] = useState<string | null>(null);
  const { data: statusData } = useIntakeStatus(designId, operationId);

  const status = statusData?.status;
  const proposals = statusData?.proposals ?? [];
  const noLlm = status === "completed" && proposals.length === 0;

  const TABS: { id: Tab; label: string }[] = [
    { id: "bulk", label: "Bulk Text" },
    { id: "form", label: "Structured Form" },
    { id: "settings", label: "⚙ LLM Settings" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Arial, sans-serif" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "10px 16px", background: "#f5f5f5", borderBottom: "1px solid #ddd" }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: "#1168BD", fontSize: 14 }}>← Back to Canvas</button>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Requirements Intake</h2>
        <span style={{ fontSize: 13, color: "#888" }}>{designId}</span>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Tabs + content */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Tab bar */}
          <div style={{ display: "flex", gap: 0, borderBottom: "2px solid #e0e0e0", flexShrink: 0 }}>
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: "10px 20px", background: "none", border: "none", cursor: "pointer",
                  fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
                  color: activeTab === tab.id ? "#1168BD" : "#666",
                  borderBottom: activeTab === tab.id ? "2px solid #1168BD" : "2px solid transparent",
                  marginBottom: -2,
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
            {activeTab === "bulk" && (
              <div>
                <IntakeTextForm designId={designId} onOperationCreated={setOperationId} />

                {operationId && status === "running" && (
                  <div style={{ marginTop: 16, color: "#1168BD", fontSize: 13 }}>⏳ Extracting requirements...</div>
                )}
                {operationId && status === "failed" && (
                  <div style={{ marginTop: 16, padding: 10, background: "#FEE2E2", borderRadius: 4, color: "#c0392b", fontSize: 13 }}>
                    Extraction failed: {statusData?.error_description ?? "Unknown error"}. Check LLM Settings.
                  </div>
                )}
                {noLlm && (
                  <div style={{ marginTop: 16, padding: 12, background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 6 }}>
                    <p style={{ margin: "0 0 6px", fontWeight: 600, fontSize: 13, color: "#92400E" }}>No requirements extracted</p>
                    <p style={{ margin: "0 0 8px", fontSize: 13, color: "#78350F" }}>
                      Make sure <code style={{ background: "#FDE68A", padding: "1px 4px", borderRadius: 3 }}>ADP_LLM_API_KEY</code> is set (see ⚙ LLM Settings tab) or use the Structured Form.
                    </p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button onClick={() => setActiveTab("settings")} style={{ padding: "6px 14px", background: "#92400E", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                        ⚙ LLM Settings
                      </button>
                      <button onClick={() => setActiveTab("form")} style={{ padding: "6px 14px", background: "#166534", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                        Use Structured Form →
                      </button>
                    </div>
                  </div>
                )}
                {operationId && status === "completed" && proposals.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <ProposalsList proposals={proposals} designId={designId} operationId={operationId} />
                  </div>
                )}
              </div>
            )}

            {activeTab === "form" && <StructuredForm designId={designId} />}
            {activeTab === "settings" && <LLMSettings />}
          </div>
        </div>

        {/* Right: Requirements summary */}
        <div style={{ flex: 1, borderLeft: "1px solid #e0e0e0", overflowY: "auto" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid #eee", fontWeight: 600, fontSize: 14 }}>
            Confirmed Requirements
          </div>
          <RequirementsList designId={designId} />
        </div>
      </div>
    </div>
  );
}
