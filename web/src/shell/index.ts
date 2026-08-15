/**
 * App view identifiers used for navigation (see ui/AppShell).
 * ADP-914.13: "canvas" (the legacy C4Canvas/Workspace view) removed -- "canvas-v2"
 * (C4DesignView) is now the sole design-editing surface.
 */
export type AppView =
  | "overview"
  | "insights"
  | "designs"
  | "intake"
  | "recommend"
  | "canvas-v2"
  | "knowledge"
  | "portfolio"
  | "governance"
  | "business"
  | "applications"
  | "technical"
  | "diagrams"
  | "strategy"
  | "admin";
