// 937-application-capabilities: read-only "application capabilities" lists shown on other
// screens (business capability L3 rows, technical capability rows, application detail). Links are
// edited only on the application capability itself; every item here navigates there.

import { useState } from "react";
import type React from "react";
import type { AppCapSummary } from "../api/appCapabilities";
import {
  MISSING_TECHNICAL_CAPABILITY,
  useAppCapsByApplication,
  useAppCapsByBusinessCapability,
  useAppCapsByTechnicalCapability,
} from "../api/appCapabilities";
import { useOpenAppCapability } from "./appCapNav";
import { useBusinessTechnology } from "../api/capAnalysis";
import { BandChip, CapLink, CapWithPath } from "./capAnalysisUi";

export function AppCapSummaryItems({
  items,
  showRealizedBy = false,
}: {
  items: AppCapSummary[];
  showRealizedBy?: boolean;
}): React.ReactElement {
  const open = useOpenAppCapability();
  if (items.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--ink-3)" }}>None.</div>;
  }
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {items.map((s) => {
        const label = (
          <>
            {s.name}
            {s.path.length > 0 && (
              <span style={{ color: "var(--ink-3)", fontSize: 11 }}> — {s.path.map((p) => p.name).join(" › ")}</span>
            )}
          </>
        );
        return (
          <li key={s.id} style={{ fontSize: 12, padding: "1px 0" }}>
            {open ? (
              <button
                onClick={() => open(s.id)}
                title="Open in Applications → Capabilities"
                style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: "var(--accent)", textAlign: "left", fontSize: 12 }}
              >
                {label}
              </button>
            ) : (
              <span>{label}</span>
            )}
            {s.warnings.includes(MISSING_TECHNICAL_CAPABILITY) && (
              <span style={{ fontSize: 10, color: "var(--warn)", marginLeft: 6 }}>⚠ no technical capability</span>
            )}
            {showRealizedBy && (
              <span style={{ fontSize: 11, color: "var(--ink-3)", marginLeft: 6 }}>
                {s.realized_by.length > 0 ? `realized by ${s.realized_by.map((a) => a.name).join(", ")}` : "no application yet"}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Expander({
  label,
  children,
}: {
  label: string;
  children: (open: boolean) => React.ReactNode;
}): React.ReactElement {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginLeft: 26, marginBottom: 2 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{ background: "none", border: "none", padding: 0, cursor: "pointer", fontSize: 11, color: "var(--ink-3)" }}
      >
        {open ? "▾" : "▸"} {label}
      </button>
      {open && <div style={{ marginLeft: 12 }}>{children(open)}</div>}
    </div>
  );
}

function ByBusiness({ capId }: { capId: string }) {
  const { data, isLoading } = useAppCapsByBusinessCapability(capId);
  if (isLoading) return <div style={{ fontSize: 12, color: "var(--ink-3)" }}>Loading…</div>;
  return <AppCapSummaryItems items={data ?? []} showRealizedBy />;
}

function ByTechnical({ tcId }: { tcId: string }) {
  const { data, isLoading } = useAppCapsByTechnicalCapability(tcId);
  if (isLoading) return <div style={{ fontSize: 12, color: "var(--ink-3)" }}>Loading…</div>;
  return <AppCapSummaryItems items={data ?? []} showRealizedBy />;
}

/** Business capability L3 row: the application capabilities supporting it, and who realizes them. */
export function BusinessCapAppCaps({ capId }: { capId: string }): React.ReactElement {
  return <Expander label="Application capabilities">{() => <ByBusiness capId={capId} />}</Expander>;
}

function TechnologyDeps({ capId }: { capId: string }) {
  const { data, isLoading, error } = useBusinessTechnology(capId);
  if (isLoading) return <div style={{ fontSize: 12, color: "var(--ink-3)" }}>Loading…</div>;
  if (error || !data) return <div role="alert" style={{ fontSize: 12, color: "var(--crit)" }}>Failed to load technology dependencies.</div>;
  if (data.items.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--ink-3)" }}>No technical capability is reached through the application layer.</div>;
  }
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {data.items.map((d) => (
        <li key={`${d.via_business_capability.id}:${d.via_app_capability.id}:${d.technical.id}`} style={{ fontSize: 12, padding: "1px 0" }}>
          <BandChip band={d.effective_band} /> <CapWithPath kind="technical" cap={d.technical} />
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>
            {" "}via <CapLink kind="app-capability" id={d.via_app_capability.id}>{d.via_app_capability.name}</CapLink>
            {d.end_of_life_date ? ` · EOL ${d.end_of_life_date}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** 938-capability-model-analysis US4: business L3 row -- the technical capabilities it depends on
 *  through the application layer (derived, never stored; there is no direct business -> technical
 *  link). */
export function BusinessCapTechnology({ capId }: { capId: string }): React.ReactElement {
  return <Expander label="Technology dependencies">{() => <TechnologyDeps capId={capId} />}</Expander>;
}

/** Technical capability row: the application capabilities that depend on it. */
export function TechCapUsedBy({ tcId }: { tcId: string }): React.ReactElement {
  return <Expander label="Used by application capabilities">{() => <ByTechnical tcId={tcId} />}</Expander>;
}

/** Application detail: the application capabilities this application realizes. */
export function ApplicationRealizes({ appId }: { appId: string }): React.ReactElement {
  const { data, isLoading } = useAppCapsByApplication(appId);
  return (
    <section aria-label="Realizes application capabilities">
      <h4 style={{ fontSize: 13, margin: "0 0 6px", color: "var(--ink-2)" }}>Realizes application capabilities</h4>
      {isLoading ? (
        <div style={{ fontSize: 12, color: "var(--ink-3)" }}>Loading…</div>
      ) : (
        <AppCapSummaryItems items={data ?? []} />
      )}
      <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>
        Edited on the application capability (Applications → Capabilities).
      </div>
    </section>
  );
}
