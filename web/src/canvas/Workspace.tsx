import React, { useEffect, useState } from "react";
import type { C4Level } from "../types";
import { useDesign, useLayout } from "../api/designs";
import { useC4Theme } from "../api/theme";
import { useWorkspaceStore } from "../store/workspace-store";
import C4Canvas from "./C4Canvas";
import InspectionPanel from "../inspection/InspectionPanel";
import { ConflictNotificationBanner, subscribeConflict } from "./ConflictNotification";

type NavView = "canvas" | "intake" | "recommend";

interface WorkspaceProps {
  designId: string;
  // I1 fix (ADP-SPEC-018): single onNavigate replaces onNavigateToIntake
  onNavigate?: (view: NavView) => void;
}

const LEVELS: { label: string; value: C4Level }[] = [
  { label: "Context", value: "context" },
  { label: "Container", value: "container" },
  { label: "Component", value: "component" },
];

export default function Workspace({ designId, onNavigate }: WorkspaceProps): React.ReactElement {
  const { activeLevel, setActiveLevel, selectedElementId, inspectionPanelOpen, setDesignId, clearSelection } =
    useWorkspaceStore();

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

  // Header is always rendered so Requirements button is accessible even while design loads.
  const header = (
    <div style={{ display: "flex", gap: 0, padding: "8px 16px", background: "#f5f5f5", borderBottom: "1px solid #ddd" }}>
      <span style={{ fontWeight: 600, marginRight: 16, alignSelf: "center" }}>
        {design?.title ?? designId}
      </span>
      {LEVELS.map(({ label, value }) => (
        <button
          key={value}
          onClick={() => setActiveLevel(value)}
          style={{
            padding: "6px 16px",
            background: activeLevel === value ? "#1168BD" : "#fff",
            color: activeLevel === value ? "#fff" : "#333",
            border: "1px solid #ccc",
            cursor: "pointer",
            fontWeight: activeLevel === value ? 600 : 400,
          }}
        >
          {label}
        </button>
      ))}
      {/* Three-view nav — Intake | Recommendations | Canvas (active) */}
      {onNavigate && (
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {(["intake", "recommend"] as NavView[]).map((view) => (
            <button
              key={view}
              onClick={() => onNavigate(view)}
              style={{ padding: "5px 12px", background: "#fff", color: "#1168BD", border: "1px solid #1168BD", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 500 }}
            >
              {view === "intake" ? "Intake" : "Recommendations"}
            </button>
          ))}
        </div>
      )}
    </div>
  );

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "sans-serif" }}>
        {header}
        <div style={{ padding: 32 }}>Loading design...</div>
      </div>
    );
  }

  if (isError || !design) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "sans-serif" }}>
        {header}
        <div style={{ padding: 32, color: "#c0392b" }}>Failed to load design.</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "sans-serif" }}>
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
