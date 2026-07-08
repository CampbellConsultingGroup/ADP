# API Contracts: Element Technology Tagging (ADP-SPEC-029)

## New Endpoint: Set Element Technology Metadata

```
PUT /api/v1/designs/{design_id}/elements/{element_id}/tags
```

**Auth**: Bearer token required (ADP-SPEC-026); write access to design required.

**Request body** (all fields optional; omitted fields are cleared):
```json
{
  "technology": "Apache Kafka",
  "vendor": "Confluent",
  "platform": "AWS EKS",
  "version": "3.4.1",
  "owner_team": "Platform Engineering",
  "tags": ["legacy", "needs-migration"]
}
```

**Validation**:
- `technology`, `vendor`, `platform`, `owner_team`: max 200 characters
- `version`: max 50 characters
- `tags` items: max 50 characters each, must not be blank
- Sending an empty object `{}` clears all metadata for the element

**Response 200 OK**:
```json
{
  "element_id": "ELM-003",
  "design_id": "DSN-001",
  "technology": "Apache Kafka",
  "vendor": "Confluent",
  "platform": "AWS EKS",
  "version": "3.4.1",
  "owner_team": "Platform Engineering",
  "tags": ["legacy", "needs-migration"],
  "updated_at": "2026-07-05T10:00:00Z"
}
```

**Response 404**: Design or element not found.
**Response 422**: Validation error (field too long, blank tag, etc.).
**Response 403**: Insufficient role to write to this design.

**Side effects**:
1. Updates `TechnologyMetadata` on the element within the design's canonical model; increments the design version (saves a new `design_versions` row).
2. Upserts the `element_technology_tags` row for `(design_id, element_id)`.
3. Writes an ART-IX audit entry to the design's audit log recording the actor, element_id, and a field-level diff of what changed.

---

## Existing Endpoint Extended: Get Design (includes technology metadata)

```
GET /api/v1/designs/{design_id}
```

**No change to URL or auth.** Response now includes `technology_metadata` on each element when set:

```json
{
  "id": "DSN-001",
  "elements": [
    {
      "id": "ELM-003",
      "name": "Payment API Gateway",
      "kind": "container",
      "description": "Entry point for payment flows",
      "satisfies": ["REQ-001"],
      "tags": ["legacy"],
      "technology_metadata": {
        "technology": "Kong",
        "vendor": "Kong Inc.",
        "platform": "AWS EKS",
        "version": "3.4",
        "owner_team": "Platform Engineering"
      }
    }
  ]
}
```

Elements with no technology metadata have `"technology_metadata": null`.

---

## Internal: Portfolio Query (consumed by ADP-SPEC-031)

```
GET /api/v1/portfolio/elements?technology=Kafka&platform=AWS+EKS&owner_team=Platform+Engineering&tag=legacy
```

This endpoint is specified and implemented in ADP-SPEC-031. The `element_technology_tags` table created in this spec is the data source it queries. Documented here for awareness — not implemented in ADP-SPEC-029.
