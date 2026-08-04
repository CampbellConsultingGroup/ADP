import React, { useState } from "react";
import OverviewPage from "./overview/OverviewPage";
import DesignsPage from "./designs/DesignsPage";
import Workspace from "./canvas/Workspace";
import IntakePage from "./intake/IntakePage";
import KnowledgePage from "./knowledge/KnowledgePage";
import RecommendationPage from "./recommend/RecommendationPage";
import PortfolioPage from "./portfolio/PortfolioPage";
import GovernancePage from "./governance/GovernancePage";
import BusinessPage from "./business/BusinessPage";
import ApplicationPage from "./application/ApplicationPage";
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

  const onNavigate = (nextView: AppView) => setView(nextView);

  const onSelectDesign = (id: string) => {
    setCurrentDesignId(id);
    setView("intake");
  };

  function renderPage(): React.ReactElement {
    // Global views — independent of design selection.
    switch (view) {
      case "overview":
        return <OverviewPage onNavigate={onNavigate} />;
      case "portfolio":
        return <PortfolioPage onNavigate={onNavigate} onSelectDesign={onSelectDesign} />;
      case "governance":
        return <GovernancePage onNavigate={onNavigate} onSelectDesign={onSelectDesign} />;
      case "business":
        return <BusinessPage onNavigate={onNavigate} designId={currentDesignId} />;
      case "applications":
        return <ApplicationPage />;
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
    return <Workspace designId={currentDesignId} onNavigate={onNavigate} />;
  }

  return (
    <AppShell currentView={view} onNavigate={onNavigate} designId={currentDesignId}>
      {renderPage()}
    </AppShell>
  );
}
