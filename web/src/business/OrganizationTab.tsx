// 940-org-units-geography (ADP-55k.1): Business Architecture -> Organization. Two governed
// reference trees -- org units (who) and geography (where, a separate axis) -- plus the review
// queue that maps free-text business units onto org units. Later specs in epic ADP-55k map
// capabilities to these.

import { useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { Geography } from "../api/organization";
import {
  ORG_UNIT_KIND_LABEL,
  useDeleteOrgUnit,
  useGeographies,
  useLinkGeography,
  useOrgUnit,
  useOrgUnits,
  useUnlinkGeography,
  useUnmatched,
  useUpdateOrgUnit,
} from "../api/organization";
import { useBusinessWrite } from "../application/appCapNav";
import GeographyTree from "./GeographyTree";
import OrgUnitTree from "./OrgUnitTree";
import UnmatchedList from "./UnmatchedList";
import OrgFindings from "./OrgFindings";
import OrgUnitFootprint from "./OrgUnitFootprint";
import { confirmAction } from "../ui/confirm";

type Section = "org-units" | "geography" | "unmatched" | "findings";

/** ADP-blp.65: the server's answer for WRITE_BUSINESS_ARCH (it used to borrow WRITE_APPLICATION's). */
export function useCanWriteBusiness(): boolean {
  return useBusinessWrite().allowed;
}

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const h4: React.CSSProperties = { fontSize: 13, margin: "14px 0 6px", color: "var(--ink-2)" };

function geoLabel(g: Geography): string {
  return g.code ? `${g.name} (${g.code})` : `${g.name} — ${g.kind}`;
}

function OrgUnitDetailPanel({
  id,
  canWrite,
  onDeleted,
  onOpenCapability,
}: {
  id: string;
  canWrite: boolean;
  onDeleted: () => void;
  onOpenCapability?: (id: string) => void;
}): React.ReactElement {
  const { data, isLoading } = useOrgUnit(id);
  const geos = useGeographies();
  const update = useUpdateOrgUnit();
  const del = useDeleteOrgUnit();
  const link = useLinkGeography();
  const unlink = useUnlinkGeography();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [addGeo, setAddGeo] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !data) return <div style={muted}>Loading…</div>;
  const allGeos = (geos.data?.items ?? []).filter((g) => g.kind !== "global").sort((a, b) => a.name.localeCompare(b.name));
  const linked = new Set(data.geography_ids);
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  return (
    <div aria-label={`Org unit ${data.name}`}>
      {data.path.length > 0 && <div style={muted}>{data.path.map((p) => p.name).join(" › ")}</div>}
      {editing ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await update.mutateAsync({ id, body: { name: name.trim(), description: description.trim() || null } });
              setEditing(false);
            });
          }}
          style={{ display: "flex", flexDirection: "column", gap: 6, margin: "6px 0" }}
        >
          <input aria-label="Org unit name" value={name} onChange={(e) => setName(e.target.value)} style={{ ...field, fontSize: 14 }} />
          <textarea aria-label="Org unit description" value={description} onChange={(e) => setDescription(e.target.value)} style={field} rows={2} />
          <div style={{ display: "flex", gap: 6 }}>
            <button type="submit" className="ui-btn ui-btn-primary ui-btn-sm" disabled={!name.trim()}>
              Save
            </button>
            <button type="button" className="ui-btn ui-btn-sm" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <h3 style={{ margin: "2px 0", fontSize: 17 }}>{data.name}</h3>
          <span style={muted}>{ORG_UNIT_KIND_LABEL[data.kind]}</span>
          {canWrite && (
            <>
              <button
                className="ui-btn ui-btn-sm"
                style={{ marginLeft: "auto" }}
                onClick={() => {
                  setName(data.name);
                  setDescription(data.description ?? "");
                  setEditing(true);
                }}
              >
                Edit
              </button>
              <button
                className="ui-btn ui-btn-sm"
                style={{ color: "var(--crit)" }}
                onClick={async () => {
                  if (!(await confirmAction(`Delete "${data.name}"? Applications it owns keep their free-text business unit and lose the link.`))) return;
                  void run(async () => {
                    await del.mutateAsync(id);
                    onDeleted();
                  });
                }}
              >
                Delete
              </button>
            </>
          )}
        </div>
      )}
      {!editing && data.description && <p style={{ fontSize: 13, color: "var(--ink-2)", margin: "4px 0" }}>{data.description}</p>}
      {error && (
        <div role="alert" style={{ fontSize: 12, color: "var(--crit)", margin: "6px 0" }}>
          {error}
        </div>
      )}

      <h4 style={h4}>Primary geography</h4>
      {canWrite ? (
        <select
          aria-label="Primary geography"
          value={data.primary_geography_id ?? ""}
          onChange={(e) => void run(() => update.mutateAsync({ id, body: { primary_geography_id: e.target.value || null } }))}
          style={field}
        >
          <option value="">None</option>
          {allGeos.map((g) => (
            <option key={g.id} value={g.id}>
              {geoLabel(g)}
            </option>
          ))}
        </select>
      ) : (
        <div style={{ fontSize: 13 }}>{allGeos.find((g) => g.id === data.primary_geography_id)?.name ?? "None"}</div>
      )}
      <div style={muted}>For organizations whose business units are themselves geographic (e.g. “Europe Retail”).</div>

      <h4 style={h4}>Operates in ({data.geographies.length})</h4>
      {data.geographies.length === 0 ? (
        <div style={muted}>No geographies yet.</div>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {data.geographies.map((g) => (
            <li key={g.id} style={{ fontSize: 13, padding: "2px 0", display: "flex", gap: 8 }}>
              {g.name}
              {canWrite && (
                <button
                  aria-label={`Remove ${g.name}`}
                  onClick={() => void run(() => unlink.mutateAsync({ id, geographyId: g.id }))}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--crit)", fontSize: 11 }}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canWrite && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!addGeo) return;
            void run(async () => {
              await link.mutateAsync({ id, geographyId: addGeo });
              setAddGeo("");
            });
          }}
          style={{ display: "flex", gap: 6, marginTop: 6 }}
        >
          <select aria-label="Add geography" value={addGeo} onChange={(e) => setAddGeo(e.target.value)} style={field}>
            <option value="">Add a region or country…</option>
            {allGeos
              .filter((g) => !linked.has(g.id))
              .map((g) => (
                <option key={g.id} value={g.id}>
                  {geoLabel(g)}
                </option>
              ))}
          </select>
          <button type="submit" className="ui-btn ui-btn-sm" disabled={!addGeo}>
            Link
          </button>
        </form>
      )}

      <h4 style={h4}>Owns applications ({data.applications.length})</h4>
      {data.applications.length === 0 ? (
        <div style={muted}>None. Set an application's owning org unit on its form, or resolve values in Unmatched.</div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {data.applications.map((a) => (
            <li key={a.id}>{a.name}</li>
          ))}
        </ul>
      )}

      {/* 941-capability-org-mappings US4 */}
      <OrgUnitFootprint orgUnitId={id} onOpenCapability={onOpenCapability} />
    </div>
  );
}

const tab = (active: boolean): React.CSSProperties => ({
  fontSize: 12,
  padding: "3px 10px",
  border: "1px solid var(--border)",
  borderRadius: 4,
  background: active ? "var(--accent)" : "var(--surface)",
  color: active ? "#fff" : "var(--ink-2)",
  cursor: "pointer",
});

export default function OrganizationTab({ onOpenCapability }: { onOpenCapability?: (id: string) => void } = {}): React.ReactElement {
  const canWrite = useCanWriteBusiness();
  const orgUnits = useOrgUnits();
  const unmatched = useUnmatched();
  const [section, setSection] = useState<Section>("org-units");
  const [selected, setSelected] = useState<string | null>(null);
  const items = orgUnits.data?.items ?? [];
  const current = selected && items.some((i) => i.id === selected) ? selected : null;
  const unmatchedCount = unmatched.data?.total ?? 0;

  return (
    <div>
      <p style={{ ...muted, fontSize: 13, marginTop: 0 }}>
        Who performs and owns the work (org units) and where (geography) are kept separate from the capability model, so a
        reorg changes mappings, not capabilities.
      </p>
      <div role="tablist" aria-label="Organization sections" style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        <button role="tab" aria-selected={section === "org-units"} style={tab(section === "org-units")} onClick={() => setSection("org-units")}>
          Org units
        </button>
        <button role="tab" aria-selected={section === "geography"} style={tab(section === "geography")} onClick={() => setSection("geography")}>
          Geography
        </button>
        <button role="tab" aria-selected={section === "unmatched"} style={tab(section === "unmatched")} onClick={() => setSection("unmatched")}>
          Unmatched{unmatchedCount > 0 ? ` (${unmatchedCount})` : ""}
        </button>
        <button role="tab" aria-selected={section === "findings"} style={tab(section === "findings")} onClick={() => setSection("findings")}>
          Findings
        </button>
      </div>

      {section === "org-units" &&
        (orgUnits.isLoading ? (
          <div style={muted}>Loading org units…</div>
        ) : orgUnits.error ? (
          <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load org units.</div>
        ) : (
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
            <div style={{ flex: "0 0 380px" }}>
              <OrgUnitTree items={items} selectedId={current} onSelect={setSelected} canWrite={canWrite} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              {current ? (
                <OrgUnitDetailPanel
                  key={current}
                  id={current}
                  canWrite={canWrite}
                  onDeleted={() => setSelected(null)}
                  onOpenCapability={onOpenCapability}
                />
              ) : (
                <div style={muted}>Select an org unit to see where it operates and what it owns.</div>
              )}
            </div>
          </div>
        ))}
      {section === "geography" && <GeographyTree canWrite={canWrite} />}
      {section === "unmatched" && <UnmatchedList canWrite={canWrite} />}
      {section === "findings" && <OrgFindings onOpenCapability={onOpenCapability} />}
    </div>
  );
}
