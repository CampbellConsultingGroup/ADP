import { useRationalization } from "../api/application";
import type { Quadrant, RationalizationEntry } from "../api/application";

/**
 * APM US1 — TIME rationalization view (ADP-SPEC-038).
 * Plots applications on business value (↑) × technical health (→). Apps missing
 * either score are listed separately as unassessed — never placed in a quadrant.
 */

const QUADRANT_META: Record<Quadrant, { label: string; hint: string; color: string; bg: string }> = {
  invest: { label: "Invest", hint: "High value · High health", color: "#1f7a4d", bg: "rgba(31,122,77,0.08)" },
  migrate: { label: "Migrate", hint: "High value · Low health", color: "#b0742a", bg: "rgba(176,116,42,0.08)" },
  tolerate: { label: "Tolerate", hint: "Low value · High health", color: "#2a6db0", bg: "rgba(42,109,176,0.08)" },
  eliminate: { label: "Eliminate", hint: "Low value · Low health", color: "#b0453c", bg: "rgba(176,69,60,0.08)" },
};

// Grid reading order: row 1 = high value, row 2 = low value; col 1 = low health, col 2 = high health.
const GRID_ORDER: Quadrant[] = ["migrate", "invest", "eliminate", "tolerate"];

function AppChip({ entry }: { entry: RationalizationEntry }) {
  const bv = entry.business_value ?? "–";
  const hs = entry.health_score ?? "–";
  return (
    <div
      title={`business value ${bv} · technical health ${hs}`}
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
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.name}</span>
      <span style={{ color: "var(--ink-3)", fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
        {bv}/{hs}
      </span>
    </div>
  );
}

function QuadrantCell({ quadrant, entries }: { quadrant: Quadrant; entries: RationalizationEntry[] }) {
  const meta = QUADRANT_META[quadrant];
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: 160,
        padding: 12,
        background: meta.bg,
        border: `1px solid var(--border)`,
        borderTop: `3px solid ${meta.color}`,
        borderRadius: 8,
        gap: 8,
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontWeight: 600, color: meta.color }}>{meta.label}</span>
        <span style={{ fontSize: 12, color: "var(--ink-3)", fontVariantNumeric: "tabular-nums" }}>
          {entries.length}
        </span>
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {meta.hint}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, overflow: "auto" }}>
        {entries.map((e) => (
          <AppChip key={e.app_id} entry={e} />
        ))}
      </div>
    </div>
  );
}

export default function RationalizationView() {
  const { data, isLoading, error } = useRationalization();

  if (isLoading) {
    return <div style={{ padding: 24, color: "var(--ink-3)" }}>Loading rationalization…</div>;
  }
  if (error || !data) {
    return <div style={{ padding: 24, color: "var(--ink-3)" }}>Could not load the rationalization view.</div>;
  }

  const byQuadrant: Record<Quadrant, RationalizationEntry[]> = {
    invest: [],
    migrate: [],
    tolerate: [],
    eliminate: [],
  };
  for (const entry of data.assessed) {
    if (entry.quadrant) byQuadrant[entry.quadrant].push(entry);
  }

  return (
    <div style={{ padding: 24, overflow: "auto", height: "100%" }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>Rationalization</h2>
        <p style={{ margin: 0, color: "var(--ink-3)", fontSize: 13 }}>
          Business value (↑) × technical health (→). {data.assessed.length} placed · {data.unassessed.length} unassessed
          · {data.total} total.
        </p>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
        {/* Y-axis label */}
        <div
          style={{
            writingMode: "vertical-rl",
            transform: "rotate(180deg)",
            textAlign: "center",
            fontSize: 12,
            color: "var(--ink-3)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            padding: "4px 0",
          }}
        >
          Business value →
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {GRID_ORDER.map((q) => (
              <QuadrantCell key={q} quadrant={q} entries={byQuadrant[q]} />
            ))}
          </div>
          {/* X-axis label */}
          <div
            style={{
              textAlign: "center",
              marginTop: 8,
              fontSize: 12,
              color: "var(--ink-3)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Technical health →
          </div>
        </div>
      </div>

      {/* Unassessed */}
      <div style={{ marginTop: 24 }}>
        <div style={{ fontSize: 12, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
          Unassessed ({data.unassessed.length}) — missing a business-value or health score
        </div>
        {data.unassessed.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Every application is scored.</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {data.unassessed.map((e) => (
              <div key={e.app_id} style={{ minWidth: 160, maxWidth: 240 }}>
                <AppChip entry={e} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
