import React, { useState } from "react";
import { useIntakeStatus } from "../api/intake";
import IntakeTextForm from "./IntakeTextForm";
import StructuredForm from "./StructuredForm";
import ProposalsList from "./ProposalsList";
import RequirementsList from "./RequirementsList";

interface IntakePageProps {
  designId: string;
  onBack: () => void;
}

export default function IntakePage({ designId, onBack }: IntakePageProps): React.ReactElement {
  const [activeTab, setActiveTab] = useState<"bulk" | "form">("bulk");
  const [operationId, setOperationId] = useState<string | null>(null);
  const { data: statusData } = useIntakeStatus(designId, operationId);

  const status = statusData?.status;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Arial, sans-serif" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "10px 16px", background: "#f5f5f5", borderBottom: "1px solid #ddd" }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: "#1168BD", fontSize: 14 }}>← Back to Canvas</button>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Requirements Intake</h2>
        <span style={{ fontSize: 13, color: "#888" }}>{designId}</span>
      </div>

      {/* Main content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Input + Proposals */}
        <div style={{ flex: 2, padding: 16, overflowY: "auto" }}>
          {/* Tabs */}
          <div style={{ display: "flex", gap: 0, marginBottom: 16, borderBottom: "2px solid #e0e0e0" }}>
            {(["bulk", "form"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: "8px 20px", background: "none", border: "none", cursor: "pointer",
                  fontSize: 14, fontWeight: activeTab === tab ? 600 : 400,
                  color: activeTab === tab ? "#1168BD" : "#666",
                  borderBottom: activeTab === tab ? "2px solid #1168BD" : "2px solid transparent",
                  marginBottom: -2,
                }}
              >
                {tab === "bulk" ? "Bulk Text" : "Structured Form"}
              </button>
            ))}
          </div>

          {activeTab === "bulk" ? (
            <div>
              <IntakeTextForm designId={designId} onOperationCreated={setOperationId} />

              {/* Extraction status */}
              {operationId && status === "running" && (
                <div style={{ marginTop: 16, color: "#1168BD", fontSize: 13 }}>⏳ Extracting requirements...</div>
              )}
              {operationId && status === "failed" && (
                <div style={{ marginTop: 16, padding: 10, background: "#FEE2E2", borderRadius: 4, color: "#c0392b", fontSize: 13 }}>
                  Extraction failed: {statusData?.error_description ?? "Unknown error"}. Please try again.
                </div>
              )}
              {operationId && status === "completed" && (
                <div style={{ marginTop: 16 }}>
                  <ProposalsList
                    proposals={statusData?.proposals ?? []}
                    designId={designId}
                    operationId={operationId}
                  />
                </div>
              )}
            </div>
          ) : (
            <StructuredForm designId={designId} />
          )}
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
