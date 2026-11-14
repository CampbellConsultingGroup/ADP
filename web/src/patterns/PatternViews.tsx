/** The Views tab of a pattern version: structure / catalog / traceability (935 US4). */

import { usePatternView } from "../api/patterns";
import type { PatternViewKind } from "../api/patterns";
import FlowchartView, { ViewsTab } from "./FlowchartView";

const TITLES: Record<PatternViewKind, string> = {
  structure: "Pattern structure",
  catalog: "Related patterns",
  traceability: "Why this pattern exists",
};

function LoadedView({ patternKey, version, view, depth }: { patternKey: string; version: string; view: PatternViewKind; depth: number }) {
  const { data, isLoading, error } = usePatternView(patternKey, version, view, depth);
  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Rendering…</div>;
  if (error || !data) return <div className="ui-alert crit" role="alert">The view could not be loaded.</div>;
  return <FlowchartView flowchart={data.flowchart} title={TITLES[view]} truncated={data.truncated} />;
}

export default function PatternViews({ patternKey, version }: { patternKey: string; version: string }) {
  return (
    <ViewsTab
      patternKey={patternKey}
      version={version}
      render={(view, depth) => <LoadedView patternKey={patternKey} version={version} view={view} depth={depth} />}
    />
  );
}
