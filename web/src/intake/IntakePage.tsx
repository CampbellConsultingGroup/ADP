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
  const proposals = statusData?.proposals ?? [];
  const noLlm = status === "completed" && proposals.length === 0;

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

              {/* No LLM configured — guide user to structured form */}
              {noLlm && (
                <div style={{ marginTop: 16, padding: 12, background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 6 }}>
                  <p style={{ margin: "0 0 6px", fontWeight: 600, fontSize: 13, color: "#92400E" }}>
                    AI extraction requires an LLM endpoint
                  </p>
                  <p style={{ margin: "0 0 8px", fontSize: 13, color: "#78350F" }}>
                    Set <code style={{ background: "#FDE68A", padding: "1px 4px", borderRadius: 3 }}>ADP_LLM_ENDPOINT</code> and restart the server to enable automatic extraction.
                  </p>
                  <button
                    onClick={() => setActiveTab("form")}
                    style={{ padding: "6px 14px", background: "#166534", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}
                  >
                    Use Structured Form instead →
                  </button>
                </div>
              )}

              {operationId && status === "completed" && proposals.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <ProposalsList proposals={proposals} designId={designId} operationId={operationId} />
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
