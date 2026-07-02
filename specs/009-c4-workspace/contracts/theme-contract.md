# Contract: C4 Theme JSON (consumed from ADP-SPEC-010)

**Endpoint**: `GET /api/v1/theme/c4` (served by ADP-SPEC-010 or ADP-SPEC-003)  
**Consumer**: `web/src/api/theme.ts`  
**Date**: 2026-07-01

The locked C4 theme defines the visual appearance of every element type. The workspace MUST apply these styles and MUST NOT expose any controls that override them.

---

## Theme JSON Shape (v1 baseline)

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

## Theme Application Rule

The workspace applies theme styles ONLY based on `element.kind`. There is NO mechanism to override styles. The `C4ElementNode` component receives the `element` and the `theme`, computes the style, and renders — no style props are accepted from outside.

```typescript
// Correct — style from theme only
function C4ElementNode({ data }: { data: C4NodeData }) {
  const style = data.style; // pre-computed from theme by kind
  return <div style={{ background: style.fill, color: style.color, ... }} />;
}

// FORBIDDEN — would expose style overrides
function C4ElementNode({ data, customColor }: ...) { ... }
```
