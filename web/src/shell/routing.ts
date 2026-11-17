import type { AppView } from "./index";

/**
 * The app's location as a URL hash (ADP-blp.53).
 *
 * Navigation lived only in React state: a reload always landed on Overview, the browser's Back
 * button left the app, and nothing could be linked to. The location is now mirrored into the
 * hash, so Back/Forward, reload and a pasted link all work. A hash (rather than a path) needs no
 * server-side fallback route and cannot collide with /api or /auth.
 *
 *   #/business                         a screen
 *   #/business/<capability id>         a screen with one entity open
 *   #/applications/capabilities/<id>   an application capability
 *   #/patterns/adoptions/<id>          a pattern adoption
 *   #/intake?design=DSN-001            a design-scoped screen
 */
export const APP_VIEWS: readonly AppView[] = [
  "overview", "insights", "designs", "intake", "canvas-v2", "knowledge", "portfolio",
  "governance", "business", "applications", "technical", "diagrams", "strategy", "compliance",
  "agents", "patterns", "admin", "scoring-rubrics",
];

/** What "entity" means for a view: the kind of id a route can carry. */
export type EntityKind =
  | "business_capability"
  | "application"
  | "application_capability"
  | "technical_capability"
  | "agent"
  | "adoption";

export interface AppRoute {
  view: AppView;
  entity: { kind: EntityKind; id: string } | null;
  designId: string | null;
}

const ENTITY_BY_VIEW: Partial<Record<AppView, EntityKind>> = {
  business: "business_capability",
  applications: "application",
  technical: "technical_capability",
  agents: "agent",
};

// A sub-path that selects a different kind of entity on the same screen.
const SUB_PATHS: { view: AppView; segment: string; kind: EntityKind }[] = [
  { view: "applications", segment: "capabilities", kind: "application_capability" },
  { view: "patterns", segment: "adoptions", kind: "adoption" },
];

export function formatRoute(route: AppRoute): string {
  let path = `#/${route.view}`;
  if (route.entity) {
    const sub = SUB_PATHS.find((s) => s.view === route.view && s.kind === route.entity!.kind);
    if (sub) path += `/${sub.segment}/${encodeURIComponent(route.entity.id)}`;
    else if (ENTITY_BY_VIEW[route.view] === route.entity.kind) {
      path += `/${encodeURIComponent(route.entity.id)}`;
    }
  }
  if (route.designId) path += `?design=${encodeURIComponent(route.designId)}`;
  return path;
}

/** The route in a hash, or null when the hash is empty or names no known screen. */
export function parseRoute(hash: string): AppRoute | null {
  const raw = hash.replace(/^#\/?/, "");
  if (!raw) return null;
  const [pathPart, queryPart = ""] = raw.split("?");
  const segments = pathPart.split("/").filter(Boolean).map(decodeURIComponent);
  const view = segments[0] as AppView;
  if (!APP_VIEWS.includes(view)) return null;

  let entity: AppRoute["entity"] = null;
  const sub = SUB_PATHS.find((s) => s.view === view && s.segment === segments[1]);
  if (sub && segments[2]) entity = { kind: sub.kind, id: segments[2] };
  else if (!sub && segments[1] && ENTITY_BY_VIEW[view]) {
    entity = { kind: ENTITY_BY_VIEW[view]!, id: segments[1] };
  }
  const designId = new URLSearchParams(queryPart).get("design");
  return { view, entity, designId: designId || null };
}
