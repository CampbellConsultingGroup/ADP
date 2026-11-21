// 948 GEO-03 (ADP-bo1.3): framework jurisdiction and derived applicability.
//
// A framework's jurisdiction is a set of places/nodes (e.g. the EU node of a regulatory
// hierarchy) plus trigger relations (e.g. an application "processes personal data of people in").
// Whether it applies to an application or legal entity is derived on read from their typed
// geography links -- an application also counts its legal entities' links ("via") -- and is
// three-valued: applies / does not apply / unknown, always with the reason or the evidence.

import { useMemo, useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { Applicability, ApplicabilityEvidence, ApplicabilityStatus, JurisdictionTrigger } from "../api/compliance";
import {
  APPLICABILITY_LABEL,
  useFrameworkApplicability,
  useFrameworkJurisdiction,
  useSetFrameworkJurisdiction,
  useSubjectApplicability,
} from "../api/compliance";
import { geographyLabel, useGeographies, useGeoLinkRelations } from "../api/organization";
import { EntityLink } from "../shell/EntityLink";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const h4: React.CSSProperties = { fontSize: 14, margin: "16px 0 8px" };
const chip: React.CSSProperties = { fontSize: 11, background: "var(--surface-2)", padding: "1px 6px", borderRadius: 8, display: "inline-flex", gap: 4, alignItems: "center" };

const TONE: Record<ApplicabilityStatus, React.CSSProperties> = {
  applies: { color: "var(--accent)", background: "var(--accent-wash)" },
  does_not_apply: { color: "var(--ink-3)", background: "var(--surface-2)" },
  unknown: { color: "var(--warn)", background: "var(--warn-wash)" },
};

export function StatusPill({ status }: { status: ApplicabilityStatus }): React.ReactElement {
  return <span style={{ ...chip, ...TONE[status], fontWeight: 600 }}>{APPLICABILITY_LABEL[status]}</span>;
}

const HOW: Record<ApplicabilityEvidence["how"], string> = {
  same: "is",
  inside: "is in",
  covers: "covers",
  shares_countries: "shares countries with",
};

/** "Processes personal data of people in Germany (DE), which is in EU (Germany › EU), via Retail GmbH". */
export function evidenceText(e: ApplicabilityEvidence): string {
  const where = geographyLabel(e.geography);
  const scope = geographyLabel(e.jurisdiction_geography);
  const meet = e.how === "same" ? "" : `, which ${HOW[e.how]} ${scope}`;
  const path = e.how === "inside" && (e.path ?? []).length > 2 ? ` (${(e.path ?? []).join(" › ")})` : "";
  const via = e.via_legal_entity ? `, via ${e.via_legal_entity.name}` : "";
  const dates = e.valid_from || e.valid_to ? ` [${e.valid_from ?? "…"} – ${e.valid_to ?? "…"}]` : "";
  return `${e.relation_label} ${where}${meet}${path}${via}${dates}`;
}

function Why({ item }: { item: Applicability }): React.ReactElement {
  if (item.status !== "applies") return <span style={muted}>{item.reason}</span>;
  return (
    <ul style={{ margin: "2px 0 0", paddingLeft: 18, fontSize: 12, color: "var(--ink-2)" }}>
      {(item.evidence ?? []).map((e, i) => (
        <li key={i}>{evidenceText(e)}</li>
      ))}
    </ul>
  );
}

function AsOf({ value, onChange }: { value: string; onChange: (v: string) => void }): React.ReactElement {
  return (
    <label style={muted}>
      As of <input type="date" aria-label="Applicability as of" value={value} onChange={(e) => onChange(e.target.value)} style={field} />
    </label>
  );
}

// ── Subject side: an application or a legal entity ──────────────────────────

export function SubjectApplicability({ subject, subjectId }: { subject: "application" | "legal_entity"; subjectId: string }): React.ReactElement {
  const [asOf, setAsOf] = useState("");
  const { data, isLoading, error } = useSubjectApplicability(subject, subjectId, asOf || null);
  return (
    <section aria-label="Framework applicability">
      <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
        <h4 style={h4}>Which regulations apply</h4>
        <AsOf value={asOf} onChange={setAsOf} />
      </div>
      <div style={{ ...muted, marginBottom: 6 }}>
        Derived from {subject === "application" ? "this application's geography links and those of its legal entities" : "this legal entity's geography links"} and each framework's jurisdiction.
      </div>
      {isLoading ? (
        <div style={muted}>Loading…</div>
      ) : error ? (
        <div role="alert" style={{ ...muted, color: "var(--crit)" }}>
          Failed to load applicability.
        </div>
      ) : (data?.items ?? []).length === 0 ? (
        <div style={muted}>No frameworks yet.</div>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {data?.items.map((i) => (
            <li key={i.framework.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <StatusPill status={i.status} />
                <span style={{ fontSize: 13 }}>{i.framework.name}</span>
              </div>
              <Why item={i} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── Framework side: jurisdiction editor + what it applies to ─────────────────

function JurisdictionEditor({ frameworkId, onDone }: { frameworkId: string; onDone: () => void }): React.ReactElement {
  const current = useFrameworkJurisdiction(frameworkId);
  const geos = useGeographies();
  const matrix = useGeoLinkRelations();
  const save = useSetFrameworkJurisdiction(frameworkId);
  const [geoIds, setGeoIds] = useState<string[]>(() => current.data?.geographies.map((g) => g.id) ?? []);
  const [triggers, setTriggers] = useState<Set<string>>(() => new Set((current.data?.triggers ?? []).map((t) => `${t.subject_type}:${t.relation}`)));
  const [error, setError] = useState<string | null>(null);
  const options = useMemo(
    () => [...(geos.data?.items ?? [])].sort((a, b) => Number(!!b.code) - Number(!!a.code) || geographyLabel(a).localeCompare(geographyLabel(b))),
    [geos.data],
  );
  const byId = new Map(options.map((g) => [g.id, g]));
  const toggle = (key: string) =>
    setTriggers((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  return (
    <form
      aria-label="Edit jurisdiction"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        try {
          await save.mutateAsync({
            geography_ids: geoIds,
            triggers: [...triggers].map((k) => {
              const [subject_type, relation] = k.split(":");
              return { subject_type: subject_type as JurisdictionTrigger["subject_type"], relation };
            }),
          });
          onDone();
        } catch (err) {
          setError(errorDetail(err));
        }
      }}
      style={{ display: "flex", flexDirection: "column", gap: 8, border: "1px solid var(--border)", borderRadius: 4, padding: 10 }}
    >
      <div>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 4 }}>Covers</div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
          {geoIds.length === 0 && <span style={muted}>Nothing yet.</span>}
          {geoIds.map((id) => (
            <span key={id} style={chip}>
              {geographyLabel(byId.get(id), id)}
              <button type="button" className="ui-btn-plain" aria-label={`Remove ${geographyLabel(byId.get(id), id)}`} onClick={() => setGeoIds(geoIds.filter((g) => g !== id))} style={{ color: "var(--ink-3)" }}>
                ×
              </button>
            </span>
          ))}
        </div>
        <select
          aria-label="Add to the jurisdiction"
          value=""
          onChange={(e) => {
            const id = e.target.value;
            if (id && !geoIds.includes(id)) setGeoIds([...geoIds, id]);
          }}
          style={field}
        >
          <option value="">Add a country, region or bloc…</option>
          {options
            .filter((g) => !geoIds.includes(g.id))
            .map((g) => (
              <option key={g.id} value={g.id}>
                {geographyLabel(g)}
              </option>
            ))}
        </select>
        <div style={muted}>Blocs such as the EU come from a regulatory hierarchy (Business → Organization → Geography); their dated memberships carry joins and exits.</div>
      </div>
      <fieldset style={{ border: "none", margin: 0, padding: 0 }}>
        <legend style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 4 }}>Applies when</legend>
        {(["application", "legal_entity"] as const).map((subject) => (
          <div key={subject} style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12, marginBottom: 2 }}>
            <span style={{ ...muted, width: 110 }}>{subject === "application" ? "An application" : "A legal entity"}</span>
            {(matrix.data?.subjects[subject] ?? []).map((r) => {
              const key = `${subject}:${r.relation}`;
              return (
                <label key={key}>
                  <input type="checkbox" checked={triggers.has(key)} onChange={() => toggle(key)} /> {r.label.toLowerCase()}
                </label>
              );
            })}
          </div>
        ))}
      </fieldset>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <button type="submit" className="ui-btn ui-btn-primary ui-btn-sm" disabled={save.isPending}>
          Save
        </button>
        <button type="button" className="ui-btn ui-btn-sm" onClick={onDone}>
          Cancel
        </button>
        {error && (
          <span role="alert" style={{ fontSize: 12, color: "var(--crit)" }}>
            {error}
          </span>
        )}
      </div>
    </form>
  );
}

export function FrameworkJurisdictionPanel({ frameworkId, canWrite }: { frameworkId: string; canWrite: boolean }): React.ReactElement {
  const jurisdiction = useFrameworkJurisdiction(frameworkId);
  const [editing, setEditing] = useState(false);
  const [asOf, setAsOf] = useState("");
  const [showAll, setShowAll] = useState(false);
  const applicability = useFrameworkApplicability(frameworkId, asOf || null);
  const j = jurisdiction.data;
  const items = (applicability.data?.items ?? []).filter((i) => showAll || i.status === "applies");
  const counts = applicability.data?.counts;

  return (
    <section aria-label="Jurisdiction and applicability" style={{ marginBottom: 16 }}>
      <h4 style={{ ...h4, display: "flex", gap: 8, alignItems: "baseline" }}>
        Jurisdiction
        {canWrite && !editing && (
          <button type="button" className="ui-btn ui-btn-sm" onClick={() => setEditing(true)}>
            Edit
          </button>
        )}
      </h4>
      {jurisdiction.isLoading ? (
        <div style={muted}>Loading…</div>
      ) : editing ? (
        <JurisdictionEditor frameworkId={frameworkId} onDone={() => setEditing(false)} />
      ) : !j?.configured ? (
        <div style={muted}>
          Not recorded. Add the countries or blocs it covers and what brings an application or legal entity into scope; until then its applicability is unknown.
        </div>
      ) : (
        <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
          <div>Covers {j.geographies.map((g) => geographyLabel(g)).join(", ")}.</div>
          <div>
            Applies when{" "}
            {j.triggers.map((t) => `${t.subject_type === "application" ? "an application" : "a legal entity"} ${(t.label ?? t.relation).toLowerCase()} it`).join("; or ")}.
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 12, alignItems: "baseline", flexWrap: "wrap" }}>
        <h4 style={h4}>Applies to</h4>
        <AsOf value={asOf} onChange={setAsOf} />
        <label style={muted}>
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show unknown and does not apply
        </label>
      </div>
      {counts && (
        <div style={{ ...muted, marginBottom: 6 }}>
          {counts.applies ?? 0} apply · {counts.unknown ?? 0} unknown · {counts.does_not_apply ?? 0} do not apply
        </div>
      )}
      {applicability.isLoading ? (
        <div style={muted}>Loading…</div>
      ) : items.length === 0 ? (
        <div style={muted}>{showAll ? "No applications or legal entities yet." : "Nothing it applies to on this date."}</div>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {items.map((i) => (
            <li key={`${i.subject_type}:${i.subject.id}`} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <StatusPill status={i.status} />
                <span style={muted}>{i.subject_type === "application" ? "Application" : "Legal entity"}</span>
                <span style={{ fontSize: 13 }}>
                  {i.subject_type === "application" ? (
                    <EntityLink kind="application" id={i.subject.id}>
                      {i.subject.name}
                    </EntityLink>
                  ) : (
                    i.subject.name
                  )}
                </span>
              </div>
              <Why item={i} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
