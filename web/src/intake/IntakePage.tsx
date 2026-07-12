import React, { useState } from "react";
import { useIntakeStatus, type ProposalResponse } from "../api/intake";
import type { AppView } from "../shell";
import IntakeTextForm from "./IntakeTextForm";
import StructuredForm from "./StructuredForm";
import ProposalsList from "./ProposalsList";
import RequirementsList from "./RequirementsList";
import LLMSettings from "./LLMSettings";
import BusinessContextPanel from "../business/BusinessContextPanel";
import { Button } from "../ui";

interface IntakePageProps {
  designId: string;
  onNavigate: (view: AppView) => void;
}

type Tab = "bulk" | "form" | "settings";

const KIND_COLORS: Record<string, string> = {
  functional: "var(--accent)",
  non_functional: "var(--biz)",
  constraint: "var(--tec)",
  driver: "var(--good)",
};

/** Rejected Requirements section — renders in the right sidebar below Confirmed Requirements (FR-003, FR-004). */
function RejectedRequirementsSection({ proposals }: { proposals: ProposalResponse[] }) {
  const rejected = proposals.filter((p) => p.status === "rejected");
  if (rejected.length === 0) return null;

  return (
    <div>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 14, color: "var(--ink-3)", display: "flex", alignItems: "center", gap: 6 }}>
        <span>✕</span> Rejected Requirements ({rejected.length})
      </div>
      <div>
        {rejected.map((p) => (
          <div
            key={p.proposal_id}
            style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "8px 12px", borderBottom: "1px solid var(--surface-2)", opacity: 0.6 }}
          >
            <span
              style={{
                flexShrink: 0,
                background: KIND_COLORS[p.kind] ?? "var(--ink-3)",
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
            <span style={{ fontSize: 12, color: "var(--ink-3)", textDecoration: "line-through" }}>
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
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "Arial, sans-serif" }}>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Tabs + extraction content */}
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
            {activeTab === "bulk" && (
              <div>
                <IntakeTextForm designId={designId} onOperationCreated={setOperationId} />

                {operationId && status === "running" && (
                  <div style={{ marginTop: 16, color: "var(--accent)", fontSize: 13 }}>⏳ Extracting requirements...</div>
                )}
                {operationId && status === "failed" && (
                  <div className="ui-alert crit" style={{ marginTop: 16 }}>
                    Extraction failed: {statusData?.error_description ?? "Unknown error"}. Check ⚙ LLM Settings.
                  </div>
                )}
                {noLlm && (
                  <div className="ui-alert warn" style={{ marginTop: 16 }}>
                    <p style={{ margin: "0 0 6px", fontWeight: 600, fontSize: 13 }}>No requirements extracted</p>
                    <p style={{ margin: "0 0 10px", fontSize: 13 }}>
                      Make sure <code style={{ background: "var(--warn-wash)", padding: "1px 4px", borderRadius: 3, fontFamily: "var(--mono)" }}>ADP_LLM_API_KEY</code> is set or use the Structured Form.
                    </p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <Button size="sm" onClick={() => setActiveTab("settings")}>⚙ LLM Settings</Button>
                      <Button size="sm" variant="primary" onClick={() => setActiveTab("form")}>Use Structured Form →</Button>
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
                  <div className="ui-alert good" style={{ marginTop: 16 }}>
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
        <div style={{ flex: 1, borderLeft: "1px solid var(--border)", overflowY: "auto", background: "var(--surface-2)" }}>
          {/* Confirmed Requirements */}
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 14, color: "var(--good)", display: "flex", alignItems: "center", gap: 6 }}>
            <span>✓</span> Confirmed Requirements
          </div>
          <RequirementsList designId={designId} />

          {/* Rejected Requirements — below confirmed (FR-003) */}
          <RejectedRequirementsSection proposals={allProposals} />

          {/* Business context — capabilities and value streams linked to this design (ADP-SPEC-034) */}
          <div style={{ padding: "0 16px 16px" }}>
            <BusinessContextPanel designId={designId} onNavigate={onNavigate} />
          </div>
        </div>
      </div>
    </div>
  );
}
