import React, { useState } from "react";
import type { Application, ApplicationCreate } from "../api/application";
import { useApplication, useUpdateApplication, useDeleteApplication } from "../api/application";
import ApplicationForm from "./ApplicationForm";
import CapabilityLinksEditor from "./CapabilityLinksEditor";
import TechCapLinkEditor from "./TechCapLinkEditor";
import StageLinkEditor from "./StageLinkEditor";
import DomainIntegrationEditor from "./DomainIntegrationEditor";
import DesignLinkEditor from "./DesignLinkEditor";
import IntegrationList from "./IntegrationList";

const TIME_BADGE: Record<string, { bg: string; text: string }> = {
  Invest: { bg: "#d4edda", text: "#155724" },
  Migrate: { bg: "#fff3cd", text: "#856404" },
  Eliminate: { bg: "#f8d7da", text: "#721c24" },
  Tolerate: { bg: "#e2e3e5", text: "#383d41" },
};

interface Props {
  appId: string;
  allApps: Application[];
  onDeleted: () => void;
}

type Section = "overview" | "capabilities" | "tech-caps" | "stages" | "integrations" | "designs";

export default function ApplicationDetail({ appId, allApps, onDeleted }: Props) {
  const { data: app, isLoading } = useApplication(appId);
  const updateApp = useUpdateApplication(appId);
  const deleteApp = useDeleteApplication();
  const [editing, setEditing] = useState(false);
  const [section, setSection] = useState<Section>("overview");

  if (isLoading) return <div style={{ padding: 24, fontSize: 13, color: "#888" }}>Loading…</div>;
  if (!app) return <div style={{ padding: 24, fontSize: 13, color: "#888" }}>Not found</div>;

  const tc = app.time_classification;
  const colors = tc ? TIME_BADGE[tc] : null;

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
  ];

  const tabStyle = (id: Section): React.CSSProperties => ({
    fontSize: 12,
    padding: "5px 12px",
    background: section === id ? "#1168BD" : "#f0f0f0",
    color: section === id ? "#fff" : "#444",
    border: "none",
    cursor: "pointer",
    borderRadius: 4,
  });

  if (editing) {
    return <ApplicationForm initial={app} onSave={handleSave} onCancel={() => setEditing(false)} saving={updateApp.isPending} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #e0e0e0", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{app.name}</h2>
              {colors && tc && (
                <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 10, background: colors.bg, color: colors.text }}>
                  {tc}
                </span>
              )}
              {app.r_strategy && <span style={{ fontSize: 11, color: "#888" }}>({app.r_strategy})</span>}
            </div>
            {app.vendor && <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{app.vendor}</div>}
            {app.primary_owner && <div style={{ fontSize: 12, color: "#888" }}>Owner: {app.primary_owner}</div>}
            {app.health_score !== null && (
              <div style={{ fontSize: 12, marginTop: 2 }}>
                Health: <span style={{ color: "#555" }}>{"★".repeat(app.health_score)}{"☆".repeat(5 - app.health_score)}</span>
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            <button onClick={() => setEditing(true)} style={{ fontSize: 11, padding: "4px 10px", background: "#f0f0f0", border: "1px solid #ccc", borderRadius: 4, cursor: "pointer" }}>Edit</button>
            <button onClick={handleDelete} style={{ fontSize: 11, padding: "4px 10px", background: "#fde8e8", border: "1px solid #f0a0a0", borderRadius: 4, cursor: "pointer", color: "#c00" }}>Delete</button>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: "flex", gap: 6, padding: "8px 16px", borderBottom: "1px solid #e0e0e0", flexShrink: 0, flexWrap: "wrap" }}>
        {tabs.map(t => <button key={t.id} style={tabStyle(t.id)} onClick={() => setSection(t.id)}>{t.label}</button>)}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: "14px 16px" }}>
        {section === "overview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {app.description && <p style={{ margin: 0, fontSize: 13, color: "#444" }}>{app.description}</p>}
            {app.pace_layer && (
              <div style={{ fontSize: 12 }}>
                <strong>Pace Layer:</strong> {app.pace_layer}
              </div>
            )}
            <div style={{ fontSize: 11, color: "#aaa" }}>
              Created: {new Date(app.created_at).toLocaleDateString()} · Updated: {new Date(app.updated_at).toLocaleDateString()}
            </div>
          </div>
        )}
        {section === "capabilities" && <CapabilityLinksEditor appId={appId} />}
        {section === "tech-caps" && <TechCapLinkEditor appId={appId} />}
        {section === "stages" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <StageLinkEditor appId={appId} />
            <hr style={{ border: "none", borderTop: "1px solid #eee" }} />
            <DomainIntegrationEditor appId={appId} />
          </div>
        )}
        {section === "integrations" && <IntegrationList apps={allApps} filterAppId={appId} />}
        {section === "designs" && <DesignLinkEditor appId={appId} />}
      </div>
    </div>
  );
}
