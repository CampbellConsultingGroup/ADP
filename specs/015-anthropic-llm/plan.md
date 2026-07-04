# Implementation Plan: Anthropic LLM Integration with Model Selection

**Branch**: `015-anthropic-llm` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Status**: Retroactive — all implementation is complete; this plan documents the as-built decisions.

> **Process note**: This plan was written after implementation to correct an ART-I violation. The implementation detail below is accurate and matches the committed code.

## Summary

Three coordinated changes delivered together:

1. **Anthropic API support**: Updated `adp.intake.llm.LLMClient` to detect `anthropic.com` in the base URL and route to Anthropic's `/v1/messages` API (different auth header, request shape, and response format from OpenAI). Normalizes Anthropic responses to the OpenAI-compatible shape used by `LLMResponseParser`. Strips markdown code fences from Claude's JSON responses.

2. **Model selection UI**: Added `GET/PUT /api/v1/config/models|llm` endpoints with a module-level in-process config store. Added `ModelSelector` and `LLMSettings` React components. Added `model` override field to `IntakeSubmitRequest`. Intake screen now has a "⚙ LLM Settings" tab.

3. **Two bug fixes**:
   - **Vite proxy**: Added `server.proxy` to `vite.config.ts` so relative fetch calls from the browser reach the FastAPI backend.
   - **Audit entry uniqueness**: Changed `DesignStore.save()` to use `INSERT ... ON CONFLICT (id) DO NOTHING`; replaced `len()+1` audit ID generation with `max(existing)+1`.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x (frontend)
**New backend deps**: None — uses existing `httpx` for HTTP and `pydantic` for models
**New frontend deps**: None — uses existing TanStack Query
**Changed files**: `adp/intake/llm.py`, `adp/intake/orchestrator.py`, `adp/api/routers/config.py` (new), `adp/api/routers/intake.py`, `adp/api/app.py`, `adp/store/store.py`, `web/vite.config.ts`, `web/src/api/config.ts` (new), `web/src/intake/ModelSelector.tsx` (new), `web/src/intake/LLMSettings.tsx` (new), `web/src/intake/IntakeTextForm.tsx`, `web/src/intake/IntakePage.tsx`

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| QG-04 (ART-IV): Tests | ✅ 350 Python + 23 TS pass | Existing tests; no new test files added in this change |
| QG-06 (ART-V): SAST | ✅ ruff clean | |
| QG-08 (ART-V): No secret leakage | ✅ | `ADP_LLM_API_KEY` never in logs, spans, or responses |
| QG-10 (ART-VI): Structured logs | ✅ | LLM request metadata logged without content |
| QG-18 (ART-XIV): Schema drift | ✅ | `adp-generate --check` exits 0 |

**Missing**: No new test file was written covering the Anthropic-specific code paths (code-fence stripping, provider detection, config endpoints). This is a gap that should be addressed in a follow-up.

## Project Structure

```text
# New Python files
src/adp/api/routers/config.py    # GET /api/v1/config/models, GET/PUT /api/v1/config/llm

# Modified Python files
src/adp/intake/llm.py            # Anthropic provider detection + _call_anthropic() + fence stripping
src/adp/intake/orchestrator.py   # _next_audit_id() helper; uses max+1 not len+1
src/adp/api/routers/intake.py    # model override in IntakeSubmitRequest; _make_orchestrator(model=)
src/adp/api/app.py               # register config.router
src/adp/store/store.py           # ON CONFLICT DO NOTHING for audit entries

# New TypeScript files
web/src/api/config.ts            # useAvailableModels(), useLLMConfig(), useUpdateLLMConfig()
web/src/intake/ModelSelector.tsx # Inline model dropdown next to Extract button
web/src/intake/LLMSettings.tsx   # Full settings panel in ⚙ LLM Settings tab

# Modified TypeScript files
web/src/api/intake.ts            # model field added to IntakeSubmitRequest interface
web/src/intake/IntakeTextForm.tsx # ModelSelector added; ADP_LLM_API_KEY guidance
web/src/intake/IntakePage.tsx    # ⚙ LLM Settings tab added; improved no-LLM banner
web/vite.config.ts               # server.proxy to forward /api/, /health, /metrics to :8001
```

## Key Design Decisions

1. **Provider detection by URL**: `"anthropic.com" in base_url.lower()` — simple string check, no config flag needed.
2. **Response normalization**: Anthropic responses are wrapped into OpenAI-compatible shape (`choices[0].message.content`) so `LLMResponseParser` is unchanged.
3. **Code fence stripping**: `stripped.startswith("```")` → strip first line and last line. Handles `\`\`\`json` and plain `\`\`\`` variants.
4. **In-process config store**: `_llm_config: dict[str, str]` with environment variable defaults. Resets on restart. Persistent storage is v2.
5. **`ON CONFLICT DO NOTHING`**: Uses `sqlalchemy.dialects.postgresql.insert` (pg-specific). The full `audit_log` is always stored in the `design_versions.content` JSON for queryability; the `audit_entries` table rows are de-duplicated on insert.
6. **`_next_audit_id(design)`**: Reads `design.audit_log` (loaded from DB via `store.get()`), finds max existing `AUD-NNN`, returns `AUD-{max+1:03d}`. Consistent with `adp.audit.writer.write_audit_record()`.
