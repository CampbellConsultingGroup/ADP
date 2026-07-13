# API Contract: Business Architecture

**Router prefix**: `/api/v1/business`
**Tag**: `business`
**Auth**: All write operations require authenticated actor (same `AuthMiddleware` as existing routers). Reads are open when `ADP_AUTH_ENABLED=false`.

---

## Business Capabilities

### GET /api/v1/business/capabilities

Returns the full capability hierarchy as a flat list. Client assembles the tree using `parent_id`.

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Customer Engagement",
      "description": "...",
      "level": 1,
      "parent_id": null,
      "position": 0,
      "created_at": "2026-07-10T12:00:00Z",
      "updated_at": "2026-07-10T12:00:00Z"
    },
    {
      "id": "uuid2",
      "name": "Sales",
      "description": null,
      "level": 2,
      "parent_id": "uuid",
      "position": 0,
      "created_at": "2026-07-10T12:01:00Z",
      "updated_at": "2026-07-10T12:01:00Z"
    }
  ],
  "total": 2
}
```

---

### POST /api/v1/business/capabilities

Create a new capability.

**Request body**:
```json
{
  "name": "Customer Engagement",
  "description": "Strategic capability for engaging customers",
  "level": 1,
  "parent_id": null,
  "position": 0
}
```

**Validation**:
- `name`: required, non-empty after trim
- `level`: 1, 2, or 3
- `parent_id`: required if `level > 1`; must reference a capability with `level == level - 1`
- `parent_id`: must be null if `level == 1`

**Response 201**: Full `BusinessCapability` object

**Errors**:
- `422` — validation failure (name empty, bad level, parent_id/level mismatch)
- `404` — `parent_id` does not reference an existing capability

---

### GET /api/v1/business/capabilities/{id}

**Response 200**: Full `BusinessCapability` object
**Response 404**: Capability not found

---

### PUT /api/v1/business/capabilities/{id}

Update name, description, or position of a capability. Level and parent cannot be changed (reparenting out of scope).

**Request body** (all fields optional):
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "position": 2
}
```

**Response 200**: Updated `BusinessCapability` object
**Response 404**: Capability not found
**Response 422**: Validation failure (name empty)

---

### DELETE /api/v1/business/capabilities/{id}

**Response 204**: Deleted successfully
**Response 404**: Capability not found
**Response 409**: Capability has child capabilities — deletion blocked

```json
{
  "detail": "Cannot delete capability 'Customer Engagement': it has 3 child capabilities. Delete or reassign them first."
}
```

---

## Value Streams

### GET /api/v1/business/value-streams

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Order to Cash",
      "description": "...",
      "stakeholder": "Customer",
      "position": 0,
      "created_at": "2026-07-10T12:00:00Z",
      "updated_at": "2026-07-10T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### POST /api/v1/business/value-streams

**Request body**:
```json
{
  "name": "Order to Cash",
  "description": "End-to-end process from customer order to cash receipt",
  "stakeholder": "Customer"
}
```

**Response 201**: Full `ValueStream` object (no stages on creation)
**Response 422**: Validation failure

---

### GET /api/v1/business/value-streams/{id}

Returns the value stream with its stages in `position` order.

**Response 200** (`ValueStreamDetail`):
```json
{
  "id": "uuid",
  "name": "Order to Cash",
  "description": "...",
  "stakeholder": "Customer",
  "position": 0,
  "created_at": "2026-07-10T12:00:00Z",
  "updated_at": "2026-07-10T12:00:00Z",
  "stages": [
    { "id": "s1", "value_stream_id": "uuid", "name": "Order Capture", "description": null, "position": 0 },
    { "id": "s2", "value_stream_id": "uuid", "name": "Fulfilment", "description": null, "position": 1 }
  ]
}
```

**Response 404**: Value stream not found

---

### PUT /api/v1/business/value-streams/{id}

Update metadata only (name, description, stakeholder).

**Response 200**: Updated `ValueStream` (without stages)
**Response 404**: Not found
**Response 422**: Validation failure

---

### DELETE /api/v1/business/value-streams/{id}

Cascades to all stages.

**Response 204**: Deleted
**Response 404**: Not found

---

## Value Stream Stages

### POST /api/v1/business/value-streams/{id}/stages

Add a stage to a value stream.

**Request body**:
```json
{ "name": "Invoicing", "description": null, "position": 2 }
```

**Response 201**: Full `ValueStreamStage` object
**Response 404**: Value stream not found
**Response 422**: Validation failure

---

### PUT /api/v1/business/value-streams/{id}/stages/{stage_id}

Edit a single stage.

**Request body** (all optional):
```json
{ "name": "Invoice and Collect", "description": "Updated", "position": 3 }
```

**Response 200**: Updated `ValueStreamStage`
**Response 404**: Value stream or stage not found

---

### DELETE /api/v1/business/value-streams/{id}/stages/{stage_id}

**Response 204**: Deleted
**Response 404**: Value stream or stage not found

---

### PUT /api/v1/business/value-streams/{id}/stages

Bulk-replace the stages list (reorder). Accepts an ordered array of stage objects; positions are reassigned 0..n-1 based on array order. Existing stage IDs are preserved; stages not in the list are deleted.

**Request body**:
```json
{
  "stages": [
    { "id": "s2", "name": "Fulfilment", "description": null },
    { "id": "s1", "name": "Order Capture", "description": null },
    { "id": "s3", "name": "Invoicing", "description": null }
  ]
}
```

**Response 200**: `ValueStreamDetail` with reordered stages
**Response 404**: Value stream not found
**Response 422**: Stage ID in list not found for this value stream
