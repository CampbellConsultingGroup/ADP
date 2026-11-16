// 942-regional-assessments (ADP-55k.3) US3: the regional heat map. Capabilities down the side in
// tree order, a baseline column (the capability's own maturity), then one column per chosen
// geography (the regions by default, at most 12). Each cell is derived by the server: assessed
// (coloured, with ▲/▼ against the baseline and the note on hover), not assessed, or not applicable
// (a region-specific capability outside its scope). No roll-up and no inheritance: a cell only
// ever shows that exact assessment. The column choice lives in BusinessPage, for the session.

import { useState } from "react";
import type React from "react";
import { MATURITY_LEVEL_LABEL } from "../api/business";
import type { GeoRef, HeatmapCell, HeatmapRow } from "../api/organization";
import { useGeographies, useRegionalHeatmap } from "../api/organization";
import { assessableGeographies, CellEditor } from "./RegionalAssessmentEditor";
import { maturitySwatch } from "./maturityScale";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const th: React.CSSProperties = { fontSize: 11, padding: "4px 6px", textAlign: "center", fontWeight: 600, color: "var(--ink-2)", whiteSpace: "nowrap" };
// Border as separate longhands: cells switch to borderStyle "dashed" when not assessed, and mixing
// that with the `border` shorthand mis-styles a cell on re-render (React warned, found live).
const cellBase: React.CSSProperties = {
  fontSize: 11,
  padding: "3px 6px",
  textAlign: "center",
  borderWidth: 1,
  borderStyle: "solid",
  borderColor: "var(--border)",
  minWidth: 84,
};

function label(level: number): string {
  return MATURITY_LEVEL_LABEL[level as 1 | 2 | 3 | 4 | 5];
}

function Delta({ delta }: { delta: number | null }): React.ReactElement | null {
  if (delta === null || delta === 0) return null;
  const up = delta > 0;
  return (
    <span aria-label={`${up ? "above" : "below"} baseline by ${Math.abs(delta)}`} style={{ marginLeft: 3, fontWeight: 700 }}>
      {up ? "▲" : "▼"}
      {Math.abs(delta)}
    </span>
  );
}

function cellView(c: HeatmapCell): { style: React.CSSProperties; text: React.ReactNode; title: string } {
  if (c.state === "not_applicable") {
    return {
      style: { background: "repeating-linear-gradient(45deg, var(--surface-2), var(--surface-2) 4px, var(--surface) 4px, var(--surface) 8px)", color: "var(--ink-3)" },
      text: "Not applicable",
      title: "Region-specific capability: not applicable here",
    };
  }
  if (c.state === "not_assessed") {
    return { style: { color: "var(--ink-3)", borderStyle: "dashed" }, text: "Not assessed", title: "Not assessed" };
  }
  const note = c.note ? `\n${c.note}` : "";
  if (c.maturity_level === null) {
    return { style: { color: "var(--ink-2)", fontStyle: "italic" }, text: "Note only", title: `Not scored${note}` };
  }
  const sw = maturitySwatch(c.maturity_level);
  return {
    style: { background: sw.bg, color: sw.fg },
    text: (
      <>
        {c.maturity_level} {label(c.maturity_level)}
        <Delta delta={c.delta} />
        {c.note && <span aria-hidden="true"> ✎</span>}
      </>
    ),
    title: `${c.maturity_level} · ${label(c.maturity_level)}${note}`,
  };
}

function ColumnPicker({
  columns,
  max,
  onChange,
}: {
  columns: GeoRef[];
  max: number;
  onChange: (ids: string[] | null) => void;
}): React.ReactElement {
  const geos = useGeographies();
  const [pick, setPick] = useState("");
  const ids = columns.map((c) => c.id);
  const options = assessableGeographies(geos.data?.items ?? []).filter((g) => !ids.includes(g.id));
  const full = ids.length >= max;
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
      <span style={muted}>Columns:</span>
      {columns.map((c) => (
        <span key={c.id} style={{ fontSize: 11, background: "var(--surface-2)", padding: "1px 6px", borderRadius: 8 }}>
          {c.name}{" "}
          <button
            type="button"
            aria-label={`Remove column ${c.name}`}
            disabled={ids.length === 1}
            onClick={() => onChange(ids.filter((x) => x !== c.id))}
            style={{ border: "none", background: "none", color: "var(--ink-3)", cursor: "pointer", padding: 0 }}
          >
            ×
          </button>
        </span>
      ))}
      <select aria-label="Add column" value={pick} disabled={full} onChange={(e) => setPick(e.target.value)} style={{ fontSize: 12, padding: "2px 4px" }}>
        <option value="">{full ? `At most ${max} columns` : "Add a region or country…"}</option>
        {options.map((g) => (
          <option key={g.id} value={g.id}>
            {g.code ? `${g.name} (${g.code})` : g.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={!pick || full}
        onClick={() => {
          onChange([...ids, pick]);
          setPick("");
        }}
        style={{ fontSize: 12 }}
      >
        Add
      </button>
      <button type="button" onClick={() => onChange(null)} style={{ fontSize: 12, border: "none", background: "none", color: "var(--accent)", cursor: "pointer" }}>
        Reset to regions
      </button>
    </div>
  );
}

function Row({
  row,
  columns,
  canWrite,
  onOpenCapability,
}: {
  row: HeatmapRow;
  columns: GeoRef[];
  canWrite: boolean;
  onOpenCapability?: (id: string) => void;
}): React.ReactElement {
  const [editing, setEditing] = useState<string | null>(null);
  const indent = (row.capability.level - 1) * 14;
  const base = row.baseline ? maturitySwatch(row.baseline) : null;
  return (
    <tr>
      <th scope="row" style={{ textAlign: "left", fontSize: 12, fontWeight: row.capability.level === 1 ? 600 : 400, padding: "3px 6px", paddingLeft: 6 + indent, whiteSpace: "nowrap" }}>
        <button
          type="button"
          onClick={() => onOpenCapability?.(row.capability.id)}
          style={{ border: "none", background: "none", padding: 0, cursor: "pointer", color: "var(--ink)", font: "inherit" }}
          title="Open on the Capabilities tab"
        >
          {row.capability.name}
        </button>
        {row.region_specific && (
          <span style={{ marginLeft: 6, fontSize: 10, color: "var(--accent-2)" }} title="Region-specific capability">
            region-specific
          </span>
        )}
        {row.scope_needs_update && (
          <span style={{ marginLeft: 6, fontSize: 10, color: "var(--warn)" }}>scope needs updating</span>
        )}
      </th>
      <td style={{ ...cellBase, ...(base ? { background: base.bg, color: base.fg } : { color: "var(--ink-3)", borderStyle: "dashed" }) }}>
        {row.baseline ? `${row.baseline} ${label(row.baseline)}` : "Not assessed"}
      </td>
      {row.cells.map((c, i) => {
        const v = cellView(c);
        const geo = columns[i];
        const editable = canWrite && c.state !== "not_applicable";
        return (
          <td key={c.geography_id} style={{ ...cellBase, ...v.style, position: "relative", cursor: editable ? "pointer" : "default" }} title={v.title}>
            {editable ? (
              <button
                type="button"
                aria-label={`${row.capability.name} in ${geo.name}: ${v.title.split("\n")[0]}`}
                onClick={() => setEditing(editing === c.geography_id ? null : c.geography_id)}
                style={{ border: "none", background: "none", color: "inherit", font: "inherit", cursor: "pointer", padding: 0, width: "100%" }}
              >
                {v.text}
              </button>
            ) : (
              v.text
            )}
            {editing === c.geography_id && (
              <div style={{ position: "absolute", zIndex: 5, top: "100%", left: 0, textAlign: "left", boxShadow: "0 4px 12px rgba(0,0,0,.15)" }}>
                <CellEditor
                  capabilityId={row.capability.id}
                  capabilityName={row.capability.name}
                  geography={geo}
                  current={c.state === "assessed" ? { maturity_level: c.maturity_level, note: c.note } : null}
                  onDone={() => setEditing(null)}
                />
              </div>
            )}
          </td>
        );
      })}
    </tr>
  );
}

export default function RegionalHeatMap({
  columns,
  onColumnsChange,
  canWrite,
  onOpenCapability,
}: {
  columns: string[] | null;
  onColumnsChange: (ids: string[] | null) => void;
  canWrite: boolean;
  onOpenCapability?: (id: string) => void;
}): React.ReactElement {
  const { data, isLoading, error } = useRegionalHeatmap(columns);
  if (isLoading) return <div style={muted}>Loading regional heat map…</div>;
  if (error || !data) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load the regional heat map.</div>;
  return (
    <div>
      <p style={{ ...muted, marginTop: 0 }}>
        Maturity by region, against each capability's global baseline. A cell only shows an assessment made for that exact
        region or country; nothing is averaged or inherited.
        {canWrite && " Click a cell to record or change it."}
      </p>
      <ColumnPicker columns={data.columns} max={data.max_columns} onChange={onColumnsChange} />
      {data.rows.length === 0 ? (
        <div style={muted}>No capabilities yet.</div>
      ) : (
        <div style={{ overflowX: "auto", maxWidth: "100%", paddingBottom: 140 }}>
          <table style={{ borderCollapse: "collapse" }} aria-label="Regional maturity heat map">
            <thead>
              <tr>
                <th style={{ ...th, textAlign: "left" }}>Capability</th>
                <th style={th}>Baseline</th>
                {data.columns.map((c) => (
                  <th key={c.id} style={th}>
                    {c.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <Row key={r.capability.id} row={r} columns={data.columns} canWrite={canWrite} onOpenCapability={onOpenCapability} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
