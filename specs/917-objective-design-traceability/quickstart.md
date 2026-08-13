# Quickstart: Objective ↔ Design/Application Traceability

Manual/curl verification scenarios. Assumes a running local stack (`ADP_AUTH_ENABLED=false`, backend on
`:8001`) and at least one existing objective, one existing design, and one existing application —
substitute real ids from `GET /api/v1/strategy/objectives`, `GET /api/v1/designs`,
`GET /api/v1/applications`.

## 1. Link an objective to a design (User Story 1)

```bash
OBJ={objective_id}
DSN={design_id}

# Link
curl -s -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/designs \
  -H "Content-Type: application/json" -d "{\"design_id\": \"$DSN\"}"
# → 201, list includes $DSN

# Forward: the objective shows the design
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ | python3 -c "import json,sys; print(json.load(sys.stdin)['design_ids'])"

# Reverse: the design shows the objective
curl -s localhost:8001/api/v1/designs/$DSN/objectives

# Duplicate -- expect 409
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/designs \
  -H "Content-Type: application/json" -d "{\"design_id\": \"$DSN\"}"

# Unknown design -- expect 404
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/designs \
  -H "Content-Type: application/json" -d "{\"design_id\": \"nonexistent\"}"

# Unlink
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE localhost:8001/api/v1/strategy/objectives/$OBJ/designs/$DSN
curl -s localhost:8001/api/v1/designs/$DSN/objectives   # empty items
```

## 2. Link an objective to an application (User Story 2)

```bash
OBJ={objective_id}
APP={application_id}

curl -s -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/applications \
  -H "Content-Type: application/json" -d "{\"application_id\": \"$APP\"}"

curl -s localhost:8001/api/v1/strategy/objectives/$OBJ | python3 -c "import json,sys; print(json.load(sys.stdin)['application_ids'])"

curl -s localhost:8001/api/v1/applications/$APP/objectives

curl -s -o /dev/null -w "%{http_code}\n" -X DELETE localhost:8001/api/v1/strategy/objectives/$OBJ/applications/$APP
curl -s localhost:8001/api/v1/applications/$APP/objectives   # empty items
```

## 3. Cascade cleanup (Edge Cases, FR-010/FR-011)

```bash
# Delete an objective that has both a design link and an application link, then confirm no orphaned
# rows -- direct DB spot-check (no endpoint returns links for a deleted objective):
#   SELECT count(*) FROM objective_design_links WHERE objective_id = '{deleted_id}';
#   SELECT count(*) FROM objective_application_links WHERE objective_id = '{deleted_id}';
#   -- both expect 0
```

## 4. Browser walkthrough

- Open a strategic objective's detail view; confirm "Linked Designs" and "Linked Applications" sections
  appear alongside the existing capability/value-stream editors, and support add/remove.
- Open that same design in the C4 Design View; confirm the "Traceability" section shows the linked
  objective.
- Open that same application's detail screen; confirm the objective appears in its "Objectives
  realized" section.
