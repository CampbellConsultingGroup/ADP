import { useEffect, useState } from "react";
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

// ── The open entity, read and written by the page that shows it (ADP-blp.57, ADP-blp.68) ──
// App used to hold one "pending id" per kind of entity and hand it to the page as an initial
// prop, remounting the page to apply it. A selection made inside a page never reached the URL.
// Now the page reads its entity from the hash with useRouteEntity and writes it back, so a
// selection is a history entry and a link to an entity is just an address.

/** The screen that shows each kind of entity. */
export const VIEW_FOR_ENTITY: Record<EntityKind, AppView> = {
  business_capability: "business",
  application: "applications",
  application_capability: "applications",
  technical_capability: "technical",
  agent: "agents",
  adoption: "patterns",
};

export function entityHref(kind: EntityKind, id: string): string {
  return formatRoute({ view: VIEW_FOR_ENTITY[kind], entity: { kind, id }, designId: null });
}

/** Go to an entity's own screen (from an event handler; in markup use <EntityLink>). */
export function goToEntity(kind: EntityKind, id: string): void {
  window.location.hash = entityHref(kind, id);
}

/** Raised after the hash is changed with pushState, which fires no hashchange of its own. */
export const ROUTE_EVENT = "adp:route";

function routeEntityId(kind: EntityKind): string | null {
  const route = parseRoute(window.location.hash);
  return route?.entity?.kind === kind ? route.entity.id : null;
}

/**
 * Open an entity (or with null, close the one open) as a new history entry. On the entity's
 * own screen the page's other parameters (?tab=...) are kept; from another screen this is an
 * ordinary navigation. Does nothing when there is no route in the URL (a component rendered
 * outside the shell).
 */
export function openEntity(kind: EntityKind, id: string | null): void {
  const current = parseRoute(window.location.hash);
  if (!current) return;
  const view = VIEW_FOR_ENTITY[kind];
  if (current.view !== view) {
    if (id !== null) window.location.hash = entityHref(kind, id);
    return;
  }
  if (id === null && current.entity?.kind !== kind) return; // some other kind is open: leave it
  if (id !== null && current.entity?.kind === kind && current.entity.id === id) return;
  const { params } = splitHash();
  const path = formatRoute({ view, entity: id === null ? null : { kind, id }, designId: null });
  const query = params.toString();
  window.history.pushState(null, "", query ? `${path}?${query}` : path);
  window.dispatchEvent(new Event(ROUTE_EVENT));
}

/**
 * The entity of one kind that is open on this screen, kept in the URL. `initial` is used when
 * the URL names none (a caller that opens a page on a given entity; tests).
 */
export function useRouteEntity(
  kind: EntityKind,
  initial: string | null = null,
): [string | null, (id: string | null) => void] {
  const [id, setId] = useState<string | null>(() => routeEntityId(kind) ?? initial);

  useEffect(() => {
    // Follow Back/Forward, a link clicked elsewhere on the page, and other users of this hook.
    const sync = () => {
      if (parseRoute(window.location.hash)) setId(routeEntityId(kind));
    };
    window.addEventListener("popstate", sync);
    window.addEventListener("hashchange", sync);
    window.addEventListener(ROUTE_EVENT, sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("hashchange", sync);
      window.removeEventListener(ROUTE_EVENT, sync);
    };
  }, [kind]);

  const set = (next: string | null) => {
    setId(next);
    openEntity(kind, next);
  };
  return [id, set];
}

// ── Page state in the URL (ADP-blp.68) ─────────────────────────────────────────
// A page's own choices -- which tab is showing -- live in the hash query string beside the
// route (`#/business?tab=capabilities`), so a reload or a shared link opens the same tab.
// The route itself is still written by App; these helpers only touch one named parameter.

const PARAM_EVENT = "adp:hashparam";

function splitHash(): { path: string; params: URLSearchParams } {
  const raw = window.location.hash;
  const at = raw.indexOf("?");
  return {
    path: at === -1 ? raw : raw.slice(0, at),
    params: new URLSearchParams(at === -1 ? "" : raw.slice(at + 1)),
  };
}

export function readHashParam(name: string): string | null {
  return splitHash().params.get(name);
}

/** Set (or with null, remove) one hash query parameter without adding a history entry. */
export function writeHashParam(name: string, value: string | null): void {
  const { path, params } = splitHash();
  if (!path.startsWith("#/")) return; // no route in the URL yet: nothing to attach to
  if (value === null) params.delete(name);
  else params.set(name, value);
  const query = params.toString();
  window.history.replaceState(null, "", query ? `${path}?${query}` : path);
  window.dispatchEvent(new Event(PARAM_EVENT));
}

/**
 * A piece of page state kept in the URL. `allowed` lists the valid values; anything else in
 * the URL falls back to `initial`, as does a missing parameter.
 */
export function useHashParam<T extends string>(
  name: string,
  allowed: readonly T[],
  initial: T,
): [T, (value: T) => void] {
  const read = (): T => {
    const value = readHashParam(name);
    return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : initial;
  };
  const [value, setValue] = useState<T>(read);

  useEffect(() => {
    const sync = () => setValue(read());
    window.addEventListener("popstate", sync);
    window.addEventListener("hashchange", sync);
    window.addEventListener(PARAM_EVENT, sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("hashchange", sync);
      window.removeEventListener(PARAM_EVENT, sync);
    };
    // `read` only depends on the arguments, which are constants at every call site.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  const set = (next: T) => {
    setValue(next);
    writeHashParam(name, next === initial ? null : next);
  };
  return [value, set];
}
