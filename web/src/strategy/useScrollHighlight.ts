import { useEffect, useRef } from "react";

/** Scrolls the row registered for `focusId` into view and briefly
 * highlights it -- shared by ThemeList and InitiativeList, the two strategy
 * entities with no dedicated detail view (only a flat list with inline
 * edit), mirroring 043-capability-heat-map's CapabilityNode/
 * focusCapabilityId precedent (research.md Decision 3: "drill-through
 * target is a scroll-and-highlight, not a new page" for exactly this
 * shape of entity). Objective, which *does* have a real detail view
 * (ObjectiveDetail), uses the existing drill-in (selectedObjectiveId)
 * mechanism instead -- this hook is deliberately not used there. */
export function useScrollHighlight(focusId: string | null | undefined) {
  const nodeRefs = useRef(new Map<string, HTMLDivElement>());

  useEffect(() => {
    if (!focusId) return;
    nodeRefs.current.get(focusId)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusId]);

  function registerRef(id: string) {
    return (el: HTMLDivElement | null) => {
      if (el) nodeRefs.current.set(id, el);
      else nodeRefs.current.delete(id);
    };
  }

  return { registerRef };
}
