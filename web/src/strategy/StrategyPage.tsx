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
  // Cross-entity navigation (theme <-> objective <-> initiative), added in
  // direct response to "we need a method of navigation on the strategy
  // screens to allow navigation between themes - objectives and
  // initiatives." Mirrors BusinessPage.tsx's own focusCapabilityId
  // precedent: `focusThemeId`/`focusInitiativeId` drive a scroll-and-
  // highlight on their flat list (neither Theme nor Initiative has a
  // dedicated detail view -- research.md Decision 3 from
  // 043-capability-heat-map). `filterThemeId` narrows the Objectives list
  // to one theme's objectives -- there is no single row to highlight when
  // "jumping to" a theme's objectives, since a theme commonly has several.
  const [focusThemeId, setFocusThemeId] = useState<string | null>(null);
  const [focusInitiativeId, setFocusInitiativeId] = useState<string | null>(null);
  const [filterThemeId, setFilterThemeId] = useState<string | null>(null);

  function goToTab(t: StrategyTab) {
    setTab(t);
    setSelectedObjectiveId(null);
    setFocusThemeId(null);
    setFocusInitiativeId(null);
    setFilterThemeId(null);
  }

  function goToTheme(themeId: string) {
    setFocusThemeId(themeId);
    setFocusInitiativeId(null);
    setFilterThemeId(null);
    setSelectedObjectiveId(null);
    setTab("themes");
  }

  function goToThemeObjectives(themeId: string) {
    setFilterThemeId(themeId);
    setFocusThemeId(null);
    setFocusInitiativeId(null);
    setSelectedObjectiveId(null);
    setTab("objectives");
  }

  function goToObjective(objectiveId: string) {
    setSelectedObjectiveId(objectiveId);
    setFocusThemeId(null);
    setFocusInitiativeId(null);
    setTab("objectives");
  }

  function goToInitiative(initiativeId: string) {
    setFocusInitiativeId(initiativeId);
    setFocusThemeId(null);
    setFilterThemeId(null);
    setSelectedObjectiveId(null);
    setTab("initiatives");
  }

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
              onClick={() => goToTab(t)}
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
            ? (
              <ObjectiveDetail
                objectiveId={selectedObjectiveId}
                onBack={() => setSelectedObjectiveId(null)}
                onNavigateToTheme={goToTheme}
                onNavigateToInitiative={goToInitiative}
              />
            )
            : (
              <ObjectiveList
                onSelect={setSelectedObjectiveId}
                filterThemeId={filterThemeId}
                onClearThemeFilter={() => setFilterThemeId(null)}
              />
            )
        )}

        {tab === "themes" && <ThemeList focusThemeId={focusThemeId} onNavigateToObjectives={goToThemeObjectives} />}

        {tab === "initiatives" && <InitiativeList focusInitiativeId={focusInitiativeId} onNavigateToObjective={goToObjective} />}

        {tab === "heatmap" && <StrategyHeatMap />}
      </div>
    </div>
  );
}
