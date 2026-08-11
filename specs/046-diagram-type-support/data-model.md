# Phase 1 Data Model: Diagram Types Beyond C4

## 1. New backend table: `diagrams`

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)`, PK | UUID, server-generated on create — matches the ID shape every other ADP entity uses. |
| `title` | `String(255)`, NOT NULL | User-provided; blank rejected at the Pydantic layer (matches `name_not_blank` convention used across `adp.application`/`adp.business`). |
| `diagram_type` | `Text`, NOT NULL | One of the five supported values: `"flowchart"`, `"sequence"`, `"erd"`, `"uml"`, `"architecture"` — a Python `Literal`, not a DB enum (matches how `TimeClassification`/`LifecycleStatus` etc. are already modeled: `Literal` + `sa.Text()`, not `sa.Enum`). |
| `dsl_source` | `Text`, NOT NULL, default `''` | The diagram's authoritative content (research.md Decision 2 — opaque to the backend; capped at 50,000 characters at the Pydantic layer, five times the existing `full_text` cap on knowledge items, since a diagram's DSL is denser but still bounded plain text). |
| `created_by` | `String(255)`, nullable | Actor identifier (matches the existing `_get_actor(request)` convention used across ADP routers — the auth-disabled dev convention reads `X-Actor`, the auth-enabled path reads the JWT subject). |
| `created_at` | `DateTime(timezone=True)`, NOT NULL | |
| `updated_at` | `DateTime(timezone=True)`, NOT NULL | |

**No `design_id` column, no foreign key to `designs`** — standalone per FR-011/Clarifications. **No new database enum, no new `pgvector` column, no relationship to any other existing table.**

## 2. Pydantic v2 models (`src/adp/diagrams/models.py`)

```python
DiagramType = Literal["flowchart", "sequence", "erd", "uml", "architecture"]

class Diagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    diagram_type: DiagramType
    dsl_source: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime

class DiagramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    diagram_type: DiagramType
    dsl_source: str = ""   # FR: a brand-new diagram must be creatable before any content exists

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v

    @field_validator("dsl_source")
    @classmethod
    def dsl_source_within_cap(cls, v: str) -> str:
        if len(v) > 50_000:
            raise ValueError("dsl_source must not exceed 50,000 characters")
        return v

class DiagramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    dsl_source: str | None = None
    # diagram_type is immutable after creation -- switching a flowchart into a
    # sequence diagram mid-life is a "create a new diagram" action, not an update.

class DiagramSummary(BaseModel):
    """List-view shape (FR-006): title/type/updated_at only, no dsl_source --
    mirrors the existing summary-vs-detail split (e.g. knowledge items' list
    endpoint omitting full_text)."""
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    diagram_type: DiagramType
    updated_at: datetime

class DiagramListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[DiagramSummary]
    total: int
```

## 3. Frontend model (vendored, not redefined — reference only)

The vendored `web/src/diagrams/core/model/diagram-model.ts` (`DiagramModel`, `NodeShape`, `EntityAttribute`, `ClassMember`, etc.) is the in-memory representation the `Canvas` editor operates on. ADP's backend never sees this shape — only its serialized DSL-text form (`dsl_source`) crosses the browser↔API boundary, produced by the vendored `dslFamilies[type].serialize(model)` function and re-hydrated on load via `dslFamilies[type].parse(dsl_source)`. This is a deliberate boundary: the typed in-memory model is real, but it is a *frontend-only* concern (research.md Decision 2), not a second schema ADP's backend needs to know about or keep in sync with.

## 4. State/lifecycle

A diagram has no state machine beyond existence: created → (any number of) updated → deleted. No draft/published distinction, no versioning beyond the single current `dsl_source` value (matches FR-011's "standalone artifact" framing — there is no workflow around it the way a Design's own lifecycle might have one).
