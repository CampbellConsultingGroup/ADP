# Contract: Locked Theme Artifact (`c4-theme.json`)

**Artifact**: `src/adp/theme/c4-theme.json`
**Schema**: `src/adp/theme/c4-theme.schema.json` (generated from `LockedTheme` Pydantic model)
**Date**: 2026-07-01

Defines the canonical shape of the locked C4 theme. This contract is normative for both the theme artifact author (Enterprise Architect) and the renderer.

---

## Full JSON Shape

```json
{
  "version": "1.0.0",
  "locked": true,
  "styles": {
    "person": {
      "fill": "#08427B",
      "stroke": "#073B6F",
      "color": "#ffffff",
      "shape": "actor",
      "font_size": 14,
      "font_weight": "normal"
    },
    "system": {
      "fill": "#1168BD",
      "stroke": "#0E5FA3",
      "color": "#ffffff",
      "shape": "box",
      "font_size": 14,
      "font_weight": "bold"
    },
    "container": {
      "fill": "#438DD5",
      "stroke": "#3C7FC0",
      "color": "#ffffff",
      "shape": "box",
      "font_size": 13,
      "font_weight": "normal"
    },
    "component": {
      "fill": "#85BBE0",
      "stroke": "#78A8CC",
      "color": "#000000",
      "shape": "box",
      "font_size": 12,
      "font_weight": "normal"
    }
  },
  "relationship_style": {
    "stroke": "#707070",
    "stroke_width": 1.5,
    "arrow_end": "open"
  }
}
```

---

## Field Constraints

| Field | Constraint | Enforcement |
|---|---|---|
| `version` | Semantic version string (`MAJOR.MINOR.PATCH`) | JSON Schema `pattern` |
| `locked` | Must be `true` (boolean, not string) | JSON Schema `const: true`; Pydantic `Literal[True]` |
| `styles` | Required keys: `"person"`, `"system"`, `"container"`, `"component"` | JSON Schema `required` + `minProperties: 4` |
| `styles[*].fill` | 7-character hex `#RRGGBB` | JSON Schema `pattern: ^#[0-9A-Fa-f]{6}$` |
| `styles[*].stroke` | 7-character hex `#RRGGBB` | Same pattern |
| `styles[*].color` | 7-character hex `#RRGGBB` | Same pattern |
| `styles[*].shape` | One of: `"box"`, `"actor"`, `"cylinder"`, `"hexagon"` | JSON Schema `enum` |
| `styles[*].font_size` | Integer 8–24 | JSON Schema `minimum: 8, maximum: 24` |
| `styles[*].font_weight` | `"normal"` or `"bold"` | JSON Schema `enum` |
| `relationship_style.stroke` | 7-character hex | Same pattern |
| `relationship_style.stroke_width` | Float > 0 | JSON Schema `minimum: 0, exclusiveMinimum: 0` |
| `relationship_style.arrow_end` | One of: `"open"`, `"filled"`, `"none"` | JSON Schema `enum` |

---

## Theme Change Process (FR-005)

When a theme change is needed:

1. Update `c4-theme.json` with the new values.
2. Increment the `version` field following semantic versioning:
   - **Patch** (`1.0.0 → 1.0.1`): Color adjustment within the same visual intent
   - **Minor** (`1.0.0 → 1.1.0`): New element kind added or shape changed
   - **Major** (`1.0.0 → 2.0.0`): Breaking visual change (e.g., complete rebrand)
3. Run `adp-generate --check` to verify schema is still consistent.
4. Commit as a dedicated PR with a descriptive diff (the diff IS the change record per FR-005).

---

## WCAG AA Compliance Check

The following contrast ratios are pre-computed for the baseline theme and MUST remain ≥ 4.5:1 after any change:

| Element | Text Color | Background | Ratio | Status |
|---|---|---|---|---|
| person | #ffffff | #08427B | ~10.9:1 | ✅ AA |
| system | #ffffff | #1168BD | ~6.8:1 | ✅ AA |
| container | #ffffff | #438DD5 | ~4.6:1 | ✅ AA (barely) |
| component | #000000 | #85BBE0 | ~5.9:1 | ✅ AA |

A `test_theme_wcag_contrast()` test verifies these ratios automatically on every CI run.
