# Quickstart: Document, View & Export Generation

**Branch**: `011-document-export` | **Date**: 2026-07-02
**Prerequisites**: ADP backend running; authenticated as Architect; design DESIGN-001 exists with elements and requirements

---

## Generate a Stakeholder Document

```bash
curl -s http://localhost:8000/api/v1/designs/DESIGN-001/document \
  -H "Authorization: Bearer $ADP_TOKEN" \
  | tee design-001.md | head -20
```

Output (first 20 lines):
```
---
design_id: DESIGN-001
schema_version: "1.0.0"
generated_at: "2026-07-02T12:34:56Z"
generator: ADP-SPEC-011
level: null
---

# My Architecture

**Design ID**: DESIGN-001
**Model Version**: 3
**Generated**: 2026-07-02T12:34:56Z

## Elements

### ELM-001 — API Gateway (container)

Routes all inbound traffic through a single ingress point.
```

---

## Generate All Three C4 Views

```python
import httpx, base64, json

client = httpx.Client(base_url="http://localhost:8000", headers={"Authorization": f"Bearer {token}"})

resp = client.get("/api/v1/designs/DESIGN-001/views")
views = resp.json()

for level in ("context", "container", "component"):
    svg = views[level]["svg"]
    png = base64.b64decode(views[level]["png_base64"])
    open(f"design-001-{level}.svg", "w").write(svg)
    open(f"design-001-{level}.png", "wb").write(png)
    print(f"Saved {level} view")
```

---

## Generate the Traceability Matrix

```bash
curl -s http://localhost:8000/api/v1/designs/DESIGN-001/traceability \
  -H "Authorization: Bearer $ADP_TOKEN" \
  | python3 -m json.tool | head -30
```

Example output excerpt:
```json
{
  "design_id": "DESIGN-001",
  "total_elements": 4,
  "orphan_count": 1,
  "entries": [
    {
      "element_id": "ELM-001",
      "element_name": "API Gateway",
      "element_kind": "container",
      "satisfied_requirements": ["REQ-001", "REQ-003"],
      "provenance": "OPT-001",
      "is_orphan": false
    },
    {
      "element_id": "ELM-004",
      "element_name": "Legacy Connector",
      "element_kind": "component",
      "satisfied_requirements": [],
      "provenance": null,
      "is_orphan": true
    }
  ]
}
```

The `orphan_count: 1` signals that `ELM-004` has no satisfied requirements — a governance gap to address.

---

## Export to Version Control

### Step 1: Get a confirmation ID (ART-VIII)

```bash
CONF=$(curl -s -X POST http://localhost:8000/api/v1/operations/confirm \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "export", "target": "DESIGN-001"}' | jq -r .confirmation_id)
echo "Confirmation: $CONF"
```

### Step 2: Export with confirmation

```bash
curl -s -X POST http://localhost:8000/api/v1/designs/DESIGN-001/export \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"confirmation_id\": \"$CONF\", \"export_root\": \"/srv/architecture-exports\"}"
```

Expected response:
```json
{
  "design_id": "DESIGN-001",
  "model_version": 3,
  "export_path": "/srv/architecture-exports/exports/DESIGN-001/v3",
  "artifacts": ["model.json", "model.yaml", "traceability.json", "README.md",
                "context/diagram.dsl", "context/diagram.svg", "context/diagram.png",
                "container/diagram.dsl", "container/diagram.svg", "container/diagram.png",
                "component/diagram.dsl", "component/diagram.svg", "component/diagram.png"],
  "audit_entry_id": "AUD-042"
}
```

### Step 3: Commit in version control

```bash
cd /srv/architecture-exports
git add exports/DESIGN-001/v3/
git commit -m "ADP export: DESIGN-001 v3 ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
git push
```

The resulting diff shows exactly what changed between versions — human-readable and reviewable.

---

## Round-Trip Import

```python
import json, pathlib, httpx

# Load a previously exported model
model_json = pathlib.Path("/srv/architecture-exports/exports/DESIGN-001/v3/model.json").read_text()

client = httpx.Client(base_url="http://localhost:8000", headers={"Authorization": f"Bearer {token}"})
resp = client.post("/api/v1/designs/import", json={"model_json": model_json})
result = resp.json()

print(f"Imported design: {result['design_id']}")
print(f"Elements: {result['element_count']}, Relationships: {result['relationship_count']}")
print(f"Warnings: {result['validation_warnings'] or 'none'}")
```

---

## Orphan Detection Scenario

```
1. Architect adds ELM-005 "Monitoring Sidecar" to the design
2. Forgets to link it to any requirement
3. Generates traceability: orphan_count goes from 0 to 1
4. ELM-005 appears in the orphan section of the matrix
5. Architect realizes the gap, adds satisfies=["REQ-007"] to ELM-005
6. Regenerates traceability: orphan_count returns to 0
7. Design is ready for export
```
