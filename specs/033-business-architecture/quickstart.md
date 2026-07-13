# Quickstart / Integration Scenarios: Business Architecture

**Feature**: 033-business-architecture
**Date**: 2026-07-10

These scenarios drive integration tests and E2E acceptance verification.

---

## Scenario 1: Build a 3-level capability hierarchy

**Goal**: Verify FR-001 through FR-008 and SC-001.

```
1. POST /api/v1/business/capabilities
   body: { "name": "Customer Engagement", "level": 1, "parent_id": null }
   → 201, id = C1

2. POST /api/v1/business/capabilities
   body: { "name": "Sales", "level": 2, "parent_id": C1 }
   → 201, id = C2

3. POST /api/v1/business/capabilities
   body: { "name": "Lead Qualification", "level": 3, "parent_id": C2 }
   → 201, id = C3

4. GET /api/v1/business/capabilities
   → 200, items contains C1, C2, C3
   → C1.parent_id == null, C2.parent_id == C1, C3.parent_id == C2

5. PUT /api/v1/business/capabilities/C3
   body: { "name": "Lead Scoring" }
   → 200, name == "Lead Scoring"

6. DELETE /api/v1/business/capabilities/C1
   → 409 (has children)

7. DELETE /api/v1/business/capabilities/C3
   → 204

8. DELETE /api/v1/business/capabilities/C2
   → 204

9. DELETE /api/v1/business/capabilities/C1
   → 204

10. GET /api/v1/business/capabilities
    → 200, total == 0
```

---

## Scenario 2: Depth limit enforcement

**Goal**: Verify FR-004.

```
1. POST /api/v1/business/capabilities
   body: { "name": "L1", "level": 1 }
   → 201, id = L1

2. POST /api/v1/business/capabilities
   body: { "name": "L2", "level": 2, "parent_id": L1 }
   → 201, id = L2

3. POST /api/v1/business/capabilities
   body: { "name": "L3", "level": 3, "parent_id": L2 }
   → 201, id = L3

4. POST /api/v1/business/capabilities
   body: { "name": "L4-attempt", "level": 4, "parent_id": L3 }
   → 422 (level must be 1, 2, or 3)
```

---

## Scenario 3: Parent level mismatch rejection

**Goal**: Verify the parent_id/level consistency check.

```
1. Create L1 (id = A), L2 child of A (id = B)

2. POST /api/v1/business/capabilities
   body: { "name": "Bad", "level": 2, "parent_id": B }
   → 422 (parent B is level 2; a level-2 child requires a level-1 parent)
```

---

## Scenario 4: Full value stream lifecycle

**Goal**: Verify FR-009 through FR-014 and SC-002.

```
1. POST /api/v1/business/value-streams
   body: { "name": "Order to Cash", "stakeholder": "Customer" }
   → 201, id = VS1

2. POST /api/v1/business/value-streams/VS1/stages
   body: { "name": "Order Capture", "position": 0 }
   → 201, id = S1

3. POST /api/v1/business/value-streams/VS1/stages
   body: { "name": "Fulfilment", "position": 1 }
   → 201, id = S2

4. POST /api/v1/business/value-streams/VS1/stages
   body: { "name": "Invoicing", "position": 2 }
   → 201, id = S3

5. GET /api/v1/business/value-streams/VS1
   → 200, stages == [S1, S2, S3] in position order

6. PUT /api/v1/business/value-streams/VS1/stages
   body: { "stages": [S3, S1, S2] }  (reorder)
   → 200, stages == [S3, S1, S2] with positions 0, 1, 2

7. PUT /api/v1/business/value-streams/VS1/stages/S1
   body: { "name": "Order Intake" }
   → 200, name updated

8. DELETE /api/v1/business/value-streams/VS1/stages/S3
   → 204

9. GET /api/v1/business/value-streams/VS1
   → 200, stages count == 2

10. DELETE /api/v1/business/value-streams/VS1
    → 204

11. GET /api/v1/business/value-streams/VS1
    → 404
```

---

## Scenario 5: Cascade delete of stages

**Goal**: Verify FR-013 — deleting a value stream removes its stages (no orphan rows).

```
1. Create value stream VS1 with 3 stages

2. DELETE /api/v1/business/value-streams/VS1
   → 204

3. Verify: SELECT * FROM value_stream_stages WHERE value_stream_id = VS1
   → 0 rows (CASCADE enforced)
```

---

## Scenario 6: UI Navigation

**Goal**: Verify the "Business" nav item exists and routes correctly.

```
1. Open the web app
2. Click "Business" in the top nav bar
3. → BusinessPage renders with two tabs: "Capabilities" and "Value Streams"
4. Click "Capabilities" tab → capability tree displays (empty state shown if no data)
5. Click "Value Streams" tab → value stream list displays (empty state shown if no data)
```

---

## Scenario 7: Empty-state behaviour

**Goal**: Verify the UI handles zero data gracefully.

```
1. Start with clean database (no capabilities, no value streams)
2. View Capabilities tab → empty state message with "Create your first capability" CTA
3. View Value Streams tab → empty state message with "Create your first value stream" CTA
```
