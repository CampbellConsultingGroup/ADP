/** One pattern version (935 US1–US5): family versions, Overview, YAML, Views and History tabs,
 * and the lifecycle / draft actions the caller is allowed to take. */

import React, { useState } from "react";
import { usePatternFamily, usePatternVersion, usePatternYaml, yamlDownloadUrl } from "../api/patterns";
import type { PatternVersionDetail } from "../api/patterns";
import { StatusBadge } from "../ui";
import History from "./History";
import IssueList from "./IssueList";
import { KIND_LABELS, LIFECYCLE_LABELS, LIFECYCLE_TONES } from "./labels";
import LifecycleDialog from "./LifecycleDialog";

type Tab = "overview" | "yaml" | "history";

const h4: React.CSSProperties = { margin: "14px 0 6px", fontSize: 13 };
const cell: React.CSSProperties = { padding: "5px 8px", borderBottom: "1px solid var(--border)", fontSize: 12, textAlign: "left", verticalAlign: "top" };

function List({ items }: { items: string[] }) {
  if (items.length === 0) return <div style={{ fontSize: 12.5, color: "var(--ink-3)" }}>—</div>;
  return <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>{items.map((i) => <li key={i}>{i}</li>)}</ul>;
}

function cardinality(c: { min: number; max: number | null; per: string | null }): string {
  const range = c.max === c.min ? `${c.min}` : `${c.min}..${c.max ?? "*"}`;
  return c.per ? `${range} per ${c.per}` : range;
}

function Overview({ detail }: { detail: PatternVersionDetail }) {
  const d = detail.definition;
  return (
    <div>
      <p style={{ fontSize: 13, margin: "0 0 8px" }}>{d.summary}</p>
      <IssueList issues={detail.issues} title="Unresolved references" />
      <h4 style={h4}>Motivation</h4>
      <div style={{ fontSize: 12.5 }}><strong>Context.</strong> {d.motivation.context}</div>
      <div style={{ fontSize: 12.5, marginTop: 4 }}><strong>Problem.</strong> {d.motivation.problem}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginTop: 8 }}>
        <div><h4 style={h4}>Forces</h4><List items={d.motivation.forces} /></div>
        <div><h4 style={h4}>Benefits</h4><List items={d.motivation.benefits} /></div>
        <div><h4 style={h4}>Liabilities</h4><List items={d.motivation.liabilities} /></div>
        <div><h4 style={h4}>Principles</h4><List items={d.motivation.principles} /></div>
        <div><h4 style={h4}>Controls</h4><List items={d.motivation.controls} /></div>
      </div>
      <h4 style={h4}>Roles</h4>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <tbody>
          {Object.entries(d.roles).map(([key, r]) => (
            <tr key={key}>
              <td style={{ ...cell, fontWeight: 600 }}>{r.label ?? key}</td>
              <td style={cell}>{r.stereotype ? `«${r.stereotype}» ` : ""}{r.element_type}</td>
              <td style={cell}>{cardinality(r.cardinality)}</td>
              <td style={{ ...cell, fontFamily: "var(--mono, monospace)" }}>{r.selector ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {d.relationships.length > 0 && (
        <>
          <h4 style={h4}>Relationships</h4>
          <List items={d.relationships.map((r) => `${r.id}: ${r.source} ${r.type}${r.via ? ` via ${r.via}` : ""} → ${r.target}${r.label ? ` (${r.label})` : ""}`)} />
        </>
      )}
      {d.constraints.length > 0 && (
        <>
          <h4 style={h4}>Constraints</h4>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <tbody>
              {d.constraints.map((c) => (
                <tr key={c.id}>
                  <td style={{ ...cell, fontWeight: 600 }}>{c.id}</td>
                  <td style={cell}>{c.rule}</td>
                  <td style={cell}>{c.polarity} · {c.severity}{c.for_each ? ` · for each ${c.for_each}` : ""}</td>
                  <td style={{ ...cell, fontFamily: "var(--mono, monospace)" }}>{c.expr}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {detail.relations.length > 0 && (
        <>
          <h4 style={h4}>Related patterns</h4>
          <List items={detail.relations.map((r) => `${r.relation_type} ${r.target_pattern_key}${r.target_resolved ? "" : " (not in registry)"}`)} />
        </>
      )}
    </div>
  );
}

function YamlTab({ patternKey, version }: { patternKey: string; version: string }) {
  const { data, isLoading } = usePatternYaml(patternKey, version);
  return (
    <div>
      <a className="ui-btn ui-btn-sm" href={yamlDownloadUrl(patternKey, version)} download={`${patternKey}@${version}.yaml`}>
        Download YAML
      </a>
      <pre aria-label="Canonical YAML" style={{ fontSize: 12, background: "var(--surface-2, #f6f8fa)", padding: 10, overflow: "auto", marginTop: 8 }}>
        {isLoading ? "Loading…" : data}
      </pre>
    </div>
  );
}

export default function PatternVersion({
  patternKey,
  version,
  onBack,
  onSelectVersion,
}: {
  patternKey: string;
  version: string;
  onBack: () => void;
  onSelectVersion: (version: string) => void;
  onNewVersion: (yaml: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const { data: detail, isLoading, error } = usePatternVersion(patternKey, version);
  const { data: family } = usePatternFamily(patternKey);

  if (isLoading) return <div style={{ padding: 20, fontSize: 13 }}>Loading…</div>;
  if (error || !detail) return <div style={{ padding: 20 }} role="alert">Pattern version not found.</div>;

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "yaml", label: "YAML" },
    { id: "history", label: `History (${detail.history.length})` },
  ];

  return (
    <div style={{ padding: "16px 20px", overflow: "auto", height: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
      <button type="button" className="ui-btn ui-btn-sm" style={{ alignSelf: "flex-start" }} onClick={onBack}>← All patterns</button>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: 17 }}>{detail.name}</h2>
        <StatusBadge tone={LIFECYCLE_TONES[detail.lifecycle]}>{LIFECYCLE_LABELS[detail.lifecycle]}</StatusBadge>
        <span style={{ fontSize: 12, color: "var(--ink-3)", fontFamily: "var(--mono, monospace)" }}>{detail.pattern_key}@{detail.version}</span>
        <span style={{ fontSize: 12, color: "var(--ink-3)" }}>{KIND_LABELS[detail.kind]}</span>
      </div>
      <LifecycleDialog detail={detail} />
      {family && family.versions.length > 1 && (
        <div aria-label="Versions" style={{ display: "flex", gap: 6, flexWrap: "wrap", fontSize: 12 }}>
          {family.versions.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`ui-btn ui-btn-sm${v.version === version ? " ui-btn-primary" : ""}`}
              onClick={() => onSelectVersion(v.version)}
            >
              {v.version} · {LIFECYCLE_LABELS[v.lifecycle]}
            </button>
          ))}
        </div>
      )}
      <div role="tablist" style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)" }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`ui-btn ui-btn-sm${tab === t.id ? " ui-btn-primary" : " ui-btn-ghost"}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "overview" && <Overview detail={detail} />}
      {tab === "yaml" && <YamlTab patternKey={patternKey} version={version} />}
      {tab === "history" && <History events={detail.history} />}
    </div>
  );
}
