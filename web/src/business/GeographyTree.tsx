// 940-org-units-geography US2: the seeded geography tree (global > region > country). About 255
// rows, so regions start collapsed and a filter matches names and ISO codes. Writers can add a
// country or region and remove leaves; the server keeps codes unique and refuses deleting a parent.

import { useMemo, useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import type { Geography } from "../api/organization";
import { useCreateGeography, useDeleteGeography, useGeographies } from "../api/organization";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const smallBtn: React.CSSProperties = { background: "none", border: "none", cursor: "pointer", fontSize: 11, color: "var(--accent)", padding: "1px 4px" };

function AddCountry({ parent, onDone }: { parent: Geography; onDone: () => void }): React.ReactElement {
  const create = useCreateGeography();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const isGlobal = parent.kind === "global";
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await create.mutateAsync({ name: name.trim(), parent_id: parent.id, code: isGlobal ? null : code.trim() || null });
      onDone();
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  return (
    <form onSubmit={submit} style={{ display: "flex", gap: 6, alignItems: "center", margin: "4px 0 4px 18px" }}>
      <input
        autoFocus
        aria-label={isGlobal ? "New region name" : "New country name"}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={isGlobal ? "Region name (e.g. EMEA)" : "Country name"}
        style={{ fontSize: 12, padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 3 }}
      />
      {!isGlobal && (
        <input
          aria-label="ISO code"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="ISO"
          maxLength={2}
          style={{ width: 44, fontSize: 12, padding: "2px 6px", border: "1px solid var(--border)", borderRadius: 3 }}
        />
      )}
      <button type="submit" disabled={!name.trim() || create.isPending} style={smallBtn}>
        Add
      </button>
      <button type="button" onClick={onDone} style={{ ...smallBtn, color: "var(--ink-3)" }}>
        Cancel
      </button>
      {error && (
        <span role="alert" style={{ fontSize: 11, color: "var(--crit)" }}>
          {error}
        </span>
      )}
    </form>
  );
}

export default function GeographyTree({ canWrite }: { canWrite: boolean }): React.ReactElement {
  const { data, isLoading, error } = useGeographies();
  const del = useDeleteGeography();
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState<string | null>(null);
  const [delError, setDelError] = useState<string | null>(null);

  const items = data?.items ?? [];
  const children = useMemo(() => {
    const m = new Map<string | null, Geography[]>();
    for (const g of items) {
      const list = m.get(g.parent_id) ?? [];
      list.push(g);
      m.set(g.parent_id, list);
    }
    for (const list of m.values()) list.sort((a, b) => a.name.localeCompare(b.name));
    return m;
  }, [items]);

  if (isLoading) return <div style={muted}>Loading geography…</div>;
  if (error) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load geography.</div>;

  const q = filter.trim().toLowerCase();
  const matches = (g: Geography) => !q || g.name.toLowerCase().includes(q) || (g.code ?? "").toLowerCase() === q;
  const toggle = (id: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const remove = async (g: Geography) => {
    if (!confirm(`Remove "${g.name}"? Org units linked to it lose that link.`)) return;
    try {
      setDelError(null);
      await del.mutateAsync(g.id);
    } catch (err) {
      setDelError(errorDetail(err));
    }
  };

  const roots = children.get(null) ?? [];
  const row = (g: Geography, depth: number) => {
    const kids = children.get(g.id) ?? [];
    const visibleKids = kids.filter((k) => matches(k) || (children.get(k.id) ?? []).some(matches));
    const isOpen = q ? visibleKids.length > 0 : g.kind === "global" || open.has(g.id);
    if (q && depth > 0 && !matches(g) && visibleKids.length === 0) return null;
    return (
      <div key={g.id} style={{ marginLeft: depth * 14 }} data-geography-row={g.id}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "2px 0", fontSize: 13 }}>
          {kids.length > 0 ? (
            <button
              onClick={() => toggle(g.id)}
              aria-label={isOpen ? `Collapse ${g.name}` : `Expand ${g.name}`}
              style={{ fontSize: 10, background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", padding: 0, minWidth: 12 }}
            >
              {isOpen ? "▾" : "▸"}
            </button>
          ) : (
            <span style={{ minWidth: 12 }} />
          )}
          <span style={{ flex: 1 }}>
            {g.name}
            {g.code && <span style={{ ...muted, marginLeft: 6 }}>{g.code}</span>}
          </span>
          {kids.length > 0 && <span style={muted}>{kids.length}</span>}
          {g.org_unit_count > 0 && (
            <span style={muted} title="Org units operating here">
              {g.org_unit_count} org unit{g.org_unit_count === 1 ? "" : "s"}
            </span>
          )}
          {canWrite && g.kind !== "country" && (
            <button style={smallBtn} onClick={() => setAdding(g.id)} aria-label={`Add to ${g.name}`}>
              + {g.kind === "global" ? "region" : "country"}
            </button>
          )}
          {canWrite && kids.length === 0 && g.kind !== "global" && (
            <button style={{ ...smallBtn, color: "var(--crit)" }} onClick={() => remove(g)} aria-label={`Remove ${g.name}`}>
              ✕
            </button>
          )}
        </div>
        {adding === g.id && <AddCountry parent={g} onDone={() => setAdding(null)} />}
        {isOpen && kids.map((k) => row(k, depth + 1))}
      </div>
    );
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <input
          aria-label="Filter geography"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name or ISO code"
          style={{ flex: 1, fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
        />
        <span style={muted}>{items.filter((g) => g.kind === "country").length} countries</span>
      </div>
      <div style={{ ...muted, marginBottom: 8 }}>
        Seeded from ISO 3166 countries grouped into UN M49 regions. Everything is editable.
      </div>
      {delError && (
        <div role="alert" style={{ fontSize: 12, color: "var(--crit)", marginBottom: 6 }}>
          {delError}
        </div>
      )}
      {roots.map((r) => row(r, 0))}
    </div>
  );
}
