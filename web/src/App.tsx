import React, { useState } from "react";
import OverviewPage from "./overview/OverviewPage";
import InsightsPage from "./insights/InsightsPage";
import DesignsPage from "./designs/DesignsPage";
import { C4DesignView } from "./canvas-v2/C4DesignView";
import IntakePage from "./intake/IntakePage";
import KnowledgePage from "./knowledge/KnowledgePage";
import RecommendationPage from "./recommend/RecommendationPage";
import PortfolioPage from "./portfolio/PortfolioPage";
import GovernancePage from "./governance/GovernancePage";
import BusinessPage from "./business/BusinessPage";
import ApplicationPage from "./application/ApplicationPage";
import { DiagramsPage } from "./diagrams/DiagramsPage";
import type { DiagramSeed } from "./diagrams/generators";
import StrategyPage from "./strategy/StrategyPage";
import AdminPage from "./admin/AdminPage";
import { AppShell } from "./ui";
import type { AppView } from "./shell";

// ADP-SPEC-025: Multi-design support.
// currentDesignId is null until the user selects or creates a design.
// Initial view is "overview" (the landing dashboard). All views render inside
// the shared AppShell (left-rail nav + top bar).
export default function App(): React.ReactElement {
  const [view, setView] = useState<AppView>("overview");
  const [currentDesignId, setCurrentDesignId] = useState<string | null>(null);
  // ADP-914.7: a diagram generated from a value stream/capability elsewhere in
  // the app, waiting to be opened in the Diagrams editor -- mirrors
  // currentDesignId/onSelectDesign below exactly (research.md Decision 3).
  const [pendingDiagramSeed, setPendingDiagramSeed] = useState<DiagramSeed | null>(null);

  const onNavigate = (nextView: AppView) => setView(nextView);

  const onSelectDesign = (id: string) => {
    setCurrentDesignId(id);
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
        return <PortfolioPage onNavigate={onNavigate} onSelectDesign={onSelectDesign} />;
      case "governance":
        return <GovernancePage onNavigate={onNavigate} onSelectDesign={onSelectDesign} />;
      case "business":
        return <BusinessPage onNavigate={onNavigate} designId={currentDesignId} onGenerateDiagram={onGenerateDiagram} />;
      case "applications":
        return <ApplicationPage />;
      case "diagrams":
        return (
          <DiagramsPage
            seed={pendingDiagramSeed}
            onSeedConsumed={() => setPendingDiagramSeed(null)}
          />
        );
      case "strategy":
        return <StrategyPage />;
      case "admin":
        return <AdminPage />;
      case "knowledge":
        return <KnowledgePage onNavigate={onNavigate} designId={currentDesignId} />;
      default:
        break;
    }

    // No design selected → always show the Designs screen.
    if (!currentDesignId || view === "designs") {
      return <DesignsPage onSelectDesign={onSelectDesign} onNavigate={onNavigate} />;
    }

    // Design-scoped views.
    if (view === "recommend") {
      return <RecommendationPage designId={currentDesignId} onNavigate={onNavigate} />;
    }
    if (view === "intake") {
      return <IntakePage designId={currentDesignId} onNavigate={onNavigate} />;
    }
    // ADP-914.13: C4DesignView is now the sole design-editing surface -- the legacy
    // Workspace/C4Canvas ("canvas") fallback it replaced is deleted. Every remaining
    // design-scoped view falls through to it (matches the pre-914.13 fallback shape,
    // which defaulted unmatched design-scoped views to Workspace).
    return <C4DesignView designId={currentDesignId} />;
  }

  return (
    <AppShell currentView={view} onNavigate={onNavigate} designId={currentDesignId}>
      {renderPage()}
    </AppShell>
  );
}
