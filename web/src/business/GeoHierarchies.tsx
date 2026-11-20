// 946 GEO-01 (ADP-bo1.1): Business -> Organization -> Geography. Several typed geography
// hierarchies (regulatory, data residency, sales, ...) over one set of places (countries), with
// dated memberships. Replaces the 940 editable UN tree, which is now the read-only reference
// hierarchy. Everything is shown "as of" a date; the server validates every write (no cycles,
// one parent at a time in a strict tree, end after start) and names the rule it refused.

import { useMemo, useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { Geography, GeoHierarchy, GeoHierarchyDetail, GeoMembership, HierarchyKind, HierarchyShape } from "../api/organization";
import {
  COMPLIANCE_KINDS,
  HIERARCHY_KIND_LABEL,
  useAddGeoMemberships,
  useCreateGeoHierarchy,
  useCreateGeoNode,
  useDeleteGeoHierarchy,
  useDeleteGeoMembership,
  useDeleteGeography,
  useGeoHierarchies,
  useGeoHierarchy,
  useGeographies,
  useUpdateGeoMembership,
  useUpdateGeography,
} from "../api/organization";
import { confirmAction } from "../ui/confirm";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const chip: React.CSSProperties = { fontSize: 11, background: "var(--surface-2)", padding: "1px 6px", borderRadius: 8, display: "inline-flex", gap: 4, alignItems: "center" };

const KIND_ORDER: HierarchyKind[] = ["reference", "regulatory", "data_residency", "tax", "sales", "operational", "infrastructure", "custom"];
const SHAPE_LABEL: Record<HierarchyShape, string> = { strict_tree: "Strict tree", dag: "Several parents allowed" };

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function period(m: GeoMembership): string {
  if (!m.valid_from && !m.valid_to) return "";
  if (m.valid_from && m.valid_to) return `${m.valid_from} – ${m.valid_to}`;
  return m.valid_from ? `from ${m.valid_from}` : `until ${m.valid_to}`;
}

function ErrorLine({ error }: { error: string | null }): React.ReactElement | null {
  return error ? (
    <span role="alert" style={{ fontSize: 12, color: "var(--crit)" }}>
      {error}
    </span>
  ) : null;
}

// ── New hierarchy ─────────────────────────────────────────────────────────────

function NewHierarchyForm({ canWriteCompliance, onDone }: { canWriteCompliance: boolean; onDone: (id?: string) => void }): React.ReactElement {
  const create = useCreateGeoHierarchy();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Exclude<HierarchyKind, "reference">>("sales");
  const [shape, setShape] = useState<HierarchyShape>("strict_tree");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      aria-label="New hierarchy"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          const h = await create.mutateAsync({ name: name.trim(), kind, shape });
          onDone(h.id);
        } catch (err) {
          setError(errorDetail(err));
        }
      }}
      style={{ display: "flex", flexDirection: "column", gap: 4, margin: "6px 0", padding: 8, border: "1px solid var(--border)", borderRadius: 6 }}
    >
      <input autoFocus aria-label="Hierarchy name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name (e.g. Sales regions)" style={field} />
      <select aria-label="Hierarchy kind" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} style={field}>
        {KIND_ORDER.filter((k) => k !== "reference").map((k) => (
          <option key={k} value={k} disabled={COMPLIANCE_KINDS.has(k) && !canWriteCompliance}>
            {HIERARCHY_KIND_LABEL[k]}
            {COMPLIANCE_KINDS.has(k) && !canWriteCompliance ? " (needs compliance permission)" : ""}
          </option>
        ))}
      </select>
      <select aria-label="Hierarchy shape" value={shape} onChange={(e) => setShape(e.target.value as HierarchyShape)} style={field}>
        <option value="strict_tree">{SHAPE_LABEL.strict_tree}: one parent at a time</option>
        <option value="dag">{SHAPE_LABEL.dag} (e.g. EU, EEA, Eurozone)</option>
      </select>
      <div style={{ display: "flex", gap: 6 }}>
        <button type="submit" className="ui-btn ui-btn-xs" disabled={!name.trim() || create.isPending}>
          {create.isPending ? "Adding…" : "Add"}
        </button>
        <button type="button" className="ui-btn-link muted" onClick={() => onDone()}>
          Cancel
        </button>
      </div>
      <ErrorLine error={error} />
    </form>
  );
}

// ── Members of one node ───────────────────────────────────────────────────────

function AddMembers({
  hierarchy,
  nodeId,
  countries,
  regions,
  nodes,
}: {
  hierarchy: GeoHierarchyDetail;
  nodeId: string;
  countries: Geography[];
  regions: Geography[];
  nodes: { id: string; name: string }[];
}): React.ReactElement {
  const add = useAddGeoMemberships();
  const [child, setChild] = useState("");
  const [region, setRegion] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const run = async (childIds: string[]) => {
    setError(null);
    setMessage(null);
    if (childIds.length === 0) return;
    try {
      const added = await add.mutateAsync({ hierarchyId: hierarchy.id, parentId: nodeId, childIds, validFrom: from || null, validTo: to || null });
      setMessage(`Added ${added.length}.`);
      setChild("");
      setRegion("");
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, margin: "6px 0" }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <select aria-label="Add a member" value={child} onChange={(e) => setChild(e.target.value)} style={field}>
          <option value="">Add a country or node…</option>
          {nodes.filter((n) => n.id !== nodeId).length > 0 && (
            <optgroup label="Nodes of this hierarchy">
              {nodes
                .filter((n) => n.id !== nodeId)
                .map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.name}
                  </option>
                ))}
            </optgroup>
          )}
          <optgroup label="Countries">
            {countries.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </optgroup>
        </select>
        <button type="button" className="ui-btn ui-btn-xs" disabled={!child || add.isPending} onClick={() => void run([child])}>
          Add
        </button>
        <select aria-label="Add every country of a UN region" value={region} onChange={(e) => setRegion(e.target.value)} style={field}>
          <option value="">Every country of…</option>
          {regions.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="ui-btn ui-btn-xs"
          disabled={!region || add.isPending}
          onClick={() => void run(countries.filter((c) => c.parent_id === region).map((c) => c.id))}
        >
          {add.isPending ? "Adding…" : "Add all"}
        </button>
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <label style={muted}>
          From{" "}
          <input type="date" aria-label="Member from" value={from} onChange={(e) => setFrom(e.target.value)} style={field} />
        </label>
        <label style={muted}>
          Until (exclusive){" "}
          <input type="date" aria-label="Member until" value={to} onChange={(e) => setTo(e.target.value)} style={field} />
        </label>
        <span style={muted}>Leave blank for always / open-ended.</span>
      </div>
      {message && <span style={muted}>{message}</span>}
      <ErrorLine error={error} />
    </div>
  );
}

function MemberChip({ m, label, editable }: { m: GeoMembership; label: string; editable: boolean }): React.ReactElement {
  const remove = useDeleteGeoMembership();
  const update = useUpdateGeoMembership();
  const [editing, setEditing] = useState(false);
  const [from, setFrom] = useState(m.valid_from ?? "");
  const [to, setTo] = useState(m.valid_to ?? "");
  const [error, setError] = useState<string | null>(null);
  const p = period(m);
  if (editing) {
    return (
      <form
        aria-label={`Dates for ${label}`}
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await update.mutateAsync({ id: m.id, validFrom: from || null, validTo: to || null });
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
    <span style={{ ...chip, opacity: m.active ? 1 : 0.55 }} title={p || "Always"}>
      {label}
      {p && <span style={{ color: "var(--ink-3)" }}>{p}</span>}
      {editable && (
        <>
          <button type="button" className="ui-btn-plain" aria-label={`Change dates of ${label}`} onClick={() => setEditing(true)} style={{ color: "var(--ink-3)" }}>
            ✎
          </button>
          <button type="button" className="ui-btn-plain" aria-label={`Remove ${label}`} onClick={() => remove.mutate(m.id)} style={{ color: "var(--ink-3)" }}>
            ×
          </button>
        </>
      )}
    </span>
  );
}

// ── One node, recursively ─────────────────────────────────────────────────────

interface TreeCtx {
  detail: GeoHierarchyDetail;
  editable: boolean;
  showAll: boolean;
  names: Map<string, Geography>;
  countries: Geography[];
  regions: Geography[];
  filter: string;
}

function NodeRow({ id, depth, via, ctx, path }: { id: string; depth: number; via?: GeoMembership; ctx: TreeCtx; path: Set<string> }): React.ReactElement {
  const { detail, editable, showAll, names, filter } = ctx;
  const [open, setOpen] = useState(depth === 0 && detail.kind !== "reference");
  const [adding, setAdding] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const rename = useUpdateGeography();
  const del = useDeleteGeography();
  const name = detail.nodes.find((n) => n.id === id)?.name ?? id;
  const children = detail.memberships.filter((m) => m.parent_id === id && (showAll || m.active));
  const subNodes = children.filter((m) => m.child_entity === "node");
  const places = children
    .filter((m) => m.child_entity === "place")
    .filter((m) => !filter || (names.get(m.child_id)?.name ?? "").toLowerCase().includes(filter))
    .sort((a, b) => (names.get(a.child_id)?.name ?? "").localeCompare(names.get(b.child_id)?.name ?? ""));
  const placeCount = children.filter((m) => m.child_entity === "place" && m.active).length;
  const isOpen = open || (!!filter && places.length > 0);

  return (
    <div style={{ marginLeft: depth * 14 }} data-geo-node={id}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "2px 0", fontSize: 13 }}>
        <button type="button" className="ui-btn-plain" onClick={() => setOpen((o) => !o)} aria-label={isOpen ? `Collapse ${name}` : `Expand ${name}`} aria-expanded={isOpen} style={{ fontSize: 10, color: "var(--ink-3)", minWidth: 12 }}>
          {isOpen ? "▾" : "▸"}
        </button>
        {renaming ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await rename.mutateAsync({ id, body: { name: newName.trim() } });
                setRenaming(false);
              } catch (err) {
                setError(errorDetail(err));
              }
            }}
            style={{ display: "flex", gap: 4 }}
          >
            <input autoFocus aria-label={`New name for ${name}`} value={newName} onChange={(e) => setNewName(e.target.value)} style={field} />
            <button type="submit" className="ui-btn-link" disabled={!newName.trim()}>
              Save
            </button>
            <button type="button" className="ui-btn-link muted" onClick={() => setRenaming(false)}>
              Cancel
            </button>
          </form>
        ) : (
          <span style={{ flex: 1 }}>
            {name}
            {via && period(via) && <span style={{ ...muted, marginLeft: 6 }}>{period(via)}</span>}
          </span>
        )}
        <span style={muted}>
          {placeCount} countr{placeCount === 1 ? "y" : "ies"}
          {subNodes.length > 0 ? `, ${subNodes.length} node${subNodes.length === 1 ? "" : "s"}` : ""}
        </span>
        {editable && !renaming && (
          <>
            <button type="button" className="ui-btn-link" onClick={() => { setOpen(true); setAdding((a) => !a); }}>
              + Members
            </button>
            <button type="button" className="ui-btn-link" aria-label={`Rename ${name}`} onClick={() => { setNewName(name); setRenaming(true); }}>
              Rename
            </button>
            <button
              type="button"
              className="ui-btn-link danger"
              aria-label={`Delete ${name}`}
              onClick={async () => {
                if (!(await confirmAction(`Delete "${name}"? Its memberships go, and anything linked to it loses that link.`))) return;
                try {
                  setError(null);
                  await del.mutateAsync(id);
                } catch (err) {
                  setError(errorDetail(err));
                }
              }}
            >
              Delete
            </button>
          </>
        )}
      </div>
      <div style={{ marginLeft: 18 }}>
        <ErrorLine error={error} />
      </div>
      {isOpen && (
        <div style={{ marginLeft: 18 }}>
          {adding && editable && <AddMembers hierarchy={detail} nodeId={id} countries={ctx.countries} regions={ctx.regions} nodes={detail.nodes} />}
          {places.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, margin: "2px 0 4px" }}>
              {places.map((m) => {
                const g = names.get(m.child_id);
                return <MemberChip key={m.id} m={m} label={g ? (g.code ? `${g.name} (${g.code})` : g.name) : m.child_id} editable={editable} />;
              })}
            </div>
          )}
          {subNodes.map((m) =>
            path.has(m.child_id) ? null : (
              <NodeRow key={m.id} id={m.child_id} depth={1} via={m} ctx={ctx} path={new Set([...path, m.child_id])} />
            ),
          )}
        </div>
      )}
    </div>
  );
}

// ── One hierarchy ─────────────────────────────────────────────────────────────

function HierarchyView({
  id,
  asOf,
  showAll,
  canWrite,
  canWriteCompliance,
  geographies,
  onDeleted,
}: {
  id: string;
  asOf: string;
  showAll: boolean;
  canWrite: boolean;
  canWriteCompliance: boolean;
  geographies: Geography[];
  onDeleted: () => void;
}): React.ReactElement {
  const { data, isLoading, error } = useGeoHierarchy(id, asOf);
  const createNode = useCreateGeoNode();
  const delH = useDeleteGeoHierarchy();
  const [addingNode, setAddingNode] = useState(false);
  const [nodeName, setNodeName] = useState("");
  const [nodeParent, setNodeParent] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const ctxBase = useMemo(() => {
    const names = new Map(geographies.map((g) => [g.id, g]));
    const byName = (a: Geography, b: Geography) => a.name.localeCompare(b.name);
    return {
      names,
      countries: geographies.filter((g) => g.entity !== "node" && g.kind === "country").sort(byName),
      regions: geographies.filter((g) => g.kind === "region" && g.hierarchy_kind === "reference").sort(byName),
    };
  }, [geographies]);

  if (isLoading) return <div style={muted}>Loading hierarchy…</div>;
  if (error || !data) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load the hierarchy.</div>;

  const needsCompliance = COMPLIANCE_KINDS.has(data.kind);
  const editable = canWrite && !data.read_only && (!needsCompliance || canWriteCompliance);
  const visible = data.memberships.filter((m) => showAll || m.active);
  const childNodes = new Set(visible.filter((m) => m.child_entity === "node").map((m) => m.child_id));
  const roots = data.nodes.filter((n) => !childNodes.has(n.id));
  const ctx: TreeCtx = { detail: data, editable, showAll, filter: filter.trim().toLowerCase(), ...ctxBase };

  return (
    <section aria-label={`Hierarchy ${data.name}`}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <h4 style={{ fontSize: 14, margin: 0 }}>{data.name}</h4>
        <span style={muted}>
          {HIERARCHY_KIND_LABEL[data.kind]} · {SHAPE_LABEL[data.shape]}
        </span>
        {editable && data.node_count === 0 && (
          <button
            type="button"
            className="ui-btn-link danger"
            onClick={async () => {
              if (!(await confirmAction(`Delete the hierarchy "${data.name}"?`))) return;
              await delH.mutateAsync(data.id);
              onDeleted();
            }}
          >
            Delete hierarchy
          </button>
        )}
      </div>
      {data.description && <div style={muted}>{data.description}</div>}
      {data.read_only && (
        <div style={{ ...muted, marginTop: 4 }}>Read-only: mastered in {data.system_of_record}.</div>
      )}
      {!data.read_only && canWrite && needsCompliance && !canWriteCompliance && (
        <div style={{ ...muted, marginTop: 4 }}>Read-only for you: changing a {HIERARCHY_KIND_LABEL[data.kind].toLowerCase()} hierarchy needs the compliance permission.</div>
      )}
      <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "8px 0" }}>
        <input aria-label="Filter countries" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter countries" style={{ ...field, flex: 1, maxWidth: 260 }} />
        {editable && (
          <button type="button" className="ui-btn ui-btn-xs" onClick={() => setAddingNode((a) => !a)}>
            + Node
          </button>
        )}
      </div>
      {addingNode && (
        <form
          aria-label="New node"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              setFormError(null);
              await createNode.mutateAsync({ hierarchyId: data.id, name: nodeName.trim(), parentId: nodeParent || null });
              setNodeName("");
              setAddingNode(false);
            } catch (err) {
              setFormError(errorDetail(err));
            }
          }}
          style={{ display: "flex", gap: 6, alignItems: "center", margin: "4px 0" }}
        >
          <input autoFocus aria-label="Node name" value={nodeName} onChange={(e) => setNodeName(e.target.value)} placeholder="Node name (e.g. APAC)" style={field} />
          <select aria-label="Node parent" value={nodeParent} onChange={(e) => setNodeParent(e.target.value)} style={field}>
            <option value="">At the top</option>
            {data.nodes.map((n) => (
              <option key={n.id} value={n.id}>
                Under {n.name}
              </option>
            ))}
          </select>
          <button type="submit" className="ui-btn ui-btn-xs" disabled={!nodeName.trim() || createNode.isPending}>
            {createNode.isPending ? "Adding…" : "Add"}
          </button>
          <button type="button" className="ui-btn-link muted" onClick={() => setAddingNode(false)}>
            Cancel
          </button>
          <ErrorLine error={formError} />
        </form>
      )}
      {data.nodes.length === 0 ? (
        <div style={muted}>No nodes yet.{editable ? ' Click "+ Node" to add one.' : ""}</div>
      ) : (
        roots.map((n) => <NodeRow key={n.id} id={n.id} depth={0} ctx={ctx} path={new Set([n.id])} />)
      )}
    </section>
  );
}

// ── The screen ────────────────────────────────────────────────────────────────

export default function GeoHierarchies({ canWrite, canWriteCompliance }: { canWrite: boolean; canWriteCompliance: boolean }): React.ReactElement {
  const list = useGeoHierarchies();
  const geos = useGeographies();
  const [selected, setSelected] = useState<string | null>(null);
  const [asOf, setAsOf] = useState(today());
  const [showAll, setShowAll] = useState(false);
  const [adding, setAdding] = useState(false);

  const items = useMemo(() => list.data?.items ?? [], [list.data]);
  const current = selected && items.some((h) => h.id === selected) ? selected : (items.find((h) => h.kind !== "reference") ?? items[0])?.id ?? null;
  const byKind = useMemo(() => {
    const m = new Map<HierarchyKind, GeoHierarchy[]>();
    for (const h of items) m.set(h.kind, [...(m.get(h.kind) ?? []), h]);
    return KIND_ORDER.filter((k) => m.has(k)).map((k) => [k, m.get(k)!] as const);
  }, [items]);

  if (list.isLoading) return <div style={muted}>Loading geography…</div>;
  if (list.error) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load geography hierarchies.</div>;

  return (
    <div>
      <p style={{ ...muted, marginTop: 0 }}>
        Countries are grouped by several hierarchies at once: regulatory blocs, data-residency zones, sales regions and so on.
        Memberships can be dated, and everything here is shown as of the date you choose. The UN M49 regions are the read-only
        reference.
      </p>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <label style={muted}>
          As of{" "}
          <input type="date" aria-label="As of" value={asOf} onChange={(e) => setAsOf(e.target.value || today())} style={field} />
        </label>
        <label style={muted}>
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show memberships from other periods
        </label>
      </div>
      <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
        <nav aria-label="Geography hierarchies" style={{ flex: "0 0 240px" }}>
          {byKind.map(([kind, hs]) => (
            <div key={kind} style={{ marginBottom: 8 }}>
              <div style={{ ...muted, textTransform: "uppercase", fontSize: 10, letterSpacing: 0.5 }}>{HIERARCHY_KIND_LABEL[kind]}</div>
              {hs.map((h) => (
                <button
                  key={h.id}
                  type="button"
                  className="ui-btn-plain"
                  aria-current={h.id === current ? "true" : undefined}
                  onClick={() => setSelected(h.id)}
                  style={{ display: "block", width: "100%", padding: "2px 4px", fontSize: 13, fontWeight: h.id === current ? 600 : 400, borderRadius: 4, background: h.id === current ? "var(--accent-wash, #e8f1f8)" : undefined }}
                >
                  {h.name}
                  <span style={{ ...muted, marginLeft: 6 }}>{h.node_count}</span>
                </button>
              ))}
            </div>
          ))}
          {canWrite &&
            (adding ? (
              <NewHierarchyForm
                canWriteCompliance={canWriteCompliance}
                onDone={(id) => {
                  setAdding(false);
                  if (id) setSelected(id);
                }}
              />
            ) : (
              <button type="button" className="ui-btn ui-btn-xs" onClick={() => setAdding(true)}>
                + Hierarchy
              </button>
            ))}
        </nav>
        <div style={{ flex: 1, minWidth: 0 }}>
          {current ? (
            <HierarchyView
              key={current}
              id={current}
              asOf={asOf}
              showAll={showAll}
              canWrite={canWrite}
              canWriteCompliance={canWriteCompliance}
              geographies={geos.data?.items ?? []}
              onDeleted={() => setSelected(null)}
            />
          ) : (
            <div style={muted}>No hierarchies.</div>
          )}
        </div>
      </div>
    </div>
  );
}
