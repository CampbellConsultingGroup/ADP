// 939-governance-architecture-health (ADP-loz, ADP-n2t): Governance -> Architecture Health.
// Five tiles, then what needs attention: pattern adoptions (936 conformance) and the capability
// model (938 exposure, overlaps, gaps), plus 941's ownership / performer findings (ADP-m7x).
// Frontend only -- every figure comes from an endpoint that is
// already derived on the server and already applies its own permission rules (conformance is
// evaluated for the viewer). Each section loads, fails and empties independently (FR-007).

import type React from "react";
import { useCapabilities, type BusinessCapability } from "../api/business";
import { useCapabilityFindings, useCapabilityRollup } from "../api/capAnalysis";
import { useCapabilityOrgFindings } from "../api/organization";
import { useAdoptions } from "../api/patterns";
import CapFindingsViews from "../application/CapFindingsViews";
import { EntityLink } from "../shell/EntityLink";
import { goToEntity } from "../shell/routing";
import OrgFindings from "../business/OrgFindings";
import { BandChip, CapWithPath, muted } from "../application/capAnalysisUi";
import { SCOPE_LABELS, STATUS_LABELS, STATUS_TONES } from "../patterns/labels";
import { StatusBadge } from "../ui";
import { adoptionsNeedingAttention, exposedCapabilities, gapCount, overlapCounts } from "./architectureHealth";

interface Source {
  isLoading: boolean;
  error: unknown;
}

/** "…" while loading and "—" on error, so a tile never shows a misleading 0 (plan R4). */
function tileValue(source: Source, value: number): string {
  if (source.isLoading) return "…";
  if (source.error) return "—";
  return String(value);
}

function Tile({ label, value, tone, note }: { label: string; value: string; tone: "crit" | "warn" | "info"; note?: string }): React.ReactElement {
  const color = value !== "0" && value !== "…" && value !== "—" ? `var(--${tone})` : "var(--ink)";
  return (
    <div
      role="group"
      aria-label={label}
      style={{ flex: "1 1 150px", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 14px", background: "var(--surface)" }}
    >
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{label}</div>
      {note && <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{note}</div>}
    </div>
  );
}

const h3: React.CSSProperties = { fontSize: 15, margin: "0 0 8px", color: "var(--ink)" };
const card: React.CSSProperties = { border: "1px solid var(--border)", borderRadius: 8, padding: "12px 16px", marginBottom: 16 };
const errorText: React.CSSProperties = { ...muted, color: "var(--crit)" };

export default function ArchitectureHealthTab(): React.ReactElement {
  const adoptions = useAdoptions(true);
  const rollup = useCapabilityRollup(true);
  const findings = useCapabilityFindings();
  const businessCaps = useCapabilities();
  const orgFindings = useCapabilityOrgFindings();
  const orgCounts = orgFindings.data?.counts;

  const att = adoptionsNeedingAttention(adoptions.data?.items);
  const exposed = exposedCapabilities(rollup.data);
  const adoptionCount = adoptions.data?.items.length ?? 0;

  return (
    <div>
      <p style={{ ...muted, fontSize: 13, marginTop: 0 }}>
        Pattern conformance and capability-model findings, computed live from the registries. Nothing here is stored.
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 20 }}>
        <Tile label="Non-conformant adoptions" value={tileValue(adoptions, att.nonConformant)} tone="crit" />
        <Tile label="Indeterminate adoptions" value={tileValue(adoptions, att.indeterminate)} tone="info" />
        <Tile label="Exposed capabilities" value={tileValue(rollup, exposed.length)} tone="warn" />
        <Tile
          label="Overlaps"
          value={tileValue(findings, overlapCounts(findings.data).needsAttention)}
          tone="warn"
          note={findings.data ? `${overlapCounts(findings.data).explained} explained` : undefined}
        />
        <Tile label="Gaps" value={tileValue(findings, gapCount(findings.data))} tone="info" />
        {/* ADP-m7x: 941 capability <-> org unit findings. */}
        <Tile
          label="No accountable owner"
          value={tileValue(orgFindings, orgCounts?.no_owner ?? 0)}
          tone="warn"
          note={orgCounts ? `of ${orgCounts.l1_l2_total} L1/L2` : undefined}
        />
        <Tile label="Shared-service candidates" value={tileValue(orgFindings, orgCounts?.shared_service ?? 0)} tone="info" />
        <Tile
          label="Unmapped L3s"
          value={tileValue(orgFindings, orgCounts?.unmapped ?? 0)}
          tone="warn"
          note={orgCounts ? `of ${orgCounts.l3_total} L3` : undefined}
        />
      </div>

      <section aria-label="Pattern conformance" style={card}>
        <h3 style={h3}>Patterns</h3>
        {adoptions.isLoading ? (
          <div style={muted}>Evaluating adoptions…</div>
        ) : adoptions.error ? (
          <div role="alert" style={errorText}>Failed to load pattern conformance.</div>
        ) : adoptionCount === 0 ? (
          <div style={muted}>No patterns have been adopted yet.</div>
        ) : (
          <>
            {att.attention.length === 0 ? (
              <div style={muted}>Every adoption is conformant or not applicable.</div>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {att.attention.map((a) => (
                  <li key={a.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 0", fontSize: 13 }}>
                    {a.status && <StatusBadge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</StatusBadge>}
                    <EntityLink kind="adoption" id={a.id} title="Open on the Patterns screen">{a.name}</EntityLink>
                    <span style={{ ...muted, fontSize: 11 }}>
                      {a.pattern_name ?? a.pattern_key} · {SCOPE_LABELS[a.scope_type]}
                      {a.scope_name ? `: ${a.scope_name}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div style={{ ...muted, marginTop: 8 }}>
              {att.conformant} conformant · {att.notApplicable} not applicable
            </div>
            {att.indeterminate > 0 && (
              <div style={{ ...muted, marginTop: 4 }}>
                Indeterminate can mean the pattern depends on data you can't see (risk, cost or governance fields), or on registry data that is missing.
              </div>
            )}
          </>
        )}
      </section>

      <section aria-label="Capability model" style={card}>
        <h3 style={h3}>Capabilities</h3>

        <section aria-label="Exposed capabilities" style={{ marginBottom: 14 }}>
          <h4 style={{ fontSize: 13, margin: "0 0 4px", color: "var(--ink-2)" }}>
            Business capabilities exposed to retiring or past-end-of-life technology
          </h4>
          {rollup.isLoading ? (
            <div style={muted}>Loading…</div>
          ) : rollup.error ? (
            <div role="alert" style={errorText}>Failed to load capability exposure.</div>
          ) : exposed.length === 0 ? (
            <div style={muted}>No business capability depends on retiring or past-end-of-life technology.</div>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {exposed.map((c) => (
                <li key={c.capability_id} style={{ padding: "3px 0", fontSize: 13 }}>
                  {c.exposure.worst && <BandChip band={c.exposure.worst} />}{" "}
                  <CapWithPath
                    kind="business"
                    cap={{ id: c.capability_id, name: c.name, level: c.level, path: pathOf(c.capability_id, businessCaps.data?.items) }}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        <h4 style={{ fontSize: 13, margin: "0 0 4px", color: "var(--ink-2)" }}>Overlaps</h4>
        <div style={{ marginBottom: 14 }}>
          <CapFindingsViews mode="overlaps" />
        </div>
        <CapFindingsViews mode="gaps" />
      </section>

      <section aria-label="Organization" style={card}>
        <h3 style={h3}>Organization</h3>
        <OrgFindings onOpenCapability={(id) => goToEntity("business_capability", id)} />
      </section>
    </div>
  );
}

/** L1 › L2 path for a business capability (the roll-up carries no parent ids). Empty while the
 *  capability list is unavailable -- the name still shows and still navigates. */
function pathOf(capId: string, all: BusinessCapability[] | undefined): { id: string; name: string; level: number }[] {
  const byId = new Map((all ?? []).map((c) => [c.id, c]));
  const out: { id: string; name: string; level: number }[] = [];
  const seen = new Set([capId]);
  let parentId = byId.get(capId)?.parent_id ?? null;
  while (parentId && !seen.has(parentId)) {
    seen.add(parentId);
    const parent = byId.get(parentId);
    if (!parent) break;
    out.unshift({ id: parent.id, name: parent.name, level: parent.level });
    parentId = parent.parent_id;
  }
  return out;
}
