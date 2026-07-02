"""Structurizr DSL generator — converts ArchitectureDescription + theme → DSL string."""

from __future__ import annotations

from adp.models import ArchitectureDescription
from adp.theme.models import C4Level, LockedTheme

_LEVEL_KINDS: dict[C4Level, list[str]] = {
    "context":   ["person", "system"],
    "container": ["system", "container"],
    "component": ["container", "component"],
}

_DSL_ELEMENT_TYPE: dict[str, str] = {
    "person":    "person",
    "system":    "softwareSystem",
    "container": "container",
    "component": "component",
}

_DSL_VIEW_TYPE: dict[C4Level, str] = {
    "context":   "systemContext",
    "container": "container",
    "component": "component",
}


def _safe_id(element_id: str) -> str:
    """Convert an element id like ELM-001 to a valid DSL identifier."""
    return element_id.replace("-", "_")


def design_to_dsl(
    design: ArchitectureDescription,
    theme: LockedTheme,
    level: C4Level,
) -> str:
    """Generate a Structurizr DSL string for a design at a given C4 level.

    Theme colors are written dynamically from the LockedTheme so that a theme
    version bump is immediately reflected in DSL output (stays in sync with SVG).
    """
    allowed_kinds = _LEVEL_KINDS[level]
    visible = [e for e in design.elements if e.kind in allowed_kinds]

    lines: list[str] = []
    lines.append(f'workspace "{design.title}" {{')
    lines.append("    model {")
    for el in sorted(visible, key=lambda e: e.id):
        dsl_type = _DSL_ELEMENT_TYPE.get(el.kind, "softwareSystem")
        desc = el.description or ""
        lines.append(f'        {_safe_id(el.id)} = {dsl_type} "{el.name}" "{desc}"')
    lines.append("    }")

    # Views section
    view_type = _DSL_VIEW_TYPE[level]
    lines.append("    views {")
    if visible:
        first_id = _safe_id(sorted(visible, key=lambda e: e.id)[0].id)
        lines.append(f"        {view_type} {first_id} \"{design.title} — {level}\" {{")
    else:
        lines.append(f"        {view_type} \"{design.title} — {level}\" {{")
    lines.append("            include *")
    lines.append("            autolayout lr")
    lines.append("        }")

    # Styles block — written dynamically from theme (ART-XII; not hardcoded)
    lines.append("        styles {")
    for kind in allowed_kinds:
        if kind in theme.styles:
            style = theme.styles[kind]
            dsl_el_label = kind.capitalize()
            lines.append(f'            element "{dsl_el_label}" {{')
            lines.append(f"                background {style.fill}")
            lines.append(f"                color {style.color}")
            lines.append(f"                stroke {style.stroke}")
            if style.shape == "actor":
                lines.append("                shape Person")
            elif style.shape == "cylinder":
                lines.append("                shape Cylinder")
            lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines) + "\n"
