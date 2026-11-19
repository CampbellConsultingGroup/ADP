/** TimeQuadrantChart — applications as bubbles on the TIME 2x2 (ADP-v2n).
 *
 * x = technical health, y = business value (both 1-5, from the rationalization projection);
 * the quadrant lines are the same ones the Applications screen uses. Colour = the hand-set TIME
 * classification; bubble area = total cost of ownership when the caller may read cost (the
 * heat map's `cost_permitted`), otherwise every bubble is the same size. Each bubble links to
 * its application. Layout is in ./timeQuadrant.ts. */

import React, { useMemo } from "react";
import { useRationalization, type Quadrant, type TimeClassification } from "../api/application";
import { useApplicationsHeatmap } from "../api/portfolio";
import { entityHref } from "../shell/routing";
import { EntityLink } from "../shell/EntityLink";
import { Alert, EmptyState, Loading } from "../ui/primitives";
import { CHART, PLOT_H, PLOT_W, SPLIT, layoutBubbles, xFor, yFor, type Bubble } from "./timeQuadrant";

const TIME_FILL: Record<TimeClassification, string> = {
  Invest: "var(--good)",
  Migrate: "var(--warn)",
  Eliminate: "var(--crit)",
  Tolerate: "var(--ink-3)",
};

const TIME_ORDER: TimeClassification[] = ["Invest", "Tolerate", "Migrate", "Eliminate"];

const QUADRANTS: { q: Quadrant; label: string; fill: string; high: boolean; healthy: boolean }[] = [
  { q: "migrate", label: "Migrate", fill: "var(--warn-wash)", high: true, healthy: false },
  { q: "invest", label: "Invest", fill: "var(--good-wash)", high: true, healthy: true },
  { q: "eliminate", label: "Eliminate", fill: "var(--crit-wash)", high: false, healthy: false },
  { q: "tolerate", label: "Tolerate", fill: "var(--surface-2)", high: false, healthy: true },
];

function money(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

function describe(b: Bubble, costShown: boolean): string {
  const parts = [
    b.name,
    `business value ${b.businessValue}, technical health ${b.health}`,
    `quadrant ${b.quadrant}`,
    `TIME ${b.time ?? "not classified"}`,
  ];
  if (costShown) parts.push(b.cost === null ? "no cost recorded" : `TCO ${money(b.cost)}`);
  return parts.join("; ");
}

export default function TimeQuadrantChart(): React.ReactElement {
  const rat = useRationalization();
  const heat = useApplicationsHeatmap();
  const costShown = heat.data?.cost_permitted ?? false;

  const bubbles = useMemo(
    () => layoutBubbles(rat.data?.assessed ?? [], heat.data?.items ?? [], costShown),
    [rat.data, heat.data, costShown],
  );

  if (rat.isLoading || heat.isLoading) return <Loading label="Loading applications…" />;
  if (rat.error || heat.error) return <Alert tone="crit">Failed to load the TIME quadrant chart</Alert>;

  const unassessed = rat.data?.unassessed ?? [];
  const mismatches = bubbles.filter((b) => b.mismatch).length;
  const unclassified = bubbles.filter((b) => b.time === null).length;
  const splitX = xFor(SPLIT);
  const splitY = yFor(SPLIT);

  if (bubbles.length === 0) {
    return (
      <EmptyState
        compact
        title="No applications to plot yet"
        why="An application appears here once it has both a business value and a health score."
      />
    );
  }

  return (
    <div>
      <p style={{ fontSize: 13, color: "var(--ink-3)", margin: "0 0 8px" }}>
        {bubbles.length} application{bubbles.length === 1 ? "" : "s"} placed by business value and technical health.
        Colour is the TIME classification set on the application
        {costShown ? "; bubble size is total cost of ownership." : "."}
        {mismatches > 0 && (
          <>
            {" "}
            <strong style={{ color: "var(--ink)" }}>
              {mismatches} {mismatches === 1 ? "has" : "have"} a TIME classification that differs from {mismatches === 1 ? "its" : "their"} quadrant
            </strong>{" "}
            (outlined).
          </>
        )}
      </p>

      <div style={{ overflowX: "auto" }}>
        <svg
          viewBox={`0 0 ${CHART.width} ${CHART.height}`}
          style={{ width: "100%", maxWidth: CHART.width, minWidth: 420, display: "block" }}
          role="group"
          aria-label="TIME quadrant chart: business value against technical health"
        >
          {QUADRANTS.map(({ q, label, fill, high, healthy }) => {
            const x = healthy ? splitX : CHART.left;
            const y = high ? CHART.top : splitY;
            const w = healthy ? CHART.left + PLOT_W - splitX : splitX - CHART.left;
            const h = high ? splitY - CHART.top : CHART.top + PLOT_H - splitY;
            return (
              <g key={q}>
                <rect x={x} y={y} width={w} height={h} fill={fill} />
                <text
                  x={healthy ? x + w - 8 : x + 8}
                  y={high ? y + 18 : y + h - 8}
                  textAnchor={healthy ? "end" : "start"}
                  fontSize={13}
                  fontWeight={600}
                  fill="var(--ink-2)"
                >
                  {label}
                </text>
              </g>
            );
          })}

          <rect x={CHART.left} y={CHART.top} width={PLOT_W} height={PLOT_H} fill="none" stroke="var(--border)" />
          <line x1={splitX} x2={splitX} y1={CHART.top} y2={CHART.top + PLOT_H} stroke="var(--border-strong)" strokeDasharray="4 3" />
          <line x1={CHART.left} x2={CHART.left + PLOT_W} y1={splitY} y2={splitY} stroke="var(--border-strong)" strokeDasharray="4 3" />

          {[1, 2, 3, 4, 5].map((s) => (
            <g key={s} fontSize={11} fill="var(--ink-3)">
              <text x={xFor(s)} y={CHART.top + PLOT_H + 16} textAnchor="middle">{s}</text>
              <text x={CHART.left - 8} y={yFor(s) + 4} textAnchor="end">{s}</text>
            </g>
          ))}
          <text x={CHART.left + PLOT_W / 2} y={CHART.height - 8} textAnchor="middle" fontSize={12} fill="var(--ink-2)">
            Technical health →
          </text>
          <text
            x={14}
            y={CHART.top + PLOT_H / 2}
            textAnchor="middle"
            fontSize={12}
            fill="var(--ink-2)"
            transform={`rotate(-90 14 ${CHART.top + PLOT_H / 2})`}
          >
            Business value →
          </text>

          {bubbles.map((b) => {
            const label = describe(b, costShown);
            return (
              <a key={b.id} href={entityHref("application", b.id)} aria-label={label}>
                <title>{label}</title>
                <circle
                  data-testid={`bubble-${b.id}`}
                  cx={b.cx}
                  cy={b.cy}
                  r={b.r}
                  fill={b.time ? TIME_FILL[b.time] : "var(--surface)"}
                  fillOpacity={b.time ? 0.85 : 1}
                  stroke={b.mismatch ? "var(--ink)" : b.time ? "var(--surface)" : "var(--ink-3)"}
                  strokeWidth={b.mismatch ? 2.5 : b.time ? 1 : 1.5}
                  strokeDasharray={b.time ? undefined : "3 2"}
                />
              </a>
            );
          })}
        </svg>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 12, color: "var(--ink-2)", marginTop: 8 }} aria-label="Legend">
        {TIME_ORDER.map((t) => (
          <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <svg width={12} height={12} aria-hidden="true"><circle cx={6} cy={6} r={5} fill={TIME_FILL[t]} /></svg>
            {t}
          </span>
        ))}
        {unclassified > 0 && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <svg width={12} height={12} aria-hidden="true">
              <circle cx={6} cy={6} r={5} fill="var(--surface)" stroke="var(--ink-3)" strokeWidth={1.5} strokeDasharray="3 2" />
            </svg>
            Not classified
          </span>
        )}
        {mismatches > 0 && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <svg width={12} height={12} aria-hidden="true">
              <circle cx={6} cy={6} r={4.5} fill="none" stroke="var(--ink)" strokeWidth={2} />
            </svg>
            Differs from quadrant
          </span>
        )}
        {!costShown && <span style={{ color: "var(--ink-3)" }}>Bubble size is the same for all: cost is not available to you.</span>}
      </div>

      {unassessed.length > 0 && (
        <details style={{ marginTop: 12, fontSize: 13 }}>
          <summary style={{ cursor: "pointer", color: "var(--ink-2)" }}>
            {unassessed.length} not plotted (missing business value or health score)
          </summary>
          <ul style={{ margin: "6px 0 0", paddingLeft: 20 }}>
            {unassessed.map((u) => (
              <li key={u.app_id}>
                <EntityLink kind="application" id={u.app_id}>{u.name}</EntityLink>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
