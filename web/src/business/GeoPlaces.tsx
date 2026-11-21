// 949 GEO-04 (ADP-bo1.4): Business -> Organization -> Places. Every place (countries, the
// subdivisions added so far, governed custom places such as Lloyd's of London) against every
// hierarchy, as of a date: each cell names the hierarchy's nodes that contain the place. A
// subdivision counts as inside its country everywhere. Subdivisions are added one at a time from
// the pinned ISO 3166-2 list; the server takes the name from that list.

import { useMemo, useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { Geography, PlaceType } from "../api/organization";
import {
  HIERARCHY_KIND_LABEL,
  PLACE_TYPE_LABEL,
  useAddSubdivision,
  useGeoHierarchies,
  useGeographies,
  usePlaceMatrix,
  useSubdivisionCatalog,
} from "../api/organization";
import { Table } from "../ui/primitives";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 3 };

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function AddSubdivision({ countries }: { countries: Geography[] }): React.ReactElement {
  const [country, setCountry] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const catalog = useSubdivisionCatalog(country || null);
  const add = useAddSubdivision();
  const options = (catalog.data?.items ?? []).filter((i) => !i.added);
  return (
    <form
      aria-label="Add a subdivision"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        setMessage(null);
        try {
          const geo = await add.mutateAsync(code);
          setMessage(`Added ${geo.name} (${geo.code}).`);
          setCode("");
        } catch (err) {
          setError(errorDetail(err));
        }
      }}
      style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", margin: "6px 0 10px" }}
    >
      <select aria-label="Country" value={country} onChange={(e) => { setCountry(e.target.value); setCode(""); }} style={field}>
        <option value="">Add a subdivision of…</option>
        {countries.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      {country && (
        <select aria-label="Subdivision" value={code} onChange={(e) => setCode(e.target.value)} style={field} disabled={catalog.isLoading}>
          <option value="">
            {catalog.isLoading ? "Loading…" : options.length === 0 ? "None left to add" : "Choose a subdivision…"}
          </option>
          {options.map((i) => (
            <option key={i.code} value={i.code}>
              {i.name} ({i.code}, {i.type.toLowerCase()})
            </option>
          ))}
        </select>
      )}
      {country && (
        <button type="submit" className="ui-btn ui-btn-xs" disabled={!code || add.isPending}>
          {add.isPending ? "Adding…" : "Add"}
        </button>
      )}
      {message && <span style={muted}>{message}</span>}
      {error && (
        <span role="alert" style={{ fontSize: 12, color: "var(--crit)" }}>
          {error}
        </span>
      )}
    </form>
  );
}

export default function GeoPlaces({ canWrite }: { canWrite: boolean }): React.ReactElement {
  const [asOf, setAsOf] = useState(today());
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [types, setTypes] = useState<"all" | "not-countries">("all");
  const hierarchies = useGeoHierarchies();
  const geographies = useGeographies();
  const matrix = usePlaceMatrix(asOf || null, null);

  const countries = useMemo(
    () => (geographies.data?.items ?? []).filter((g) => g.entity !== "node" && (g.place_type ?? "country") === "country"),
    [geographies.data],
  );
  const columns = (matrix.data?.hierarchies ?? []).filter((h) => !hidden.has(h.id));
  const needle = filter.trim().toLowerCase();
  const rows = (matrix.data?.rows ?? []).filter((r) => {
    if (types === "not-countries" && r.place.place_type === "country") return false;
    if (!needle) return true;
    return r.place.name.toLowerCase().includes(needle) || (r.place.code ?? "").toLowerCase().includes(needle);
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={muted}>
        Every place against every hierarchy, as of a date. A cell names the nodes that contain the place. A subdivision is inside its country, so it shows the
        country&apos;s nodes too. Countries come from ISO 3166-1; subdivisions are added only when needed, from the ISO 3166-2 list.
      </div>
      {canWrite && <AddSubdivision countries={countries} />}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <label style={muted}>
          As of{" "}
          <input type="date" aria-label="Places as of" value={asOf} onChange={(e) => setAsOf(e.target.value)} style={field} />
        </label>
        <input aria-label="Filter places" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by name or code" style={field} />
        <label style={muted}>
          <input type="checkbox" checked={types === "not-countries"} onChange={(e) => setTypes(e.target.checked ? "not-countries" : "all")} /> Only
          subdivisions and custom places
        </label>
      </div>
      <fieldset style={{ border: 0, padding: 0, margin: 0, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <legend style={{ ...muted, marginBottom: 2 }}>Hierarchies shown</legend>
        {(hierarchies.data?.items ?? []).map((h) => (
          <label key={h.id} style={{ fontSize: 12 }}>
            <input
              type="checkbox"
              checked={!hidden.has(h.id)}
              onChange={(e) => {
                const next = new Set(hidden);
                if (e.target.checked) next.delete(h.id);
                else next.add(h.id);
                setHidden(next);
              }}
            />{" "}
            {h.name} <span style={muted}>({HIERARCHY_KIND_LABEL[h.kind]})</span>
          </label>
        ))}
      </fieldset>
      {matrix.isLoading ? (
        <div style={muted}>Loading places…</div>
      ) : matrix.error ? (
        <div role="alert" style={{ ...muted, color: "var(--crit)" }}>
          Failed to load places: {errorDetail(matrix.error)}
        </div>
      ) : (
        <>
          <div style={muted}>
            {rows.length} of {matrix.data?.rows.length ?? 0} places
          </div>
          <Table dense caption="Places by hierarchy" columns={["Place", "Type", ...columns.map((h) => h.name)]}>
            {rows.map((r) => (
              <tr key={r.place.id}>
                <td style={{ paddingLeft: r.place.parent_place_id ? 18 : undefined }}>
                  {r.place.name}
                  {r.place.code && <span style={muted}> ({r.place.code})</span>}
                </td>
                <td style={muted}>{PLACE_TYPE_LABEL[(r.place.place_type ?? "country") as PlaceType]}</td>
                {columns.map((h) => (
                  <td key={h.id}>{(r.cells[h.id] ?? []).map((n) => n.name).join(" · ") || <span style={muted}>—</span>}</td>
                ))}
              </tr>
            ))}
          </Table>
        </>
      )}
    </div>
  );
}
