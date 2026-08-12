// ADP-914.8: detects the fenced-DSL-block convention the system prompt
// instructs the assistant to use (research.md Decision 3) -- a pure
// function, no dependency on the editor or the chat API.

import type { DiagramType } from "../api";

const FENCE_PATTERN = /```([^\n`]*)\n([\s\S]*?)```/g;

/**
 * Looks for a single fenced code block in `responseText` whose info-string
 * matches `diagramType`; falls back to the first fenced block with no
 * info-string at all when no type-matching one exists. Returns the block's
 * trimmed content, or `null` when no fenced block is present at all (a
 * plain conversational reply, per spec.md's Edge Cases).
 */
export function extractProposedDsl(responseText: string, diagramType: DiagramType): string | null {
  const matches = Array.from(responseText.matchAll(FENCE_PATTERN));
  if (matches.length === 0) return null;

  const typed = matches.find((m) => m[1].trim() === diagramType);
  if (typed) return typed[2].trim();

  const untyped = matches.find((m) => m[1].trim() === "");
  if (untyped) return untyped[2].trim();

  return null;
}
