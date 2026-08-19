import React, { useState } from "react";
import OverviewPage from "./overview/OverviewPage";
import InsightsPage from "./insights/InsightsPage";
import DesignsPage from "./designs/DesignsPage";
import { C4DesignView } from "./canvas-v2/C4DesignView";
import IntakePage from "./intake/IntakePage";
import KnowledgePage from "./knowledge/KnowledgePage";
import PortfolioPage from "./portfolio/PortfolioPage";
import GovernancePage from "./governance/GovernancePage";
import BusinessPage from "./business/BusinessPage";
import ApplicationPage from "./application/ApplicationPage";
import TechCapPage from "./application/TechCapPage";
import { DiagramsPage } from "./diagrams/DiagramsPage";
import type { DiagramSeed } from "./diagrams/generators";
import StrategyPage from "./strategy/StrategyPage";
import CompliancePage from "./compliance/CompliancePage";
import AdminPage from "./admin/AdminPage";
import { AppShell } from "./ui";
import type { AppView } from "./shell";

// C4 Design has no meaning without a design (it operates on elements that only
// exist once one does) -- clicking it from the always-visible Design nav group
// with no design selected detours through the Designs list (to pick or create
// one) rather than silently landing on that same list with no explanation.
//
// Intake is deliberately NOT here: it's where a design starts (capturing the
// Business Problem), so it must be reachable directly with no detour at all --
// see IntakePage/IntakeTextForm, which create the design lazily on first submit.
// Recommendations is no longer a top-level view at all -- it's a tab inside
// IntakePage itself (the second step of Intake's own flow), so it needs no
// entry here either.
const DESIGN_ONLY_VIEWS: AppView[] = ["canvas-v2"];
const DESIGN_ONLY_VIEW_LABELS: Record<string, string> = {
  "canvas-v2": "C4 Design",
};

// ADP-SPEC-025: Multi-design support.
// currentDesignId is null until the user selects or creates a design.
// Initial view is "overview" (the landing dashboard). All views render inside
// the shared AppShell (left-rail nav + top bar).
export default function App(): React.ReactElement {
  const [view, setView] = useState<AppView>("overview");
  const [currentDesignId, setCurrentDesignId] = useState<string | null>(null);
  // Set when a design-only view is requested with no design selected yet --
  // consumed by onSelectDesign below so the user lands on the screen they
  // actually asked for (e.g. Recommendations) instead of always defaulting
  // to Intake once they pick or create a design.
  const [pendingView, setPendingView] = useState<AppView | null>(null);
  // ADP-914.7: a diagram generated from a value stream/capability elsewhere in
  // the app, waiting to be opened in the Diagrams editor -- mirrors
  // currentDesignId/onSelectDesign below exactly (research.md Decision 3).
  const [pendingDiagramSeed, setPendingDiagramSeed] = useState<DiagramSeed | null>(null);

  const onNavigate = (nextView: AppView) => {
    if (!currentDesignId && DESIGN_ONLY_VIEWS.includes(nextView)) {
      setPendingView(nextView);
      setView("designs");
      return;
    }
    setView(nextView);
  };

  const onSelectDesign = (id: string) => {
    setCurrentDesignId(id);
    setView(pendingView ?? "intake");
    setPendingView(null);
  };

  // Nav bar "Intake" click == "New Design": always resets to a blank Intake
  // form, even if a design is currently selected. Deliberately distinct from
  // onNavigate("intake") -- that generic path is also used by onSelectDesign
  // (Open a design -> populated Intake) and by the governance tabs'
  // onSelectDesign(id); onNavigate("intake") pattern, both of which must keep
  // landing on the *selected* design's data, not a blank one. This handler is
  // wired only to the nav bar's Intake button (see AppShell's onStartNewDesign
  // prop), so none of those other call sites are affected.
  const onStartNewDesign = () => {
    setCurrentDesignId(null);
    setPendingView(null);
    setView("intake");
  };

  const onGenerateDiagram = (seed: DiagramSeed) => {
    setPendingDiagramSeed(seed);
    setView("diagrams");
  };

  function renderPage(): React.ReactElement {
    // Global views — independent of design selection.
    switch (view) {
      case "overview":
        return <OverviewPage onNavigate={onNavigate} />;
      case "insights":
        return <InsightsPage />;
      case "portfolio":
        return <PortfolioPage />;
      case "governance":
        return <GovernancePage onNavigate={onNavigate} onSelectDesign={onSelectDesign} />;
      case "business":
        return <BusinessPage onNavigate={onNavigate} designId={currentDesignId} onGenerateDiagram={onGenerateDiagram} />;
      case "applications":
        return <ApplicationPage />;
      case "technical":
        return <TechCapPage />;
      case "diagrams":
        return (
          <DiagramsPage
            seed={pendingDiagramSeed}
            onSeedConsumed={() => setPendingDiagramSeed(null)}
          />
        );
      case "strategy":
        return <StrategyPage />;
      case "compliance":
        return <CompliancePage />;
      case "admin":
        return <AdminPage />;
      case "knowledge":
        return <KnowledgePage onNavigate={onNavigate} designId={currentDesignId} />;
      case "intake":
        // Always reachable, design or no design -- see the DESIGN_ONLY_VIEWS
        // comment above.
        return (
          <IntakePage
            designId={currentDesignId}
            onNavigate={onNavigate}
            onDesignCreated={setCurrentDesignId}
          />
        );
      default:
        break;
    }

    // No design selected → always show the Designs screen.
    if (!currentDesignId || view === "designs") {
      return (
        <DesignsPage
          onSelectDesign={onSelectDesign}
          onNavigate={onNavigate}
          continueTo={pendingView ? DESIGN_ONLY_VIEW_LABELS[pendingView] : null}
        />
      );
    }

    // Design-scoped views.
    // ADP-914.13: C4DesignView is now the sole design-editing surface -- the legacy
    // Workspace/C4Canvas ("canvas") fallback it replaced is deleted. Every remaining
    // design-scoped view falls through to it (matches the pre-914.13 fallback shape,
    // which defaulted unmatched design-scoped views to Workspace).
    return <C4DesignView designId={currentDesignId} />;
  }

  return (
    <AppShell currentView={view} onNavigate={onNavigate} designId={currentDesignId} onStartNewDesign={onStartNewDesign}>
      {renderPage()}
    </AppShell>
  );
}
