import React, { useState } from "react";
import ThemeList from "./ThemeList";
import ObjectiveList from "./ObjectiveList";
import ObjectiveDetail from "./ObjectiveDetail";
import InitiativeList from "./InitiativeList";
import StrategyHeatMap from "./StrategyHeatMap";
import { Tabs } from "../ui/Tabs";
import { PageHeader } from "../ui/primitives";
import { useHashParam } from "../shell/routing";

type StrategyTab = "themes" | "objectives" | "initiatives" | "heatmap";

const STRATEGY_TABS: { id: StrategyTab; label: string }[] = [
  { id: "themes", label: "Themes" },
  { id: "objectives", label: "Objectives" },
  { id: "initiatives", label: "Initiatives" },
  { id: "heatmap", label: "Heat Map" },
];

export default function StrategyPage(): React.ReactElement {
  // ADP-blp.68: the tab is in the URL (?tab=...).
  const [tab, setTab] = useHashParam<StrategyTab>(
    "tab",
    ["themes", "objectives", "initiatives", "heatmap"],
    "themes",
  );
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
  // ADP-q3j: when an objective was opened from an initiative, its Back control
  // returns to that initiative instead of the objectives list.
  const [objectiveFromInitiativeId, setObjectiveFromInitiativeId] = useState<string | null>(null);

  function goToTab(t: StrategyTab) {
    setTab(t);
    setSelectedObjectiveId(null);
    setFocusThemeId(null);
    setFocusInitiativeId(null);
    setFilterThemeId(null);
    setObjectiveFromInitiativeId(null);
  }

  function goToTheme(themeId: string) {
    setObjectiveFromInitiativeId(null);
    setFocusThemeId(themeId);
    setFocusInitiativeId(null);
    setFilterThemeId(null);
    setSelectedObjectiveId(null);
    setTab("themes");
  }

  function goToThemeObjectives(themeId: string) {
    setObjectiveFromInitiativeId(null);
    setFilterThemeId(themeId);
    setFocusThemeId(null);
    setFocusInitiativeId(null);
    setSelectedObjectiveId(null);
    setTab("objectives");
  }

  function goToObjective(objectiveId: string, fromInitiativeId?: string) {
    setSelectedObjectiveId(objectiveId);
    setObjectiveFromInitiativeId(fromInitiativeId ?? null);
    setFocusThemeId(null);
    setFocusInitiativeId(null);
    setTab("objectives");
  }

  function goToInitiative(initiativeId: string) {
    setObjectiveFromInitiativeId(null);
    setFocusInitiativeId(initiativeId);
    setFocusThemeId(null);
    setFilterThemeId(null);
    setSelectedObjectiveId(null);
    setTab("initiatives");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <PageHeader title="Strategy" lede="Capture strategic objectives as structured entities, traceable to real capabilities and value streams." />

        <Tabs label="Strategy" tabs={STRATEGY_TABS} active={tab} onChange={goToTab} />

        {/* Tab content */}
        {tab === "objectives" && (
          selectedObjectiveId
            ? (
              <ObjectiveDetail
                objectiveId={selectedObjectiveId}
                backLabel={objectiveFromInitiativeId ? "Back to initiative" : undefined}
                onBack={() => {
                  if (objectiveFromInitiativeId) goToInitiative(objectiveFromInitiativeId);
                  else setSelectedObjectiveId(null);
                }}
                onNavigateToTheme={goToTheme}
                onNavigateToInitiative={goToInitiative}
              />
            )
            : (
              <ObjectiveList
                onSelect={(id) => {
                  setObjectiveFromInitiativeId(null);
                  setSelectedObjectiveId(id);
                }}
                filterThemeId={filterThemeId}
                onClearThemeFilter={() => setFilterThemeId(null)}
                onThemeFilterChange={setFilterThemeId}
                onNavigateToTheme={goToTheme}
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
