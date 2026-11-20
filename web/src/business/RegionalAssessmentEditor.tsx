// 942-regional-assessments (ADP-55k.3): editing regional maturity and region-specific scope.
//
// CellEditor records or changes one capability x geography assessment (a 1-5 score on the same
// scale as global maturity, and/or a variant note). It is used by the regional heat map's cells
// and by RegionalAssessmentsPanel, the content of each Capabilities row's "Regions" expander,
// which also holds RegionScopeEditor. The capability's own maturity (the baseline) is never edited
// here. Notes are plain text and rendered as text.

import { useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import { MATURITY_LEVEL_LABEL } from "../api/business";
import type { Geography, GeoRef, RegionalAssessment } from "../api/organization";
import {
  REGIONAL_NOTE_MAX,
  useGeographies,
  useRegionScope,
  useRegionalAssessments,
  useRemoveRegionalAssessment,
  useSetRegionScope,
  useSetRegionalAssessment,
  geographyLabel,
} from "../api/organization";
import { maturitySwatch } from "./maturityScale";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
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
const LEVELS = [1, 2, 3, 4, 5] as const;

export function maturityLabel(level: number): string {
  return `${level} · ${MATURITY_LEVEL_LABEL[level as 1 | 2 | 3 | 4 | 5]}`;
}

function geoLabel(g: GeoRef | Geography): string {
  return geographyLabel(g);
}

/** Regions first, then countries, both by name; never Global (that is the baseline). */
export function assessableGeographies(items: Geography[]): Geography[] {
  return items
    .filter((g) => g.kind !== "global")
    .sort((a, b) => a.level - b.level || a.name.localeCompare(b.name));
}

export function CellEditor({
  capabilityId,
  capabilityName,
  geography,
  current,
  onDone,
}: {
  capabilityId: string;
  capabilityName: string;
  geography: GeoRef;
  current: { maturity_level: number | null; note: string | null } | null;
  onDone: () => void;
}): React.ReactElement {
  const save = useSetRegionalAssessment();
  const remove = useRemoveRegionalAssessment();
  const [level, setLevel] = useState<string>(current?.maturity_level ? String(current.maturity_level) : "");
  const [note, setNote] = useState(current?.note ?? "");
  const [error, setError] = useState<string | null>(null);
  const empty = level === "" && note.trim() === "";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await save.mutateAsync({
        capabilityId,
        geographyId: geography.id,
        maturity_level: level === "" ? null : Number(level),
        note: note.trim() === "" ? null : note.trim(),
      });
      onDone();
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  const drop = async () => {
    setError(null);
    try {
      await remove.mutateAsync({ capabilityId, geographyId: geography.id });
      onDone();
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  return (
    <form
      onSubmit={submit}
      aria-label={`Assess ${capabilityName} in ${geography.name}`}
      style={{ display: "grid", gap: 6, padding: 8, minWidth: 240, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4 }}
    >
      <div style={{ fontSize: 12, fontWeight: 600 }}>
        {capabilityName} — {geography.name}
      </div>
      <select aria-label="Regional maturity" value={level} onChange={(e) => setLevel(e.target.value)} style={field}>
        <option value="">Not assessed</option>
        {LEVELS.map((l) => (
          <option key={l} value={l}>
            {maturityLabel(l)}
          </option>
        ))}
      </select>
      <textarea
        aria-label="Regional variant note"
        value={note}
        maxLength={REGIONAL_NOTE_MAX}
        rows={2}
        placeholder="How it differs here (optional)"
        onChange={(e) => setNote(e.target.value)}
        style={{ ...field, resize: "vertical" }}
      />
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <button type="submit" style={btn} disabled={empty || save.isPending}>
          Save
        </button>
        {current && (
          <button type="button" style={{ ...btn, borderColor: "var(--crit)", color: "var(--crit)" }} onClick={() => void drop()}>
            Remove
          </button>
        )}
        <button type="button" style={{ ...btn, border: "none" }} onClick={onDone}>
          Cancel
        </button>
        {empty && <span style={muted}>Pick a score, write a note, or both.</span>}
      </div>
      {error && (
        <div role="alert" style={{ fontSize: 11, color: "var(--crit)" }}>
          {error}
        </div>
      )}
    </form>
  );
}

function AssessmentLine({
  a,
  capabilityName,
  canWrite,
}: {
  a: RegionalAssessment;
  capabilityName: string;
  canWrite: boolean;
}): React.ReactElement {
  const [editing, setEditing] = useState(false);
  if (editing) {
    return (
      <li style={{ padding: "4px 0" }}>
        <CellEditor capabilityId={a.capability_id} capabilityName={capabilityName} geography={a.geography} current={a} onDone={() => setEditing(false)} />
      </li>
    );
  }
  const sw = a.maturity_level ? maturitySwatch(a.maturity_level) : null;
  return (
    <li style={{ fontSize: 12, display: "flex", gap: 8, alignItems: "baseline", padding: "2px 0" }}>
      <span style={{ minWidth: 110 }}>{geoLabel(a.geography)}</span>
      {sw && a.maturity_level ? (
        <span style={{ background: sw.bg, color: sw.fg, padding: "0 6px", borderRadius: 3, fontSize: 11 }}>{maturityLabel(a.maturity_level)}</span>
      ) : (
        <span style={muted}>Not assessed</span>
      )}
      {a.note && <span style={{ color: "var(--ink-2)" }}>{a.note}</span>}
      {canWrite && (
        <button type="button" style={{ ...btn, border: "none", padding: "0 4px" }} aria-label={`Edit ${a.geography.name}`} onClick={() => setEditing(true)}>
          Edit
        </button>
      )}
    </li>
  );
}

export function RegionScopeEditor({ capabilityId, canWrite }: { capabilityId: string; canWrite: boolean }): React.ReactElement {
  const { data } = useRegionScope(capabilityId);
  const geos = useGeographies();
  const save = useSetRegionScope();
  const [draft, setDraft] = useState<{ on: boolean; ids: string[] } | null>(null);
  const [pick, setPick] = useState("");
  const [error, setError] = useState<string | null>(null);
  const current = { on: data?.region_specific ?? false, ids: (data?.geographies ?? []).map((g) => g.id) };
  const state = draft ?? current;
  const options = assessableGeographies(geos.data?.items ?? []);
  const name = (id: string) => options.find((g) => g.id === id)?.name ?? data?.geographies.find((g) => g.id === id)?.name ?? id;

  const submit = async () => {
    setError(null);
    try {
      await save.mutateAsync({ capabilityId, region_specific: state.on, geography_ids: state.on ? state.ids : [] });
      setDraft(null);
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  if (!canWrite) {
    return (
      <div style={muted}>
        {data?.region_specific ? `Region-specific: applies in ${data.geographies.map((g) => g.name).join(", ") || "—"}.` : "Applies in every region."}
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <label style={{ fontSize: 12, display: "flex", gap: 6, alignItems: "center" }}>
        <input type="checkbox" checked={state.on} onChange={(e) => setDraft({ on: e.target.checked, ids: e.target.checked ? state.ids : [] })} />
        Region-specific (only exists in some places)
      </label>
      {data?.scope_needs_update && !draft && (
        <div style={{ ...muted, color: "var(--warn)" }}>Scope needs updating: its geographies were removed.</div>
      )}
      {state.on && (
        <>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {state.ids.length === 0 && <span style={muted}>Add at least one region or country.</span>}
            {state.ids.map((id) => (
              <span key={id} style={{ fontSize: 11, background: "var(--surface-2)", padding: "1px 6px", borderRadius: 8 }}>
                {name(id)}{" "}
                <button
                  type="button"
                  aria-label={`Remove ${name(id)} from scope`}
                  onClick={() => setDraft({ on: true, ids: state.ids.filter((x) => x !== id) })}
                  style={{ border: "none", background: "none", color: "var(--crit)", cursor: "pointer", padding: 0 }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <select aria-label="Add scope geography" value={pick} onChange={(e) => setPick(e.target.value)} style={field}>
              <option value="">Add a region or country…</option>
              {options
                .filter((g) => !state.ids.includes(g.id))
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {geoLabel(g)}
                  </option>
                ))}
            </select>
            <button
              type="button"
              style={btn}
              disabled={!pick}
              onClick={() => {
                setDraft({ on: true, ids: [...state.ids, pick] });
                setPick("");
              }}
            >
              Add
            </button>
          </div>
        </>
      )}
      {draft && (
        <div style={{ display: "flex", gap: 6 }}>
          <button type="button" style={btn} disabled={(state.on && state.ids.length === 0) || save.isPending} onClick={() => void submit()}>
            Save scope
          </button>
          <button type="button" style={{ ...btn, border: "none" }} onClick={() => setDraft(null)}>
            Cancel
          </button>
        </div>
      )}
      {error && (
        <div role="alert" style={{ fontSize: 11, color: "var(--crit)" }}>
          {error}
        </div>
      )}
    </div>
  );
}

export function RegionalAssessmentsPanel({
  capabilityId,
  capabilityName,
  baseline,
  canWrite,
}: {
  capabilityId: string;
  capabilityName: string;
  baseline: number | null;
  canWrite: boolean;
}): React.ReactElement {
  const { data, isLoading } = useRegionalAssessments(capabilityId);
  const geos = useGeographies();
  const [adding, setAdding] = useState("");
  const items = data?.items ?? [];
  const taken = new Set(items.map((a) => a.geography.id));
  const options = assessableGeographies(geos.data?.items ?? []).filter((g) => !taken.has(g.id));
  const addingGeo = options.find((g) => g.id === adding);

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={muted}>
        Global baseline: {baseline ? maturityLabel(baseline) : "Not assessed"} (set on the row; regional scores never change it).
      </div>
      {isLoading ? (
        <div style={muted}>Loading…</div>
      ) : items.length === 0 ? (
        <div style={muted}>No regional assessments yet.</div>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {items.map((a) => (
            <AssessmentLine key={a.id} a={a} capabilityName={capabilityName} canWrite={canWrite} />
          ))}
        </ul>
      )}
      {canWrite &&
        (addingGeo ? (
          <CellEditor
            capabilityId={capabilityId}
            capabilityName={capabilityName}
            geography={{ id: addingGeo.id, name: addingGeo.name, level: addingGeo.level, code: addingGeo.code }}
            current={null}
            onDone={() => setAdding("")}
          />
        ) : (
          <select aria-label="Assess in" value="" onChange={(e) => setAdding(e.target.value)} style={{ ...field, maxWidth: 260 }}>
            <option value="">Assess in a region or country…</option>
            {options.map((g) => (
              <option key={g.id} value={g.id}>
                {geoLabel(g)}
              </option>
            ))}
          </select>
        ))}
      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 6 }}>
        <RegionScopeEditor capabilityId={capabilityId} canWrite={canWrite} />
      </div>
    </div>
  );
}
