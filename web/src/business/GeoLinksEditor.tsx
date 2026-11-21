// 947 GEO-02 (ADP-bo1.2): typed, dated geography links of an application, legal entity or org
// unit. Each link says HOW the subject touches the geography ("deployed in", "licensed in",
// "operates in", ...); the relations a subject may use come from the server's matrix. Shown "as
// of" a date; the server checks every write (relation fits the subject, incorporated in is a
// country and one at a time, no overlapping duplicate, end after start) and names the rule.

import { useMemo, useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { Geography, GeoLink, GeoLinkSubject } from "../api/organization";
import {
  geographyLabel,
  useAddGeoLink,
  useDeleteGeoLink,
  useGeographies,
  useGeoLinkRelations,
  useGeoLinks,
  useUpdateGeoLink,
} from "../api/organization";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const chip: React.CSSProperties = { fontSize: 11, background: "var(--surface-2)", padding: "1px 6px", borderRadius: 8, display: "inline-flex", gap: 4, alignItems: "center" };
const h4: React.CSSProperties = { fontSize: 13, margin: "14px 0 6px", color: "var(--ink-2)" };

export function linkPeriod(l: { valid_from?: string | null; valid_to?: string | null }): string {
  if (!l.valid_from && !l.valid_to) return "";
  if (l.valid_from && l.valid_to) return `${l.valid_from} – ${l.valid_to}`;
  return l.valid_from ? `from ${l.valid_from}` : `until ${l.valid_to}`;
}

function ErrorLine({ error }: { error: string | null }): React.ReactElement | null {
  return error ? (
    <span role="alert" style={{ fontSize: 12, color: "var(--crit)" }}>
      {error}
    </span>
  ) : null;
}

function LinkChip({ link, subject, subjectId, editable }: { link: GeoLink; subject: GeoLinkSubject; subjectId: string; editable: boolean }): React.ReactElement {
  const update = useUpdateGeoLink();
  const remove = useDeleteGeoLink();
  const [editing, setEditing] = useState(false);
  const [from, setFrom] = useState(link.valid_from ?? "");
  const [to, setTo] = useState(link.valid_to ?? "");
  const [error, setError] = useState<string | null>(null);
  const label = geographyLabel(link.geography);
  const p = linkPeriod(link);
  if (editing) {
    return (
      <form
        aria-label={`Dates for ${label}`}
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await update.mutateAsync({ subject, id: subjectId, linkId: link.id, validFrom: from || null, validTo: to || null });
            setEditing(false);
          } catch (err) {
            setError(errorDetail(err));
          }
        }}
        style={{ ...chip, padding: "2px 6px" }}
      >
        {label}
        <input type="date" aria-label={`${label} from`} value={from} onChange={(e) => setFrom(e.target.value)} style={field} />
        <input type="date" aria-label={`${label} until`} value={to} onChange={(e) => setTo(e.target.value)} style={field} />
        <button type="submit" className="ui-btn-link">
          Save
        </button>
        <button type="button" className="ui-btn-link muted" onClick={() => setEditing(false)}>
          Cancel
        </button>
        <ErrorLine error={error} />
      </form>
    );
  }
  return (
    <span style={{ ...chip, opacity: link.active ? 1 : 0.55 }} title={p || "No dates: always"}>
      {label}
      {p && <span style={{ color: "var(--ink-3)" }}>{p}</span>}
      {editable && (
        <>
          <button type="button" className="ui-btn-plain" aria-label={`Change dates of ${label}`} onClick={() => setEditing(true)} style={{ color: "var(--ink-3)" }}>
            ✎
          </button>
          <button
            type="button"
            className="ui-btn-plain"
            aria-label={`Remove ${label}`}
            onClick={() => remove.mutate({ subject, id: subjectId, linkId: link.id })}
            style={{ color: "var(--ink-3)" }}
          >
            ×
          </button>
        </>
      )}
    </span>
  );
}

function sortGeos(items: Geography[]): Geography[] {
  // Countries first, then the nodes of each hierarchy; Global last.
  const rank = (g: Geography) => (g.entity === "place" || g.code ? 0 : g.level === 1 ? 2 : 1);
  return [...items].sort((a, b) => rank(a) - rank(b) || geographyLabel(a).localeCompare(geographyLabel(b)));
}

function AddLink({ subject, subjectId, relations }: { subject: GeoLinkSubject; subjectId: string; relations: { relation: string; label: string; place_only?: boolean }[] }): React.ReactElement {
  const add = useAddGeoLink();
  const geos = useGeographies();
  const [relation, setRelation] = useState(relations[0]?.relation ?? "");
  const [geo, setGeo] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const placeOnly = relations.find((r) => r.relation === relation)?.place_only ?? false;
  const options = useMemo(() => {
    const items = geos.data?.items ?? [];
    return sortGeos(placeOnly ? items.filter((g) => g.entity === "place" || !!g.code) : items);
  }, [geos.data, placeOnly]);
  return (
    <form
      aria-label="Add a geography link"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!relation || !geo) return;
        setError(null);
        try {
          await add.mutateAsync({ subject, id: subjectId, relation, geographyId: geo, validFrom: from || null, validTo: to || null });
          setGeo("");
          setFrom("");
          setTo("");
        } catch (err) {
          setError(errorDetail(err));
        }
      }}
      style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginTop: 8 }}
    >
      <select aria-label="Relation" value={relation} onChange={(e) => setRelation(e.target.value)} style={field}>
        {relations.map((r) => (
          <option key={r.relation} value={r.relation}>
            {r.label}
          </option>
        ))}
      </select>
      <select aria-label="Geography" value={geo} onChange={(e) => setGeo(e.target.value)} style={field}>
        <option value="">{placeOnly ? "Choose a country…" : "Choose a country, region or node…"}</option>
        {options.map((g) => (
          <option key={g.id} value={g.id}>
            {geographyLabel(g)}
          </option>
        ))}
      </select>
      <label style={muted}>
        from <input type="date" aria-label="Link from" value={from} onChange={(e) => setFrom(e.target.value)} style={field} />
      </label>
      <label style={muted}>
        until <input type="date" aria-label="Link until" value={to} onChange={(e) => setTo(e.target.value)} style={field} />
      </label>
      <button type="submit" className="ui-btn ui-btn-sm" disabled={!relation || !geo || add.isPending}>
        Add
      </button>
      <ErrorLine error={error} />
    </form>
  );
}

export default function GeoLinksEditor({
  subject,
  subjectId,
  canWrite,
  title = "Geography",
  hint,
}: {
  subject: GeoLinkSubject;
  subjectId: string;
  canWrite: boolean;
  title?: string;
  hint?: string;
}): React.ReactElement {
  const [asOf, setAsOf] = useState("");
  const [showAll, setShowAll] = useState(false);
  const matrix = useGeoLinkRelations();
  const links = useGeoLinks(subject, subjectId, asOf || null, showAll);
  const relations = matrix.data?.subjects[subject] ?? [];
  const items = links.data?.items ?? [];
  const byRelation = new Map<string, GeoLink[]>();
  for (const l of items) byRelation.set(l.relation, [...(byRelation.get(l.relation) ?? []), l]);

  return (
    <section aria-label={`${title} links`}>
      <h4 style={h4}>{title}</h4>
      {hint && <div style={{ ...muted, marginBottom: 6 }}>{hint}</div>}
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", ...muted }}>
        <label>
          As of <input type="date" aria-label="Links as of" value={asOf} onChange={(e) => setAsOf(e.target.value)} style={field} />
        </label>
        {asOf && (
          <button type="button" className="ui-btn-link muted" onClick={() => setAsOf("")}>
            Today
          </button>
        )}
        <label>
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show links from other periods
        </label>
      </div>
      {links.isLoading || matrix.isLoading ? (
        <div style={muted}>Loading…</div>
      ) : links.error ? (
        <div role="alert" style={{ ...muted, color: "var(--crit)" }}>
          Failed to load geography links.
        </div>
      ) : (
        <dl style={{ margin: "8px 0 0" }}>
          {relations.map((r) => {
            const these = byRelation.get(r.relation) ?? [];
            return (
              <div key={r.relation} style={{ display: "flex", gap: 8, padding: "3px 0", alignItems: "baseline" }}>
                <dt style={{ fontSize: 12, color: "var(--ink-2)", flex: "0 0 210px" }}>{r.label}</dt>
                <dd style={{ margin: 0, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {these.length === 0 ? (
                    <span style={muted}>—</span>
                  ) : (
                    these.map((l) => <LinkChip key={l.id} link={l} subject={subject} subjectId={subjectId} editable={canWrite} />)
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
      {canWrite && relations.length > 0 && <AddLink subject={subject} subjectId={subjectId} relations={relations} />}
    </section>
  );
}
