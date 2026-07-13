# Implementation Plan: Internal Architecture Consolidation (ADP-SPEC-023)

## Tech Stack
No new packages. Pure refactor of existing Python 3.12 + FastAPI + SQLAlchemy 2 stack.

## Three Independent Moves

These three moves can be executed in any order and are safe to review separately.

### Move A: Single DB Pool

**Current state**: Three engines created independently.
```
adp.api.deps              → engine for design store (architecture_descriptions)
adp.api.routers.knowledge → engine for knowledge_items
adp.calm.importer         → engine for knowledge_items (CLI context)
```

**Target state**:
```
adp.api.deps              → ONE engine + ONE session factory, exported as:
                             get_design_store()  (existing)
                             get_kb_session()    (new)
adp.api.routers.knowledge → uses Depends(get_kb_session) from adp.api.deps
adp.api.routers.calm      → uses Depends(get_kb_session) from adp.api.deps
adp.calm.importer         → creates its own engine only in CLI path (no FastAPI context)
```

Files changed: `adp/api/deps.py`, `adp/api/routers/knowledge.py`, `adp/api/routers/calm.py`

### Move B: Audit Utility

**Current state**: `_next_audit_id(design)` in `adp/intake/orchestrator.py` (private, line ~20).
Imported by: `adp/recommendation/orchestrator.py`, `adp/api/routers/intake.py`, `adp/api/routers/calm.py`.

**Target state**:
```
adp/audit/writer.py → def next_audit_id(design) -> str  (public)
adp/intake/orchestrator.py → _next_audit_id = next_audit_id  (backward compat alias)
```

Files changed: `adp/audit/writer.py` (add), `adp/intake/orchestrator.py` (add alias), `adp/recommendation/orchestrator.py` (update import), `adp/api/routers/calm.py` (update import)

### Move C: LLMClient Relocation

**Current state**: `LLMClient` in `adp/intake/llm.py`.
Imported by: `adp/api/routers/intake.py`, `adp/api/routers/recommend.py`, `adp/api/routers/config.py`, `adp/recommendation/steps.py`.

**Target state**:
```
adp/llm/__init__.py   → LLMClient, _is_anthropic, _strip_code_fence
adp/llm/client.py     → (same content, __init__ re-exports)
adp/intake/llm.py     → from adp.llm.client import LLMClient as LLMClient  (re-export only)
```

Files changed: `adp/llm/__init__.py` (new), `adp/llm/client.py` (new, moved content), `adp/intake/llm.py` (stripped to re-export), `adp/api/routers/recommend.py` (import update), `adp/api/routers/config.py` (import update), `adp/recommendation/steps.py` (import update)

## File Changes Summary

| File | Action |
|------|--------|
| `src/adp/api/deps.py` | EDIT — add `get_kb_session()` async generator |
| `src/adp/api/routers/knowledge.py` | EDIT — remove local pool, use `Depends(get_kb_session)` |
| `src/adp/api/routers/calm.py` | EDIT — remove local wrapper, use `Depends(get_kb_session)` |
| `src/adp/audit/writer.py` | EDIT — add `next_audit_id(design) -> str` |
| `src/adp/intake/orchestrator.py` | EDIT — add backward-compat alias |
| `src/adp/recommendation/orchestrator.py` | EDIT — update import |
| `src/adp/api/routers/intake.py` | EDIT — update import (already imports _next_audit_id directly) |
| `src/adp/llm/__init__.py` | CREATE |
| `src/adp/llm/client.py` | CREATE (moved from intake/llm.py) |
| `src/adp/intake/llm.py` | EDIT — reduce to re-export |
| `src/adp/api/routers/config.py` | EDIT — update LLMClient import |
| `src/adp/recommendation/steps.py` | EDIT — update LLMClient import |

## Validation
After each move: `pytest tests/ --ignore=tests/integration -q --no-cov` must pass.
After all three: `ruff check src/adp/` must pass.
