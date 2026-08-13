# Quickstart: Strategy Initiatives & Objective Dependencies

Manual/curl verification scenarios. Assumes a running local stack (`ADP_AUTH_ENABLED=false`, backend on `:8001`) and at least two existing objectives — substitute real ids from `GET /api/v1/strategy/objectives`.

## 1. Initiative lifecycle

```bash
# Create
curl -s -X POST localhost:8001/api/v1/strategy/initiatives \
  -H "Content-Type: application/json" \
  -d '{"name": "Claims Automation Program", "description": "Q3-Q4 delivery vehicle", "owner": "jane.architect", "status": "in_progress"}'

# Read single, list, edit
curl -s localhost:8001/api/v1/strategy/initiatives/{initiative_id}
curl -s localhost:8001/api/v1/strategy/initiatives
curl -s -X PATCH localhost:8001/api/v1/strategy/initiatives/{initiative_id} \
  -H "Content-Type: application/json" -d '{"status": "blocked"}'

# Delete -- unconditional, no in-use block (unlike theme delete)
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE localhost:8001/api/v1/strategy/initiatives/{initiative_id}
```

## 2. Link an initiative to objectives (User Story 1)

```bash
INIT={initiative_id}
OBJ1={objective_id_1}
OBJ2={objective_id_2}

curl -s -X POST localhost:8001/api/v1/strategy/initiatives/$INIT/objectives/$OBJ1
curl -s -X POST localhost:8001/api/v1/strategy/initiatives/$INIT/objectives/$OBJ2

# Forward: the initiative shows both objectives
curl -s localhost:8001/api/v1/strategy/initiatives/$INIT | python3 -c "import json,sys; print(json.load(sys.stdin)['objective_ids'])"

# Reverse: each objective shows the initiative
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ1/initiatives

# Unlink one, confirm the other survives
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE localhost:8001/api/v1/strategy/initiatives/$INIT/objectives/$OBJ1
curl -s localhost:8001/api/v1/strategy/objectives/$OBJ2/initiatives
```

## 3. Objective dependencies and cycle rejection (User Story 2)

```bash
A={objective_id_a}
B={objective_id_b}
C={objective_id_c}

# A depends on B
curl -s -X POST localhost:8001/api/v1/strategy/objectives/$A/depends-on \
  -H "Content-Type: application/json" -d "{\"depends_on_objective_id\": \"$B\"}"

# Both directions visible
curl -s localhost:8001/api/v1/strategy/objectives/$A/dependencies   # depends_on: [B]
curl -s localhost:8001/api/v1/strategy/objectives/$B/dependencies   # blocks: [A]

# Direct 2-cycle -- expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8001/api/v1/strategy/objectives/$B/depends-on \
  -H "Content-Type: application/json" -d "{\"depends_on_objective_id\": \"$A\"}"

# Chain: B depends on C, then attempt C depends on A -- expect 400 (closes a 3-cycle)
curl -s -X POST localhost:8001/api/v1/strategy/objectives/$B/depends-on \
  -H "Content-Type: application/json" -d "{\"depends_on_objective_id\": \"$C\"}"
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8001/api/v1/strategy/objectives/$C/depends-on \
  -H "Content-Type: application/json" -d "{\"depends_on_objective_id\": \"$A\"}"

# Self-dependency -- expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8001/api/v1/strategy/objectives/$A/depends-on \
  -H "Content-Type: application/json" -d "{\"depends_on_objective_id\": \"$A\"}"

# Remove a dependency
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE localhost:8001/api/v1/strategy/objectives/$A/depends-on/$B
curl -s localhost:8001/api/v1/strategy/objectives/$A/dependencies   # depends_on: []
```

## 4. Cascade cleanup (Edge Cases, FR-010)

```bash
# Delete an objective that has both an initiative link and a dependency link,
# then confirm no orphaned rows -- direct DB spot-check (no endpoint returns
# links for a deleted objective):
#   SELECT count(*) FROM strategy_initiative_objective_links WHERE objective_id = '{deleted_id}';
#   SELECT count(*) FROM strategic_objective_dependencies
#     WHERE objective_id = '{deleted_id}' OR depends_on_objective_id = '{deleted_id}';
#   -- both expect 0
```
