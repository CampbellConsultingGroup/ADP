/**
 * Inline SVG icons.
 *
 * Inline rather than an icon package or icon font: no new dependency, nothing fetched over the
 * network, and `stroke="currentColor"` means one definition works on every button variant
 * without per-variant assets (research §4).
 *
 * Always `aria-hidden`: every icon in this app sits next to a visible text label or on a control
 * that already has an accessible name, so exposing them would only add noise to the
 * accessibility tree.
 */

export type IconName =
  | 'diamond'
  | 'plus'
  | 'download'
  | 'sparkle'
  | 'upload'
  | 'share'
  | 'search'
  | 'trash'
  | 'arrow-right'
  | 'group'
  | 'chevron-down'
  | 'chevron-right'
  | 'close'
  | 'check'
  | 'warning'
  | 'history'
  | 'send'
  | 'pencil'
  | 'palette'
  | 'layout'
  | 'info'
  // ADP-SPEC-052 FR-004: shape-picker palette glyphs — one per addable NodeShape
  // (data-model.md's exact mapping), replacing the single-character Unicode glyphs
  // Canvas.tsx's SHAPE_GLYPHS previously used.
  | 'shape-rectangle'
  | 'shape-rounded'
  | 'shape-circle'
  | 'shape-stadium'
  | 'shape-subroutine'
  | 'shape-double-circle'
  | 'shape-hexagon'
  | 'shape-parallelogram'
  | 'shape-trapezoid'
  | 'shape-asymmetric';

/** Path data only — the wrapper supplies sizing, colour, and ARIA. `diamond` and `check` are
 *  filled; the rest are 1.5px strokes on a 16-unit grid. */
const PATHS: Record<IconName, { d: string; filled?: boolean }[]> = {
  diamond: [{ d: 'M8 1.5 14.5 8 8 14.5 1.5 8Z', filled: true }],
  plus: [{ d: 'M8 3.5v9M3.5 8h9' }],
  download: [{ d: 'M8 2.5v7.5M4.5 7 8 10.5 11.5 7M2.5 13h11' }],
  sparkle: [{ d: 'M8 2l1.6 3.9L13.5 7.5 9.6 9.1 8 13l-1.6-3.9L2.5 7.5l3.9-1.6Z' }],
  upload: [{ d: 'M8 10.5V3M4.5 6.5 8 3l3.5 3.5M2.5 13h11' }],
  share: [{ d: 'M11.5 5.5a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5ZM4.5 9.75a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5ZM11.5 14a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5ZM6 8.9l4 2.2M10 4.9 6 7.1' }],
  search: [{ d: 'M7.25 12a4.75 4.75 0 1 0 0-9.5 4.75 4.75 0 0 0 0 9.5ZM10.75 10.75 13.5 13.5' }],
  trash: [{ d: 'M2.5 4.5h11M6 4.5V3h4v1.5M4 4.5l.6 8.2a1 1 0 0 0 1 .8h4.8a1 1 0 0 0 1-.8L12 4.5' }],
  'arrow-right': [{ d: 'M2.5 8h11M9.5 4l4 4-4 4' }],
  group: [{ d: 'M2.5 2.5h4v4h-4zM9.5 9.5h4v4h-4zM6.5 4.5h3v5h-3' }],
  'chevron-down': [{ d: 'M4 6l4 4 4-4' }],
  'chevron-right': [{ d: 'M6 4l4 4-4 4' }],
  close: [{ d: 'M4 4l8 8M12 4l-8 8' }],
  check: [{ d: 'M3.5 8.5 6.5 11.5 12.5 5' }],
  warning: [{ d: 'M8 2.5 14.5 13.5h-13ZM8 6.5v3M8 11.5v.5' }],
  history: [{ d: 'M2.75 8a5.25 5.25 0 1 0 1.6-3.77M2.5 3v2.5H5M8 5.5V8l2 1.5' }],
  send: [{ d: 'M14 2 2 7l4.5 1.8L8.5 13 14 2ZM6.5 8.8 14 2' }],
  pencil: [{ d: 'M11.5 2.5 13.5 4.5 5.5 12.5 2.5 13.5 3.5 10.5 11.5 2.5Z' }],
  // Solid fill/color droplet — canvas-xig's style affordance, distinct from pencil (label
  // editing). Filled (like `diamond`) rather than stroked: a thin 1.5px outline on a teardrop's
  // curves loses definition at the 12px size this renders at here, while a solid silhouette stays
  // legible at any size.
  palette: [{ d: 'M8 1.5c0 0 5.3 6.4 5.3 9.3a5.3 5.3 0 0 1-10.6 0c0-2.9 5.3-9.3 5.3-9.3Z', filled: true }],
  // Auto Layout — a small hierarchy/tree glyph (one box branching to two) suggesting "arrange
  // into ranks", distinct from `group`'s overlapping-boxes grouping metaphor.
  layout: [{ d: 'M6 2h4v3h-4zM2 11h4v3h-4zM10 11h4v3h-4zM8 5v3M8 8 4 11M8 8 12 11' }],
  // canvas-hbk: Diagram Details trigger — a circled "i", distinct from `warning`'s triangle. The
  // dot is a zero-length stroked segment, rendered as a circle by the shared strokeLinecap="round".
  info: [{ d: 'M8 14.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM8 7.25v4M8 5.25v.01' }],
  // ADP-SPEC-052 FR-004: literal outline renderings of the NodeShape they name (data-model.md), on
  // the same 16-unit grid every icon above uses. Coordinates mirror shapes.tsx's renderNodeShape
  // point math at icon scale, so a shape's toolbar glyph reads as a small version of the shape
  // itself, not an abstract symbol.
  'shape-rectangle': [{ d: 'M2.5 4.5h11v7h-11Z' }],
  'shape-rounded': [{ d: 'M4.5 4.5H11.5A2 2 0 0 1 13.5 6.5V9.5A2 2 0 0 1 11.5 11.5H4.5A2 2 0 0 1 2.5 9.5V6.5A2 2 0 0 1 4.5 4.5Z' }],
  'shape-circle': [{ d: 'M2.5 8a5.5 5.5 0 1 0 11 0 5.5 5.5 0 1 0 -11 0Z' }],
  'shape-stadium': [{ d: 'M6 4.5h4a3.5 3.5 0 0 1 0 7h-4a3.5 3.5 0 0 1 0-7Z' }],
  'shape-subroutine': [{ d: 'M2.5 4.5h11v7h-11ZM5 4.5v7M11 4.5v7' }],
  'shape-double-circle': [{ d: 'M2.5 8a5.5 5.5 0 1 0 11 0 5.5 5.5 0 1 0 -11 0ZM4.5 8a3.5 3.5 0 1 0 7 0 3.5 3.5 0 1 0 -7 0Z' }],
  // Wider notch than shapes.tsx's own proportions (2px -> 3px here) so the two side points stay
  // visually distinct from a circle/stadium once the shared strokeLinejoin="round" softens them.
  'shape-hexagon': [{ d: 'M5.5 4.5 10.5 4.5 13.5 8 10.5 11.5 5.5 11.5 2.5 8Z' }],
  'shape-parallelogram': [{ d: 'M5 4.5 13.5 4.5 11 11.5 2.5 11.5Z' }],
  'shape-trapezoid': [{ d: 'M5 4.5 11 4.5 13.5 11.5 2.5 11.5Z' }],
  'shape-asymmetric': [{ d: 'M2.5 4.5 11 4.5 13.5 8 11 11.5 2.5 11.5Z' }],
};

export interface IconProps {
  name: IconName;
  /** Square size in px. Defaults to 16. */
  size?: number;
  className?: string;
}

export function Icon({ name, size = 16, className }: IconProps) {
  const paths = PATHS[name];
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      style={{ display: 'inline-block', flexShrink: 0 }}
    >
      {paths.map((p, i) =>
        p.filled ? (
          <path key={i} d={p.d} fill="currentColor" stroke="none" />
        ) : (
          <path key={i} d={p.d} />
        ),
      )}
    </svg>
  );
}
