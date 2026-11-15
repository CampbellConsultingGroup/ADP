/** "Save as diagram" (936 FR-022, research D10): turn a rendered pattern view into a DiagramSeed
 * so the Diagrams editor opens it as a new, unsaved flowchart (saving needs WRITE_DIAGRAM as
 * usual). Pure. */

import { parseFlowchart } from "../diagrams/core/dsl/flowchart-parser";
import { isParseSuccess } from "../diagrams/core/dsl/types";
import { autoLayout } from "../diagrams/core/model/auto-layout";
import type { DiagramSeed } from "../diagrams/generators";

export function flowchartToSeed(flowchart: string, title: string): DiagramSeed | null {
  const result = parseFlowchart(flowchart);
  if (!isParseSuccess(result)) return null;
  return { title: title.slice(0, 200), diagramType: "flowchart", model: autoLayout(result.model) };
}
