import React, { useState } from "react";
import DesignsPage from "./designs/DesignsPage";
import Workspace from "./canvas/Workspace";
import IntakePage from "./intake/IntakePage";
import KnowledgePage from "./knowledge/KnowledgePage";
import RecommendationPage from "./recommend/RecommendationPage";
import type { AppView } from "./shell";

// ADP-SPEC-025: Multi-design support.
// currentDesignId is null until the user selects or creates a design.
// Initial view is "designs" (the landing page).
export default function App(): React.ReactElement {
  const [view, setView] = useState<AppView>("designs");
  const [currentDesignId, setCurrentDesignId] = useState<string | null>(null);

  const onNavigate = (nextView: AppView) => setView(nextView);

  const onSelectDesign = (id: string) => {
    setCurrentDesignId(id);
    setView("intake");
  };

  // No design selected → always show the Designs screen
  if (!currentDesignId || view === "designs") {
    return <DesignsPage onSelectDesign={onSelectDesign} onNavigate={onNavigate} />;
  }

  if (view === "recommend") {
    return <RecommendationPage designId={currentDesignId} onNavigate={onNavigate} />;
  }

  if (view === "knowledge") {
    return <KnowledgePage onNavigate={onNavigate} designId={currentDesignId} />;
  }

  if (view === "intake") {
    return <IntakePage designId={currentDesignId} onNavigate={onNavigate} />;
  }

  return <Workspace designId={currentDesignId} onNavigate={onNavigate} />;
}
