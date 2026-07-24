import React, { useEffect, useState } from "react";
import type { C4Level } from "../types";
import { useDesign, useLayout } from "../api/designs";
import { useC4Theme } from "../api/theme";
import { getAuthHeader } from "../api/client";
import { useWorkspaceStore } from "../store/workspace-store";
import type { AppView } from "../shell";
import C4Canvas from "./C4Canvas";
import InspectionPanel from "../inspection/InspectionPanel";
import { ConflictNotificationBanner, subscribeConflict } from "./ConflictNotification";

interface WorkspaceProps {
  designId: string;
  onNavigate?: (view: AppView) => void;
}

const LEVELS: { label: string; value: C4Level }[] = [
  { label: "Context", value: "context" },
  { label: "Container", value: "container" },
  { label: "Component", value: "component" },
];

export default function Workspace({ designId }: WorkspaceProps): React.ReactElement {
  const { activeLevel, setActiveLevel, selectedElementId, inspectionPanelOpen, setDesignId, clearSelection } =
    useWorkspaceStore();

  const [calmExporting, setCalmExporting] = useState(false);
  const [calmError, setCalmError] = useState<string | null>(null);

  const handleExportCalm = async () => {
    setCalmExporting(true);
    setCalmError(null);
    try {
      const authHeader = await getAuthHeader();
      const resp = await fetch(`/api/v1/designs/${designId}/export/calm`, { headers: authHeader });
      if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${designId}-calm.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setCalmError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setCalmExporting(false);
    }
  };

  const [conflictDesignId, setConflictDesignId] = useState<string | null>(null);

  useEffect(() => {
    setDesignId(designId);
  }, [designId, setDesignId]);

  useEffect(() => {
    return subscribeConflict((id) => {
      setConflictDesignId(id);
      const timer = setTimeout(() => setConflictDesignId(null), 30_000);
      return () => clearTimeout(timer);
    });
  }, []);

  const { data: design, isLoading, isError } = useDesign(designId);
  const { data: layout } = useLayout(designId, activeLevel);
  const { data: theme } = useC4Theme();

  // Header: NavBar + level-selector toolbar
  const header = (
    <>
      <div style={{ display: "flex", gap: 0, padding: "8px 16px", background: "var(--surface-2)", borderBottom: "1px solid var(--border)" }}>
        <span style={{ fontWeight: 600, marginRight: 16, alignSelf: "center" }}>
          {design?.title ?? designId}
        </span>
        {LEVELS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => setActiveLevel(value)}
            style={{
              padding: "6px 16px",
              background: activeLevel === value ? "var(--accent)" : "var(--surface)",
              color: activeLevel === value ? "var(--surface)" : "var(--ink)",
              border: "1px solid var(--border)",
              cursor: "pointer",
              fontWeight: activeLevel === value ? 600 : 400,
            }}
          >
            {label}
          </button>
        ))}
        <button
          onClick={handleExportCalm}
          disabled={calmExporting}
          title="Export design as CALM JSON (FINOS)"
          style={{ marginLeft: 12, padding: "5px 12px", background: calmExporting ? "var(--border)" : "var(--good)", color: "#fff", border: "none", borderRadius: 4, cursor: calmExporting ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 600 }}
        >
          {calmExporting ? "Exporting..." : "Export CALM"}
        </button>
        {calmError && (
          <div style={{ position: "fixed", bottom: 16, right: 16, background: "var(--crit-wash)", border: "1px solid var(--crit)", borderRadius: 6, padding: "10px 16px", fontSize: 13, color: "var(--crit)", zIndex: 999 }}>
            {calmError}
            <button onClick={() => setCalmError(null)} style={{ marginLeft: 10, background: "none", border: "none", cursor: "pointer", fontSize: 13, color: "var(--crit)" }}>✕</button>
          </div>
        )}
      </div>
    </>
  );

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "sans-serif" }}>
        {header}
        <div style={{ padding: 32 }}>Loading design...</div>
      </div>
    );
  }

  if (isError || !design) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "sans-serif" }}>
        {header}
        <div style={{ padding: 32, color: "var(--crit)" }}>Failed to load design.</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "sans-serif" }}>
      {conflictDesignId && (
        <ConflictNotificationBanner
          designId={conflictDesignId}
          onDismiss={() => setConflictDesignId(null)}
        />
      )}

      {header}

      {/* Main content */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <div style={{ flex: 1, position: "relative" }}>
          <C4Canvas
            design={design}
            layout={layout}
            theme={theme}
            activeLevel={activeLevel}
          />
        </div>

        {inspectionPanelOpen && selectedElementId && (
          <InspectionPanel
            elementId={selectedElementId}
            design={design}
            onClose={clearSelection}
          />
        )}
      </div>
    </div>
  );
}
