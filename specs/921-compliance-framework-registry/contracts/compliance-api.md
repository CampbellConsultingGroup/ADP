# API Contract: Compliance Framework & Control Registry (COMPLY-01)

**Router prefix**: `/api/v1/compliance`
**Tag**: `compliance`
**Auth**: All write operations (POST/PATCH/DELETE) require `ActionType.WRITE_COMPLIANCE` (Enterprise
Architect, Platform Admin, Solution Architect, Technical Architect — research.md D4). Reads (GET) are open
to any authenticated user, matching every other registry domain's convention.

---

## Regulatory Frameworks

### GET /api/v1/compliance/frameworks

Returns every registered framework (flat list, no controls).

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "NIST 800-53 Rev 5",
      "jurisdiction": "US-Federal",
      "authority": "NIST",
      "version": "Rev 5",
      "effective_date": "2020-09-23",
      "source_url": "https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final",
      "created_at": "2026-08-17T12:00:00Z",
      "updated_at": "2026-08-17T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### POST /api/v1/compliance/frameworks

Create a new framework.

**Request body**:
```json
{
  "name": "GDPR",
  "jurisdiction": "EU",
  "authority": "European Commission",
  "version": "2016/679",
  "effective_date": "2018-05-25",
  "source_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj"
}
```

**Validation**: `name`, `jurisdiction`, `authority`, `version` required, non-empty after trim.
`effective_date`/`source_url` optional (Edge Case: a perpetually-current framework has no `effective_date`).

**Response 201**: Full `RegulatoryFramework` object
**Response 422**: Validation failure

---

### GET /api/v1/compliance/frameworks/{framework_id}

Returns the framework with its full control hierarchy, nested by `parent_id`, ordered by `position`
(`RegulatoryFrameworkDetail`; User Story 3).

**Response 200**:
```json
{
  "id": "uuid",
  "name": "GDPR",
  "jurisdiction": "EU",
  "authority": "European Commission",
  "version": "2016/679",
  "effective_date": "2018-05-25",
  "source_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
  "created_at": "2026-08-17T12:00:00Z",
  "updated_at": "2026-08-17T12:00:00Z",
  "controls": [
    {
      "id": "c1", "framework_id": "uuid", "parent_id": null,
      "code": "Art. 5", "title": "Principles relating to processing",
      "description": "...", "position": 0,
      "created_at": "...", "updated_at": "...",
      "children": [
        {
          "id": "c2", "framework_id": "uuid", "parent_id": "c1",
          "code": "Art. 5(1)(a)", "title": "Lawfulness, fairness and transparency",
          "description": "...", "position": 0,
          "created_at": "...", "updated_at": "...", "children": []
        }
      ]
    },
    {
      "id": "c3", "framework_id": "uuid", "parent_id": null,
      "code": "Art. 33", "title": "Notification of a personal data breach",
      "description": "...", "position": 1,
      "created_at": "...", "updated_at": "...", "children": []
    }
  ]
}
```

**Response 404**: Framework not found

---

### PATCH /api/v1/compliance/frameworks/{framework_id}

Update one or more fields (all optional).

**Request body**:
```json
{ "authority": "European Commission (updated)", "source_url": "https://new-link.example" }
```

**Response 200**: Updated `RegulatoryFramework` object
**Response 404**: Framework not found
**Response 422**: Validation failure (a provided field is blank)

---

### DELETE /api/v1/compliance/frameworks/{framework_id}

Deletes the framework and every control beneath it, at every hierarchy level (research.md D2 — DB-level
`ON DELETE CASCADE`, not an app-layer block). The caller is expected to have already disclosed the scope to
the user client-side (D3) before issuing this request.

**Response 204**: Deleted
**Response 404**: Framework not found

---

## Controls

### POST /api/v1/compliance/frameworks/{framework_id}/controls

Add a control under a framework — top-level (`parent_id: null`) or nested under an existing control in the
*same* framework.

**Request body**:
```json
{
  "parent_id": "c1",
  "code": "Art. 5(1)(b)",
  "title": "Purpose limitation",
  "description": "Collected for specified, explicit and legitimate purposes.",
  "position": 1
}
```

**Validation**:
- `code`, `title`, `description` required, non-empty after trim
- `(framework_id, code)` must be unique (409 on collision, not 422 — this is a conflict with existing data,
  not a malformed request)
- `parent_id`, if set, must reference an existing control in this same framework (404 if missing, 422 if it
  belongs to a different framework)
- `parent_id` must not create a cycle (422 — not applicable on create since the new control has no
  descendants yet, but validated identically to keep create/update logic shared)

**Response 201**: Full `Control` object
**Response 404**: Framework (or referenced `parent_id`) not found
**Response 409**: `code` already in use for this framework
**Response 422**: Validation failure (blank field, cross-framework parent)

---

### PATCH /api/v1/compliance/controls/{control_id}

Update a control. All fields optional. Changing `code` re-checks framework-scoped uniqueness (D6);
changing `parent_id` re-checks the cycle/cross-framework rule (D5) — per FR-012, editing title/description/
position alone never touches code or hierarchy position.

**Request body**:
```json
{ "title": "Purpose limitation (revised wording)", "position": 2 }
```

**Response 200**: Updated `Control` object
**Response 404**: Control (or newly-referenced `parent_id`) not found
**Response 409**: New `code` already in use for this framework
**Response 422**: Validation failure (blank field, cycle, cross-framework parent)

---

### DELETE /api/v1/compliance/controls/{control_id}

Deletes the control and every descendant control beneath it, at every level (D2). As with framework
deletion, the caller discloses scope to the user client-side (D3) before issuing this request.

**Response 204**: Deleted
**Response 404**: Control not found
