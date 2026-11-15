// 935-pattern-registry FR-017 / SC-005: every committed pattern-view golden (rendered by the
// Python adp.patterns.render module) must parse with ZERO errors in the in-app flowchart dialect.
// This replaces the source bundle's mermaid-cli job (spec GT-8): ADP renders with diagram-core,
// not real Mermaid.

import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parseFlowchart } from "../diagrams/core/dsl/flowchart-parser";
import { isParseSuccess } from "../diagrams/core/dsl/types";

// Vitest runs from web/ (jsdom gives import.meta.url an http scheme, so resolve from the cwd).
const GOLDENS = resolve(process.cwd(), "..", "tests", "unit", "patterns", "goldens");
const files = readdirSync(GOLDENS).filter((f) => f.endsWith(".mmd")).sort();

describe("pattern view goldens parse in diagram-core", () => {
  it("has goldens for all three views", () => {
    for (const view of ["structure__", "catalog__", "traceability__"]) {
      expect(files.some((f) => f.startsWith(view))).toBe(true);
    }
  });

  it.each(files)("%s", (file) => {
    const text = readFileSync(join(GOLDENS, file), "utf-8");
    const result = parseFlowchart(text);
    if (!isParseSuccess(result)) {
      throw new Error(`${file}: ${JSON.stringify(result.errors, null, 2)}`);
    }
    // Every declared node survives, and every edge resolves to declared nodes.
    const declared = text.split("\n").filter((l) => /^\s+[A-Za-z0-9_]+[[({]/.test(l)).length;
    expect(result.model.nodes.length).toBe(declared);
    const ids = new Set(result.model.nodes.map((n) => n.id));
    for (const edge of result.model.edges) {
      expect(ids.has(edge.sourceId)).toBe(true);
      expect(ids.has(edge.targetId)).toBe(true);
    }
    // Labels never carry literal quote characters (the dialect keeps quotes verbatim).
    for (const node of result.model.nodes) expect(node.label).not.toContain('"');
  });
});
