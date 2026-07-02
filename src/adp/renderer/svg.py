"""SVG generator — converts ArchitectureDescription + LockedTheme → SVG string.

Generates SVG XML directly in Python (no external tools required).
Layout: deterministic grid auto-layout, stable-sorted by element id.
ART-XII: styling derives ONLY from LockedTheme; no style override parameters.
"""

from __future__ import annotations

from adp.models import ArchitectureDescription
from adp.theme.models import C4Level, LockedTheme

_LEVEL_KINDS: dict[C4Level, list[str]] = {
    "context":   ["person", "system"],
    "container": ["system", "container"],
    "component": ["container", "component"],
}

_CELL_W = 200
_CELL_H = 120
_MARGIN = 20
_COLS = 4
_FONT_FAMILY = "Arial, sans-serif"


def _grid_pos(index: int) -> tuple[float, float]:
    col = index % _COLS
    row = index // _COLS
    x = _MARGIN + col * (_CELL_W + _MARGIN)
    y = _MARGIN + row * (_CELL_H + _MARGIN)
    return float(x), float(y)


def design_to_svg(
    design: ArchitectureDescription,
    theme: LockedTheme,
    level: C4Level,
    positions: dict[str, dict[str, float]] | None = None,
) -> str:
    """Return a complete SVG XML document for the design at the given C4 level.

    Styling is applied exclusively from `theme` by element kind (ART-XII / FR-002).
    The `positions` parameter accepts optional position hints from the layout API;
    when absent, deterministic grid auto-layout is used.
    """
    allowed_kinds = _LEVEL_KINDS[level]
    visible = sorted(
        [e for e in design.elements if e.kind in allowed_kinds],
        key=lambda e: e.id,
    )
    visible_ids = {e.id for e in visible}
    visible_rels = [
        r for r in design.relationships
        if r.source in visible_ids and r.target in visible_ids
    ]

    # Compute element centre points
    centres: dict[str, tuple[float, float]] = {}
    for i, el in enumerate(visible):
        if positions and el.id in positions:
            px = float(positions[el.id].get("x", 0))
            py = float(positions[el.id].get("y", 0))
            x, y = px, py
        else:
            x, y = _grid_pos(i)
        centres[el.id] = (x + _CELL_W / 2, y + _CELL_H / 2)

    num_rows = max(1, (len(visible) + _COLS - 1) // _COLS)
    canvas_w = _COLS * (_CELL_W + _MARGIN) + _MARGIN
    canvas_h = num_rows * (_CELL_H + _MARGIN) + _MARGIN + 60  # extra for arrows

    rel_stroke = theme.relationship_style.stroke
    rel_width = theme.relationship_style.stroke_width

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{canvas_w}" height="{canvas_h}">'
    )

    # Arrowhead marker definition
    parts.append(
        f'  <defs>'
        f'    <marker id="arrow" markerWidth="10" markerHeight="7" '
        f'refX="10" refY="3.5" orient="auto">'
        f'      <polygon points="0 0, 10 3.5, 0 7" fill="{rel_stroke}" />'
        f'    </marker>'
        f'  </defs>'
    )

    # Relationship lines (drawn before elements so they appear behind)
    for rel in visible_rels:
        sx, sy = centres.get(rel.source, (0.0, 0.0))
        tx, ty = centres.get(rel.target, (0.0, 0.0))
        parts.append(
            f'  <line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" '
            f'stroke="{rel_stroke}" stroke-width="{rel_width}" '
            f'marker-end="url(#arrow)" />'
        )
        if rel.label:
            mx, my = (sx + tx) / 2, (sy + ty) / 2
            parts.append(
                f'  <text x="{mx:.1f}" y="{my:.1f}" '
                f'font-family="{_FONT_FAMILY}" font-size="11" '
                f'fill="#333" text-anchor="middle">{rel.label}</text>'
            )

    # Element boxes
    for i, el in enumerate(visible):
        style = theme.styles.get(el.kind)
        fill = style.fill if style else "#888888"
        stroke = style.stroke if style else "#666666"
        text_color = style.color if style else "#ffffff"
        font_size = style.font_size if style else 13
        font_weight = style.font_weight if style else "normal"

        if positions and el.id in positions:
            rx = float(positions[el.id].get("x", 0))
            ry = float(positions[el.id].get("y", 0))
        else:
            rx, ry = _grid_pos(i)

        parts.append(
            f'  <rect x="{rx:.1f}" y="{ry:.1f}" width="{_CELL_W}" height="{_CELL_H}" '
            f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5" />'
        )
        # Element name label
        cx = rx + _CELL_W / 2
        cy = ry + _CELL_H / 2 - 8
        parts.append(
            f'  <text x="{cx:.1f}" y="{cy:.1f}" '
            f'font-family="{_FONT_FAMILY}" font-size="{font_size}" '
            f'font-weight="{font_weight}" fill="{text_color}" text-anchor="middle">'
            f'{el.name}</text>'
        )
        # Kind label (smaller, below name)
        ky = cy + font_size + 4
        parts.append(
            f'  <text x="{cx:.1f}" y="{ky:.1f}" '
            f'font-family="{_FONT_FAMILY}" font-size="11" '
            f'fill="{text_color}" text-anchor="middle" opacity="0.85">'
            f'[{el.kind}]</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)
