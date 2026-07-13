# API Contract: Business Architecture Traceability Endpoints (ADP-SPEC-034)

**Feature**: 034-business-arch-traceability
**Generated**: 2026-07-10
**Base path**: `/api/v1/business/`

All write endpoints require a Bearer JWT (same auth gate as existing business endpoints).
All responses are `application/json`. All request bodies use `Content-Type: application/json`.

---

## Capability–Design Links (3 endpoints)

### `GET /api/v1/business/capabilities/{capability_id}/designs`

List all designs linked to a capability.

**Path params**: `capability_id` (UUID string)

**Response 200**:
```json
{
  "items": [
    {
      "design_id": "DES-001",
      "title": "Order Management System",
      "lifecycle_status": "current"
    }
  ]
}
```

**Response 404**: Capability not found.

---

### `POST /api/v1/business/capabilities/{capability_id}/designs`

Link a design to a capability.

**Path params**: `capability_id` (UUID string)

**Request body**:
```json
{ "design_id": "DES-001" }
```

**Response 201**: Created — returns the updated linked-designs list.
```json
{
  "items": [
    {
      "design_id": "DES-001",
      "title": "Order Management System",
      "lifecycle_status": "current"
    }
  ]
}
```

**Response 404**: Capability or design not found.
**Response 409**: Link already exists.
**Response 422**: `design_id` blank or invalid.

---

### `DELETE /api/v1/business/capabilities/{capability_id}/designs/{design_id}`

Remove a capability–design link.

**Path params**: `capability_id`, `design_id`

**Response 204**: No content.
**Response 404**: Capability not found, design not found, or link does not exist.

---

## Value Stream–Design Links (3 endpoints)

### `GET /api/v1/business/value-streams/{value_stream_id}/designs`

List all designs linked to a value stream.

**Path params**: `value_stream_id` (UUID string)

**Response 200**:
```json
{
  "items": [
    {
      "design_id": "DES-002",
      "title": "Inventory Platform",
      "lifecycle_status": "draft"
    }
  ]
}
```

**Response 404**: Value stream not found.

---

### `POST /api/v1/business/value-streams/{value_stream_id}/designs`

Link a design to a value stream.

**Path params**: `value_stream_id` (UUID string)

**Request body**:
```json
{ "design_id": "DES-002" }
```

**Response 201**: Returns updated linked-designs list (same schema as GET).
**Response 404**: Value stream or design not found.
**Response 409**: Link already exists.
**Response 422**: `design_id` blank.

---

### `DELETE /api/v1/business/value-streams/{value_stream_id}/designs/{design_id}`

Remove a value-stream–design link.

**Path params**: `value_stream_id`, `design_id`

**Response 204**: No content.
**Response 404**: Value stream, design, or link not found.

---

## Design Business Context — Reverse Lookup (1 endpoint)

### `GET /api/v1/business/designs/{design_id}/context`

Return all capabilities and value streams linked to a given design.

**Path params**: `design_id` (text ID, e.g. `"DES-001"`)

**Response 200** (returns empty lists if design exists but has no links):
```json
{
  "design_id": "DES-001",
  "capabilities": [
    {
      "capability_id": "abc-123-...",
      "name": "Order Processing",
      "level": 2
    }
  ],
  "value_streams": [
    {
      "value_stream_id": "def-456-...",
      "name": "Order to Cash",
      "stakeholder": "Finance"
    }
  ]
}
```

**Response 404**: Design not found in `designs` table.

---

## Total New Endpoints: 7

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/business/capabilities/{id}/designs` | List designs linked to capability |
| POST | `/business/capabilities/{id}/designs` | Link design to capability |
| DELETE | `/business/capabilities/{id}/designs/{design_id}` | Remove capability–design link |
| GET | `/business/value-streams/{id}/designs` | List designs linked to value stream |
| POST | `/business/value-streams/{id}/designs` | Link design to value stream |
| DELETE | `/business/value-streams/{id}/designs/{design_id}` | Remove value-stream–design link |
| GET | `/business/designs/{design_id}/context` | Get capabilities + value streams for a design |
