// 940-org-units-geography US4: the review queue. Each distinct free-text owning_business_unit value
// with no org-unit link is listed (exact values; "Store Systems" and "Store systems" are separate).
// Mapping links every application with exactly that value. The free text is never changed and
// nothing is created except by the explicit "Create org unit" action (spec D4, SC-004).

import { useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { OrgUnit, UnmatchedValue } from "../api/organization";
import { useOrgUnits, useResolveUnmatched, useUnmatched } from "../api/organization";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const btn: React.CSSProperties = { fontSize: 12, padding: "3px 10px", border: "1px solid var(--accent)", borderRadius: 4, background: "var(--surface)", color: "var(--accent)", cursor: "pointer" };

function label(ou: OrgUnit): string {
  return [...ou.path.map((p) => p.name), ou.name].join(" › ");
}

function Row({
  item,
  orgUnits,
  canWrite,
  onResolved,
}: {
  item: UnmatchedValue;
  orgUnits: OrgUnit[];
  canWrite: boolean;
  onResolved: (message: string) => void;
}): React.ReactElement {
  const resolve = useResolveUnmatched();
  const [mode, setMode] = useState<"map" | "create">("map");
  const [target, setTarget] = useState("");
  const [name, setName] = useState(item.value);
  const [parent, setParent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const parents = orgUnits.filter((o) => o.level < 3);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const result = await resolve.mutateAsync(
        mode === "map"
          ? { value: item.value, org_unit_id: target }
          : { value: item.value, create: { name: name.trim(), parent_id: parent || null } },
      );
      // Reported by the list, not this row: once resolved, the value leaves the list and the row unmounts.
      onResolved(`Linked ${result.updated_count} application${result.updated_count === 1 ? "" : "s"} with “${item.value}” to ${result.org_unit.name}.`);
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  return (
    <li style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <strong style={{ fontSize: 13 }}>“{item.value}”</strong>
        <span style={muted}>
          {item.application_count} application{item.application_count === 1 ? "" : "s"}
          {item.sample_applications.length > 0 && `: ${item.sample_applications.map((a) => a.name).join(", ")}`}
          {item.application_count > item.sample_applications.length && ", …"}
        </span>
      </div>
      {canWrite && (
          <form onSubmit={submit} style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginTop: 6 }}>
            <select aria-label={`Action for ${item.value}`} value={mode} onChange={(e) => setMode(e.target.value as "map" | "create")} style={field}>
              <option value="map">Map to org unit</option>
              <option value="create">Create org unit</option>
            </select>
            {mode === "map" ? (
              <select aria-label={`Org unit for ${item.value}`} value={target} onChange={(e) => setTarget(e.target.value)} style={field}>
                <option value="">Select…</option>
                {orgUnits.map((o) => (
                  <option key={o.id} value={o.id}>
                    {label(o)}
                  </option>
                ))}
              </select>
            ) : (
              <>
                <input aria-label={`New org unit name for ${item.value}`} value={name} onChange={(e) => setName(e.target.value)} style={field} />
                <select aria-label={`Parent for ${item.value}`} value={parent} onChange={(e) => setParent(e.target.value)} style={field}>
                  <option value="">(no parent — enterprise)</option>
                  {parents.map((o) => (
                    <option key={o.id} value={o.id}>
                      {label(o)}
                    </option>
                  ))}
                </select>
              </>
            )}
            <button
              type="submit"
              style={btn}
              disabled={resolve.isPending || (mode === "map" ? !target : !name.trim())}
            >
              {mode === "map" ? "Map" : "Create & map"}
            </button>
            {error && (
              <span role="alert" style={{ fontSize: 11, color: "var(--crit)" }}>
                {error}
              </span>
            )}
          </form>
      )}
    </li>
  );
}

export default function UnmatchedList({ canWrite }: { canWrite: boolean }): React.ReactElement {
  const { data, isLoading, error } = useUnmatched();
  const orgUnits = useOrgUnits();
  const [message, setMessage] = useState<string | null>(null);
  if (isLoading) return <div style={muted}>Loading…</div>;
  if (error) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load unmatched values.</div>;
  const items = data?.items ?? [];
  return (
    <div>
      <p style={{ ...muted, marginTop: 0 }}>
        Free-text “owning business unit” values on applications that aren't linked to an org unit yet. Mapping a value links
        every application with exactly that text; the text itself is kept. Values that differ only in case or spacing are listed
        separately, so you decide whether they're the same unit.
      </p>
      {message && (
        <div role="status" style={{ fontSize: 12, color: "var(--good, #1a7f37)", marginBottom: 8 }}>
          {message}
        </div>
      )}
      {items.length === 0 ? (
        <div style={{ ...muted, fontSize: 13 }}>Every business unit value is matched.</div>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {items.map((u) => (
            <Row key={u.value} item={u} orgUnits={orgUnits.data?.items ?? []} canWrite={canWrite} onResolved={setMessage} />
          ))}
        </ul>
      )}
    </div>
  );
}
