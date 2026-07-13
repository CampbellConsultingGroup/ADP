# Quickstart: Locked Visual Theme & Diagram Rendering

**Branch**: `010-locked-theme-rendering` | **Date**: 2026-07-01
**Prerequisites**: ADP backend running; authenticated as Architect; design DESIGN-001 exists

---

## Rendering a Design

```bash
curl -X POST http://localhost:8000/api/v1/designs/DESIGN-001/render \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"level": "container"}'
```

Response:
```json
{
  "design_id": "DESIGN-001",
  "level": "container",
  "dsl": "workspace \"My Architecture\" {\n  model {\n    person ...",
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"800\" height=\"400\">...",
  "png_base64": "iVBORw0KGgoAAAANS..."
}
```

### Saving the SVG

```python
import json, base64, httpx

resp = httpx.post(
    "http://localhost:8000/api/v1/designs/DESIGN-001/render",
    json={"level": "container"},
    headers={"Authorization": f"Bearer {token}"},
)
result = resp.json()

# Save DSL
with open("design-001-container.dsl", "w") as f:
    f.write(result["dsl"])

# Save SVG
with open("design-001-container.svg", "w") as f:
    f.write(result["svg"])

# Save PNG
with open("design-001-container.png", "wb") as f:
    f.write(base64.b64decode(result["png_base64"]))
```

---

## Style Override Attempt (Rejected)

```bash
# This request will be rejected with 422 — extra fields not permitted
curl -X POST http://localhost:8000/api/v1/designs/DESIGN-001/render \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"level": "container", "fill": "#FF0000"}'
# → 422 Unprocessable Entity: extra fields not permitted
```

---

## Theme Validation

```python
# Validate the current theme
from adp.theme.loader import ThemeLoader

loader = ThemeLoader()
theme = loader.load()         # Loads c4-theme.json
loader.validate(theme)        # Validates against c4-theme.schema.json; raises on failure
print(f"Theme version: {theme.version}")  # → "1.0.0"
print(f"Theme locked: {theme.locked}")    # → True
```

---

## Rendering All Three C4 Levels

```bash
for level in context container component; do
  curl -s -X POST http://localhost:8000/api/v1/designs/DESIGN-001/render \
    -H "Authorization: Bearer $ADP_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"level\": \"$level\"}" \
    | python3 -c "
import sys, json, base64
r = json.load(sys.stdin)
open(f'design-001-{r[\"level\"]}.svg', 'w').write(r['svg'])
open(f'design-001-{r[\"level\"]}.dsl', 'w').write(r['dsl'])
open(f'design-001-{r[\"level\"]}.png', 'wb').write(base64.b64decode(r['png_base64']))
print(f'Rendered {r[\"level\"]} level')
"
done
# → Rendered context level
# → Rendered container level
# → Rendered component level
```

---

## Theme Consistency Scenario

```
1. Architect A renders DESIGN-001 → Container element "API Gateway" is blue (#438DD5)
2. Architect B creates DESIGN-002 with a different Container element "Auth Service"
3. Architect B renders DESIGN-002 → "Auth Service" is also blue (#438DD5)
4. Both architects confirm: any Container element on any design looks identical
5. No manual color selection was made — the locked theme enforced it
```

---

## Programmatic Theme Inspection

```python
from adp.theme.loader import ThemeLoader
from adp.theme.contrast import compute_contrast_ratio

loader = ThemeLoader()
theme = loader.load()

for kind, style in theme.styles.items():
    ratio = compute_contrast_ratio(style.color, style.fill)
    print(f"{kind}: {ratio:.1f}:1 contrast — {'✅ AA' if ratio >= 4.5 else '❌ FAIL'}")

# → person:    10.9:1 contrast — ✅ AA
# → system:     6.8:1 contrast — ✅ AA
# → container:  4.6:1 contrast — ✅ AA
# → component:  5.9:1 contrast — ✅ AA
```
