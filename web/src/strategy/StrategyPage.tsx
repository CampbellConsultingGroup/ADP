import React, { useState } from "react";
import ThemeList from "./ThemeList";
import ObjectiveList from "./ObjectiveList";
import ObjectiveDetail from "./ObjectiveDetail";
import InitiativeList from "./InitiativeList";
import StrategyHeatMap from "./StrategyHeatMap";

type StrategyTab = "themes" | "objectives" | "initiatives" | "heatmap";

export default function StrategyPage(): React.ReactElement {
  const [tab, setTab] = useState<StrategyTab>("themes");
  const [selectedObjectiveId, setSelectedObjectiveId] = useState<string | null>(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "Arial, sans-serif" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink)", margin: "0 0 4px" }}>Strategy</h2>
          <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>
            Capture strategic objectives as structured entities, traceable to real capabilities and value streams.
          </p>
        </div>

        {/* Tab bar */}
        <div style={{ display: "flex", gap: 0, borderBottom: "2px solid var(--border)", marginBottom: 20 }}>
          {(
            [
              ["themes", "Themes"],
              ["objectives", "Objectives"],
              ["initiatives", "Initiatives"],
              ["heatmap", "Heat Map"],
            ] as [StrategyTab, string][]
          ).map(([t, label]) => (
            <button
              key={t}
              onClick={() => { setTab(t); setSelectedObjectiveId(null); }}
              style={{
                padding: "8px 20px",
                fontSize: 14,
                fontWeight: tab === t ? 600 : 400,
                color: tab === t ? "var(--accent)" : "var(--ink-3)",
                background: "transparent",
                border: "none",
                borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent",
                cursor: "pointer",
                marginBottom: -2,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === "objectives" && (
          selectedObjectiveId
            ? <ObjectiveDetail objectiveId={selectedObjectiveId} onBack={() => setSelectedObjectiveId(null)} />
            : <ObjectiveList onSelect={setSelectedObjectiveId} />
        )}

        {tab === "themes" && <ThemeList />}

        {tab === "initiatives" && <InitiativeList />}

        {tab === "heatmap" && <StrategyHeatMap />}
      </div>
    </div>
  );
}
