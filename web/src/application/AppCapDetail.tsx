// 937-application-capabilities: one application capability's detail -- path, name/description,
// and the three link editors (spec clarification: links are edited only here). Pickers offer only
// the levels the mapping rules allow, so the server's 422 is a backstop, not the normal path.

import { useState } from "react";
import type React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";
import type { ApplicationListResponse, TechCapListResponse } from "../api/application";
import type { BusinessCapability } from "../api/business";
import { useCapabilities } from "../api/business";
import type { CapRef, LinkKind } from "../api/appCapabilities";
import {
  MISSING_TECHNICAL_CAPABILITY,
  errorDetail,
  useAddAppCapLink,
  useAppCapability,
  useDeleteAppCapability,
  useRemoveAppCapLink,
  useUpdateAppCapability,
} from "../api/appCapabilities";
import { Button } from "../ui";
import { MissingTechBadge } from "./AppCapTree";
import RealizationList from "./RealizationList";

export function pathLabel(path: CapRef[], name?: string): string {
  return [...path.map((p) => p.name), ...(name ? [name] : [])].join(" › ");
}

interface Option {
  id: string;
  label: string;
}

/** Business capability L3s only, labelled with their L1/L2 path (rule: business L3 <-> app L3). */
export function businessL3Options(caps: BusinessCapability[]): Option[] {
  const byId = new Map(caps.map((c) => [c.id, c]));
  const label = (c: BusinessCapability): string => {
    const parts = [c.name];
    let p = c.parent_id ? byId.get(c.parent_id) : undefined;
    while (p) {
      parts.unshift(p.name);
      p = p.parent_id ? byId.get(p.parent_id) : undefined;
    }
    return parts.join(" › ");
  };
  return caps
    .filter((c) => c.level === 3)
    .map((c) => ({ id: c.id, label: label(c) }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

/** Technical capabilities at L2 or L3 only (rule: app L3 -> technical L2/L3). */
export function technicalOptions(caps: { id: string; name: string; level: number; parent_id: string | null }[]): Option[] {
  const byId = new Map(caps.map((c) => [c.id, c]));
  const label = (id: string): string => {
    const parts: string[] = [];
    let c = byId.get(id);
    while (c) {
      parts.unshift(c.name);
      c = c.parent_id ? byId.get(c.parent_id) : undefined;
    }
    return parts.join(" › ");
  };
  return caps
    .filter((c) => c.level === 2 || c.level === 3)
    .map((c) => ({ id: c.id, label: `${label(c.id)} (L${c.level})` }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

const sectionHead: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: "var(--ink-2)", margin: "14px 0 6px" };
const removeBtn: React.CSSProperties = { background: "none", border: "none", cursor: "pointer", fontSize: 11, color: "var(--crit)" };

function LinkSection({
  title,
  hint,
  kind,
  acId,
  linked,
  options,
  canWrite,
  emptyText,
}: {
  title: string;
  hint: string;
  kind: LinkKind;
  acId: string;
  linked: Option[];
  options: Option[];
  canWrite: boolean;
  emptyText: string;
}) {
  const add = useAddAppCapLink();
  const remove = useRemoveAppCapLink();
  const [choice, setChoice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const linkedIds = new Set(linked.map((l) => l.id));
  const available = options.filter((o) => !linkedIds.has(o.id));

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      setError(null);
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  return (
    <section aria-label={title}>
      <h4 style={sectionHead}>{title}</h4>
      <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>{hint}</div>
      {linked.length === 0 && <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{emptyText}</div>}
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {linked.map((l) => (
          <li key={l.id} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, padding: "2px 0" }}>
            <span style={{ flex: 1 }}>{l.label}</span>
            {canWrite && (
              <button
                style={removeBtn}
                aria-label={`Remove ${l.label}`}
                onClick={() => run(() => remove.mutateAsync({ id: acId, kind, targetId: l.id }))}
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      {canWrite && (
        <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
          <select
            aria-label={`Add ${title.toLowerCase()}`}
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
            style={{ flex: 1, fontSize: 12, padding: "2px 4px" }}
          >
            <option value="">Select…</option>
            {available.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
          <Button
            size="sm"
            disabled={!choice || add.isPending}
            onClick={() =>
              run(async () => {
                await add.mutateAsync({ id: acId, kind, targetId: choice });
                setChoice("");
              })
            }
          >
            Link
          </Button>
        </div>
      )}
      {error && <div role="alert" style={{ fontSize: 12, color: "var(--crit)", marginTop: 4 }}>{error}</div>}
    </section>
  );
}

export default function AppCapDetail({
  acId,
  canWrite,
  onDeleted,
}: {
  acId: string;
  canWrite: boolean;
  onDeleted: () => void;
}): React.ReactElement {
  const { data: ac, isLoading, error } = useAppCapability(acId);
  const { data: bizCaps } = useCapabilities();
  const { data: techCaps } = useQuery<TechCapListResponse>({
    queryKey: ["tech-caps"],
    queryFn: () => apiGet("/api/v1/technical-capabilities"),
  });
  const { data: apps } = useQuery<ApplicationListResponse>({
    queryKey: ["applications"],
    queryFn: () => apiGet("/api/v1/applications"),
  });
  const update = useUpdateAppCapability();
  const del = useDeleteAppCapability();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  if (isLoading) return <div style={{ color: "var(--ink-3)", fontSize: 13 }}>Loading…</div>;
  if (error || !ac) return <div role="alert" style={{ color: "var(--crit)", fontSize: 13 }}>Could not load this application capability.</div>;

  const startEdit = () => {
    setName(ac.name);
    setDescription(ac.description ?? "");
    setFormError(null);
    setEditing(true);
  };
  const save = async () => {
    try {
      await update.mutateAsync({ id: ac.id, body: { name: name.trim(), description: description.trim() || null } });
      setEditing(false);
    } catch (err) {
      setFormError(errorDetail(err));
    }
  };
  const remove = async () => {
    if (!confirm(`Delete "${ac.name}"? Its links are removed too.`)) return;
    try {
      await del.mutateAsync(ac.id);
      onDeleted();
    } catch (err) {
      setFormError(errorDetail(err));
    }
  };

  const isLeaf = ac.level === 3;

  return (
    <div aria-label="Application capability detail">
      {ac.path.length > 0 && <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{pathLabel(ac.path)}</div>}
      {editing ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, margin: "6px 0" }}>
          <input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} style={{ fontSize: 14, padding: "3px 6px" }} />
          <textarea
            aria-label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            style={{ fontSize: 13, padding: "3px 6px" }}
          />
          <div style={{ display: "flex", gap: 6 }}>
            <Button size="sm" variant="primary" disabled={!name.trim() || update.isPending} onClick={save}>Save</Button>
            <Button size="sm" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "4px 0" }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>{ac.name}</h3>
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>L{ac.level}</span>
          {ac.warnings.includes(MISSING_TECHNICAL_CAPABILITY) && <MissingTechBadge />}
          {canWrite && (
            <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <Button size="sm" onClick={startEdit}>Edit</Button>
              <Button size="sm" variant="danger" onClick={remove}>Delete</Button>
            </span>
          )}
        </div>
      )}
      {!editing && ac.description && <p style={{ fontSize: 13, color: "var(--ink-2)", margin: "4px 0" }}>{ac.description}</p>}
      {formError && <div role="alert" style={{ fontSize: 12, color: "var(--crit)" }}>{formError}</div>}

      {!isLeaf && (
        <p style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 12 }}>
          Level {ac.level} is for navigation and grouping only. Links are made at Level 3.
        </p>
      )}
      {isLeaf && (
        <>
          <LinkSection
            title="Supports business capabilities"
            hint="Business capabilities are mapped at L3."
            kind="business"
            acId={ac.id}
            canWrite={canWrite}
            emptyText="Not linked to any business capability."
            linked={ac.business_capabilities.map((c) => ({ id: c.id, label: pathLabel(c.path, c.name) }))}
            options={businessL3Options(bizCaps?.items ?? [])}
          />
          <LinkSection
            title="Depends on technical capabilities"
            hint="Map to a technical L3 where the dependency is architecturally meaningful, otherwise its L2. Don't map incidental usage."
            kind="technical"
            acId={ac.id}
            canWrite={canWrite}
            emptyText="No technical capability yet — this raises a governance warning (saving is not blocked)."
            linked={ac.technical_capabilities.map((c) => ({ id: c.id, label: `${pathLabel(c.path, c.name)} (L${c.level})` }))}
            options={technicalOptions(techCaps?.items ?? [])}
          />
          <RealizationList
            acId={ac.id}
            canWrite={canWrite}
            linked={ac.realized_by}
            options={(apps?.items ?? []).map((a) => ({ id: a.id, label: a.name })).sort((a, b) => a.label.localeCompare(b.label))}
          />
        </>
      )}
    </div>
  );
}
