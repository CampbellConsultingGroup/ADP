# Contract: Intake Web Screen UI

**Files**: `web/src/intake/`
**Date**: 2026-07-02

---

## Screen Layout

```
┌─────────────────────────────────────────────────────────────┐
│  My First Architecture                                       │
│  [Context] [Container] [Component]     [Requirements ★]     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  REQUIREMENTS INTAKE                                        │
│  ┌─────────────────────────┐  ┌────────────────────────┐   │
│  │ [Bulk Text]  [Form]     │  │  CONFIRMED REQUIREMENTS │   │
│  │─────────────────────────│  │  ────────────────────── │   │
│  │ Paste requirements...   │  │  REQ-001 [functional]   │   │
│  │                         │  │  Stateless API          │   │
│  │                         │  │                         │   │
│  │  [⚠ Source text never  │  │  REQ-002 [non_func]     │   │
│  │   stored after extract] │  │  10k concurrent users   │   │
│  │─────────────────────────│  └────────────────────────┘   │
│  │  [Extract Requirements] │                               │
│  └─────────────────────────┘                               │
│                                                             │
│  EXTRACTED PROPOSALS (3)                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [non_functional] ██████████░░ 92%                   │   │
│  │ The system MUST handle 10,000 concurrent users...   │   │
│  │ ┌───────────────────────────────────────────────┐  │   │
│  │ │ Source: "must handle 10,000 concurrent users" │  │   │
│  │ └───────────────────────────────────────────────┘  │   │
│  │ [Confirm] [Edit & Confirm] [Reject]                 │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [functional] ████████░░░░ 78%              ✓ confirmed │  │
│  │ The API must authenticate every request              │  │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Tree

```
IntakePage
├── IntakeTextForm          (bulk text tab)
│   ├── <textarea>          placeholder: "Paste requirements text..."
│   ├── SecurityNotice      ⚠ "Source text is not stored"
│   └── <button> Extract    disabled while pending/running
│
├── StructuredForm          (form tab)
│   ├── <input> statement   required
│   ├── <select> kind       functional | non_functional | constraint | driver
│   └── <button> Add Requirement
│
├── ExtractionStatus        shown when operation exists
│   ├── Spinner + "Extracting..." when status=running
│   ├── Error banner when status=failed
│   └── nothing when status=completed
│
├── ProposalsList           shown when status=completed
│   └── ProposalCard (×n)
│       ├── KindBadge       colour-coded: functional=blue, non_func=purple, etc.
│       ├── ConfidenceBar   filled proportion = confidence value
│       ├── StatementText   editable inline when "Edit & Confirm" clicked
│       ├── SourceExcerpt   grey quoted box — always visible (SC-005)
│       └── ActionButtons
│           ├── [Confirm]         POST confirm with null edited_statement
│           ├── [Edit & Confirm]  expand inline editor; POST confirm with edited text
│           └── [Reject]          POST reject; card fades to muted/strikethrough
│
└── RequirementsList        always visible (right panel)
    └── RequirementItem (×n)
        ├── id badge (REQ-001)
        ├── kind badge
        └── title text
```

---

## TanStack Query Hooks (`web/src/api/intake.ts`)

```typescript
// Submit intake
useSubmitIntake(designId: string) → UseMutationResult<IntakeSubmitResponse, ...>
  // POST /api/v1/designs/{designId}/intake

// Poll status (auto-stops when completed/failed)
useIntakeStatus(designId: string, operationId: string | null) → UseQueryResult<IntakeStatusResponse>
  // GET /api/v1/designs/{designId}/intake/{operationId}
  // refetchInterval: 2000ms while status is pending/running

// Confirm proposal
useConfirmProposal(designId: string, operationId: string) → UseMutationResult
  // POST /api/v1/designs/{designId}/intake/{operationId}/proposals/{proposalId}/confirm

// Reject proposal
useRejectProposal(designId: string, operationId: string) → UseMutationResult
  // POST /api/v1/designs/{designId}/intake/{operationId}/proposals/{proposalId}/reject

// Add direct requirement
useAddRequirement(designId: string) → UseMutationResult<ConfirmProposalResponse, ...>
  // POST /api/v1/designs/{designId}/requirements

// List requirements (feeds right panel)
useRequirements(designId: string) → UseQueryResult<RequirementListResponse>
  // GET /api/v1/designs/{designId}/requirements
  // refetchInterval: false (refresh manually after confirm/add)
```

---

## Navigation Integration

`App.tsx` parses `/designs/{id}/intake` path to render `<IntakePage designId={id} />`.

`Workspace.tsx` header adds a "Requirements" button alongside the level toggle:
```
[My Architecture]  [Context] [Container] [Component]  |  [Requirements]
```
The Requirements button navigates to `/designs/{id}/intake`.

---

## Accessibility

- Kind badges use both colour AND text label (not colour-only) — accessible without colour vision
- Confidence bars include `aria-valuenow` and `aria-valuemax` attributes
- All action buttons have `aria-label` descriptions
- Inline edit textarea has `aria-label="Edit requirement statement"`
- Source excerpt block has `role="blockquote"`
