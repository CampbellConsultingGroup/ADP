# API Contract: Application Registry (ADP-SPEC-036)

Router prefixes:
- Applications + sub-resources: `/api/v1/applications`
- Technical capabilities: `/api/v1/technical-capabilities`
- Application integrations: `/api/v1/integrations`

Auth: All endpoints require `AuthMiddleware` (standard ADP-SPEC-003 middleware).
Logging: All mutations emit `logger.info()` with `actor`, entity type, id, and action (ART-IX via ART-VI).

---

## Application Endpoints

### GET /api/v1/applications

List all applications ordered by name.

**Response 200** — `ApplicationListResponse`

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Customer Portal",
      "description": "Customer-facing self-service web app",
      "vendor": "Acme Corp",
      "primary_owner": "Platform Team",
      "time_classification": "Invest",
      "r_strategy": "Refactor",
      "pace_layer": "Differentiation",
      "health_score": 4,
      "created_at": "2026-07-11T00:00:00Z",
      "updated_at": "2026-07-11T00:00:00Z"
    }
  ],
  "total": 1
}
```

---

### POST /api/v1/applications

Create a new application.

**Request**

```json
{
  "name": "Customer Portal",
  "description": "Customer-facing self-service web app",
  "vendor": "Acme Corp",
  "primary_owner": "Platform Team",
  "time_classification": "Invest",
  "r_strategy": "Refactor",
  "pace_layer": "Differentiation",
  "health_score": 4
}
```

All fields except `name` are optional.

**Response 201** — `Application`

**Response 422** — blank `name`, invalid `time_classification`, invalid `r_strategy`, invalid `pace_layer`, or `health_score` outside 1–5

---

### GET /api/v1/applications/{app_id}

**Response 200** — `Application`

**Response 404** — application not found

---

### PATCH /api/v1/applications/{app_id}

Partial update. Only fields present in the request body are changed.

**Request** (all fields optional)

```json
{ "vendor": "New Vendor", "health_score": 3 }
```

**Response 200** — updated `Application`

**Response 404** — not found
**Response 422** — validation error (blank name, invalid enum value, score out of range)

---

### DELETE /api/v1/applications/{app_id}

Deletes the application and all associated links (cascade).

**Response 204** — deleted

**Response 404** — not found

---

## Application–Business Capability Link Endpoints

### GET /api/v1/applications/{app_id}/capability-links

**Response 200** — `ApplicationCapabilityLinksResponse`

```json
{
  "items": [
    {
      "app_id": "app-uuid",
      "capability_id": "cap-uuid",
      "capability_name": "Customer Engagement",
      "fit_score": 3
    }
  ]
}
```

**Response 404** — application not found

---

### POST /api/v1/applications/{app_id}/capability-links

**Request**

```json
{ "capability_id": "cap-uuid", "fit_score": 3 }
```

**Response 201** — `ApplicationCapabilityLink`

**Response 404** — application or capability not found
**Response 409** — link already exists
**Response 422** — `fit_score` outside 1–5

---

### PATCH /api/v1/applications/{app_id}/capability-links/{capability_id}

Update the fit score on an existing link.

**Request**

```json
{ "fit_score": 5 }
```

**Response 200** — updated `ApplicationCapabilityLink`

**Response 404** — link not found
**Response 422** — `fit_score` outside 1–5

---

### DELETE /api/v1/applications/{app_id}/capability-links/{capability_id}

**Response 204** — link deleted

**Response 404** — link not found

---

## Technical Capability Endpoints

### GET /api/v1/technical-capabilities

List all technical capabilities ordered by level then name.

**Response 200** — `TechCapListResponse`

```json
{
  "items": [
    { "id": "uuid1", "name": "Data Management", "description": null, "parent_id": null, "level": 1, "created_at": "..." },
    { "id": "uuid2", "name": "Structured Storage", "description": null, "parent_id": "uuid1", "level": 2, "created_at": "..." },
    { "id": "uuid3", "name": "Relational Database", "description": null, "parent_id": "uuid2", "level": 3, "created_at": "..." }
  ],
  "total": 3
}
```

---

### POST /api/v1/technical-capabilities

Create a new technical capability. Level is derived from parent: L1 if no parent, parent_level+1 otherwise.

**Request**

```json
{ "name": "Data Management", "parent_id": null }
```

```json
{ "name": "Structured Storage", "parent_id": "uuid1" }
```

**Response 201** — `TechnicalCapability` (includes derived `level`)

**Response 404** — parent not found
**Response 422** — blank name, or parent is L3 (depth exceeded)

---

### GET /api/v1/technical-capabilities/{tc_id}

**Response 200** — `TechnicalCapability`

**Response 404** — not found

---

### PATCH /api/v1/technical-capabilities/{tc_id}

Update name or description only (parent cannot be changed).

**Request**

```json
{ "name": "Structured Data Storage" }
```

**Response 200** — updated `TechnicalCapability`

**Response 404** — not found
**Response 422** — blank name

---

### DELETE /api/v1/technical-capabilities/{tc_id}

**Response 204** — deleted

**Response 404** — not found
**Response 409** — has children (delete children first)

---

## Application–Technical Capability Link Endpoints

### GET /api/v1/applications/{app_id}/technical-capability-links

**Response 200** — `ApplicationTechCapLinksResponse`

```json
{
  "items": [
    { "app_id": "app-uuid", "tech_cap_id": "tc-uuid", "tech_cap_name": "Relational Database", "usage_type": "provides" },
    { "app_id": "app-uuid", "tech_cap_id": "tc-uuid2", "tech_cap_name": "Event Streaming", "usage_type": "consumes" }
  ]
}
```

**Response 404** — application not found

---

### POST /api/v1/applications/{app_id}/technical-capability-links

**Request**

```json
{ "tech_cap_id": "tc-uuid", "usage_type": "provides" }
```

**Response 201** — `ApplicationTechCapLink`

**Response 404** — application or technical capability not found
**Response 409** — link (same app + same tech cap + same usage_type) already exists
**Response 422** — invalid `usage_type`

---

### DELETE /api/v1/applications/{app_id}/technical-capability-links/{tc_id}/{usage_type}

**Response 204** — link deleted

**Response 404** — link not found

---

## Application–Value Stream Stage Link Endpoints

### GET /api/v1/applications/{app_id}/stage-links

**Response 200** — `ApplicationStageLinksResponse`

```json
{
  "items": [
    { "app_id": "app-uuid", "stage_id": "stage-uuid", "stage_name": "Fulfil Order" }
  ]
}
```

**Response 404** — application not found

---

### POST /api/v1/applications/{app_id}/stage-links

**Request**

```json
{ "stage_id": "stage-uuid" }
```

**Response 201** — `ApplicationStageLink`

**Response 404** — application or stage not found
**Response 409** — link already exists

---

### DELETE /api/v1/applications/{app_id}/stage-links/{stage_id}

**Response 204** — link deleted

**Response 404** — link not found

---

## Application–Domain Integration Endpoints

### GET /api/v1/applications/{app_id}/domain-integrations

**Response 200** — `ApplicationDomainIntegrationsResponse`

```json
{
  "items": [
    {
      "id": "link-uuid",
      "app_id": "app-uuid",
      "domain_id": "domain-uuid",
      "domain_name": "Customer",
      "integration_type": "primary-support",
      "direction": "inbound",
      "created_at": "..."
    }
  ]
}
```

**Response 404** — application not found

---

### POST /api/v1/applications/{app_id}/domain-integrations

**Request**

```json
{
  "domain_id": "domain-uuid",
  "integration_type": "primary-support",
  "direction": "inbound"
}
```

**Response 201** — `ApplicationDomainIntegration`

**Response 404** — application or domain not found
**Response 422** — blank `integration_type`, invalid `direction`

---

### DELETE /api/v1/applications/{app_id}/domain-integrations/{link_id}

**Response 204** — link deleted

**Response 404** — link not found

---

## Application Integration Endpoints

### GET /api/v1/integrations

List integrations. When `app_id` query param provided, returns integrations where the app is source OR target.

**Query params**: `app_id` (optional UUID)

**Response 200** — `ApplicationIntegrationListResponse`

```json
{
  "items": [
    {
      "id": "int-uuid",
      "source_app_id": "app-uuid-a",
      "source_app_name": "Customer Portal",
      "target_app_id": "app-uuid-b",
      "target_app_name": "CRM System",
      "integration_type": "API",
      "description": "REST API call to sync customer profiles",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 1
}
```

---

### POST /api/v1/integrations

Create a new point-to-point integration.

**Request**

```json
{
  "source_app_id": "app-uuid-a",
  "target_app_id": "app-uuid-b",
  "integration_type": "API",
  "description": "REST API call to sync customer profiles"
}
```

**Response 201** — `ApplicationIntegration`

**Response 404** — source or target application not found
**Response 422** — `source_app_id == target_app_id`, invalid `integration_type`

---

### GET /api/v1/integrations/{int_id}

**Response 200** — `ApplicationIntegration`

**Response 404** — integration not found

---

### PATCH /api/v1/integrations/{int_id}

Update description only.

**Request**

```json
{ "description": "Updated description" }
```

**Response 200** — updated `ApplicationIntegration`

**Response 404** — not found

---

### DELETE /api/v1/integrations/{int_id}

**Response 204** — deleted

**Response 404** — not found

---

## Application–Design Link Endpoints

### GET /api/v1/applications/{app_id}/design-links

**Response 200** — `ApplicationDesignLinksResponse`

```json
{
  "items": [
    { "app_id": "app-uuid", "design_id": "design-uuid" }
  ]
}
```

**Response 404** — application not found

---

### POST /api/v1/applications/{app_id}/design-links

**Request**

```json
{ "design_id": "design-uuid" }
```

**Response 201** — `ApplicationDesignLink`

**Response 404** — application or design not found
**Response 409** — link already exists

---

### DELETE /api/v1/applications/{app_id}/design-links/{design_id}

**Response 204** — link deleted

**Response 404** — link not found
