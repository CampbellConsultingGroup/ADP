import type { RequirementKind } from "../api/intake";

/** Requirement kind → categorical wayfinding hue (theme-aware token). */
export const KIND_HUE: Record<RequirementKind, string> = {
  functional: "var(--accent)",
  non_functional: "var(--biz)",
  constraint: "var(--tec)",
  driver: "var(--good)",
};

export const kindLabel = (kind: string): string => kind.replace("_", " ");
