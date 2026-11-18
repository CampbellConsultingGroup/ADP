/** EA pattern catalog (935-pattern-registry US1): every pattern version, filterable by kind,
 * lifecycle, tag and text; opens a version, or imports a new one. */

import { useState } from "react";
import { PATTERN_KINDS, PATTERN_LIFECYCLES, usePatterns } from "../api/patterns";
import type { PatternFilters, PatternKind, PatternLifecycle } from "../api/patterns";
import { StatusBadge } from "../ui";
import AdoptionsList from "./AdoptionsList";
import ImportPanel from "./ImportPanel";
import { KIND_LABELS, LIFECYCLE_LABELS, LIFECYCLE_TONES } from "./labels";
import PatternVersion from "./PatternVersion";
import { useCanManagePatterns } from "./permissions";
import type { DiagramSeed } from "../diagrams/generators";
import { PageHeader, Loading, EmptyState, Table } from "../ui/primitives";

type Mode = { kind: "list" } | { kind: "import"; yaml: string } | { kind: "version"; key: string; version: string };

export default function PatternsPage({
  onGenerateDiagram,
  initialAdoptionId = null,
}: {
  onGenerateDiagram?: (seed: DiagramSeed) => void;
  /** 939-governance-architecture-health: open this adoption (in the Adoptions section) on arrival. */
  initialAdoptionId?: string | null;
} = {}) {
  const [section, setSection] = useState<"patterns" | "adoptions">(initialAdoptionId ? "adoptions" : "patterns");
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div role="tablist" aria-label="Patterns sections" style={{ display: "flex", gap: 4, padding: "10px 20px 0" }}>
        {(["patterns", "adoptions"] as const).map((sct) => (
          <button
            key={sct}
            type="button"
            role="tab"
            aria-selected={section === sct}
            className={`ui-btn ui-btn-sm${section === sct ? " ui-btn-primary" : " ui-btn-ghost"}`}
            onClick={() => setSection(sct)}
          >
            {sct === "patterns" ? "Patterns" : "Adoptions"}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        {section === "patterns" ? <PatternCatalog /> : <AdoptionsList onGenerateDiagram={onGenerateDiagram} initialSelected={initialAdoptionId} />}
      </div>
    </div>
  );
}

function PatternCatalog() {
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
  const filtered = Object.values(filters).some((v) => v !== undefined);
  return (
    <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12, overflow: "auto", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ flex: 1 }}>
          <PageHeader
            compact
            title="Patterns"
            lede="Governed EA patterns: reference architectures, portfolio rules, transitions and anti-patterns. Current versions also appear in the Knowledge base."
          />
        </div>
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
        {filtered && (
          <button type="button" className="ui-btn ui-btn-sm" onClick={() => setFilters({})}>Clear filters</button>
        )}
      </div>

      {isLoading ? (
        <Loading />
      ) : items.length === 0 ? (
        filtered ? (
          <EmptyState compact title="No patterns match these filters" action={
            <button type="button" className="ui-btn ui-btn-sm" onClick={() => setFilters({})}>Clear filters</button>
          }>
            Change or clear the filters to see more patterns.
          </EmptyState>
        ) : (
          <EmptyState
            compact
            icon="tags"
            title="No patterns yet"
            why="A pattern is a governed, versioned rule or reference architecture written as YAML. Adopting one checks a domain or set of applications against it."
          >
            {canManage
              ? "Use Import pattern to add the first one."
              : "Your role can view patterns but not import them."}
          </EmptyState>
        )
      ) : (
        <Table caption="Patterns" columns={["Pattern", "Key", "Version", "Kind", "Lifecycle", "Tags"]}>
            {items.map((v) => (
              <tr key={v.id} onClick={() => open(v.pattern_key, v.version)} className="clickable">
                <td>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); open(v.pattern_key, v.version); }}
                    style={{ background: "none", border: "none", padding: 0, color: "var(--accent)", cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}
                  >
                    {v.name}
                  </button>
                </td>
                <td style={{ fontFamily: "var(--mono, monospace)" }}>{v.pattern_key}</td>
                <td>{v.version}</td>
                <td>{KIND_LABELS[v.kind]}</td>
                <td><StatusBadge tone={LIFECYCLE_TONES[v.lifecycle]}>{LIFECYCLE_LABELS[v.lifecycle]}</StatusBadge></td>
                <td>{v.tags.join(", ") || "—"}</td>
              </tr>
            ))}
        </Table>
      )}
    </div>
  );
}
