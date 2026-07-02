import React, { useState } from "react";
import Workspace from "./canvas/Workspace";
import IntakePage from "./intake/IntakePage";

function getDesignIdFromPath(): string {
  const match = window.location.pathname.match(/\/designs\/([^/]+)/);
  return match?.[1] ?? "DESIGN-001";
}

// C1 fix: use in-app view state instead of window.location.href to preserve
// TanStack Query cache and ADP-SPEC-012 trace_id ContextVar across view switch (ART-VI).
export default function App(): React.ReactElement {
  const designId = getDesignIdFromPath();
  const [view, setView] = useState<"canvas" | "intake">("canvas");

  if (view === "intake") {
    return <IntakePage designId={designId} onBack={() => setView("canvas")} />;
  }

  return <Workspace designId={designId} onNavigateToIntake={() => setView("intake")} />;
}
