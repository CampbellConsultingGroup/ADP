# Research: Agent Registry Core (933)

All findings below come from direct reads of the codebase on 2026-11-13. Line numbers are from that date.

## D1 — Package placement: new sibling package `adp.agentic`

- **Decision**: create a new package `src/adp/agentic/` (`models.py`, `store.py`, `router.py`) with its own `_metadata`, engine, session factory and router, prefix `/api/v1/agentic`.
- **Rationale**: `adp.compliance` (921) is the precedent for a cross-cutting domain that sits beside `adp.application` rather than inside it. `adp.application`'s `store.py` (81 KB) and `router.py` (43 KB) are already past the size at which `adp.strategy` was split.
- **Alternatives**:
  - **`adp.application.agents` sub-module:** rejected, because it grows already-oversized files.
  - **`adp.agents`:** rejected, because that name is taken by the unrelated Agent Review provenance/grounding toolkit (039/040).

## D2 — Cross-package references through narrow mirror tables

- **Decision**: `adp.agentic.store` declares a narrow `applications` mirror with `id`, `name` and `application_type`. It never imports `adp.application`, following `compliance/store.py:175-195`. Foreign keys exist only in the migration.
- **Membership check**: membership writes check that the target application exists (404) and that `application_type == "agentic"` (422, `NotAgenticSolutionError`).

## D3 — Guard against reclassifying an application away from "agentic" (Clarification Q1)

- **Decision**: `adp.application.store.update_application` adds a guard right after `existing` is loaded (store.py:540). It fires when all of these hold:
  - `application_type` is in `model_fields_set`;
  - `existing.application_type == "agentic"`;
  - the new value is not "agentic";
  - any `solution_agents` row has `solution_app_id == app_id`.

  When it fires, it raises a new `AgenticSolutionHasAgentsError`, which the router maps to **409**.
- **How the guard queries**: through a narrow `solution_agents` mirror (`solution_app_id`, `agent_id`) on `astore._metadata`. This is the same idiom as `astore`'s existing `regulatory_frameworks` mirror (932).
- **Delete parity**: `delete_application` also deletes that app's `solution_agents` rows explicitly, so SQLite fixtures (no FK enforcement) behave like Postgres, where the migration's CASCADE is the safety net. This follows the value-chains precedent (ADP-nag).
- **Known fixture collision (932 gotcha)**: any fixture that runs both `astore._metadata.create_all` and `agstore._metadata.create_all` on one connection must create `astore` first, excluding `solution_agents` (`tables=[t for t in astore._metadata.sorted_tables if t.name != "solution_agents"]`), and then `agstore`. The full table definition must win, and agstore's narrow `applications` mirror must not shadow the real table.
- **Alternatives**:
  - **Raw `sa.text` query:** rejected, because it breaks on app-only SQLite fixtures that never create the table.
  - **Hook registry:** rejected as over-engineering.

## D4 — Changing the application-type value set

- **Decision**: migration 043 drops `ck_app_application_type` (created in 039) and re-creates it with `'agentic'` added. The downgrade first sets `application_type = NULL` where it is `'agentic'`, then restores the four-value CHECK. This is the same drop/re-create pattern as migrations 013, 020 and 026.
- **Python**: the `ApplicationType` Literal is `models.py:35`.
- **Frontend**: four hardcoded lists need updating:
  - `web/src/api/application.ts:16`
  - `web/src/application/ApplicationForm.tsx:18-23`
  - `web/src/application/ApplicationDetail.tsx:33-38`
  - `web/src/portfolio/groupApplications.ts:131-137`

  The bucket order becomes Custom → COTS → SaaS → Legacy → Agentic. `BucketCard.tsx` needs no change.

## D5 — Authorization

- **Decision**: add one prefix rule, `("/api/v1/agentic/", ActionType.WRITE_APPLICATION)`, to `enforcement.py:_PREFIX_ROUTE_ACTIONS`. There is no new ActionType and no `PERMISSIONS_VERSION` bump. Reads are ungated, like `GET /applications`.
- **Cost (Clarification Q2)**:
  - **Reads:** GET handlers take `user: AuthenticatedUser = Depends(get_current_user)` and evaluate `is_permitted(user.role, ActionType.READ_APPLICATION_COST)` inline. This follows the `api/routers/portfolio.py:141` precedent. When the user is not permitted, `est_cost_per_run` and `runs_per_month` are returned as `null` with `cost_visible: false`, so the UI can show "restricted" instead of "not estimated".
  - **Writes:** a create or PATCH that *sets* either cost field requires `WRITE_APPLICATION_COST`, checked inline in the handler; otherwise the response is 403. This mirrors how application cost writes are gated (`enforcement.py:93`). Omitting the fields is always allowed.
- **Alternatives**:
  - **Route-level gate:** rejected, because it would hide whole agents from users who lack the cost permission.
  - **New `WRITE_AGENT` action:** rejected, because the spec reuses application-write.

## D6 — Audit (FR-016)

- **Decision**: structured `logger.info("agentic.<entity>.<verb> id=%s ... actor=%s", ...)` on every mutation, with no `audit_entries` write.
- **Rationale**: `audit_entries` is coupled to `design_id`/`design_version`. `adp.application`, `adp.business`, `adp.compliance` and `adp.strategy` all satisfy ART-IX with actor-attributed structured logs (`strategy/router.py:31-36`, `compliance/router.py:23-27`). Following the established precedent is consistent; a parallel audit mechanism would not be.

## D7 — Search

- **Decision**: add `ENTITY_AGENT = "agent"` to `src/adp/search/index.py` and re-export it from `search/__init__.py`, in both the import and `__all__`.
- **Indexed text**: `build_text(name, description, model_provider, model_id, framework)`, so a search for "langgraph" or "claude" finds agents.
- **When to index**: index on create and update, and unindex on delete. Both are best-effort (`index_entity` never raises).
- **Backfill**: add a counts key and loop to `backfill.reindex_all()`.

## D8 — Export

- **Decision**: new module `src/adp/export/agentic.py`, modelled on `export/strategy.py`, which has its own package and its own session factory. It writes `agentic/agents/<id>.json` containing the agent's fields plus `solutions: [{app_id, role, position}]`, and cleans up orphan files.
- **Wiring**: `start_agentic_export()` / `stop_agentic_export()` in the `app.py` lifespan, alongside the three existing export tasks, using the same `ADP_BUSINESS_ARCH_EXPORT_ROOT` / interval env vars.
- **Cost estimates**: exported unredacted, matching `application_arch.py`'s documented treatment of application cost (docstring :6-8). FR-015 asks for "same treatment as application cost".

## D9 — Seed (FR-017)

- **Decision**: in `scripts/seed_retail.py`:
  - add `agents` and `solution_agents` to `WIPE_TABLES`;
  - seed one application, "Architecture Design Platform (ADP)", with `application_type="agentic"`;
  - seed five agents, joined in this order:

  | Agent | Role | Framework | Autonomy |
  |---|---|---|---|
  | Chat Assistant | orchestrator | Anthropic SDK, tool use | L1 |
  | Intake Extractor | worker | – | L0, approval always (confirm gate) |
  | Recommendation Engine | worker | LangGraph | L0 |
  | LLM-as-Judge Critics | reviewer | – | L2 |
  | Agent Review | worker | – | L0 |

  The seed goes through `agstore` functions, never raw SQL. The `prompt_ref` values point at the 042 prompt-management keys.

## D10 — Field types and validation

- **Closed sets** (Pydantic `Literal` plus DB `CHECK`):
  - `autonomy_level`: `SmallInteger`, 0–4
  - `human_approval`: `none | on_write | on_irreversible | always`
  - `lifecycle_status`: `planned | active | sunset | retired`, default `active`
  - `data_classification_max`: `public | internal | confidential | restricted`, the same vocabulary as `application_risk`, redefined locally to keep `adp.agentic` import-free
  - `role`: `orchestrator | worker | reviewer | router`
- **`a2a_card_url`**: `http`/`https` only, via a field validator mirroring `compliance.models._validate_source_url`. The frontend renders it as a link only via a shared `isHttpUrl()`, extracted from `compliance/FrameworkDetail.tsx:30-37` to `web/src/ui/url.ts`.
- **`prompt_ref`**: at most 200 characters. **`external_registry_ref`**: at most 255.
- **Cost and volume**: `est_cost_per_run` is `Numeric(12,4)` ≥ 0; `runs_per_month` is `Integer` ≥ 0. Both are nullable, and null means "not estimated".
- **Membership ordering**: positions are normalised to 0..n-1 per solution on every add, remove and reorder. A reorder with a mismatched id list returns 422. Both follow the value-chain precedent (ADP-nag).

## D11 — Schema generation

`adp-generate` emits JSON Schema for the canonical `adp.models` only. Domain packages such as application and compliance are not part of the generated set, so `adp-generate --check` is unaffected. No change is needed.
