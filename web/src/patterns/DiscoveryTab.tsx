/** Anti-pattern discovery across the whole portfolio (936 US4, FR-017). No verdict: matches are
 * information to act on. */

import { useDiscovery } from "../api/patterns";
import FindingsTable from "./FindingsTable";

export default function DiscoveryTab({ patternKey, version }: { patternKey: string; version: string }) {
  const { data, isLoading, error } = useDiscovery(patternKey, version);
  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Searching the portfolio…</div>;
  if (error || !data) return <div className="ui-alert crit" role="alert">Discovery could not run.</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ margin: 0, fontSize: 13 }}>
        <strong>{data.match_count}</strong> occurrence{data.match_count === 1 ? "" : "s"} of this anti-pattern across the portfolio.
      </p>
      <FindingsTable findings={data.matches} empty="No occurrences found." />
    </div>
  );
}
