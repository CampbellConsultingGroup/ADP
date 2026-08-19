import React, { useState } from "react";
import type { Application, ApplicationCreate } from "../api/application";
import { useApplication, useUpdateApplication, useDeleteApplication } from "../api/application";
import { Button, StatusBadge } from "../ui";
import { TIME_TONE } from "./ApplicationList";
import ApplicationForm from "./ApplicationForm";
import CapabilityLinksEditor from "./CapabilityLinksEditor";
import TechCapLinkEditor from "./TechCapLinkEditor";
import StageLinkEditor from "./StageLinkEditor";
import DomainIntegrationEditor from "./DomainIntegrationEditor";
import DesignLinkEditor from "./DesignLinkEditor";
import IntegrationList from "./IntegrationList";
import RiskPanel from "./RiskPanel";
import CostPanel from "./CostPanel";
import TechFitPanel from "./TechFitPanel";
import InitiativeLinkEditor from "./InitiativeLinkEditor";
import GovernancePanel from "./GovernancePanel";
import QualityPanel from "./QualityPanel";
import ObjectiveLinksPanel from "./ObjectiveLinksPanel";
import HealthAssessmentModal from "./HealthAssessmentModal";
import BusinessValueAssessmentModal from "./BusinessValueAssessmentModal";
import ApplicationComplianceMappings from "./ApplicationComplianceMappings";

interface Props {
  appId: string;
  allApps: Application[];
  onDeleted: () => void;
}

type Section = "overview" | "capabilities" | "tech-caps" | "stages" | "integrations" | "designs" | "risk" | "cost" | "tech-fit" | "initiatives" | "governance" | "quality" | "objectives" | "compliance-mappings";

export default function ApplicationDetail({ appId, allApps, onDeleted }: Props) {
  const { data: app, isLoading } = useApplication(appId);
  const updateApp = useUpdateApplication(appId);
  const deleteApp = useDeleteApplication();
  const [editing, setEditing] = useState(false);
  const [section, setSection] = useState<Section>("overview");
  const [showHealthModal, setShowHealthModal] = useState(false);
  const [showBusinessValueModal, setShowBusinessValueModal] = useState(false);

  if (isLoading) return <div style={{ padding: 24, fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;
  if (!app) return <div style={{ padding: 24, fontSize: 13, color: "var(--ink-3)" }}>Not found</div>;

  const tc = app.time_classification;

  const handleSave = async (data: ApplicationCreate) => {
    await updateApp.mutateAsync(data);
    setEditing(false);
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${app.name}"?`)) return;
    await deleteApp.mutateAsync(appId);
    onDeleted();
  };

  const tabs: { id: Section; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "capabilities", label: "Capabilities" },
    { id: "tech-caps", label: "Tech Caps" },
    { id: "stages", label: "Stages" },
    { id: "integrations", label: "Integrations" },
    { id: "designs", label: "Designs" },
    { id: "risk", label: "Risk & Compliance" },
    { id: "cost", label: "Cost (TCO)" },
    { id: "tech-fit", label: "Technical Fit" },
    { id: "initiatives", label: "Initiatives" },
    { id: "governance", label: "Governance" },
    { id: "quality", label: "Quality" },
    { id: "objectives", label: "Objectives" },
    // Deliberately NOT called "Compliance" -- the "risk" tab above is already labeled
    // "Risk & Compliance" (APM's own risk_compliance_contribution field, ADP-SPEC-038 US3),
    // an unrelated concept. "Regulatory Compliance" disambiguates the two (COMPLY-02).
    { id: "compliance-mappings", label: "Regulatory Compliance" },
  ];

  const tabStyle = (id: Section): React.CSSProperties => ({
    fontSize: 12,
    padding: "6px 13px",
    background: section === id ? "var(--accent)" : "var(--surface-2)",
    color: section === id ? "var(--accent-ink)" : "var(--ink-2)",
    border: "1px solid " + (section === id ? "var(--accent)" : "var(--border)"),
    cursor: "pointer",
    borderRadius: 7,
    fontFamily: "inherit",
    fontWeight: section === id ? 600 : 500,
  });

  if (editing) {
    // The parent panel (ApplicationPage.tsx) has overflow:hidden, and
    // ApplicationForm's own root has no scroll region of its own -- with 17
    // fields plus Save/Cancel, the form's real height exceeds the viewport,
    // clipping the last few fields (Hosting Model, Architecture Pattern,
    // Tech-Debt Flags) with no way to reach them (bug report, 2026-08-15).
    // Wrapping in a scrollable container mirrors every other page's own
    // content-area convention (e.g. BusinessPage.tsx/StrategyPage.tsx).
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ApplicationForm initial={app} onSave={handleSave} onCancel={() => setEditing(false)} saving={updateApp.isPending} />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "var(--ink)" }}>{app.name}</h2>
              {tc && <StatusBadge tone={TIME_TONE[tc]}>{tc}</StatusBadge>}
              {app.r_strategy && <span style={{ fontSize: 11, color: "var(--ink-3)" }}>({app.r_strategy})</span>}
            </div>
            {app.vendor && <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 3 }}>{app.vendor}</div>}
            {app.primary_owner && <div style={{ fontSize: 12, color: "var(--ink-3)" }}>Owner: {app.primary_owner}</div>}
            <div style={{ fontSize: 12, marginTop: 3, color: "var(--ink-2)", display: "flex", alignItems: "center", gap: 8 }}>
              {app.health_score !== null ? (
                <span>
                  Health: <span style={{ color: "var(--warn)" }}>{"★".repeat(app.health_score)}</span>
                  <span style={{ color: "var(--ink-3)" }}>{"☆".repeat(5 - app.health_score)}</span>
                </span>
              ) : (
                <span>Health: — not assessed —</span>
              )}
              <button
                type="button"
                onClick={() => setShowHealthModal(true)}
                style={{
                  fontSize: 11, padding: "1px 8px", borderRadius: 4,
                  border: "1px solid var(--accent)", background: "none", color: "var(--accent)",
                  cursor: "pointer",
                }}
              >
                Assess Health
              </button>
            </div>
            <div style={{ fontSize: 12, marginTop: 3, color: "var(--ink-2)", display: "flex", alignItems: "center", gap: 8 }}>
              {app.business_value !== null ? (
                <span>
                  Business Value: <span style={{ color: "var(--warn)" }}>{"★".repeat(app.business_value)}</span>
                  <span style={{ color: "var(--ink-3)" }}>{"☆".repeat(5 - app.business_value)}</span>
                </span>
              ) : (
                <span>Business Value: — not assessed —</span>
              )}
              <button
                type="button"
                onClick={() => setShowBusinessValueModal(true)}
                style={{
                  fontSize: 11, padding: "1px 8px", borderRadius: 4,
                  border: "1px solid var(--accent)", background: "none", color: "var(--accent)",
                  cursor: "pointer",
                }}
              >
                Assess Business Value
              </button>
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            <Button size="sm" onClick={() => setEditing(true)}>Edit</Button>
            <Button size="sm" variant="danger" onClick={handleDelete}>Delete</Button>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: "flex", gap: 6, padding: "10px 18px", borderBottom: "1px solid var(--border)", flexShrink: 0, flexWrap: "wrap" }}>
        {tabs.map((t) => <button key={t.id} style={tabStyle(t.id)} onClick={() => setSection(t.id)}>{t.label}</button>)}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px 18px" }}>
        {section === "overview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {app.description && <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)", lineHeight: 1.55 }}>{app.description}</p>}
            {app.pace_layer && <div style={{ fontSize: 12, color: "var(--ink-2)" }}><strong style={{ color: "var(--ink)" }}>Pace layer:</strong> {app.pace_layer}</div>}
            <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
              Created {new Date(app.created_at).toLocaleDateString()} · Updated {new Date(app.updated_at).toLocaleDateString()}
            </div>
          </div>
        )}
        {section === "capabilities" && <CapabilityLinksEditor appId={appId} />}
        {section === "tech-caps" && <TechCapLinkEditor appId={appId} />}
        {section === "stages" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <StageLinkEditor appId={appId} />
            <hr style={{ border: "none", borderTop: "1px solid var(--border)", width: "100%" }} />
            <DomainIntegrationEditor appId={appId} />
          </div>
        )}
        {section === "integrations" && <IntegrationList apps={allApps} filterAppId={appId} />}
        {section === "designs" && <DesignLinkEditor appId={appId} />}
        {section === "risk" && <RiskPanel appId={appId} />}
        {section === "cost" && <CostPanel appId={appId} />}
        {section === "tech-fit" && <TechFitPanel app={app} />}
        {section === "initiatives" && <InitiativeLinkEditor appId={appId} />}
        {section === "governance" && <GovernancePanel appId={appId} />}
        {section === "quality" && <QualityPanel appId={appId} />}
        {section === "objectives" && <ObjectiveLinksPanel appId={appId} />}
        {section === "compliance-mappings" && <ApplicationComplianceMappings appId={appId} />}
      </div>

      {showHealthModal && (
        <HealthAssessmentModal appId={appId} onClose={() => setShowHealthModal(false)} />
      )}
      {showBusinessValueModal && (
        <BusinessValueAssessmentModal appId={appId} onClose={() => setShowBusinessValueModal(false)} />
      )}
    </div>
  );
}
