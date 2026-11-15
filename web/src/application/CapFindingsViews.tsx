// 938-capability-model-analysis US5: rationalization views on Applications -> Capabilities.
// Overlaps (a business L3 realized by two or more applications), gaps (three lists) and shared
// application capabilities (informational). Derived on the server, never stored; read-only for all.

import type React from "react";
import type { LinkedCapRef } from "../api/appCapabilities";
import { useCapabilityFindings } from "../api/capAnalysis";
import { CapLink, CapWithPath, muted } from "./capAnalysisUi";

export type FindingsMode = "overlaps" | "gaps" | "shared";

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
    return (
      <div aria-label="Overlaps">
        <div style={intro}>
          Business capabilities realized by more than one application. Each is a rationalization candidate. Retired applications are ignored.
        </div>
        {data.overlaps.length === 0 ? (
          <div style={muted}>No business capability is realized by more than one application.</div>
        ) : (
          <ul style={ul}>
            {data.overlaps.map((o) => (
              <li key={o.business.id} style={li}>
                <CapWithPath kind="business" cap={o.business} />
                <ul style={{ ...ul, marginLeft: 14 }}>
                  {o.applications.map((a) => (
                    <li key={a.id} style={{ fontSize: 12, padding: "1px 0" }}>
                      <CapLink kind="application" id={a.id}>{a.name}</CapLink>
                      <span style={{ color: "var(--ink-3)" }}> via </span>
                      {a.via.map((v, i) => (
                        <span key={v.id}>
                          {i > 0 && ", "}
                          <CapLink kind="app-capability" id={v.id}>{v.name}</CapLink>
                        </span>
                      ))}
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
