// 947 GEO-02 (ADP-bo1.2): Business -> Organization -> Legal entities. The companies that
// contract, hold licences and file (ADP-native, epic OQ-B3). A legal entity may be owned by
// another (group tree) and linked to org units and applications; its typed geography links say
// where it is incorporated, licensed, established and tax resident. Nothing is inferred from an
// application's owning org unit (Q2).

import { useMemo, useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { LegalEntity, LegalEntityFields } from "../api/organization";
import {
  useCreateLegalEntity,
  useDeleteLegalEntity,
  useLegalEntities,
  useLegalEntity,
  useLinkLegalEntityOrgUnit,
  useOrgUnits,
  useUnlinkLegalEntityOrgUnit,
  useUpdateLegalEntity,
} from "../api/organization";
import { EntityLink } from "../shell/EntityLink";
import { confirmAction } from "../ui/confirm";
import { SubjectApplicability } from "../compliance/Applicability";
import GeoLinksEditor from "./GeoLinksEditor";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const h4: React.CSSProperties = { fontSize: 13, margin: "14px 0 6px", color: "var(--ink-2)" };
const chip: React.CSSProperties = { fontSize: 11, background: "var(--surface-2)", padding: "1px 6px", borderRadius: 8, display: "inline-flex", gap: 4, alignItems: "center" };

/** Ids of ``id`` and everything it owns, directly or not (a parent can't be one of these). */
function ownedBy(id: string, items: LegalEntity[]): Set<string> {
  const out = new Set([id]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const e of items) {
      if (e.parent_id && out.has(e.parent_id) && !out.has(e.id)) {
        out.add(e.id);
        grew = true;
      }
    }
  }
  return out;
}

function EntityForm({
  initial,
  items,
  selfId,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial: LegalEntityFields;
  items: LegalEntity[];
  selfId?: string;
  submitLabel: string;
  onSubmit: (body: LegalEntityFields & { name: string }) => Promise<void>;
  onCancel: () => void;
}): React.ReactElement {
  const [name, setName] = useState(initial.name ?? "");
  const [reg, setReg] = useState(initial.registration_number ?? "");
  const [lei, setLei] = useState(initial.lei ?? "");
  const [description, setDescription] = useState(initial.description ?? "");
  const [parent, setParent] = useState(initial.parent_id ?? "");
  const [error, setError] = useState<string | null>(null);
  const excluded = selfId ? ownedBy(selfId, items) : new Set<string>();
  return (
    <form
      aria-label={submitLabel === "Add" ? "New legal entity" : "Edit legal entity"}
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        try {
          await onSubmit({
            name: name.trim(),
            registration_number: reg.trim() || null,
            lei: lei.trim() || null,
            description: description.trim() || null,
            parent_id: parent || null,
          });
        } catch (err) {
          setError(errorDetail(err));
        }
      }}
      style={{ display: "flex", flexDirection: "column", gap: 6, margin: "6px 0", maxWidth: 520 }}
    >
      <input aria-label="Legal entity name" placeholder="Name, e.g. Retail Co GmbH" value={name} onChange={(e) => setName(e.target.value)} style={{ ...field, fontSize: 14 }} />
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <input aria-label="Registration number" placeholder="Registration number" value={reg} onChange={(e) => setReg(e.target.value)} style={field} />
        <input aria-label="LEI" placeholder="LEI (20 characters)" value={lei} onChange={(e) => setLei(e.target.value)} style={{ ...field, width: 200 }} maxLength={20} />
        <select aria-label="Owned by" value={parent} onChange={(e) => setParent(e.target.value)} style={field}>
          <option value="">Not owned by another legal entity</option>
          {items
            .filter((i) => !excluded.has(i.id))
            .map((i) => (
              <option key={i.id} value={i.id}>
                Owned by {i.name}
              </option>
            ))}
        </select>
      </div>
      <textarea aria-label="Legal entity description" placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} style={field} rows={2} />
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <button type="submit" className="ui-btn ui-btn-primary ui-btn-sm" disabled={!name.trim()}>
          {submitLabel}
        </button>
        <button type="button" className="ui-btn ui-btn-sm" onClick={onCancel}>
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

function EntityDetail({ id, items, canWrite, onDeleted, onSelect }: { id: string; items: LegalEntity[]; canWrite: boolean; onDeleted: () => void; onSelect: (id: string) => void }): React.ReactElement {
  const { data, isLoading } = useLegalEntity(id);
  const orgUnits = useOrgUnits();
  const update = useUpdateLegalEntity();
  const del = useDeleteLegalEntity();
  const link = useLinkLegalEntityOrgUnit();
  const unlink = useUnlinkLegalEntityOrgUnit();
  const [editing, setEditing] = useState(false);
  const [addOu, setAddOu] = useState("");
  const [error, setError] = useState<string | null>(null);
  if (isLoading || !data) return <div style={muted}>Loading…</div>;
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  const linked = new Set(data.org_unit_ids);
  return (
    <div aria-label={`Legal entity ${data.name}`}>
      {(data.path ?? []).length > 0 && <div style={muted}>Owned by {(data.path ?? []).map((p) => p.name).join(" › ")}</div>}
      {editing ? (
        <EntityForm
          initial={data}
          items={items}
          selfId={id}
          submitLabel="Save"
          onCancel={() => setEditing(false)}
          onSubmit={async (body) => {
            await update.mutateAsync({ id, body });
            setEditing(false);
          }}
        />
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <h3 style={{ margin: "2px 0", fontSize: 17 }}>{data.name}</h3>
            {canWrite && (
              <>
                <button className="ui-btn ui-btn-sm" style={{ marginLeft: "auto" }} onClick={() => setEditing(true)}>
                  Edit
                </button>
                <button
                  className="ui-btn ui-btn-sm"
                  style={{ color: "var(--crit)" }}
                  onClick={async () => {
                    if (!(await confirmAction(`Delete "${data.name}"? Its org unit, application and geography links are removed too.`))) return;
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
          <div style={{ ...muted, display: "flex", gap: 14, flexWrap: "wrap" }}>
            <span>Registration number: {data.registration_number ?? "—"}</span>
            <span>LEI: {data.lei ?? "—"}</span>
          </div>
          {data.description && <p style={{ fontSize: 13, color: "var(--ink-2)", margin: "4px 0" }}>{data.description}</p>}
        </>
      )}
      {error && (
        <div role="alert" style={{ fontSize: 12, color: "var(--crit)", margin: "6px 0" }}>
          {error}
        </div>
      )}

      {(data.children ?? []).length > 0 && (
        <>
          <h4 style={h4}>Owns ({data.children?.length})</h4>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {data.children?.map((c) => (
              <button key={c.id} type="button" className="ui-btn-link" onClick={() => onSelect(c.id)}>
                {c.name}
              </button>
            ))}
          </div>
        </>
      )}

      <GeoLinksEditor
        subject="legal_entity"
        subjectId={id}
        canWrite={canWrite}
        hint="Where it is incorporated (one country at a time), licensed, has an establishment and is tax resident. Regulations attach to these."
      />

      {/* 948 GEO-03 */}
      <SubjectApplicability subject="legal_entity" subjectId={id} />

      <h4 style={h4}>Org units ({data.org_units?.length ?? 0})</h4>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {(data.org_units ?? []).length === 0 && <span style={muted}>None.</span>}
        {data.org_units?.map((o) => (
          <span key={o.id} style={chip}>
            {o.name}
            {canWrite && (
              <button type="button" className="ui-btn-plain" aria-label={`Unlink ${o.name}`} onClick={() => void run(() => unlink.mutateAsync({ id, orgUnitId: o.id }))} style={{ color: "var(--ink-3)" }}>
                ×
              </button>
            )}
          </span>
        ))}
      </div>
      {canWrite && (
        <select
          aria-label="Link an org unit"
          value={addOu}
          onChange={(e) => {
            const ou = e.target.value;
            setAddOu("");
            if (ou) void run(() => link.mutateAsync({ id, orgUnitId: ou }));
          }}
          style={{ ...field, marginTop: 6 }}
        >
          <option value="">Link an org unit…</option>
          {(orgUnits.data?.items ?? [])
            .filter((o) => !linked.has(o.id))
            .map((o) => (
              <option key={o.id} value={o.id}>
                {[...o.path.map((p) => p.name), o.name].join(" › ")}
              </option>
            ))}
        </select>
      )}

      <h4 style={h4}>Applications ({data.applications?.length ?? 0})</h4>
      {(data.applications ?? []).length === 0 ? (
        <div style={muted}>None. Link legal entities on an application's Geography tab.</div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {data.applications?.map((a) => (
            <li key={a.id}>
              <EntityLink kind="application" id={a.id}>
                {a.name}
              </EntityLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EntityTree({ items, selected, onSelect }: { items: LegalEntity[]; selected: string | null; onSelect: (id: string) => void }): React.ReactElement {
  const children = useMemo(() => {
    const ids = new Set(items.map((i) => i.id));
    const m = new Map<string | null, LegalEntity[]>();
    for (const i of items) {
      const p = i.parent_id && ids.has(i.parent_id) ? i.parent_id : null;
      m.set(p, [...(m.get(p) ?? []), i]);
    }
    return m;
  }, [items]);
  const row = (e: LegalEntity, depth: number, seen: Set<string>): React.ReactNode => {
    if (seen.has(e.id)) return null;
    const next = new Set(seen).add(e.id);
    return (
      <li key={e.id}>
        <button
          type="button"
          className="ui-btn-plain"
          aria-current={selected === e.id ? "true" : undefined}
          onClick={() => onSelect(e.id)}
          style={{
            display: "block",
            width: "100%",
            textAlign: "left",
            fontSize: 13,
            padding: `3px 6px 3px ${6 + depth * 16}px`,
            borderRadius: 3,
            background: selected === e.id ? "var(--surface-2)" : "transparent",
          }}
        >
          {e.name}
          {e.application_count > 0 && <span style={{ ...muted, marginLeft: 6 }}>{e.application_count} app{e.application_count === 1 ? "" : "s"}</span>}
        </button>
        {(children.get(e.id) ?? []).length > 0 && <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>{children.get(e.id)?.map((c) => row(c, depth + 1, next))}</ul>}
      </li>
    );
  };
  return (
    <nav aria-label="Legal entities">
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>{(children.get(null) ?? []).map((e) => row(e, 0, new Set()))}</ul>
    </nav>
  );
}

export default function LegalEntities({ canWrite }: { canWrite: boolean }): React.ReactElement {
  const list = useLegalEntities();
  const create = useCreateLegalEntity();
  const [selected, setSelected] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const items = list.data?.items ?? [];
  const current = selected && items.some((i) => i.id === selected) ? selected : null;

  if (list.isLoading) return <div style={muted}>Loading legal entities…</div>;
  if (list.error)
    return (
      <div role="alert" style={{ ...muted, color: "var(--crit)" }}>
        Failed to load legal entities.
      </div>
    );
  return (
    <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
      <div style={{ flex: "0 0 320px" }}>
        <p style={{ ...muted, marginTop: 0 }}>The companies that contract, hold licences and file. Many regulations attach to these rather than to a division or a country.</p>
        {canWrite &&
          (adding ? (
            <EntityForm
              initial={{}}
              items={items}
              submitLabel="Add"
              onCancel={() => setAdding(false)}
              onSubmit={async (body) => {
                const le = await create.mutateAsync(body);
                setAdding(false);
                setSelected(le.id);
              }}
            />
          ) : (
            <button type="button" className="ui-btn ui-btn-sm" onClick={() => setAdding(true)} style={{ marginBottom: 8 }}>
              + Legal entity
            </button>
          ))}
        {items.length === 0 ? <div style={muted}>No legal entities yet.</div> : <EntityTree items={items} selected={current} onSelect={setSelected} />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {current ? (
          <EntityDetail key={current} id={current} items={items} canWrite={canWrite} onDeleted={() => setSelected(null)} onSelect={setSelected} />
        ) : (
          <div style={muted}>Select a legal entity to see where it is incorporated, licensed and established.</div>
        )}
      </div>
    </div>
  );
}
