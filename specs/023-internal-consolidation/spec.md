# Feature Specification: Internal Architecture Consolidation

**Feature Branch**: `023-internal-consolidation`
**Created**: 2026-07-03
**Status**: Draft
**Prerequisite for**: ADP-SPEC-024, ADP-SPEC-025

## Context

This is a purely internal refactor. There are zero user-visible changes. It exists because three independent architectural problems have accumulated across specs 001–022 that, if left unaddressed, will block the path to multi-user and production deployment:

1. **Three separate PostgreSQL connection pools** — `adp.api.deps` (design store), `adp.api.routers.knowledge` (KB reads/writes), and `adp.calm.importer` (CLI import) each create their own `create_async_engine` + `async_sessionmaker`. This means up to three pools open simultaneously against the same database, each consuming connections independently of the others. PostgreSQL's default `max_connections` is 100; pgBouncer or careful pool sizing is hard when the pool count itself is uncontrolled.

2. **`_next_audit_id` is a private intake function imported by three unrelated modules** — `adp.recommendation.orchestrator`, `adp.api.routers.intake`, and `adp.api.routers.calm` all import this utility from `adp.intake.orchestrator`. It is not an intake concept; it is a general audit sequencing utility. Its current home is an accident of implementation order.

3. **`LLMClient` lives in `adp.intake.llm`** — it was written for requirements extraction and named accordingly. It has since grown to serve the recommendation pipeline, the validation layer, and the config system via the `chat()` method added in ADP-SPEC-015. Keeping it in `intake` misleads contributors and creates a false import dependency between unrelated domains.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: all existing tests must pass unchanged; no new behaviour means no new test gap
- **ART-II** — Model is Source of Truth: the canonical data model is untouched

## Threat Model

**Assets at risk**: Internal code structure only. No data, no API surface, no user-visible behaviour changes.

**Residual risk**: Import path changes could break callers if the refactor is incomplete. Mitigated by running the full test suite after each move, and by providing backward-compatible re-exports during the transition.

## User Scenarios & Testing

This spec has no user stories because it has no user-visible changes. The sole acceptance criterion is:

**All 437 existing tests pass after the refactor. No new tests are required beyond updating import paths in existing tests.**

### Edge Cases

- External callers (scripts, CLI tools) that import from the old paths must continue to work via re-exports in the old modules.
- The CLI tool `adp-import-calm` calls `import_calm_data` which creates its own engine — after this spec it must use the shared factory when available (i.e. when called from the API context) and create its own engine only when called standalone from the CLI.

## Requirements

### Functional Requirements

**Pool Consolidation (FR-001 to FR-003)**

- **FR-001**: A single `get_kb_session()` async dependency generator MUST be added to `src/adp/api/deps.py`, using the same engine/session factory pattern already present for `get_design_store()`. All knowledge-base DB access from within the FastAPI application context MUST use this dependency.
- **FR-002**: `src/adp/api/routers/knowledge.py` MUST remove its local `_get_session_factory()`, `_engine`, `_session_factory` globals, and `_get_db_session()` function, replacing Depends usage with the shared `get_kb_session` from `adp.api.deps`.
- **FR-003**: `src/adp/api/routers/calm.py` MUST remove its local `_get_kb_session()` wrapper and use the shared dependency directly. The `adp.calm.importer` CLI path is exempt — it must create its own engine because it runs outside the FastAPI context.

**Audit Utility Move (FR-004 to FR-005)**

- **FR-004**: `_next_audit_id(design)` MUST be moved to `src/adp/audit/writer.py` as a public function `next_audit_id(design)` (no leading underscore — it is now an intentional public API within the `adp.audit` package).
- **FR-005**: All three existing import sites (`adp.intake.orchestrator`, `adp.recommendation.orchestrator`, `adp.api.routers.calm`) MUST be updated to import from `adp.audit.writer`. `adp.intake.orchestrator` MUST keep a backward-compatible alias `_next_audit_id = next_audit_id` for the transition period.

**LLMClient Move (FR-006 to FR-008)**

- **FR-006**: `LLMClient` (and all its methods: `extract`, `chat`, `_call_anthropic`, `_call_anthropic_chat`, `_call_openai_compatible`, `_call_openai_compatible_chat`, `_strip_code_fence`, `_is_anthropic`) MUST be moved to `src/adp/llm/__init__.py` (or `src/adp/llm/client.py`).
- **FR-007**: `src/adp/intake/llm.py` MUST be reduced to a backward-compatible re-export: `from adp.llm.client import LLMClient as LLMClient` so existing callers in the intake module continue to work without changes.
- **FR-008**: The recommendation pipeline's import of `LLMClient` (currently via `adp.intake.llm`) MUST be updated to import from `adp.llm.client` directly. The config router and any other callers MUST also be updated.

### Key Entities

No new entities. Existing entities move to more appropriate homes.

## Success Criteria

- **SC-001**: `pytest tests/ --ignore=tests/integration -q` exits 0 with the same count of passing tests as before this refactor (437 at time of writing).
- **SC-002**: `ruff check src/adp/` exits 0.
- **SC-003**: `mypy src/adp/` exits 0 (or with the same errors as before, if mypy was already non-clean).
- **SC-004**: A single `psql` query shows `SELECT count(*) FROM pg_stat_activity WHERE datname = 'adp'` does not exceed `pool_size * pool_count` during a representative load test — confirming pool reduction.
- **SC-005**: `grep -rn "from adp.intake.llm import LLMClient" src/adp/` returns only the re-export in `adp/intake/llm.py` itself — all direct uses are from `adp.llm.client`.

## Assumptions

- The refactor is completed in a single branch and merged atomically — no intermediate state where some callers use the old path and some use the new path.
- The Alembic migration in ADP-SPEC-024 depends on this spec being complete first.
- `adp.api.deps` already has the pattern for async dependencies; this spec extends it, not replaces it.
