// ADP-914.8: unit tests for extractProposedDsl -- a pure function detecting
// the fenced-DSL-block convention the system prompt instructs the assistant
// to use (research.md Decision 3). No rendering, no mocking.

import { describe, expect, it } from "vitest";
import { extractProposedDsl } from "./extractProposedDsl";

describe("extractProposedDsl", () => {
  it("extracts a fenced block whose info-string matches the diagram type", () => {
    const response = [
      "Sure, here's the updated diagram:",
      "```flowchart",
      "flowchart LR",
      "  A[Start] --> B[End]",
      "```",
    ].join("\n");

    expect(extractProposedDsl(response, "flowchart")).toBe("flowchart LR\n  A[Start] --> B[End]");
  });

  it("falls back to a fenced block with no info-string when no type-matching one exists", () => {
    const response = ["Here you go:", "```", "flowchart LR", "  A --> B", "```"].join("\n");

    expect(extractProposedDsl(response, "flowchart")).toBe("flowchart LR\n  A --> B");
  });

  it("returns null for plain conversational text with no fenced block", () => {
    expect(extractProposedDsl("This diagram has 3 steps: Intake, Review, Bind.", "flowchart")).toBeNull();
  });

  it("uses the first fenced block when multiple are present", () => {
    const response = [
      "```flowchart",
      "flowchart LR\n  A --> B",
      "```",
      "and also, unrelated:",
      "```flowchart",
      "flowchart LR\n  C --> D",
      "```",
    ].join("\n");

    expect(extractProposedDsl(response, "flowchart")).toBe("flowchart LR\n  A --> B");
  });

  it("trims the extracted content", () => {
    const response = ["```flowchart", "", "  flowchart LR", "  A --> B", "", "```"].join("\n");

    expect(extractProposedDsl(response, "flowchart")).toBe("flowchart LR\n  A --> B");
  });
});
