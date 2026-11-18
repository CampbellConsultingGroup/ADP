// 937-application-capabilities: Applications -> Capabilities tab. Catalog tree on the left (or
// the "missing technical capability" gaps list), the selected capability's detail on the right,
// and the mapping guidance from ADP-6et.

import { useState } from "react";
import type React from "react";
import type { ApplicationCapability } from "../api/appCapabilities";
import { MISSING_TECHNICAL_CAPABILITY, useAppCapabilities } from "../api/appCapabilities";
import AppCapDetail from "./AppCapDetail";
import AppCapTree from "./AppCapTree";
import CapFindingsViews, { type FindingsMode } from "./CapFindingsViews";
import { useCanWriteApplications } from "./appCapNav";
import { useRouteEntity } from "../shell/routing";
import { Tabs } from "../ui/Tabs";

/** Gaps list: every L3 with no technical capability, labelled with its L1/L2 path. */
export function missingTechGaps(items: ApplicationCapability[]): { id: string; name: string; path: string }[] {
  const byId = new Map(items.map((i) => [i.id, i]));
  const path = (i: ApplicationCapability): string => {
    const parts: string[] = [];
    let p = i.parent_id ? byId.get(i.parent_id) : undefined;
    while (p) {
      parts.unshift(p.name);
      p = p.parent_id ? byId.get(p.parent_id) : undefined;
    }
    return parts.join(" › ");
  };
  return items
    .filter((i) => i.warnings.includes(MISSING_TECHNICAL_CAPABILITY))
    .map((i) => ({ id: i.id, name: i.name, path: path(i) }))
    .sort((a, b) => `${a.path} ${a.name}`.localeCompare(`${b.path} ${b.name}`));
}

function Guidance(): React.ReactElement {
  return (
    <details style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 10 }}>
      <summary style={{ cursor: "pointer", color: "var(--ink-3)" }}>How to map capabilities</summary>
      <ul style={{ margin: "6px 0 0", paddingLeft: 18, lineHeight: 1.5 }}>
        <li>Business → Application: map L3 to L3. L1 and L2 are too coarse to say anything.</li>
        <li>Application → Technical: map an L3 to a technical L3 where the dependency is architecturally meaningful, otherwise to its L2. Don't map incidental usage.</li>
        <li>Level 1 is for navigation and grouping only and is never mapped.</li>
        <li>There is no direct business → technical mapping; that view is derived through this layer.</li>
        <li>Keep L3s at a comparable size across the three models, or the mapping levels won't line up.</li>
      </ul>
    </details>
  );
}

export default function AppCapabilitiesView({ initialId = null }: { initialId?: string | null }): React.ReactElement {
  const { data, isLoading, error } = useAppCapabilities();
  const canWrite = useCanWriteApplications();
  const [selectedId, setSelectedId] = useRouteEntity("application_capability", initialId);
  const [mode, setMode] = useState<"tree" | "missing" | FindingsMode>("tree");

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading application capabilities…</div>;
  if (error) return <div role="alert" style={{ padding: 14, color: "var(--crit)", fontSize: 13 }}>Failed to load application capabilities.</div>;

  const items = data?.items ?? [];
  const gaps = missingTechGaps(items);
  const selected = selectedId && items.some((i) => i.id === selectedId) ? selectedId : null;

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 420, borderRight: "1px solid var(--border)", overflow: "auto", padding: 14, flexShrink: 0 }}>
        <Guidance />
        <Tabs
          variant="pill"
          label="Application capability views"
          active={mode}
          onChange={setMode}
          style={{ marginBottom: 10 }}
          tabs={[
            { id: "tree", label: "Catalog" },
            { id: "missing", label: `Missing technical capability (${gaps.length})` },
            // 938-capability-model-analysis US5
            { id: "overlaps", label: "Overlaps" },
            { id: "gaps", label: "Gaps" },
            { id: "shared", label: "Shared" },
            { id: "redundant", label: "Redundant" },
          ]}
        />
        {mode === "tree" && <AppCapTree items={items} selectedId={selected} onSelect={setSelectedId} canWrite={canWrite} />}
        {mode === "missing" && (
          <div aria-label="Missing technical capability">
            {gaps.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Every Level 3 application capability has a technical capability.</div>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {gaps.map((g) => (
                  <li key={g.id} style={{ padding: "4px 0" }}>
                    <button
                      onClick={() => setSelectedId(g.id)}
                      className="ui-btn-plain" style={{ background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: 0 }}
                    >
                      <div style={{ fontSize: 13, color: "var(--ink)" }}>{g.name}</div>
                      <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{g.path}</div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {(mode === "overlaps" || mode === "gaps" || mode === "shared" || mode === "redundant") && (
          // Application capabilities picked from a finding open here, in the detail pane.
          <CapFindingsViews mode={mode} />
        )}
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 18 }}>
        {selected ? (
          <AppCapDetail key={selected} acId={selected} canWrite={canWrite} onDeleted={() => setSelectedId(null)} />
        ) : (
          <div style={{ color: "var(--ink-3)", fontSize: 14 }}>Select an application capability to see and edit its links.</div>
        )}
      </div>
    </div>
  );
}
