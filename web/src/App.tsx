import React, { useState } from "react";
import Workspace from "./canvas/Workspace";
import IntakePage from "./intake/IntakePage";
import RecommendationPage from "./recommend/RecommendationPage";

type AppView = "canvas" | "intake" | "recommend";

function getDesignIdFromPath(): string {
  const match = window.location.pathname.match(/\/designs\/([^/]+)/);
  return match?.[1] ?? "DESIGN-001";
}

// I1 fix (ADP-SPEC-018): single onNavigate(view) prop passed to all three pages.
// Replaces the previous mix of onBack/onNavigateToIntake/onNavigateToRecommend.
export default function App(): React.ReactElement {
  const designId = getDesignIdFromPath();
  const [view, setView] = useState<AppView>("intake"); // ADP-SPEC-016: Intake is the default

  const onNavigate = (nextView: AppView) => setView(nextView);

  if (view === "recommend") {
    return <RecommendationPage designId={designId} onNavigate={onNavigate} />;
  }

  if (view === "intake") {
    return <IntakePage designId={designId} onNavigate={onNavigate} />;
  }

  return <Workspace designId={designId} onNavigate={onNavigate} />;
}
