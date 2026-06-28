# Quickstart: Authoring a Valid Architecture Description

**Branch**: `001-canonical-data-model` | **Date**: 2026-06-27  
**Prerequisite**: `adp` package installed from `pyproject.toml`

This guide shows how to author, validate, and serialize a conforming `ArchitectureDescription`. It covers the primary flow (User Story 1) and demonstrates the safety guarantees (User Story 2).

---

## Minimal Valid Description

A description can be empty of design content but must always carry identity and timestamp fields:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "1.0.0",
  "id": "DESIGN-001",
  "title": "My Architecture",
  "created_at": "2026-06-27T00:00:00Z",
  "updated_at": "2026-06-27T00:00:00Z"
}
```

---

## Adding a Requirement

Requirements are the starting point of every traceability chain. IDs must follow `REQ-NNN`:

```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "title": "Stateless request handling",
      "description": "All API handlers must be stateless so any instance can serve any request.",
      "priority": "must"
    }
  ]
}
```

---

## Adding Elements That Satisfy Requirements

Elements carry a `satisfies` list linking them back to the requirements they address:

```json
{
  "elements": [
    {
      "id": "ELM-001",
      "name": "API Gateway",
      "kind": "container",
      "description": "Entry point for all client requests. Routes to backend services.",
      "satisfies": ["REQ-001"]
    },
    {
      "id": "ELM-002",
      "name": "Order Service",
      "kind": "container",
      "description": "Processes and persists order lifecycle events.",
      "satisfies": ["REQ-001"]
    }
  ]
}
```

**Note**: Referencing a `RequirementId` that does not exist in `requirements` causes a load-time validation error.

---

## Connecting Elements with Relationships

```json
{
  "relationships": [
    {
      "id": "REL-001",
      "source": "ELM-001",
      "target": "ELM-002",
      "label": "Routes order requests",
      "technology": "HTTPS"
    }
  ]
}
```

---

## Recording a Solution Option and Verdict

```json
{
  "options": [
    {
      "id": "OPT-001",
      "title": "JWT-based stateless auth",
      "description": "Issue short-lived JWTs at login; validate at gateway without session store.",
      "status": "accepted",
      "satisfies": ["REQ-001"]
    }
  ],
  "verdicts": [
    {
      "id": "VRD-001",
      "option_id": "OPT-001",
      "status": "accepted",
      "rationale": "Aligns with stateless requirement and is consistent with existing platform patterns.",
      "decided_by": "architecture-board",
      "decided_at": "2026-06-27T14:00:00Z"
    }
  ]
}
```

---

## Validating Against the Schema

Use the CLI or the Python API:

```bash
# Validate a JSON file against the published schema
adp-generate --validate path/to/my-design.json

# Check that the committed schema matches the current model source (CI gate)
adp-generate --check
```

---

## What Gets Rejected

The model rejects these cases with a descriptive error:

| Attempt | Error |
|---|---|
| Unknown field on any entity | `Extra inputs are not permitted` |
| `satisfies: ["REQ-999"]` where REQ-999 doesn't exist | `Reference REQ-999 not found in requirements` |
| `"id": "REQ-ABC"` (invalid format) | `String should match pattern '^REQ-\d{3}$'` |
| Missing `schema_version` | `Field required` |
| `"kind": "module"` (not a valid ElementKind) | `Input should be 'person', 'system', 'container' or 'component'` |

---

## Traceability Thread

The full requirement → element → option → verdict chain is queryable once all entities are linked:

```
REQ-001 (Stateless request handling)
  └── satisfies ── ELM-001 (API Gateway)
  └── satisfies ── ELM-002 (Order Service)
  └── satisfies ── OPT-001 (JWT-based stateless auth)
                       └── VRD-001 (accepted by architecture-board)
```

See `fixtures/example-adp.json` for a complete, schema-valid example covering all entity types.
