// 938-capability-model-analysis US5: rationalization views on Applications -> Capabilities.
// Overlaps (a business L3 realized by two or more applications), gaps (three lists) and shared
// application capabilities (informational). Derived on the server, never stored; read-only for all.
// 943-mapping-rationale: overlaps split into "needs attention" and "explained" by each
// realization's rationale and geography, and a Redundant view lists mappings marked redundant.

import type React from "react";
import type { LinkedCapRef } from "../api/appCapabilities";
import type { OverlapEntry, OverlapReason, RedundantGroup } from "../api/capAnalysis";
import { useCapabilityFindings } from "../api/capAnalysis";
import { CapLink, CapWithPath, muted } from "./capAnalysisUi";
import { RationaleChip } from "./RealizationList";

export type FindingsMode = "overlaps" | "gaps" | "shared" | "redundant";

const REASON_LABEL: Record<OverlapReason["code"], string> = {
  unclassified: "Unclassified",
  redundant: "Redundant",
  no_target: "No target",
  competing_targets: "Competing targets",
};

function reasonText(reason: OverlapReason, names: Map<string, string>): string {
  const label = REASON_LABEL[reason.code];
  if (reason.application_ids.length === 0) return label;
  return `${label}: ${reason.application_ids.map((id) => names.get(id) ?? id).join(", ")}`;
}

const reasonChip: React.CSSProperties = {
  fontSize: 11,
  color: "var(--crit)",
  background: "var(--crit-wash)",
  borderRadius: 8,
  padding: "1px 6px",
  marginLeft: 6,
  whiteSpace: "nowrap",
};
const hintStyle: React.CSSProperties = { fontSize: 11, color: "var(--warn)", marginLeft: 4 };

const ul: React.CSSProperties = { listStyle: "none", margin: 0, padding: 0 };
const li: React.CSSProperties = { padding: "4px 0", fontSize: 13 };
const intro: React.CSSProperties = { ...muted, marginBottom: 8 };

function GapList({
  title,
  items,
  kind,
  empty,
}: {
  title: string;
  items: LinkedCapRef[];
  kind: "business" | "app-capability";
  empty: string;
}): React.ReactElement {
  return (
    <section aria-label={title} style={{ marginBottom: 14 }}>
      <h4 style={{ fontSize: 13, margin: "0 0 4px", color: "var(--ink-2)" }}>
        {title} ({items.length})
      </h4>
      {items.length === 0 ? (
        <div style={muted}>{empty}</div>
      ) : (
        <ul style={ul}>
          {items.map((c) => (
            <li key={c.id} style={li}>
              <CapWithPath kind={kind} cap={c} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function CapFindingsViews({ mode }: { mode: FindingsMode }): React.ReactElement {
  const { data, isLoading, error } = useCapabilityFindings();
  if (isLoading) return <div style={muted}>Loading…</div>;
  if (error || !data) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load findings.</div>;

  if (mode === "overlaps") {
    const needs = data.overlaps.filter((o) => o.status === "needs_attention");
    const explained = data.overlaps.filter((o) => o.status !== "needs_attention");
    return (
      <div aria-label="Overlaps">
        <div style={intro}>
          Business capabilities realized by more than one application. An overlap needs attention when a mapping is
          unclassified or redundant, there is no target, or two targets cover the same area. One target plus
          tactical, transitional or regional mappings is intended variation. Retired applications are ignored.
        </div>
        {data.overlaps.length === 0 ? (
          <div style={muted}>No business capability is realized by more than one application.</div>
        ) : (
          <>
            <OverlapSection title={`Needs attention (${needs.length})`} items={needs} empty="Every overlap is explained." />
            <OverlapSection title={`Explained (${explained.length})`} items={explained} empty="No overlap is fully explained yet." />
          </>
        )}
      </div>
    );
  }

  if (mode === "redundant") {
    return <RedundantView groups={data.redundant ?? []} />;
  }

  if (mode === "gaps") {
    return (
      <div aria-label="Gaps">
        <GapList
          title="Business capabilities with no application capability"
          items={data.gaps.business_without_app_capability}
          kind="business"
          empty="Every Level 3 business capability has an application capability."
        />
        <GapList
          title="Application capabilities with no business capability"
          items={data.gaps.app_capability_without_business}
          kind="app-capability"
          empty="Every Level 3 application capability supports a business capability."
        />
        <GapList
          title="Application capabilities with no realizing application"
          items={data.gaps.app_capability_without_application}
          kind="app-capability"
          empty="Every Level 3 application capability is realized by an application."
        />
      </div>
    );
  }

  return (
    <div aria-label="Shared">
      <div style={intro}>
        Informational, not a problem: application capabilities that support {data.shared_threshold} or more business capabilities.
      </div>
      {data.shared.length === 0 ? (
        <div style={muted}>No application capability supports {data.shared_threshold} or more business capabilities.</div>
      ) : (
        <ul style={ul}>
          {data.shared.map((s) => (
            <li key={s.app_capability.id} style={li}>
              <CapWithPath kind="app-capability" cap={s.app_capability} />
              <span style={muted}> · supports {s.count}: </span>
              {s.business.map((b, i) => (
                <span key={b.id} style={{ fontSize: 12 }}>
                  {i > 0 && ", "}
                  <CapLink kind="business" id={b.id}>{b.name}</CapLink>
                </span>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function OverlapSection({ title, items, empty }: { title: string; items: OverlapEntry[]; empty: string }): React.ReactElement {
  return (
    <section aria-label={title} style={{ marginBottom: 14 }}>
      <h4 style={{ fontSize: 13, margin: "0 0 4px", color: "var(--ink-2)" }}>{title}</h4>
      {items.length === 0 ? (
        <div style={muted}>{empty}</div>
      ) : (
        <ul style={ul}>
          {items.map((o) => {
            const names = new Map(o.applications.map((a) => [a.id, a.name]));
            return (
              <li key={o.business.id} style={li}>
                <CapWithPath kind="business" cap={o.business} />
                {o.reasons.map((r) => (
                  <span key={r.code} style={reasonChip}>
                    {reasonText(r, names)}
                  </span>
                ))}
                <ul style={{ ...ul, marginLeft: 14 }}>
                  {o.applications.map((a) => (
                    <li key={a.id} style={{ fontSize: 12, padding: "1px 0" }}>
                      <CapLink kind="application" id={a.id}>{a.name}</CapLink>
                      <span style={{ color: "var(--ink-3)" }}> via </span>
                      {a.via.map((v, i) => {
                        const m = a.mappings?.find((x) => x.via.id === v.id);
                        return (
                          <span key={v.id}>
                            {i > 0 && ", "}
                            <CapLink kind="app-capability" id={v.id}>{v.name}</CapLink>
                            {m && (
                              <span style={{ marginLeft: 4, display: "inline-flex", gap: 4, alignItems: "center" }}>
                                <RationaleChip rationale={m.rationale} />
                                {m.geography && <span style={{ color: "var(--ink-3)" }}>{m.geography.name}</span>}
                                {m.hint && <span style={hintStyle}>⚠ {m.hint}</span>}
                              </span>
                            )}
                          </span>
                        );
                      })}
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function RedundantView({ groups }: { groups: RedundantGroup[] }): React.ReactElement {
  return (
    <div aria-label="Redundant">
      <div style={intro}>
        Realizations marked redundant: rationalization candidates. Change a mapping on its application capability.
      </div>
      {groups.length === 0 ? (
        <div style={muted}>No mapping is marked redundant.</div>
      ) : (
        <ul style={ul}>
          {groups.map((g) => (
            <li key={g.business?.id ?? "none"} style={li}>
              {g.business ? <CapWithPath kind="business" cap={g.business} /> : <span style={muted}>Not linked to a business capability</span>}
              <ul style={{ ...ul, marginLeft: 14 }}>
                {g.entries.map((e) => (
                  <li key={`${e.application.id}:${e.app_capability.id}`} style={{ fontSize: 12, padding: "1px 0" }}>
                    <CapLink kind="application" id={e.application.id}>{e.application.name}</CapLink>
                    <span style={{ color: "var(--ink-3)" }}> via </span>
                    <CapLink kind="app-capability" id={e.app_capability.id}>{e.app_capability.name}</CapLink>
                    <span style={{ color: "var(--ink-3)" }}>
                      {" "}· {e.geography ? e.geography.name : "Everywhere"} · TIME {e.application.time_classification ?? "—"} · 7R{" "}
                      {e.application.r_strategy ?? "—"}
                    </span>
                    {e.hint && <span style={hintStyle}>⚠ {e.hint}</span>}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
