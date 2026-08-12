// ADP-SPEC-052 FR-010 regression guard (User Story 2): default (non-customized) shape fill/stroke
// colors are a deliberate, already-resolved product decision to stay theme-independent (spec.md,
// research.md Decision 4) -- "no code change to shapes.tsx's color defaults is in scope for this
// feature at all". This test exists so a future edit that accidentally swaps these literals for a
// theme-reactive token fails loudly here, rather than silently shipping a behavior change FR-010
// explicitly rejected.

import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { renderNodeShape, SELECTION_STROKE } from "./shapes";
import type { DiagramNode } from "../core/index";

const NODE: DiagramNode = {
  id: "n1",
  label: "Intake",
  shape: "rectangle",
  position: { x: 0, y: 0 },
};

describe("shapes.tsx: FR-010 default colors stay fixed regardless of theme", () => {
  it("renders default (unset) fill/stroke as the original literal hex values, unselected", () => {
    const { container } = render(<svg>{renderNodeShape(NODE, false)}</svg>);
    const rect = container.querySelector("rect");
    expect(rect?.getAttribute("fill")).toBe("#ffffff");
    expect(rect?.getAttribute("stroke")).toBe("#333333");
  });

  it("an explicit custom color is preserved verbatim, unaffected by theme (FR-011)", () => {
    const customNode: DiagramNode = { ...NODE, style: { fillColor: "#ff00aa", strokeColor: "#00aaff" } };
    const { container } = render(<svg>{renderNodeShape(customNode, false)}</svg>);
    const rect = container.querySelector("rect");
    expect(rect?.getAttribute("fill")).toBe("#ff00aa");
    expect(rect?.getAttribute("stroke")).toBe("#00aaff");
  });

  it("selection highlight uses the app's accent token, not a hardcoded hex (FR-009)", () => {
    const { container } = render(<svg>{renderNodeShape(NODE, true)}</svg>);
    const rect = container.querySelector("rect");
    expect(SELECTION_STROKE).toBe("var(--accent)");
    expect(rect?.getAttribute("stroke")).toBe("var(--accent)");
    // Default fill is still unaffected by selection state (FR-010).
    expect(rect?.getAttribute("fill")).toBe("#ffffff");
  });
});
