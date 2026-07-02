import type { C4ElementStyle, C4Theme, ElementKind } from "../types";

const _DEFAULT_STYLE: C4ElementStyle = {
  fill: "#888888",
  stroke: "#666666",
  color: "#ffffff",
  shape: "box",
};

/**
 * The ONLY function that maps an element kind to a visual style.
 * Style always derives from the locked theme — never from element data.
 * ART-XII: no per-element style overrides permitted.
 */
export function getElementStyle(
  kind: ElementKind,
  theme: C4Theme | null | undefined,
): C4ElementStyle {
  if (!theme) return _DEFAULT_STYLE;
  const entry = theme.styles[kind];
  if (!entry) return _DEFAULT_STYLE;
  return {
    fill: entry.fill,
    stroke: entry.stroke,
    color: entry.color,
    shape: entry.shape === "actor" ? "actor" : "box",
  };
}
