# Implementation Plan: Immutable LLM Reasoning Store (ADP-SPEC-027)

## Tech Stack
- **No new packages**: SQLAlchemy 2 async + asyncpg (existing), hashlib stdlib for SHA-256
- **New module**: `src/adp/store/reasoning.py` — `ReasoningStore`, `ReasoningRecord`
- **Migration**: New Alembic migration with table + 2 triggers (BEFORE UPDATE, BEFORE DELETE)
- **Pipeline integration**: `src/adp/recommendation/steps.py` (generate_step, analyze_tradeoffs_step) + `src/adp/intake/orchestrator.py`
- **New router**: `src/adp/api/routers/reasoning.py` — `GET /api/v1/reasoning`

## Architecture

### `llm_reasoning_log` Table

```sql
CREATE TABLE llm_reasoning_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id TEXT       NOT NULL,
    option_id   TEXT,                          -- null for non-option steps (intake)
    step_name   TEXT        NOT NULL,           -- 'generate' | 'analyze_tradeoffs' | 'extract'
    model_id    TEXT        NOT NULL,
    reasoning_text TEXT     NOT NULL,
    truncated   BOOLEAN     NOT NULL DEFAULT FALSE,
    prompt_hash TEXT        NOT NULL,           -- SHA-256 hex of system+user prompt
    input_tokens  INTEGER   NOT NULL DEFAULT 0,
    output_tokens INTEGER   NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_reasoning_operation ON llm_reasoning_log (operation_id);
CREATE INDEX ix_reasoning_option    ON llm_reasoning_log (option_id) WHERE option_id IS NOT NULL;

-- Immutability triggers
CREATE OR REPLACE FUNCTION llm_reasoning_immutable() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'llm_reasoning_log is append-only — UPDATE is not permitted';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'llm_reasoning_log is append-only — DELETE is not permitted';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reasoning_no_update
    BEFORE UPDATE ON llm_reasoning_log
    FOR EACH ROW EXECUTE FUNCTION llm_reasoning_immutable();

CREATE TRIGGER trg_reasoning_no_delete
    BEFORE DELETE ON llm_reasoning_log
    FOR EACH ROW EXECUTE FUNCTION llm_reasoning_immutable();
```

### `ReasoningStore` (`src/adp/store/reasoning.py`)

```python
@dataclass
class ReasoningRecord:
    operation_id: str
    step_name: str
    model_id: str
    reasoning_text: str
    prompt_hash: str        # SHA-256(prompt_bytes).hexdigest()
    input_tokens: int = 0
    output_tokens: int = 0
    option_id: str | None = None

class ReasoningStore:
    async def write(self, record: ReasoningRecord) -> None
    async def list_for_operation(self, operation_id: str, option_id: str | None = None) -> list[dict]
```

Write is fire-and-forget via `asyncio.create_task()`. Uses shared KB session from `adp.api.deps`.

### Pipeline integration points

**generate_step** (per option generated):
```python
await reasoning_store.write(ReasoningRecord(
    operation_id=state["operation_id"],
    option_id=option.option_id,
    step_name="generate",
    model_id=llm._model,
    reasoning_text=option.rationale[:100_000],
    prompt_hash=sha256(f"{system}\n\n{user}".encode()).hexdigest(),
    input_tokens=input_tokens,
    output_tokens=output_tokens,
))
```

**analyze_tradeoffs_step** (per option analyzed):
```python
trade_off_text = "\n\n".join(
    f"{t.criterion} [{t.stance.value}]: {t.rationale}"
    for t in option.trade_offs
)
await reasoning_store.write(ReasoningRecord(
    operation_id=..., option_id=option.option_id,
    step_name="analyze_tradeoffs",
    model_id=llm._model,
    reasoning_text=trade_off_text[:100_000],
    prompt_hash=sha256(...).hexdigest(),
    ...
))
```

**ExtractionOrchestrator.run** (one per extraction):
```python
await reasoning_store.write(ReasoningRecord(
    operation_id=op_id,
    step_name="extract",
    model_id=self._llm._model,
    reasoning_text=f"{len(proposals)} requirement(s) extracted",
    prompt_hash=sha256(submission.text.encode()).hexdigest(),
    ...
))
```

### New router `src/adp/api/routers/reasoning.py`

```
GET /api/v1/reasoning?operation_id=&option_id=  → list[ReasoningResponse]
```

## File Changes

| File | Action |
|---|---|
| `alembic/versions/XXXX_llm_reasoning_log.py` | CREATE — table + triggers |
| `src/adp/store/reasoning.py` | CREATE — ReasoningRecord + ReasoningStore |
| `src/adp/store/__init__.py` | EDIT — export ReasoningStore |
| `src/adp/api/deps.py` | EDIT — add `get_reasoning_store()` singleton dep |
| `src/adp/api/routers/reasoning.py` | CREATE — GET /api/v1/reasoning |
| `src/adp/api/app.py` | EDIT — register reasoning router |
| `src/adp/recommendation/steps.py` | EDIT — write after generate_step and analyze_tradeoffs_step |
| `src/adp/intake/orchestrator.py` | EDIT — write after successful extraction |
| `tests/unit/test_reasoning_store.py` | CREATE — unit tests |
| `tests/contract/test_reasoning_api.py` | CREATE — contract tests |

## Constitution Compliance

- **ART-IV**: Unit tests cover write, list, truncation; contract tests cover 200 with results, empty, filter by option_id
- **ART-VII**: Prompt hash enables cross-referencing without storing raw prompts
- **ART-IX**: Reasoning records are the AI extension of the audit trail — permanent and immutable
