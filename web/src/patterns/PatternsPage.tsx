/** EA pattern catalog (935-pattern-registry US1): every pattern version, filterable by kind,
 * lifecycle, tag and text; opens a version, or imports a new one. */

import React, { useState } from "react";
import { PATTERN_KINDS, PATTERN_LIFECYCLES, usePatterns } from "../api/patterns";
import type { PatternFilters, PatternKind, PatternLifecycle } from "../api/patterns";
import { StatusBadge } from "../ui";
import ImportPanel from "./ImportPanel";
import { KIND_LABELS, LIFECYCLE_LABELS, LIFECYCLE_TONES } from "./labels";
import PatternVersion from "./PatternVersion";
import { useCanManagePatterns } from "./permissions";

const cell: React.CSSProperties = { padding: "7px 10px", borderBottom: "1px solid var(--border)", fontSize: 12.5, textAlign: "left" };

type Mode = { kind: "list" } | { kind: "import"; yaml: string } | { kind: "version"; key: string; version: string };

export default function PatternsPage() {
  const [filters, setFilters] = useState<PatternFilters>({});
  const [mode, setMode] = useState<Mode>({ kind: "list" });
  const canManage = useCanManagePatterns();
  const { data, isLoading } = usePatterns(filters);
  const set = (patch: Partial<PatternFilters>) => setFilters((f) => ({ ...f, ...patch }));
  const open = (key: string, version: string) => setMode({ kind: "version", key, version });

  if (mode.kind === "version") {
    return (
      <PatternVersion
        patternKey={mode.key}
        version={mode.version}
        onBack={() => setMode({ kind: "list" })}
        onSelectVersion={(v) => open(mode.key, v)}
        onNewVersion={(yaml) => setMode({ kind: "import", yaml })}
      />
    );
  }

  if (mode.kind === "import") {
    return (
      <div style={{ padding: "16px 20px", overflow: "auto", height: "100%" }}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>Import pattern</h2>
        <ImportPanel initialYaml={mode.yaml} onImported={open} onCancel={() => setMode({ kind: "list" })} />
      </div>
    );
  }

  const items = data?.items ?? [];
  return (
    <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12, overflow: "auto", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)", flex: 1 }}>
          Governed EA patterns: reference architectures, portfolio rules, transitions and anti-patterns.
          Current versions also appear in the Knowledge base.
        </p>
        {canManage && (
          <button type="button" className="ui-btn ui-btn-primary ui-btn-sm" onClick={() => setMode({ kind: "import", yaml: "" })}>
            Import pattern
          </button>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12.5 }}>
        <input
          aria-label="Search patterns"
          placeholder="Search name or summary"
          value={filters.q ?? ""}
          onChange={(e) => set({ q: e.target.value || undefined })}
        />
        <select aria-label="Kind" value={filters.kind ?? ""} onChange={(e) => set({ kind: (e.target.value || undefined) as PatternKind | undefined })}>
          <option value="">Any kind</option>
          {PATTERN_KINDS.map((k) => <option key={k} value={k}>{KIND_LABELS[k]}</option>)}
        </select>
        <select
          aria-label="Lifecycle"
          value={filters.lifecycle ?? ""}
          onChange={(e) => set({ lifecycle: (e.target.value || undefined) as PatternLifecycle | undefined })}
        >
          <option value="">Any lifecycle</option>
          {PATTERN_LIFECYCLES.map((l) => <option key={l} value={l}>{LIFECYCLE_LABELS[l]}</option>)}
        </select>
        <input aria-label="Tag" placeholder="Tag" value={filters.tag ?? ""} onChange={(e) => set({ tag: e.target.value || undefined })} />
        {Object.values(filters).some((v) => v !== undefined) && (
          <button type="button" className="ui-btn ui-btn-sm" onClick={() => setFilters({})}>Clear filters</button>
        )}
      </div>

      {isLoading ? (
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>
      ) : items.length === 0 ? (
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No patterns match.</div>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              {["Pattern", "Key", "Version", "Kind", "Lifecycle", "Tags"].map((h) => (
                <th key={h} style={{ ...cell, color: "var(--ink-3)", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((v) => (
              <tr key={v.id} onClick={() => open(v.pattern_key, v.version)} style={{ cursor: "pointer" }}>
                <td style={cell}>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); open(v.pattern_key, v.version); }}
                    style={{ background: "none", border: "none", padding: 0, color: "var(--accent)", cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}
                  >
                    {v.name}
                  </button>
                </td>
                <td style={{ ...cell, fontFamily: "var(--mono, monospace)" }}>{v.pattern_key}</td>
                <td style={cell}>{v.version}</td>
                <td style={cell}>{KIND_LABELS[v.kind]}</td>
                <td style={cell}><StatusBadge tone={LIFECYCLE_TONES[v.lifecycle]}>{LIFECYCLE_LABELS[v.lifecycle]}</StatusBadge></td>
                <td style={cell}>{v.tags.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
