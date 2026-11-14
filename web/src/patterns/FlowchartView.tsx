/** Read-only rendering of a pattern view's flowchart text (935 US4, research D11).
 *
 * parse (vendored diagram-core flowchart dialect) → auto-layout → SVG, mounted as an <img> data
 * URL so nothing in the rendered markup can ever execute (defence in depth on top of the server's
 * label sanitisation and the renderer's own text escaping). The source is shown for copying. */

import React, { useMemo, useState } from "react";
import { parseFlowchart } from "../diagrams/core/dsl/flowchart-parser";
import { isParseSuccess } from "../diagrams/core/dsl/types";
import { autoLayout } from "../diagrams/core/model/auto-layout";
import { renderToSvg } from "../diagrams/core/render/svg-renderer";

export function flowchartToSvg(text: string): { svg: string } | { error: string } {
  const result = parseFlowchart(text);
  if (!isParseSuccess(result)) {
    return { error: result.errors.map((e) => `line ${e.line}: ${e.message}`).join("; ") };
  }
  return { svg: renderToSvg(autoLayout(result.model)) };
}

export default function FlowchartView({ flowchart, title, truncated = [] }: { flowchart: string; title: string; truncated?: string[] }) {
  const rendered = useMemo(() => flowchartToSvg(flowchart), [flowchart]);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(flowchart);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {truncated.map((t) => <div key={t} className="ui-alert warn">{t}</div>)}
      {"svg" in rendered ? (
        <div style={{ overflow: "auto", border: "1px solid var(--border)", borderRadius: 6, background: "#fff", padding: 8 }}>
          <img alt={title} src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(rendered.svg)}`} style={{ maxWidth: "none" }} />
        </div>
      ) : (
        <div className="ui-alert crit" role="alert">This view could not be drawn: {rendered.error}</div>
      )}
      <details>
        <summary style={{ fontSize: 12.5, cursor: "pointer" }}>Flowchart source</summary>
        <button type="button" className="ui-btn ui-btn-sm" style={{ margin: "6px 0" }} onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </button>
        <pre aria-label="Flowchart source" style={{ fontSize: 12, background: "var(--surface-2, #f6f8fa)", padding: 10, overflow: "auto" }}>{flowchart}</pre>
      </details>
    </div>
  );
}

export function ViewsTab({ patternKey, version, render }: {
  patternKey: string;
  version: string;
  render: (view: "structure" | "catalog" | "traceability", depth: number) => React.ReactNode;
}) {
  const [view, setView] = useState<"structure" | "catalog" | "traceability">("structure");
  const [depth, setDepth] = useState(1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }} data-pattern={`${patternKey}@${version}`}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12.5 }}>
        <select aria-label="View" value={view} onChange={(e) => setView(e.target.value as typeof view)}>
          <option value="structure">Structure</option>
          <option value="catalog">Catalog (related patterns)</option>
          <option value="traceability">Traceability</option>
        </select>
        {view === "catalog" && (
          <select aria-label="Depth" value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            {[1, 2, 3].map((d) => <option key={d} value={d}>{d} hop{d > 1 ? "s" : ""}</option>)}
          </select>
        )}
      </div>
      {render(view, depth)}
    </div>
  );
}
