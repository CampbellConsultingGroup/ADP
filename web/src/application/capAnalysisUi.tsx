// 938-capability-model-analysis: small shared pieces for the analysis views (impact, technology
// dependencies, findings): navigable links (FR-018), L1 › L2 path text, and lifecycle band chips.

import type React from "react";
import type { CapRef } from "../api/appCapabilities";
import type { LifecycleBand } from "../api/capAnalysis";
import { LIFECYCLE_BAND_LABEL } from "../api/capAnalysis";
import { EntityLink } from "../shell/EntityLink";
import type { EntityKind } from "../shell/routing";

export type CapKind = "business" | "app-capability" | "technical" | "application";

const OPEN_TITLE: Record<CapKind, string> = {
  business: "Open in Business → Capabilities",
  "app-capability": "Open in Applications → Capabilities",
  technical: "Open in Technical Architecture",
  application: "Open the application",
};

const ENTITY_KIND: Record<CapKind, EntityKind> = {
  business: "business_capability",
  "app-capability": "application_capability",
  technical: "technical_capability",
  application: "application",
};

/** A name that links to the item's own screen. */
export function CapLink({ kind, id, children }: { kind: CapKind; id: string; children: React.ReactNode }): React.ReactElement {
  return <EntityLink kind={ENTITY_KIND[kind]} id={id} title={OPEN_TITLE[kind]}>{children}</EntityLink>;
}

export function pathText(path: CapRef[]): string {
  return path.map((p) => p.name).join(" › ");
}

/** "Name — L1 › L2" with the name navigable. */
export function CapWithPath({ kind, cap }: { kind: CapKind; cap: CapRef & { path?: CapRef[] } }): React.ReactElement {
  return (
    <>
      <CapLink kind={kind} id={cap.id}>{cap.name}</CapLink>
      {cap.path && cap.path.length > 0 && (
        <span style={{ color: "var(--ink-3)", fontSize: 11 }}> — {pathText(cap.path)}</span>
      )}
    </>
  );
}

export const LIFECYCLE_BAND_SWATCH: Record<LifecycleBand, { bg: string; fg: string }> = {
  past_end_of_life: { bg: "var(--crit)", fg: "#ffffff" },
  retiring: { bg: "var(--warn)", fg: "#1a1400" },
  contained: { bg: "var(--surface-3)", fg: "var(--ink)" },
  current: { bg: "var(--good-wash)", fg: "var(--ink)" },
  emerging: { bg: "var(--accent-wash, #e8f1f8)", fg: "var(--ink)" },
};

export function BandChip({ band }: { band: LifecycleBand }): React.ReactElement {
  const s = LIFECYCLE_BAND_SWATCH[band];
  return (
    <span
      style={{
        fontSize: 10,
        padding: "0 5px",
        borderRadius: 3,
        background: s.bg,
        color: s.fg,
        border: "1px solid var(--border)",
        whiteSpace: "nowrap",
      }}
    >
      {LIFECYCLE_BAND_LABEL[band]}
    </span>
  );
}

export const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
