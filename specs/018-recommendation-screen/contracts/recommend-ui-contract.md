# Contract: Recommendation UI

**Files**: `web/src/recommend/`
**Date**: 2026-07-02

---

## Screen Layout

```
┌─────────────────────────────────────────────────────────────┐
│  [Intake]  [Recommendations ●]  [Canvas]                    │  ← nav header (active = blue)
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ARCHITECTURE RECOMMENDATIONS                               │
│  Design: DESIGN-001                                         │
│                                                             │
│  ┌─ Requirements to include ──────────────────────────────┐ │
│  │  ☑ REQ-001 [non_functional]  10,000 concurrent users   │ │
│  │  ☑ REQ-002 [constraint]      API must be stateless      │ │
│  │  ☑ REQ-003 [non_functional]  Encrypted at rest         │ │
│  │                              [Get Recommendations]      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ Option 1 ──────────────────────────────────────── ─ ─  │
│  │  #1  Microservices with API Gateway     score: 84%      │ │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │ │
│  │  Rationale: Addresses NFR-001 via horizontal scaling…   │ │
│  │                                                         │ │
│  │  Trade-offs:                                           │ │
│  │  ✅ Scalability        meets                           │ │
│  │  ⚠️  Complexity        partially meets                 │ │
│  │  ✅ Security           meets                           │ │
│  │                                                         │ │
│  │  Proposed elements:                                    │ │
│  │  [container] API Gateway — Routes all inbound traffic  │ │
│  │  [container] Auth Service — Handles OAuth 2.0          │ │
│  │                                                         │ │
│  │  Grounded on: KI-012, KI-034                           │ │
│  │                              [Accept this option]       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ Option 2 ──  ⚠️ ADVISORY ──────────────────────────── │
│  │  #2  Monolithic with CQRS               score: 71%      │ │
│  │  ⚠️ This option lacks full knowledge-base grounding.   │ │
│  │  Additional review recommended before accepting.        │ │
│  │  ...                                                    │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Confirmation Dialog (ART-VIII)

```
┌─────────────────────────────────────────────────────────────┐
│  Accept Recommendation                                      │
│  ─────────────────────────────────────────────────         │
│  Option: Microservices with API Gateway (#1)               │
│                                                             │
│  This will add 2 elements to DESIGN-001:                    │
│  • [container] API Gateway                                  │
│  • [container] Auth Service                                 │
│                                                             │
│  These elements cannot be automatically removed             │
│  after acceptance. You can edit them on the canvas.         │
│                                                             │
│  [Cancel]                          [Confirm Accept]         │
└─────────────────────────────────────────────────────────────┘

Advisory variant adds:
│  ⚠️ Advisory Warning                                        │
│  ☐ I understand this option lacks full knowledge-base       │
│    grounding and accept additional review responsibility.   │
```

---

## Component Tree

```
RecommendationPage
├── RequirementSelector    (P2: checkbox list; all checked by default)
│   ├── RequirementItem × n
│   └── <button> Get Recommendations (disabled when none checked)
│
├── ExtractionStatus       (shows spinner while running; error on failed)
│
└── OptionsList            (shown when status=completed)
    └── OptionCard × n
        ├── RankBadge      (#1, #2, ...)
        ├── AdvisoryBadge  (⚠️ ADVISORY — only when advisory=true)
        ├── ScoreBar       (ranking_score as %)
        ├── RationaleText
        ├── TradeOffTable  (criterion | stance icon | rationale)
        ├── ElementsList   (kind badge + name + description)
        ├── GroundingList  (knowledge item IDs)
        └── AcceptButton   → opens AcceptDialog
            └── AcceptDialog
                ├── ElementsSummary
                ├── AdvisoryCheckbox  (only when advisory=true)
                └── [Cancel] [Confirm Accept]
```

---

## Navigation Integration

**Three-view nav bar** shown in all views:

```
[Intake]  [Recommendations]  [Canvas]
```

- `IntakePage.tsx` header: replaces "Go to Canvas →" with three-button nav
- `Workspace.tsx` header: adds "Recommendations" button between "Requirements" and level toggle
- `App.tsx`: adds `"recommend"` to the view state union; `RecommendationPage` receives `onNavigate(view)` prop

---

## TanStack Query Hooks (`web/src/api/recommend.ts`)

```typescript
useStartRecommendation(designId: string)
  → useMutation<RecommendStatusResponse, Error, RecommendRequest>
  // POST /api/v1/designs/{designId}/recommend

useRecommendStatus(designId: string, operationId: string | null)
  → useQuery<RecommendStatusResponse>
  // GET /api/v1/designs/{designId}/recommend/{operationId}
  // refetchInterval: 2000 while pending/running; false when completed/failed

useAcceptOption(designId: string, operationId: string)
  → useMutation<AcceptOptionResponse, Error, { optionId: string } & AcceptOptionRequest>
  // POST /api/v1/designs/{designId}/recommend/{operationId}/options/{optionId}/accept
  // onSuccess: navigate to canvas; invalidate design query
```

---

## Stance Icons

| Stance | Icon | Colour |
|---|---|---|
| `meets` | ✅ | Green |
| `partially_meets` | ⚠️ | Amber |
| `does_not_meet` | ❌ | Red |
