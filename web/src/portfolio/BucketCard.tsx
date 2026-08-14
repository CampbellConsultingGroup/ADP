/** BucketCard — one grouping bucket's header + member app chips, for
 * PortfolioPage.tsx's Application Portfolio pivot (ADP-8xo). Styled like
 * web/src/application/RationalizationView.tsx's QuadrantCell/AppChip pair, but
 * generic across all 5 dimensions (RationalizationView is fixed to exactly 4
 * quadrants; a business-unit or capability bucket set is open-ended). */
import React from "react";
import type { Application } from "../api/application";
import type { Bucket, Dimension } from "./groupApplications";

function detailFor(app: Application, dimension: Dimension): string | null {
  switch (dimension) {
    case "capability":
      return null; // fit_score isn't carried on Application itself; name is enough here
    case "time":
      return null; // the bucket itself already says the TIME value
    case "r_strategy":
      return null;
    case "business_unit":
      return null;
    case "criticality":
      return app.business_criticality === null ? null : `tier ${app.business_criticality}`;
  }
}

export function AppChip({ name, detail }: { name: string; detail?: string | null }): React.ReactElement {
  return (
    <div
      title={detail ? `${name} — ${detail}` : name}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 8,
        padding: "4px 8px",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        fontSize: 13,
      }}
    >
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
      {detail && (
        <span style={{ color: "var(--ink-3)", fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
          {detail}
        </span>
      )}
    </div>
  );
}

export default function BucketCard({
  bucket,
  dimension,
}: {
  bucket: Bucket;
  dimension: Dimension;
}): React.ReactElement {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: 120,
        padding: 12,
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderTop: "3px solid var(--accent)",
        borderRadius: 8,
        gap: 8,
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontWeight: 600, color: "var(--ink)" }}>{bucket.label}</span>
        <span style={{ fontSize: 12, color: "var(--ink-3)", fontVariantNumeric: "tabular-nums" }}>
          {bucket.apps.length}
        </span>
      </div>
      {bucket.apps.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--ink-3)" }}>No applications</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, overflow: "auto" }}>
          {bucket.apps.map((app) => (
            <AppChip key={app.id} name={app.name} detail={detailFor(app, dimension)} />
          ))}
        </div>
      )}
    </div>
  );
}
