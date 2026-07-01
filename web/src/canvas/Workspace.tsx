import React, { useEffect, useState } from "react";
import type { C4Level } from "../types";
import { useDesign, useLayout } from "../api/designs";
import { useC4Theme } from "../api/theme";
import { useWorkspaceStore } from "../store/workspace-store";
import C4Canvas from "./C4Canvas";
import InspectionPanel from "../inspection/InspectionPanel";
import { ConflictNotificationBanner, subscribeConflict } from "./ConflictNotification";

interface WorkspaceProps {
  designId: string;
}

const LEVELS: { label: string; value: C4Level }[] = [
  { label: "Context", value: "context" },
  { label: "Container", value: "container" },
  { label: "Component", value: "component" },
];

export default function Workspace({ designId }: WorkspaceProps): React.ReactElement {
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

  if (isLoading) {
    return <div style={{ padding: 32, fontFamily: "sans-serif" }}>Loading design...</div>;
  }

  if (isError || !design) {
    return <div style={{ padding: 32, fontFamily: "sans-serif", color: "#c0392b" }}>Failed to load design.</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "sans-serif" }}>
      {conflictDesignId && (
        <ConflictNotificationBanner
          designId={conflictDesignId}
          onDismiss={() => setConflictDesignId(null)}
        />
      )}

      {/* Level toggle */}
      <div style={{ display: "flex", gap: 0, padding: "8px 16px", background: "#f5f5f5", borderBottom: "1px solid #ddd" }}>
        <span style={{ fontWeight: 600, marginRight: 16, alignSelf: "center" }}>{design.title}</span>
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
      </div>

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
