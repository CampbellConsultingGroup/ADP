// 941-capability-org-mappings (ADP-55k.2): who owns and performs a business capability.
//
// CapabilityOrgChips sits in each Capabilities row: the owner (own, or inherited from the nearest
// owned ancestor, shown muted) and, on L3s, the performers. CapabilityOrgEditor is the content of
// the row's "Organization" expander: the owner on L1/L2 (replace-only, at most one), performers
// (optional geography) and contributors on L3. Everything shown is derived by the server.

import { useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { CapabilityOrgMapping, CapabilityOrgView, Geography, OrgUnit } from "../api/organization";
import {
  capabilityOrgView,
  useAddCapabilityMapping,
  useCapabilityOrgMappings,
  useGeographies,
  useOrgUnits,
  useRemoveCapabilityMapping,
  useSetCapabilityOwner,
  geographyLabel,
} from "../api/organization";

// Bounded so a long owner or performer list never widens the row (found live: an unbounded chip
// pushed the row's controls off-screen and gave the page a horizontal scrollbar). Full text is
// in the title.
const chip: React.CSSProperties = {
  marginLeft: 6,
  fontSize: 10,
  padding: "1px 6px",
  borderRadius: 8,
  fontWeight: 500,
  whiteSpace: "nowrap",
  display: "inline-block",
  maxWidth: "100%",
  boxSizing: "border-box",
  overflow: "hidden",
  textOverflow: "ellipsis",
  verticalAlign: "middle",
};
const field: React.CSSProperties = { fontSize: 12, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const btn: React.CSSProperties = {
  fontSize: 12,
  padding: "3px 10px",
  border: "1px solid var(--accent)",
  borderRadius: 4,
  background: "var(--surface)",
  color: "var(--accent)",
  cursor: "pointer",
};
const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };

function ouLabel(ou: OrgUnit): string {
  return [...ou.path.map((p) => p.name), ou.name].join(" › ");
}

function performerLabel(m: CapabilityOrgMapping): string {
  return m.geography ? `${m.org_unit.name} (${m.geography.name})` : m.org_unit.name;
}

/** The capability's view, or an empty one when nothing is mapped. */
function useView(capabilityId: string, level: number): CapabilityOrgView {
  const { data } = useCapabilityOrgMappings();
  return (
    capabilityOrgView(data, capabilityId) ?? {
      capability_id: capabilityId,
      level,
      owner: null,
      effective_owner: null,
      owner_inherited_from: null,
      performers: [],
      contributors: [],
    }
  );
}

export function CapabilityOrgChips({ capabilityId, level }: { capabilityId: string; level: number }): React.ReactElement | null {
  const view = useView(capabilityId, level);
  const owner = view.effective_owner;
  const performers = Array.from(new Set(view.performers.map((p) => p.org_unit.name)));
  if (!owner && performers.length === 0) return null;
  return (
    <>
      {owner && (
        <span
          data-testid="owner-chip"
          title={
            view.owner_inherited_from
              ? `Owner: ${owner.name}, inherited from ${view.owner_inherited_from.name}`
              : `Accountable owner: ${owner.name}`
          }
          style={
            view.owner_inherited_from
              ? { ...chip, border: "1px dashed var(--border)", color: "var(--ink-3)" }
              : { ...chip, background: "var(--accent-wash)", color: "var(--accent-2)" }
          }
        >
          Owner: {owner.name}
          {view.owner_inherited_from && " (inherited)"}
        </span>
      )}
      {performers.length > 0 && (
        <span data-testid="performer-chip" title={`Performed by: ${performers.join(", ")}`} style={{ ...chip, background: "var(--surface-2)", color: "var(--ink-2)" }}>
          Performed by: {performers.join(", ")}
        </span>
      )}
    </>
  );
}

function OwnerEditor({ view, orgUnits, canWrite }: { view: CapabilityOrgView; orgUnits: OrgUnit[]; canWrite: boolean }): React.ReactElement {
  const setOwner = useSetCapabilityOwner();
  const [error, setError] = useState<string | null>(null);
  const change = async (orgUnitId: string | null) => {
    setError(null);
    try {
      await setOwner.mutateAsync({ capabilityId: view.capability_id, orgUnitId });
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  return (
    <div>
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>Owner</span>
        {canWrite ? (
          <select
            aria-label="Owner"
            value={view.owner?.id ?? ""}
            disabled={setOwner.isPending}
            onChange={(e) => void change(e.target.value || null)}
            style={field}
          >
            <option value="">(no owner of its own)</option>
            {orgUnits.map((o) => (
              <option key={o.id} value={o.id}>
                {ouLabel(o)}
              </option>
            ))}
          </select>
        ) : (
          <span style={{ fontSize: 12 }}>{view.owner?.name ?? "None of its own"}</span>
        )}
      </div>
      {!view.owner && view.effective_owner && view.owner_inherited_from && (
        <div style={{ ...muted, marginTop: 4 }}>
          Inherits {view.effective_owner.name} from {view.owner_inherited_from.name}.
        </div>
      )}
      {!view.effective_owner && (
        <div style={{ ...muted, marginTop: 4, color: "var(--warn)" }}>No accountable owner — set one here or on its L1.</div>
      )}
      {error && (
        <div role="alert" style={{ fontSize: 11, color: "var(--crit)", marginTop: 4 }}>
          {error}
        </div>
      )}
    </div>
  );
}

function geographyOptions(geos: Geography[], orgUnit: OrgUnit | undefined): { operating: Geography[]; rest: Geography[] } {
  const usable = geos.filter((g) => g.kind !== "global").sort((a, b) => a.name.localeCompare(b.name));
  const ids = new Set(orgUnit?.geography_ids ?? []);
  return { operating: usable.filter((g) => ids.has(g.id)), rest: usable.filter((g) => !ids.has(g.id)) };
}

function MappingEditor({ view, orgUnits, canWrite }: { view: CapabilityOrgView; orgUnits: OrgUnit[]; canWrite: boolean }): React.ReactElement {
  const geos = useGeographies();
  const add = useAddCapabilityMapping();
  const remove = useRemoveCapabilityMapping();
  const [role, setRole] = useState<"performer" | "contributor">("performer");
  const [orgUnitId, setOrgUnitId] = useState("");
  const [geographyId, setGeographyId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { operating, rest } = geographyOptions(geos.data?.items ?? [], orgUnits.find((o) => o.id === orgUnitId));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await add.mutateAsync({
        capability_id: view.capability_id,
        org_unit_id: orgUnitId,
        role,
        geography_id: role === "performer" && geographyId ? geographyId : null,
      });
      setOrgUnitId("");
      setGeographyId("");
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  const drop = async (id: string) => {
    setError(null);
    try {
      await remove.mutateAsync(id);
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  const list = (title: string, items: CapabilityOrgMapping[], empty: string) => (
    <div style={{ marginTop: 6 }}>
      <div style={{ fontSize: 12, fontWeight: 600 }}>{title}</div>
      {items.length === 0 ? (
        <div style={muted}>{empty}</div>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {items.map((m) => (
            <li key={m.id} style={{ fontSize: 12, display: "flex", gap: 6, alignItems: "center", padding: "2px 0" }}>
              <span>{m.role === "performer" ? performerLabel(m) : m.org_unit.name}</span>
              {m.outside_operating_geographies && (
                <span
                  title="This geography isn't one of the org unit's operating geographies"
                  style={{ fontSize: 10, color: "var(--warn)", background: "var(--warn-wash)", padding: "0 5px", borderRadius: 8 }}
                >
                  outside where it operates
                </span>
              )}
              {canWrite && (
                <button
                  type="button"
                  aria-label={`Remove ${m.role} ${performerLabel(m)}`}
                  onClick={() => void drop(m.id)}
                  style={{ ...btn, border: "none", padding: "0 4px", color: "var(--crit)" }}
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <div>
      {view.effective_owner ? (
        <div style={muted}>
          Owner: {view.effective_owner.name}
          {view.owner_inherited_from && ` (inherited from ${view.owner_inherited_from.name})`}
        </div>
      ) : (
        <div style={{ ...muted, color: "var(--warn)" }}>No accountable owner — owners are set on its L2 or L1.</div>
      )}
      {list("Performers", view.performers, "No one performs this capability yet.")}
      {list("Contributors", view.contributors, "No contributors.")}
      {canWrite && (
        <form onSubmit={submit} style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
          <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as "performer" | "contributor")} style={field}>
            <option value="performer">Performer</option>
            <option value="contributor">Contributor</option>
          </select>
          <select aria-label="Org unit" value={orgUnitId} onChange={(e) => setOrgUnitId(e.target.value)} style={field}>
            <option value="">Select an org unit…</option>
            {orgUnits.map((o) => (
              <option key={o.id} value={o.id}>
                {ouLabel(o)}
              </option>
            ))}
          </select>
          {role === "performer" && (
            <select aria-label="Geography" value={geographyId} onChange={(e) => setGeographyId(e.target.value)} style={field}>
              <option value="">Everywhere / not specific</option>
              {operating.length > 0 && (
                <optgroup label="Where it operates">
                  {operating.map((g) => (
                    <option key={g.id} value={g.id}>
                      {geographyLabel(g)}
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label={operating.length > 0 ? "Elsewhere" : "All"}>
                {rest.map((g) => (
                  <option key={g.id} value={g.id}>
                    {geographyLabel(g)}
                  </option>
                ))}
              </optgroup>
            </select>
          )}
          <button type="submit" style={btn} disabled={!orgUnitId || add.isPending}>
            Add
          </button>
        </form>
      )}
      {error && (
        <div role="alert" style={{ fontSize: 11, color: "var(--crit)", marginTop: 4 }}>
          {error}
        </div>
      )}
    </div>
  );
}

export function CapabilityOrgEditor({
  capabilityId,
  level,
  canWrite,
}: {
  capabilityId: string;
  level: number;
  canWrite: boolean;
}): React.ReactElement {
  const view = useView(capabilityId, level);
  const units = useOrgUnits();
  const orgUnits = (units.data?.items ?? []).slice().sort((a, b) => ouLabel(a).localeCompare(ouLabel(b)));
  // Not "no org units yet" while they're still loading (found live).
  if (units.isLoading) return <div style={muted}>Loading…</div>;
  if (orgUnits.length === 0 && canWrite) {
    return <div style={muted}>No org units yet — add them on Business → Organization first.</div>;
  }
  return level === 3 ? (
    <MappingEditor view={view} orgUnits={orgUnits} canWrite={canWrite} />
  ) : (
    <OwnerEditor view={view} orgUnits={orgUnits} canWrite={canWrite} />
  );
}
