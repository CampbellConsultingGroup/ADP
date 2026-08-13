/** StrategyHeatMap — theme x status matrix (918-strategy-rollups). One row
 * per theme, one column per ObjectiveStatus, count in each cell. An optional
 * theme filter narrows the matrix to a single row without changing its
 * shape (spec.md's resolved Clarification). Column tint mirrors
 * ObjectiveDetail.tsx's own STATUS_TONE mapping. */

import { useState } from "react";
import { useStrategyHeatMap, useThemes, type ThemeStatusCounts } from "../api/strategy";

const STATUS_COLUMNS: {
  key: keyof Pick<
    ThemeStatusCounts,
    "proposed_count" | "active_count" | "at_risk_count" | "achieved_count" | "abandoned_count"
  >;
  label: string;
  tint: string;
}[] = [
  { key: "proposed_count", label: "Not yet started", tint: "var(--surface-2)" },
  { key: "active_count", label: "On track", tint: "var(--accent-wash)" },
  { key: "at_risk_count", label: "At risk", tint: "var(--warn-wash)" },
  { key: "achieved_count", label: "Achieved", tint: "var(--good-wash)" },
  { key: "abandoned_count", label: "Abandoned", tint: "var(--crit-wash)" },
];

export default function StrategyHeatMap() {
  const [themeId, setThemeId] = useState("");
  const { data: themesData } = useThemes();
  const { data, isLoading, error } = useStrategyHeatMap(themeId || undefined);

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading heat map…</div>;
  if (error) return <div className="ui-alert crit">Failed to load heat map</div>;

  const rows = data?.themes ?? [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {data?.total_objectives ?? 0} objective{data?.total_objectives === 1 ? "" : "s"} across{" "}
          {rows.length} theme{rows.length === 1 ? "" : "s"}
        </span>
        <select
          value={themeId}
          onChange={(e) => setThemeId(e.target.value)}
          style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
        >
          <option value="">All themes</option>
          {(themesData?.items ?? []).map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      {rows.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No themes yet — create one on the Themes tab to see the heat map.
        </div>
      )}

      {rows.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "8px 12px", borderBottom: "2px solid var(--border)", color: "var(--ink-3)" }}>
                  Theme
                </th>
                {STATUS_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    style={{ textAlign: "center", padding: "8px 12px", borderBottom: "2px solid var(--border)", color: "var(--ink-3)", fontWeight: 600 }}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.theme_id}>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", fontWeight: 600, color: "var(--ink)" }}>
                    {row.theme_name}
                  </td>
                  {STATUS_COLUMNS.map((col) => (
                    <td
                      key={col.key}
                      style={{
                        textAlign: "center", padding: "8px 12px", borderBottom: "1px solid var(--border)",
                        background: row[col.key] > 0 ? col.tint : undefined,
                        fontVariantNumeric: "tabular-nums",
                        color: "var(--ink)",
                      }}
                    >
                      {row[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
