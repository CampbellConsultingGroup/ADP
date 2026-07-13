# Tasks: Knowledge Base & Retrieval

**Input**: Design documents from `/specs/005-knowledge-retrieval/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies, create directory skeleton, configure adp-reindex CLI entry point

- [x] T001 Add knowledge dependencies to `pyproject.toml` using minimum-version constraints: `pgvector>=0.3`, `sentence-transformers>=2.7`, `gitpython>=3.1`, `python-frontmatter>=1.1`; add dev dep `pytest-asyncio>=0.23` (already present); run `pip install -e ".[dev]"` and verify; exact versions pinned in T042
- [x] T002 [P] Create directory structure: `src/adp/knowledge/`, `src/adp/knowledge/connectors/`, `tests/knowledge/`
- [x] T003 [P] Create `src/adp/knowledge/__init__.py` (placeholder), `src/adp/knowledge/connectors/__init__.py` (empty), `tests/knowledge/__init__.py` (empty)
- [x] T004 Add `adp-reindex = "adp.knowledge.indexer:main"` to `[project.scripts]` in `pyproject.toml`
- [x] T005 Verify: `python3 -c "import pgvector, sentence_transformers, git, frontmatter; print('ok')"` and `adp-reindex --help` resolve after reinstall

**Checkpoint**: `pytest tests/unit/ tests/contract/ tests/authz/ -q --no-cov` still passes all existing tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic schema types, error hierarchy, ORM tables, Alembic migration, embedding provider, and test fixtures — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create all Pydantic models and error hierarchy in `src/adp/knowledge/schema.py`: `KnowledgeType(StrEnum)` with 5 values from data-model.md; `KnowledgeItem` (all fields from data-model.md; embedding as `list[float]`); `KnowledgeRelationship`; `CitationRef`; `RetrievalQuery` with fields from data-model.md plus `correlation_id: str | None = None` (optional trace ID from the calling AI orchestration step; threaded into structured logs per ART-VI); `RetrievalResult`; `RetrievalResultEntry`; error classes `KnowledgeError`, `RetrievalError`, `IndexingError`, `SchemaValidationError`, `CitationResolutionError` — all as `model_config = ConfigDict(extra="forbid")` on Pydantic models
- [x] T007 Create `EmbeddingProvider` class in `src/adp/knowledge/embedder.py`: `__init__(self, model_name: str)` loads the `sentence-transformers` model; `embed(text: str) -> list[float]` returns the embedding; `embed_batch(texts: list[str]) -> list[list[float]]` for efficient batch embedding; `dimension: int` property returning the model's embedding size; model is NEVER called with external API keys — self-hosted only
- [x] T008 Define SQLAlchemy `Table` objects for `knowledge_items` and `knowledge_relationships` in `src/adp/knowledge/index.py`: all columns from data-model.md; use `pgvector.sqlalchemy.Vector` for the embedding column; `full_text_search` as a server-side generated tsvector column (no client-side population)
- [x] T009 Create Alembic migration `src/adp/store/migrations/versions/002_knowledge_schema.py`: `CREATE EXTENSION IF NOT EXISTS vector`; CREATE TABLE `knowledge_items` with all columns; CREATE TABLE `knowledge_relationships`; CREATE HNSW INDEX `knowledge_items_embedding_hnsw` on `embedding` using `vector_cosine_ops`; CREATE GIN INDEX `knowledge_items_fts_gin` on `full_text_search`; CREATE B-tree INDEX on `kind`; CREATE partial INDEX on `active = TRUE`; Note: create `full_text_search` using `op.execute("ALTER TABLE knowledge_items ADD COLUMN full_text_search TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', full_text)) STORED")` — SQLAlchemy's `op.add_column` does not support PostgreSQL generated columns; verify `alembic upgrade head` completes successfully in a test environment before merging
- [x] T010 Create `KnowledgeIndex` class in `src/adp/knowledge/index.py` with async methods: `upsert_item(item: KnowledgeItem, embedding: list[float], session: AsyncSession) -> None`; `get_item(item_id: str, version: str | None, session: AsyncSession, *, include_inactive: bool = False) -> KnowledgeItem | None` — when `include_inactive=True` returns items with `active=False` (required by `resolve_citation` for FR-004); `mark_inactive(item_ids: list[str], session: AsyncSession) -> int`; `upsert_relationship(rel: KnowledgeRelationship, session: AsyncSession) -> None`; `get_all_active_ids(session: AsyncSession) -> set[str]` — returns all `id` values where `active=TRUE`; called by `Indexer` at start of each run to build the deactivation candidate set
- [x] T011 Create `tests/knowledge/conftest.py`: `embedding_provider` fixture returning a mock `EmbeddingProvider` (dimension 4, fixed-value embeddings for reproducibility); `mock_index` fixture returning a `KnowledgeIndex` with an `AsyncMock` session; function-scoped `sample_item(kind)` factory for valid `KnowledgeItem` test fixtures covering all 5 knowledge types

**Checkpoint**: `python3 -c "from adp.knowledge.schema import KnowledgeItem, CitationRef, RetrievalQuery; from adp.knowledge.embedder import EmbeddingProvider; print('ok')"` succeeds

---

## Phase 3: User Story 1 — Retrieve Grounded Knowledge for an AI Step (Priority: P1) 🎯 MVP

**Goal**: `hybrid_search()`, `vector_search()`, and `keyword_search()` each return a `RetrievalResult` in which every `RetrievalResultEntry` carries a non-null `CitationRef`; the same query submitted twice returns identical citations.

**Independent Test**: Pre-load a mock index with 5 known items; call `hybrid_search` with a query; assert all returned entries have non-empty `citation.item_id` and `citation.item_version`; call twice, assert citations are identical. No connector or embedder needed.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T012 [P] [US1] Write failing `test_vector_search_returns_results_with_citations()` and `test_keyword_search_returns_results_with_citations()` in `tests/knowledge/test_retrieval.py`: inject a `KnowledgeRetrieval` instance with mock index returning 3 pre-built `RetrievalResultEntry` objects; assert each entry has `citation is not None`, `citation.item_id != ""`, and `citation.item_version != ""`
- [x] T013 [P] [US1] Write failing `test_hybrid_search_combines_results_and_deduplicates()` in `tests/knowledge/test_retrieval.py`: mock index returning different ranked results from vector and keyword paths; call `hybrid_search`; assert the RRF-combined result has no duplicate `item_id` entries; assert entries are ordered by descending `relevance_score`
- [x] T014 [P] [US1] Write failing `test_citations_are_stable_across_identical_queries()` in `tests/knowledge/test_retrieval.py`: call `hybrid_search` twice with the same query and same mock index; assert `result1.items[i].citation == result2.items[i].citation` for all `i`

### Implementation for User Story 1

- [x] T015 [US1] Create `KnowledgeRetrieval` class in `src/adp/knowledge/retrieval.py`: `__init__(self, database_url: str, embedding_model: str, embedding_dim: int)` creates async engine + `EmbeddingProvider`; implement `vector_search(query: RetrievalQuery) -> RetrievalResult` using pgvector `<=>` (cosine distance) operator ordered by ascending distance; map results to `RetrievalResultEntry` with `match_reason="vector"`
- [x] T016 [US1] Add `keyword_search(query: RetrievalQuery) -> RetrievalResult` to `KnowledgeRetrieval` in `src/adp/knowledge/retrieval.py`: use `to_tsquery` + `ts_rank` on `knowledge_items.full_text_search`; map results to `RetrievalResultEntry` with `match_reason="keyword"`
- [x] T017 [US1] Add `hybrid_search(query: RetrievalQuery) -> RetrievalResult` to `KnowledgeRetrieval` in `src/adp/knowledge/retrieval.py`: call `vector_search` and `keyword_search` independently; merge using Reciprocal Rank Fusion (`score = Σ 1/(k + rank)` with `k=60`); deduplicate by `item_id` keeping highest combined score; emit structured log per ART-VI with `query_id`, `result_count`, `latency_ms`, and `correlation_id` from `query.correlation_id` (when present, so the calling AI step's trace is preserved through the retrieval hop)
- [x] T018 [US1] Add `resolve_citation(citation: CitationRef) -> KnowledgeItem | None` to `KnowledgeRetrieval` in `src/adp/knowledge/retrieval.py`: MUST call `KnowledgeIndex.get_item(item_id, version, include_inactive=True)` so that old versions of items marked `active=False` during re-index remain resolvable — required by FR-004 and US2 acceptance scenario 2; return `None` if not found (not an exception); include `embedding=None` in returned item (embeddings not returned to callers)
- [x] T019 [US1] Update `src/adp/knowledge/__init__.py` to export `KnowledgeRetrieval`, `KnowledgeItem`, `CitationRef`, `RetrievalQuery`, `RetrievalResult`, `KnowledgeType`, all error classes; verify T012–T014 all pass

**Checkpoint**: `pytest tests/knowledge/test_retrieval.py -q --no-cov` green; citations present in all results; SC-001 (95% query accuracy) demonstrable against the mock index

---

## Phase 4: User Story 2 — Keep the Index Current with Upstream Changes (Priority: P1)

**Goal**: `GitConnector` parses Markdown/YAML frontmatter into `KnowledgeItem` records; `DesignStoreConnector` converts approved designs into `prior_solution` items; `Indexer` upserts updated versions and marks removed items inactive; old versions remain resolvable.

**Independent Test**: Mock Git repo with one item at v1.0; update to v1.1 and re-index; assert the index returns v1.1 for queries; assert `resolve_citation(CitationRef("PAT-001", "1.0.0"))` returns the v1.0 item.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T020 [P] [US2] Write failing `test_git_connector_parses_frontmatter()` and `test_git_connector_id_from_frontmatter()` in `tests/knowledge/test_connectors.py`: create a `tmp_path` with a Markdown file containing valid frontmatter (`id: PAT-001`, `version: "1.0.0"`, `kind: pattern`, `title: ...`); call `GitConnector(repo_path=tmp_path).read_items()`; assert one `KnowledgeItem` with `id="PAT-001"`, `version="1.0.0"`, `kind=KnowledgeType.PATTERN`
- [x] T021 [P] [US2] Write failing `test_git_connector_rejects_missing_id()` in `tests/knowledge/test_connectors.py`: Markdown file without `id:` in frontmatter; assert `SchemaValidationError` is raised and no `KnowledgeItem` is produced
- [x] T022 [P] [US2] Write failing `test_design_store_connector_creates_prior_solution_items()` in `tests/knowledge/test_connectors.py`: mock `DesignStore` returning one `ArchitectureDescription` with id `DESIGN-001` and `current_version=3`; call connector; assert one `KnowledgeItem` with `kind=KnowledgeType.PRIOR_SOLUTION`, `id="DESIGN-001"`, `version="3"`
- [x] T023 [P] [US2] Write failing `test_indexer_upserts_updated_item()` in `tests/knowledge/test_indexer.py` using `AsyncMock` for `KnowledgeIndex` (no Docker needed): call `Indexer.run()` with a connector yielding a v1.0 item; call again with the connector yielding v1.1 of the same item; assert `mock_index.upsert_item` was called with `version="1.1.0"` on the second run; the version-distinguishability test requiring a real DB remains in `test_integration.py` as part of T027

### Implementation for User Story 2

- [x] T024 [US2] Create `GitConnector` in `src/adp/knowledge/connectors/git.py`: `__init__(self, repo_url: str, local_path: str)`; `pull_or_clone() -> None` (uses `gitpython` to clone if absent, pull if present); `read_items() -> Iterator[KnowledgeItem]` walks all `*.md` and `*.yaml` files, parses frontmatter via `python-frontmatter`, validates required fields (`id`, `version`, `kind`, `title`), yields `KnowledgeItem`; raises `SchemaValidationError` on missing required frontmatter fields (item skipped, not fatal to whole run)
- [x] T025 [US2] Create `DesignStoreConnector` in `src/adp/knowledge/connectors/design_store.py`: `__init__(self, store: DesignStore)`; `read_items() -> AsyncIterator[KnowledgeItem]` reads all designs with `current_version > 0`, converts each to `KnowledgeItem` with `kind=KnowledgeType.PRIOR_SOLUTION`, `id=description.id`, `version=str(record.current_version)`, `full_text = description.title + " " + " ".join(r.description for r in description.requirements)`
- [x] T026 [US2] Create `Indexer` class and `main()` CLI entry point in `src/adp/knowledge/indexer.py`: `Indexer.__init__(database_url, embedding_model, embedding_dim, git_repo_urls, git_local_path, design_store)`; `async run() -> IndexerResult`: at the start of each run call `KnowledgeIndex.get_all_active_ids()` to capture the previously active id set; maintain `seen_ids: set[str]` during the run; for each connector, call `pull_or_clone()` then iterate items in batches — connector-level failures (e.g., Git repo unreachable) fail that connector only and do not block other connectors, with the failure recorded in `IndexerResult.connector_errors: dict[str, str]`; collect all `item.full_text` strings per batch, call `EmbeddingProvider.embed_batch(texts)` once per batch (not per-item), zip embeddings with items, call `KnowledgeIndex.upsert_item()` for each; after all connectors complete, call `mark_inactive(prev_active_ids - seen_ids)` to deactivate items no longer in any canonical source; individual item-level schema failures are tracked as `failed: int` and do not abort the connector run; return `IndexerResult(indexed, updated, deactivated, failed, connector_errors)`; `main()` reads env vars, instantiates `Indexer`, calls `asyncio.run(indexer.run())`, prints summary
- [x] T027 [US2] Verify `test_git_connector_parses_frontmatter`, `test_git_connector_rejects_missing_id`, `test_design_store_connector_creates_prior_solution_items`, `test_indexer_upserts_updated_item` all pass

**Checkpoint**: `pytest tests/knowledge/test_connectors.py tests/knowledge/test_integration.py -q --no-cov` green; SC-002 (updated version returned; old version resolvable) verifiable

---

## Phase 5: User Story 3 — Traverse Knowledge Relationships (Priority: P2)

**Goal**: `relationship_query()` returns items explicitly linked by a typed relationship; text matching is NOT used; items without the relationship are absent from results.

**Independent Test**: Index items P1, P2, P3 with P1 and P2 having `satisfies` relationship to PR-001; call `relationship_query(traverse_from_id="PR-001", relationship_type="satisfies")`; assert P1 and P2 are returned; assert P3 is absent.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T028 [P] [US3] Write failing `test_relationship_query_returns_only_related_items()` in `tests/knowledge/test_retrieval.py`: inject mock index with 3 items and 2 `knowledge_relationships` rows linking P1 and P2 to PR-001 via `satisfies`; call `relationship_query(RetrievalQuery(query_text="", traverse_from_id="PR-001", relationship_type="satisfies"))`; assert P1 and P2 are in results and P3 is not; assert each result entry has `match_reason == "relationship"`
- [x] T029 [P] [US3] Write failing `test_relationship_query_returns_empty_when_no_matches()` and `test_relationship_query_result_includes_relationship_type()` in `tests/knowledge/test_retrieval.py`
- [x] T030 [P] [US3] Write failing `test_git_connector_parses_relationship_frontmatter()` in `tests/knowledge/test_connectors.py`: Markdown file with `satisfies: [PR-001, PR-002]` in frontmatter; assert `GitConnector.read_relationships()` yields two `KnowledgeRelationship` records with `source_id="PAT-001"`, `relationship_type="satisfies"`, and target ids `"PR-001"`, `"PR-002"`

### Implementation for User Story 3

- [x] T031 [US3] Add `relationship_query(query: RetrievalQuery) -> RetrievalResult` to `KnowledgeRetrieval` in `src/adp/knowledge/retrieval.py`: SQL JOIN `knowledge_relationships` → `knowledge_items` WHERE `source_id = query.traverse_from_id` AND `relationship_type = query.relationship_type` (or target direction); map to `RetrievalResultEntry` with `match_reason = f"relationship:{query.relationship_type}"`
- [x] T032 [US3] Extend `GitConnector` in `src/adp/knowledge/connectors/git.py`: add `read_relationships() -> Iterator[KnowledgeRelationship]` that reads `satisfies`, `extends`, `supersedes`, `implements` frontmatter fields (each is a list of target ids) and yields `KnowledgeRelationship` objects with `source_id` from the item's `id` field
- [x] T033 [US3] Extend `Indexer.run()` in `src/adp/knowledge/indexer.py` to call `GitConnector.read_relationships()` after reading items and call `KnowledgeIndex.upsert_relationship()` for each; verify T028–T030 pass

**Checkpoint**: `pytest tests/knowledge/test_retrieval.py tests/knowledge/test_connectors.py -q --no-cov` green; SC-003 (relationship query precision/recall) demonstrable

---

## Phase 6: User Story 4 — Citation-Ready References on Every Result (Priority: P2)

**Goal**: 100% of entries from all three retrieval modes (`vector_search`, `keyword_search`, `relationship_query`) carry a non-null `CitationRef`; `resolve_citation()` returns the correct item for known citations and `None` for unknown ones.

**Independent Test**: Call all three retrieval methods; for each result entry assert `entry.citation is not None`; call `resolve_citation(entry.citation)` and assert the returned item has the same `id` and `version`.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T034 [P] [US4] Write failing `test_all_retrieval_modes_return_citations()` in `tests/knowledge/test_retrieval.py`: parametrize over `vector_search`, `keyword_search`, `relationship_query`; for each mode assert every `RetrievalResultEntry` has `citation.item_id != ""` and `citation.item_version != ""`  (SC-004)
- [x] T035 [P] [US4] Write failing `test_resolve_citation_returns_correct_item()` and `test_resolve_citation_returns_none_for_unknown()` in `tests/knowledge/test_retrieval.py`: for a known citation assert item is returned with matching id+version; for `CitationRef(item_id="UNKNOWN", item_version="1.0.0")` assert `None` is returned (not an exception)
- [x] T035b [P] [US4] Write failing `test_resolve_citation_returns_inactive_item()` in `tests/knowledge/test_retrieval.py`: inject mock index that returns an item with `active=False` for `CitationRef("PAT-001", "1.0.0")`; call `resolve_citation(CitationRef("PAT-001", "1.0.0"))`; assert the item is returned (not `None`) — confirms FR-004 and US2 acceptance scenario 2 hold after a version update marks the old version inactive

### Implementation for User Story 4

- [x] T036 [US4] Add a private `_build_result_entry(row, match_reason) -> RetrievalResultEntry` helper in `src/adp/knowledge/retrieval.py`: always constructs `CitationRef(item_id=row.id, item_version=row.version)`; assert citation fields are non-empty before returning — raise `RetrievalError` if either is empty (defensive guard ensuring FR-005 / QG-12 invariant holds for all callers)
- [x] T037 [US4] Refactor `vector_search`, `keyword_search`, and `relationship_query` in `src/adp/knowledge/retrieval.py` to use `_build_result_entry` for all result construction; verify T034–T035 pass

**Checkpoint**: `pytest tests/knowledge/ -q --no-cov` green; SC-004 (100% citation coverage) verifiable by parametrized test; QG-12 enforced by the defensive guard in `_build_result_entry`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, performance test, dependency pinning

- [x] T038 [P] Run `pytest tests/knowledge/ --cov=adp.knowledge --cov-report=term-missing` and verify coverage ≥ 85% across `src/adp/knowledge/`; add targeted tests for uncovered branches (e.g., empty query results, connector error propagation) (QG-04)
- [x] T039 [P] Run `ruff check src/adp/knowledge/ tests/knowledge/` and `mypy src/adp/knowledge/`; fix all issues (QG-06); also verify that `ADP_EMBEDDING_DIM` and the HNSW index `m` and `ef_construction` parameters in T009 are environment-variable-configurable, not hardcoded — confirming NFR-002's "scale beyond 10k via configuration, not code changes" requirement
- [x] T040 [P] Run `bandit -r src/adp/knowledge/ -ll` and verify no HIGH-severity findings; confirm no org content logged by grepping for `full_text` in logging calls across `src/adp/knowledge/` (QG-06, QG-08)
- [x] T041 [P] Write `test_retrieval_latency_under_500ms()` in `tests/knowledge/test_integration.py` (`@pytest.mark.slow`): pre-seed a mock index with 10,000 synthetic items (with random embeddings); time `vector_search` and `keyword_search`; assert p95 latency < 500ms over 20 repeated calls (SC-005, NFR-001) — requires testcontainers PostgreSQL with pgvector
- [x] T042 Pin new dependency versions in `pyproject.toml`: run `pip show pgvector sentence-transformers gitpython python-frontmatter` to get installed versions; replace minimum-version constraints with exact pinned specifiers (QG-18)
- [x] T043 [P] Run `adp-generate --check` to confirm ADP-SPEC-001 schema is unaffected; run full test suite `pytest tests/ -q --no-cov` confirming all prior tests still pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; Pydantic schema + ORM tables + embedder must exist before any query or index code
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; retrieval interface can be tested with a mock index
- **US2 (Phase 4)**: Depends on Foundational (Indexer needs KnowledgeIndex + EmbeddingProvider); independent of US1's query implementation
- **US3 (Phase 5)**: Depends on US2 (relationships are indexed by the Indexer) + US1's `KnowledgeRetrieval` class
- **US4 (Phase 6)**: Depends on US1 (all three retrieval methods must exist to test citation completeness)
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on connectors or indexer
- **US2 (P1)**: Can start after Phase 2 in parallel with US1 — connectors + indexer are independent of retrieval
- **US3 (P2)**: Depends on US2 (relationship indexing in Indexer) and US1 (`KnowledgeRetrieval` class exists)
- **US4 (P2)**: Depends on US1 (all retrieval methods must exist); independent of US2/US3

### Parallel Opportunities

- T002, T003 (Setup): parallel — different directories
- T006, T007 (Foundational models): parallel — different files
- T008, T009, T010, T011 (Foundational DB + embedder + fixtures): parallel — different files
- T012, T013, T014 (US1 tests): parallel — independent test functions
- T020, T021, T022, T023 (US2 tests): parallel — independent test functions
- T028, T029, T030 (US3 tests): parallel — independent test functions + different files
- T034, T035 (US4 tests): parallel — independent test functions
- T038, T039, T040, T041, T043 (Polish): parallel — independent tools

---

## Parallel Example: User Story 2 (Connectors + Indexer)

```bash
# US2 tests all parallel (independent concerns):
Task T020: test_git_connector_parses_frontmatter + test_git_connector_id_from_frontmatter
Task T021: test_git_connector_rejects_missing_id
Task T022: test_design_store_connector_creates_prior_solution_items
Task T023: test_indexer_upserts_updated_item

# Implementations can also be parallelized (different files):
Task T024: src/adp/knowledge/connectors/git.py
Task T025: src/adp/knowledge/connectors/design_store.py
# Then sequentially:
T026 (Indexer in indexer.py, depends on T024 + T025)
T027 (verify)
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1: Setup (T001–T005)
2. Phase 2: Foundational (T006–T011)
3. Write US1 tests T012–T014 — verify they fail
4. Phase 3: US1 implementation (T015–T019)
5. **STOP and VALIDATE**: `pytest tests/knowledge/test_retrieval.py -q` green
6. AI steps can now call `hybrid_search()` and receive citable results

### Incremental Delivery

1. Phase 1 + 2 → Schema types + ORM + embedder available for import
2. Phase 3 (US1) → Grounded retrieval working with mock data (MVP)
3. Phase 4 (US2) → Nightly re-index operational; real knowledge indexed
4. Phase 5 (US3) → Relationship traversal enables structured governance queries
5. Phase 6 (US4) → Citation completeness formally verified across all modes
6. Phase 7 → All quality gates green; QG-12 gate enforced

---

## Notes

- [P] tasks = different files or independent test functions; no file conflict
- Tests MUST fail before implementation; commit failing tests first (ART-IV)
- The `embedding` field MUST NOT be included in `RetrievalResult` responses to callers — it is an internal index field only; strip it in `_build_result_entry`
- `full_text` content MUST NOT appear in any log entry (organizational IP); only metadata and IDs are logged
- The `ADP_EMBEDDING_MODEL` env var must be read at runtime — never hardcoded in source
- Constitution gates: QG-01, QG-03, QG-04, QG-05, QG-06, QG-07, QG-08, QG-12, QG-18
- QG-12 is enforced at the code level by `_build_result_entry`'s citation completeness assertion
