# Data Model: Agent Review Toolkit (ADP-SPEC-039)

No database migration in this feature (see research.md D1) — `AgentReviewOperation` and `AgentSuggestion` are transient, carried entirely inside the existing `operations.payload` JSONB column, exactly like intake proposals and recommendation options today. This document covers the Pydantic v2 models (all `model_config = ConfigDict(extra="forbid")`) and the authz additions.

## Shared toolkit models (`src/adp/agents/models.py`)

```python
class GroundingCitation(BaseModel):
    """One entity a suggestion references, to be independently verified."""
    entity_type: str          # e.g. "business_capability", "business_domain"
    entity_id: str

class GroundingResult(BaseModel):
    """Outcome of re-verifying a suggestion's citations against the database."""
    resolved: list[GroundingCitation]
    unresolved: list[GroundingCitation]

    @property
    def fully_grounded(self) -> bool:
        return len(self.unresolved) == 0


class AgentSuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AgentReviewOperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"      # LLM call errored (FR-021) -- error_description set; distinct
                           # from a legitimate empty suggestion set (no LLM configured)
```

`AgentSuggestionBase` is intentionally *not* a rigid shared base every adapter must extend field-for-field — Option B's adapters define their own suggestion payload shape (e.g. the Business Capabilities adapter's tagged union below). The shared pieces are the process fields every adapter's suggestion needs regardless of domain: `suggestion_id`, `status`, `rationale`, `citations: list[GroundingCitation]`, `advisory: bool`. Adapters compose these into their own domain-specific model rather than inheriting a fixed shape, so a future adapter proposing a fundamentally different kind of change isn't forced into this one's fields.

**Field-scoped stale-check (FR-015, research.md D8)**: any suggestion type that overwrites an existing field carries its own strongly-typed snapshot of that field's value *at generation time* (e.g. `previous_maturity_level` below). Accept re-reads the target entity's current value for that same field and 409s if it no longer matches the snapshot — unrelated fields on the same entity are never compared. Suggestion types that don't overwrite an existing field (`flag_duplicate`, `propose_new_capability`) have no snapshot field; their staleness concern is entity/citation existence only, already covered by the standard grounding re-check.

## `adp.agents.llm_stub`

```python
class StubLLMClient(LLMClient):
    """Shared no-API-key fallback: chat() returns an empty choice list.

    Replaces the ad hoc _StubLLMClient duplicated today in
    src/adp/api/routers/intake.py and src/adp/api/routers/recommend.py.
    Both routers are updated to import this instead of redefining it.
    """
    async def chat(self, system: str, user: str, correlation_id: str | None = None) -> dict:
        return {"choices": [], "usage": {}}
```

## `adp.agents.grounding`

```python
EntityLookup = Callable[[str], Awaitable[bool]]  # entity_id -> exists?

async def verify_references(
    citations: list[GroundingCitation],
    lookups: dict[str, EntityLookup],   # entity_type -> lookup fn
) -> GroundingResult:
    """Re-verify every citation against the database. Unrecognized entity_type
    is treated as unresolved (fail closed, never silently trust)."""
```

## `adp.agents.provenance`

```python
async def write_suggestion_audit(
    design_or_entity_context, *, actor: str, action: str, affected_entity: str,
    summary: str, operation_id: str,
) -> None:
    """Writes an AuditEntry with origin='ai', actor=the confirming human.
    Adapters call this from their accept path, after the underlying store
    write succeeds -- mirrors materialize_option's audit write."""

async def write_suggestion_reasoning(
    *, operation_id: str, suggestion_id: str, step_name: str, model_id: str,
    reasoning_text: str, input_tokens: int, output_tokens: int, session,
) -> None:
    """Fire-and-forget (asyncio.create_task by the caller) write to the
    existing llm_reasoning_log table, passing suggestion_id as option_id."""
```

## Business Capabilities adapter models (`src/adp/business/models.py` additions)

```python
AgentSuggestionType = Literal[
    "reclassify_strategic_relevance",
    "set_maturity_level",
    "assign_domain",
    "flag_duplicate",
    "propose_new_capability",
]

class CapabilitySuggestion(BaseModel):
    """One suggestion from a capability review (FR-010)."""
    suggestion_id: str
    type: AgentSuggestionType
    capability_id: str | None   # null only for propose_new_capability
    rationale: str
    citations: list[GroundingCitation]
    advisory: bool
    status: AgentSuggestionStatus
    # type-specific payload, one of:
    strategic_relevance: StrategicRelevance | None = None      # reclassify_strategic_relevance
    previous_strategic_relevance: StrategicRelevance | None = None  # snapshot at generation (FR-015)
    maturity_level: MaturityLevel | None = None                # set_maturity_level
    previous_maturity_level: MaturityLevel | None = None        # snapshot at generation (FR-015)
    domain_id: str | None = None                                # assign_domain
    # assign_domain has no previous_* snapshot: FR-012 scopes it to capabilities
    # with domain_id IS NULL, so the implicit snapshot is always None.
    duplicate_of_capability_id: str | None = None               # flag_duplicate
    proposed_name: str | None = None                            # propose_new_capability
    proposed_description: str | None = None                     # propose_new_capability
    proposed_level: Literal[1, 2, 3] | None = None              # propose_new_capability
    proposed_parent_id: str | None = None                       # propose_new_capability


class CapabilityAgentReviewResponse(BaseModel):
    """Poll response, mirrors IntakeStatusResponse's shape."""
    operation_id: str
    capability_id: str
    status: AgentReviewOperationStatus
    suggestions: list[CapabilitySuggestion]
    error_description: str | None = None   # set only when status=FAILED (FR-021); a
                                            # short, sanitized message -- never raw
                                            # prompt/response content


class SuggestionDecisionRequest(BaseModel):
    """Accept/reject body. advisory_acknowledged is required (True) to accept
    a suggestion where advisory=True; ignored on reject."""
    advisory_acknowledged: bool = False
```

Context assembly (`src/adp/business/agent_review.py`) reads, for the target capability: its own row (including `strategic_relevance`, `maturity_level`), its domain via the existing `get_capability`/domain join, its parent and direct children, its linked value-stream stages, its linked applications' `time_classification`/`r_strategy`/`pace_layer`/`health_score` only (never risk/cost/governance — research D6), its linked technical capabilities, its linked designs, and (for `flag_duplicate` only) the sibling set at the same `level`.

## Endpoints (`src/adp/business/router.py` additions)

| Method | Path | Action | Notes |
|---|---|---|---|
| `POST` | `/api/v1/business/capabilities/{cap_id}/agent-review` | `SUBMIT_AI_OPERATION` (reused) | 202 + `operation_id`; background job |
| `GET` | `/api/v1/business/capabilities/{cap_id}/agent-review/{operation_id}` | (safe method, unenforced) | poll |
| `POST` | `.../agent-review/{operation_id}/suggestions/{suggestion_id}/accept` | `CONFIRM_AGENT_SUGGESTION` (new) | re-verifies grounding + that the target entity still exists + (for field-overwrite types) that its current field value still matches the suggestion's `previous_*` snapshot (FR-015, 409 on mismatch), then calls the existing store function; re-checks `WRITE_BUSINESS_ARCH` for the target entity (FR-016) |
| `POST` | `.../agent-review/{operation_id}/suggestions/{suggestion_id}/reject` | `CONFIRM_AGENT_SUGGESTION` (new) | marks rejected; no write |

Accept dispatch by suggestion type calls, unchanged: `update_capability` (`reclassify_strategic_relevance`, `set_maturity_level`), `assign_capability_domain` (`assign_domain`), `create_capability` (`propose_new_capability`); `flag_duplicate` has no store call — accepting it is an acknowledgment only.

## Authz additions (`src/adp/authz`)

```python
# roles.py
class ActionType(StrEnum):
    ...
    CONFIRM_AGENT_SUGGESTION = "confirm_agent_suggestion"   # NEW
```

`SUBMIT_AI_OPERATION` is granted already to the same roles that need it here (solution/technical/enterprise architect) — no change. `CONFIRM_AGENT_SUGGESTION` is granted to the same three roles. `PERMISSIONS_VERSION` bumps `1.4.0` → `1.5.0`. `enforcement.py`'s `_EXPLICIT_ROUTE_ACTIONS` gains the four route entries in the table above (GET is never enforced, so only 3 explicit entries are actually needed).
