import React, { useState } from "react";
import { useIntakeStatus, type ProposalResponse } from "../api/intake";
import IntakeTextForm from "./IntakeTextForm";
import StructuredForm from "./StructuredForm";
import ProposalsList from "./ProposalsList";
import RequirementsList from "./RequirementsList";
import LLMSettings from "./LLMSettings";

type NavView = "canvas" | "intake" | "recommend";
const NAV_ITEMS: { view: NavView; label: string }[] = [
  { view: "intake", label: "Intake" },
  { view: "recommend", label: "Recommendations" },
  { view: "canvas", label: "Canvas" },
];

interface IntakePageProps {
  designId: string;
  onNavigate: (view: "canvas" | "intake" | "recommend") => void;
}

type Tab = "bulk" | "form" | "settings";

const KIND_COLORS: Record<string, string> = {
  functional: "#1D4ED8",
  non_functional: "#6B21A8",
  constraint: "#C2410C",
  driver: "#166534",
};

/** Rejected Requirements section — renders in the right sidebar below Confirmed Requirements (FR-003, FR-004). */
function RejectedRequirementsSection({ proposals }: { proposals: ProposalResponse[] }) {
  const rejected = proposals.filter((p) => p.status === "rejected");
  if (rejected.length === 0) return null;

  return (
    <div>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #E5E7EB", fontWeight: 600, fontSize: 14, color: "#6B7280", display: "flex", alignItems: "center", gap: 6 }}>
        <span>✕</span> Rejected Requirements ({rejected.length})
      </div>
      <div>
        {rejected.map((p) => (
          <div
            key={p.proposal_id}
            style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "8px 12px", borderBottom: "1px solid #F3F4F6", opacity: 0.6 }}
          >
            <span
              style={{
                flexShrink: 0,
                background: KIND_COLORS[p.kind] ?? "#6B7280",
                color: "#fff",
                fontSize: 10,
                fontWeight: "bold",
                padding: "2px 5px",
                borderRadius: 3,
                marginTop: 2,
              }}
            >
              {p.kind.replace("_", " ")}
            </span>
            <span style={{ fontSize: 12, color: "#6B7280", textDecoration: "line-through" }}>
              {p.draft_statement}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function IntakePage({ designId, onNavigate }: IntakePageProps): React.ReactElement {
  const [activeTab, setActiveTab] = useState<Tab>("bulk");
  const [operationId, setOperationId] = useState<string | null>(null);
  const { data: statusData } = useIntakeStatus(designId, operationId);

  const status = statusData?.status;
  const allProposals = statusData?.proposals ?? [];
  // Only show pending proposals in the review panel (FR-002); confirmed/rejected are removed
  const pendingProposals = allProposals.filter((p) => p.status === "pending");
  const noLlm = status === "completed" && allProposals.length === 0;

  const TABS: { id: Tab; label: string }[] = [
    { id: "bulk", label: "Bulk Text" },
    { id: "form", label: "Structured Form" },
    { id: "settings", label: "⚙ LLM Settings" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Arial, sans-serif" }}>
      {/* Header */}
      {/* Three-view nav header (I1 fix: uses onNavigate not onBack) */}
      <div style={{ display: "flex", alignItems: "center", gap: 0, padding: "0 16px", background: "#1168BD", color: "#fff", flexShrink: 0 }}>
        <span style={{ fontWeight: 700, fontSize: 15, marginRight: 20, padding: "12px 0" }}>ADP</span>
        {NAV_ITEMS.map(({ view, label }) => (
          <button
            key={view}
            onClick={() => onNavigate(view)}
            style={{
              padding: "12px 18px",
              background: view === "intake" ? "rgba(255,255,255,0.2)" : "transparent",
              color: "#fff",
              border: "none",
              borderBottom: view === "intake" ? "3px solid #fff" : "3px solid transparent",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: view === "intake" ? 600 : 400,
            }}
          >
            {label}
          </button>
        ))}
        <span style={{ fontSize: 13, opacity: 0.7, marginLeft: "auto", padding: "12px 0" }}>{designId}</span>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Tabs + extraction content */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ display: "flex", gap: 0, borderBottom: "2px solid #E5E7EB", flexShrink: 0, background: "#fff" }}>
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: "10px 20px", background: "none", border: "none", cursor: "pointer",
                  fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
                  color: activeTab === tab.id ? "#1168BD" : "#6B7280",
                  borderBottom: activeTab === tab.id ? "2px solid #1168BD" : "2px solid transparent",
                  marginBottom: -2,
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
            {activeTab === "bulk" && (
              <div>
                <IntakeTextForm designId={designId} onOperationCreated={setOperationId} />

                {operationId && status === "running" && (
                  <div style={{ marginTop: 16, color: "#1168BD", fontSize: 13 }}>⏳ Extracting requirements...</div>
                )}
                {operationId && status === "failed" && (
                  <div style={{ marginTop: 16, padding: 10, background: "#FEE2E2", borderRadius: 4, color: "#B91C1C", fontSize: 13 }}>
                    Extraction failed: {statusData?.error_description ?? "Unknown error"}. Check ⚙ LLM Settings.
                  </div>
                )}
                {noLlm && (
                  <div style={{ marginTop: 16, padding: 12, background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 6 }}>
                    <p style={{ margin: "0 0 6px", fontWeight: 600, fontSize: 13, color: "#92400E" }}>No requirements extracted</p>
                    <p style={{ margin: "0 0 8px", fontSize: 13, color: "#78350F" }}>
                      Make sure <code style={{ background: "#FDE68A", padding: "1px 4px", borderRadius: 3 }}>ADP_LLM_API_KEY</code> is set or use the Structured Form.
                    </p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button onClick={() => setActiveTab("settings")} style={{ padding: "6px 14px", background: "#92400E", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>⚙ LLM Settings</button>
                      <button onClick={() => setActiveTab("form")} style={{ padding: "6px 14px", background: "#166534", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>Use Structured Form →</button>
                    </div>
                  </div>
                )}

                {/* Pending proposals to review — confirmed/rejected are removed (FR-002, FR-003) */}
                {operationId && status === "completed" && pendingProposals.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <ProposalsList proposals={pendingProposals} designId={designId} operationId={operationId} />
                  </div>
                )}

                {/* Show empty state when all proposals have been actioned */}
                {operationId && status === "completed" && allProposals.length > 0 && pendingProposals.length === 0 && (
                  <div style={{ marginTop: 16, padding: 12, background: "#F0FDF4", border: "1px solid #BBF7D0", borderRadius: 6, fontSize: 13, color: "#166534" }}>
                    ✓ All proposals have been reviewed. See the sidebar for results.
                  </div>
                )}
              </div>
            )}

            {activeTab === "form" && <StructuredForm designId={designId} />}
            {activeTab === "settings" && <LLMSettings />}
          </div>
        </div>

        {/* Right sidebar: Confirmed then Rejected (FR-003, FR-004) */}
        <div style={{ flex: 1, borderLeft: "1px solid #E5E7EB", overflowY: "auto", background: "#FAFAFA" }}>
          {/* Confirmed Requirements */}
          <div style={{ padding: "12px 16px", borderBottom: "1px solid #E5E7EB", fontWeight: 600, fontSize: 14, color: "#166534", display: "flex", alignItems: "center", gap: 6 }}>
            <span>✓</span> Confirmed Requirements
          </div>
          <RequirementsList designId={designId} />

          {/* Rejected Requirements — below confirmed (FR-003) */}
          <RejectedRequirementsSection proposals={allProposals} />
        </div>
      </div>
    </div>
  );
}
