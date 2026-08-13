# Quickstart: Objective Progress Tracking, Lifecycle Status & Theme Management

Manual/curl verification scenarios, one per major behavior. Assumes a running local stack (`ADP_AUTH_ENABLED=false`, backend on `:8001`) and an existing objective — substitute a real `theme_id`/`objective_id` from `GET /api/v1/strategy/objectives`.

## 1. Theme lifecycle completion

```bash
# Create with the new optional fields
curl -s -X POST localhost:8001/api/v1/strategy/themes \
  -H "Content-Type: application/json" \
  -d '{"name": "Digital Channels", "description": "Customer-facing digital experience", "owner": "jane.architect", "priority": 2}'

# Read single
curl -s localhost:8001/api/v1/strategy/themes/{theme_id}

# Edit
curl -s -X PATCH localhost:8001/api/v1/strategy/themes/{theme_id} \
  -H "Content-Type: application/json" -d '{"priority": 1}'

# Delete a theme WITH objectives attached -- expect 409
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE localhost:8001/api/v1/strategy/themes/{theme_id_in_use}

# Delete a theme with none -- expect 204
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE localhost:8001/api/v1/strategy/themes/{theme_id_unused}
```

## 2. Record progress and watch status compute (User Story 1)

```bash
OBJ={objective_id}   # must have a target set (metric_name/target_value/target_unit/direction)

# No progress yet -- expect status: "proposed"
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"

# Record a first value trending toward target
curl -s -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/progress \
  -H "Content-Type: application/json" -d '{"as_of_date": "2026-08-01", "actual_value": 40}'

# Record a second value moving further toward target -- expect "active"
curl -s -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/progress \
  -H "Content-Type: application/json" -d '{"as_of_date": "2026-08-08", "actual_value": 55}'
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"

# Record a third value moving AWAY from target -- expect "at_risk"
curl -s -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/progress \
  -H "Content-Type: application/json" -d '{"as_of_date": "2026-08-15", "actual_value": 45}'
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"

# Duplicate date -- expect 409
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/progress \
  -H "Content-Type: application/json" -d '{"as_of_date": "2026-08-15", "actual_value": 999}'

# Correct that entry via PATCH instead -- expect 200, status recomputes
curl -s -X PATCH localhost:8001/api/v1/strategy/objectives/$OBJ/progress/2026-08-15 \
  -H "Content-Type: application/json" -d '{"actual_value": 60}'
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"

# Full history
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ/progress
```

## 3. Achieve and abandon (User Story 1 + 2)

```bash
# Record a value at/past target -- expect "achieved"
curl -s -X POST localhost:8001/api/v1/strategy/objectives/$OBJ/progress \
  -H "Content-Type: application/json" -d '{"as_of_date": "2026-09-01", "actual_value": 100}'
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"

# Abandon a different objective, no reason -- expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH localhost:8001/api/v1/strategy/objectives/{other_objective}/abandon \
  -H "Content-Type: application/json" -d '{}'

# Abandon with a reason -- expect 200, status "abandoned"
curl -s -X PATCH localhost:8001/api/v1/strategy/objectives/{other_objective}/abandon \
  -H "Content-Type: application/json" -d '{"status_reason": "Superseded by a broader Q3 objective"}'
curl -s localhost:8001/api/v1/strategy/objectives/{other_objective} \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'], d['status_reason'])"
```

## 4. No-target objective (Edge Case)

```bash
# An objective created without metric_name/target_value/target_unit/direction --
# expect status "proposed" forever, never an error, regardless of any progress entries
curl -s localhost:8001/api/v1/strategy/objectives/{no_target_objective} \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"
```

## 5. Objective delete cascades progress (FR-016)

```bash
curl -s -X DELETE localhost:8001/api/v1/strategy/objectives/{objective_to_delete}
# Then confirm no orphaned rows -- direct DB check (no endpoint returns progress for a
# deleted objective, so this step is a psql spot-check, not an API call):
#   SELECT count(*) FROM strategic_objective_progress WHERE objective_id = '{objective_to_delete}';
#   -- expect 0
```
