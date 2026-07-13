import type { C4Level, Element, ElementKind, Relationship } from "../types";

export const C4_LEVEL_KINDS: Record<C4Level, ElementKind[]> = {
  context: ["person", "system"],
  container: ["system", "container"],
  component: ["container", "component"],
};

export function filterElementsForLevel(elements: Element[], level: C4Level): Element[] {
  const kinds = C4_LEVEL_KINDS[level];
  return elements.filter((e) => kinds.includes(e.kind));
}

export function filterRelationshipsForLevel(
  relationships: Relationship[],
  visibleElementIds: Set<string>,
): Relationship[] {
  return relationships.filter(
    (r) => visibleElementIds.has(r.source) && visibleElementIds.has(r.target),
  );
}
