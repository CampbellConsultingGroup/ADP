# API Contract: Business Domains and Stage-Capability Links (ADP-SPEC-035)

Router prefix: `/api/v1/business`
Auth: All endpoints require `AuthMiddleware` (inherited from existing business router).
Logging: All mutations emit `logger.info()` with `actor`, entity type, id, and action.

---

## Domain Endpoints

### GET /api/v1/business/domains

List all domains ordered by name.

**Response 200**

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Customer",
      "classification": "strategic",
      "org_unit": "Customer Experience",
      "risk_flags": ["PII", "GDPR"],
      "capability_count": 3,
      "created_at": "2026-07-10T00:00:00Z",
      "updated_at": "2026-07-10T00:00:00Z"
    }
  ],
  "total": 1
}
```

Note: `scope_statement` is intentionally omitted from list items (in `DomainSummary`). Retrieve via detail endpoint.

---

### POST /api/v1/business/domains

Create a new domain.

**Request**

```json
{
  "name": "Customer",
  "scope_statement": "In: customer identity, preferences, contact. Out: billing.",
  "classification": "strategic",
  "org_unit": "Customer Experience",
  "risk_flags": ["PII", "GDPR"]
}
```

**Response 201** — `BusinessDomain` (full domain without capability list)

```json
{
  "id": "uuid",
  "name": "Customer",
  "scope_statement": "In: customer identity, preferences, contact. Out: billing.",
  "classification": "strategic",
  "org_unit": "Customer Experience",
  "risk_flags": ["PII", "GDPR"],
  "created_at": "2026-07-10T00:00:00Z",
  "updated_at": "2026-07-10T00:00:00Z"
}
```

**Response 422** — invalid classification or blank name or blank risk_flag entry

---

### GET /api/v1/business/domains/{domain_id}

Get a single domain with its L1 capabilities.

**Response 200** — `DomainDetail`

```json
{
  "id": "uuid",
  "name": "Customer",
  "scope_statement": "In: customer identity, preferences, contact. Out: billing.",
  "classification": "strategic",
  "org_unit": "Customer Experience",
  "risk_flags": ["PII", "GDPR"],
  "created_at": "2026-07-10T00:00:00Z",
  "updated_at": "2026-07-10T00:00:00Z",
  "capabilities": [
    { "capability_id": "cap-uuid", "name": "Customer Engagement", "level": 1 }
  ]
}
```

**Response 404** — domain not found

---

### PUT /api/v1/business/domains/{domain_id}

Update a domain. All fields optional; only provided fields are changed.

**Request** (all fields optional)

```json
{
  "scope_statement": "Updated scope.",
  "risk_flags": ["PII", "GDPR", "CIFIUS"]
}
```

**Response 200** — updated `BusinessDomain` (without capability list)

**Response 404** — domain not found
**Response 422** — blank name or blank risk_flag entry

---

### DELETE /api/v1/business/domains/{domain_id}

Delete a domain. L1 capabilities that were assigned to it have their `domain_id` set to null automatically (DB-level `ON DELETE SET NULL`).

**Response 204** — deleted

**Response 404** — domain not found

---

## Capability Domain Assignment

### PATCH /api/v1/business/capabilities/{cap_id}/domain

Assign a capability to a domain, or clear its domain assignment.

**Request**

```json
{ "domain_id": "domain-uuid" }   // assign
```

```json
{ "domain_id": null }             // clear assignment
```

**Response 200** — updated `BusinessCapability`

```json
{
  "id": "cap-uuid",
  "name": "Customer Engagement",
  "level": 1,
  "domain_id": "domain-uuid",
  "domain_name": "Customer",
  ...
}
```

**Response 404** — capability not found, or domain not found (when assigning to a non-existent domain)
**Response 422** — capability level is 2 or 3 (only L1 can be assigned)

---

## Stage-Capability Link Endpoints

### GET /api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities

List all capabilities linked to a value stream stage.

**Response 200**

```json
{
  "items": [
    {
      "capability_id": "cap-uuid",
      "name": "Fulfillment",
      "level": 1,
      "domain_id": "domain-uuid",
      "domain_name": "Supply Chain"
    }
  ]
}
```

**Response 404** — value stream or stage not found

---

### POST /api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities

Link a capability to a stage.

**Request**

```json
{ "capability_id": "cap-uuid" }
```

**Response 201** — `StageCapabilitiesResponse` (full list after link is created)

```json
{
  "items": [
    {
      "capability_id": "cap-uuid",
      "name": "Fulfillment",
      "level": 1,
      "domain_id": "domain-uuid",
      "domain_name": "Supply Chain"
    }
  ]
}
```

**Response 404** — value stream, stage, or capability not found
**Response 409** — capability already linked to this stage

---

### DELETE /api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities/{capability_id}

Remove a capability link from a stage.

**Response 204** — link deleted

**Response 404** — link does not exist (or stage/capability not found)
