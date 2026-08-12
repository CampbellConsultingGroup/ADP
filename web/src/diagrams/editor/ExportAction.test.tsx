// ADP-SPEC-053 T013: no test file exists for ExportAction.tsx for any diagram type today --
// confirms the tool's existing, already-generic export path (spec.md FR-006) needs no C4-specific
// change, including the one real visual distinction between the canvas and export renderers for a
// `person`-shaped node (Canvas.tsx/shapes.tsx -- vendored, no dedicated 'person' case, falls back
// to a plain <rect> -- vs. svg-renderer.ts's export path, which *does* have one: a more heavily
// rounded <rect rx="24" ry="24">, not a distinct person glyph -- both are pre-existing, unchanged,
// and correct in their own contexts).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ExportAction } from "./ExportAction";
import { renderToSvg } from "../core/render/svg-renderer";
import type { DiagramModel } from "../core/index";
import * as api from "../api";

vi.mock("../api");

const mockedApi = vi.mocked(api);

const C4_MODEL: DiagramModel = {
  diagramTypeId: "c4-context",
  nodes: [
    { id: "user", label: "Customer", shape: "person", role: "person", position: { x: 0, y: 0 } },
    { id: "sys", label: "Payments Service", shape: "rectangle", role: "system", position: { x: 200, y: 0 } },
  ],
  edges: [{ id: "e1", sourceId: "user", targetId: "sys", label: "Uses" }],
  containers: [],
};

describe("renderToSvg: C4-family model export (ADP-SPEC-053 FR-006)", () => {
  it("renders a person-shaped node using the export renderer's distinct rounded treatment", () => {
    const svg = renderToSvg(C4_MODEL);
    // svg-renderer.ts's dedicated 'person' case (distinct from the canvas's plain-rect fallback
    // for the same shape -- both correct, in different contexts, per T008's note).
    expect(svg).toContain('rx="24"');
    expect(svg).toContain("Customer");
    // Label wraps across separate <tspan> lines, same as the canvas renderer -- check each word.
    expect(svg).toContain("Payments");
    expect(svg).toContain("Service");
  });
});

describe("ExportAction: exports a C4 diagram the same way as any other type", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:mock-url"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("downloads an SVG file when Export SVG is clicked", async () => {
    const user = userEvent.setup();
    render(<ExportAction diagramId="diag-c4-1" model={C4_MODEL} />);

    await user.click(screen.getByText("Export SVG"));

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    const blob = vi.mocked(URL.createObjectURL).mock.calls[0][0] as Blob;
    expect(blob.type).toBe("image/svg+xml");
  });

  it("posts the rendered SVG for PNG export the same way every other diagram type already does", async () => {
    mockedApi.exportDiagramPng.mockResolvedValue(new Blob(["fake-png"], { type: "image/png" }));
    const user = userEvent.setup();
    render(<ExportAction diagramId="diag-c4-1" model={C4_MODEL} />);

    await user.click(screen.getByText("Export PNG"));

    expect(mockedApi.exportDiagramPng).toHaveBeenCalledTimes(1);
    const [diagramId, svg] = mockedApi.exportDiagramPng.mock.calls[0];
    expect(diagramId).toBe("diag-c4-1");
    expect(svg).toContain('rx="24"');
  });
});
