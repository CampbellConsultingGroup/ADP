// ADP-SPEC-046 User Story 2: render + export.
//
// NOT a port of the sibling project's ExportMenu.tsx -- that component's PNG
// path posts to a `resvg-js`-backed endpoint ADP doesn't have. This renders
// the current model to SVG entirely client-side (the vendored, escapeXml-
// hardened renderer -- no network call for SVG at all), offers it as a
// direct download, and separately posts that same SVG to ADP's own
// cairosvg-backed export endpoint for PNG (research.md Decision 3).

import { useState } from "react";
import { renderToSvg } from "../core/render/svg-renderer";
import type { DiagramModel } from "../core/index";
import { exportDiagramPng } from "../api";

export interface ExportActionProps {
  diagramId: string;
  model: DiagramModel;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportAction({ diagramId, model }: ExportActionProps) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleExportSvg() {
    const svg = renderToSvg(model);
    downloadBlob(new Blob([svg], { type: "image/svg+xml" }), `${diagramId}.svg`);
  }

  async function handleExportPng() {
    setExporting(true);
    setError(null);
    try {
      const svg = renderToSvg(model);
      const png = await exportDiagramPng(diagramId, svg);
      downloadBlob(png, `${diagramId}.png`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div>
      <button type="button" onClick={handleExportSvg}>
        Export SVG
      </button>
      <button type="button" onClick={handleExportPng} disabled={exporting}>
        {exporting ? "Exporting…" : "Export PNG"}
      </button>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
