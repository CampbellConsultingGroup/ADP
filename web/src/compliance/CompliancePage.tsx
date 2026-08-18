import { useState } from "react";
import FrameworkList from "./FrameworkList";
import FrameworkDetail from "./FrameworkDetail";

// Self-contained top-level page (mirrors StrategyPage's pattern) — the selected
// framework is component-local state, not lifted to App.tsx, since it has no
// cross-page relevance the way currentDesignId does.
export default function CompliancePage() {
  const [selectedFrameworkId, setSelectedFrameworkId] = useState<string | null>(null);

  if (selectedFrameworkId) {
    return (
      <FrameworkDetail
        frameworkId={selectedFrameworkId}
        onBack={() => setSelectedFrameworkId(null)}
      />
    );
  }
  return <FrameworkList onSelectFramework={setSelectedFrameworkId} />;
}
