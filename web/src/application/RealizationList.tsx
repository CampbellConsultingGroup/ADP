// 943-mapping-rationale: the "Realized by applications" editor on an application capability.
// Each realization has a rationale (target / tactical / transitional / redundant, or unclassified)
// and an optional geography (none = everywhere). The row selects save as soon as a value is
// chosen, like the Capabilities screen and the objective links (ADP-w7z); the add row has several
// fields, so it keeps a Link button (as 941's performer form does).

import { useState } from "react";
import type React from "react";
import type { AppRef, Rationale, RealizationAttrs } from "../api/appCapabilities";
import { errorDetail, useAddRealization, useRemoveAppCapLink, useUpdateRealization } from "../api/appCapabilities";
import { geographyLabel as sharedGeographyLabel, useGeographies } from "../api/organization";
import { assessableGeographies } from "../business/RegionalAssessmentEditor";
import { Button } from "../ui";
import { RATIONALES, RATIONALE_HELP, RATIONALE_LABEL, rationaleColors, rationaleLabel } from "./realizationRationale";

interface Option {
  id: string;
  label: string;
}

const select: React.CSSProperties = { fontSize: 12, padding: "2px 4px" };
export function RationaleChip({ rationale }: { rationale: Rationale | null | undefined }): React.ReactElement {
  const [fg, bg] = rationaleColors(rationale);
  return (
    <span
      title={rationale ? RATIONALE_HELP[rationale] : "No rationale recorded yet"}
      style={{ fontSize: 10, fontWeight: 600, color: fg, background: bg, borderRadius: 8, padding: "1px 6px", whiteSpace: "nowrap" }}
    >
      {rationaleLabel(rationale)}
    </span>
  );
}

export function geographyLabel(
  g: { name: string; code: string | null; hierarchy_kind?: string | null; hierarchy_name?: string | null } | null | undefined,
): string {
  return sharedGeographyLabel(g, "Everywhere"); // 946: nodes of other hierarchies show "APAC · Sales"
}

function RationaleSelect({ label, value, onChange, disabled }: { label: string; value: Rationale | null; onChange: (v: Rationale | null) => void; disabled?: boolean }) {
  return (
    <select aria-label={label} value={value ?? ""} disabled={disabled} onChange={(e) => onChange((e.target.value || null) as Rationale | null)} style={select}>
      <option value="">Unclassified</option>
      {RATIONALES.map((r) => (
        <option key={r} value={r} title={RATIONALE_HELP[r]}>
          {RATIONALE_LABEL[r]}
        </option>
      ))}
    </select>
  );
}

function GeographySelect({ label, value, onChange, options, disabled }: { label: string; value: string | null; onChange: (v: string | null) => void; options: Option[]; disabled?: boolean }) {
  return (
    <select aria-label={label} value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value || null)} style={select}>
      <option value="">Everywhere</option>
      {options.map((o) => (
        <option key={o.id} value={o.id}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export default function RealizationList({
  acId,
  linked,
  options,
  canWrite,
}: {
  acId: string;
  linked: AppRef[];
  options: Option[];
  canWrite: boolean;
}): React.ReactElement {
  const update = useUpdateRealization();
  const add = useAddRealization();
  const remove = useRemoveAppCapLink();
  const { data: geos } = useGeographies();
  const geoOptions = assessableGeographies(geos?.items ?? []).map((g) => ({ id: g.id, label: geographyLabel(g) }));
  const [error, setError] = useState<string | null>(null);
  const [newApp, setNewApp] = useState("");
  const [newRationale, setNewRationale] = useState<Rationale | null>(null);
  const [newGeo, setNewGeo] = useState<string | null>(null);
  const linkedIds = new Set(linked.map((a) => a.id));
  const available = options.filter((o) => !linkedIds.has(o.id));

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      setError(null);
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  const save = (appId: string, attrs: RealizationAttrs) => run(() => update.mutateAsync({ id: acId, appId, attrs }));

  return (
    <section aria-label="Realized by applications">
      <h4 style={{ fontSize: 13, margin: "14px 0 2px", color: "var(--ink-2)" }}>Realized by applications</h4>
      <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>
        The applications that deliver this capability, and why: target (keep and invest), tactical (tolerated for a
        regional or functional reason), transitional (being replaced) or redundant (a rationalization candidate).
      </div>
      {linked.length === 0 && <div style={{ fontSize: 12, color: "var(--ink-3)" }}>No application realizes this capability yet.</div>}
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {linked.map((a) => (
          <li key={a.id} aria-label={a.name} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, padding: "3px 0", flexWrap: "wrap" }}>
            <span style={{ flex: 1, minWidth: 120 }}>{a.name}</span>
            {canWrite ? (
              <>
                <RationaleSelect label={`Rationale for ${a.name}`} value={a.rationale ?? null} disabled={update.isPending} onChange={(v) => void save(a.id, { rationale: v })} />
                <GeographySelect
                  label={`Geography for ${a.name}`}
                  value={a.geography?.id ?? null}
                  options={geoOptions}
                  disabled={update.isPending}
                  onChange={(v) => void save(a.id, { geography_id: v })}
                />
              </>
            ) : (
              <>
                <RationaleChip rationale={a.rationale} />
                <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{geographyLabel(a.geography)}</span>
              </>
            )}
            {a.hint && (
              <span title="The rationale and the application's TIME classification disagree. Saving is not blocked." style={{ fontSize: 11, color: "var(--warn)" }}>
                ⚠ {a.hint}
              </span>
            )}
            {canWrite && (
              <button className="ui-btn ui-btn-xs" aria-label={`Remove ${a.name}`} onClick={() => void run(() => remove.mutateAsync({ id: acId, kind: "application", targetId: a.id }))}>
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      {canWrite && (
        <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
          <select aria-label="Add application" value={newApp} onChange={(e) => setNewApp(e.target.value)} style={{ ...select, flex: 1, minWidth: 140 }}>
            <option value="">Select…</option>
            {available.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
          <RationaleSelect label="Rationale for the new application" value={newRationale} onChange={setNewRationale} />
          <GeographySelect label="Geography for the new application" value={newGeo} options={geoOptions} onChange={setNewGeo} />
          <Button
            size="sm"
            disabled={!newApp || add.isPending}
            onClick={() =>
              void run(async () => {
                const attrs: RealizationAttrs = {};
                if (newRationale) attrs.rationale = newRationale;
                if (newGeo) attrs.geography_id = newGeo;
                await add.mutateAsync({ id: acId, appId: newApp, attrs });
                setNewApp("");
                setNewRationale(null);
                setNewGeo(null);
              })
            }
          >
            Link
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" style={{ fontSize: 12, color: "var(--crit)", marginTop: 4 }}>
          {error}
        </div>
      )}
    </section>
  );
}
