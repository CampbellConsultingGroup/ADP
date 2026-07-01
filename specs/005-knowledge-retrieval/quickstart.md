# Quickstart: Indexing and Querying the Knowledge Base

**Branch**: `005-knowledge-retrieval` | **Date**: 2026-06-29  
**Prerequisites**: `ADP_DATABASE_URL`, `ADP_EMBEDDING_MODEL`, `ADP_EMBEDDING_DIM`, `ADP_GIT_REPO_URLS`, `ADP_GIT_LOCAL_CLONE_PATH` set; `pgvector` extension enabled in PostgreSQL; migrations run

---

## Running the Nightly Re-index

```bash
# Run manually (nightly cron calls this automatically)
ADP_EMBEDDING_MODEL=all-MiniLM-L6-v2 ADP_EMBEDDING_DIM=384 \
ADP_GIT_REPO_URLS=https://git.example.org/patterns,https://git.example.org/standards \
ADP_GIT_LOCAL_CLONE_PATH=/var/adp/knowledge-repos \
adp-reindex

# Output:
# ✓ Indexed 234 items from git:org/patterns
# ✓ Indexed 89 items from git:org/standards
# ✓ Indexed 41 prior solutions from ADP design store
# ⚠ 3 items failed schema validation (see log for details)
# ✓ Re-index complete: 364 active, 0 deactivated, 3 failed
```

---

## US1: Hybrid Knowledge Retrieval for an AI Step

```python
from adp.knowledge import KnowledgeRetrieval, RetrievalQuery, KnowledgeType
import os

retrieval = KnowledgeRetrieval(
    database_url=os.environ["ADP_DATABASE_URL"],
    embedding_model=os.environ["ADP_EMBEDDING_MODEL"],
)

query = RetrievalQuery(
    query_text="Stateless, horizontally scalable API gateway handling 10k RPS",
    kinds=[KnowledgeType.PATTERN, KnowledgeType.REFERENCE_ARCHITECTURE],
    limit=5,
)

result = await retrieval.hybrid_search(query)

for entry in result.items:
    print(f"{entry.item.title} [{entry.citation.item_id} @ {entry.citation.item_version}]")
    print(f"  Score: {entry.relevance_score:.3f} via {entry.match_reason}")

# Output:
# API Gateway Pattern [PAT-012 @ 1.3.0]
#   Score: 0.921 via vector+keyword
# Microservices Reference Architecture [REF-003 @ 2.1.0]
#   Score: 0.847 via vector
```

---

## US2: Version Distinguishability After Re-index

```python
# Before update: PAT-012 is at version 1.2.0
old_result = await retrieval.hybrid_search(RetrievalQuery(query_text="API gateway"))
assert old_result.items[0].citation.item_version == "1.2.0"

# Upstream Git repo updates PAT-012 frontmatter to version: "1.3.0" → run adp-reindex

# After re-index: new version returned
new_result = await retrieval.hybrid_search(RetrievalQuery(query_text="API gateway"))
assert new_result.items[0].citation.item_version == "1.3.0"

# Old citation still resolvable (citation completeness)
from adp.knowledge import CitationRef
old_citation = CitationRef(item_id="PAT-012", item_version="1.2.0")
old_item = await retrieval.resolve_citation(old_citation)
assert old_item is not None
assert old_item.version == "1.2.0"
```

---

## US3: Relationship Traversal

```python
# Which patterns satisfy architecture principle PR-001?
query = RetrievalQuery(
    query_text="",                         # not used for pure relationship queries
    traverse_from_id="PR-001",
    relationship_type="satisfies",
    limit=20,
)

result = await retrieval.relationship_query(query)
for entry in result.items:
    print(f"  {entry.item.title} [{entry.item.kind}] satisfies PR-001")

# Output:
#   API Gateway Pattern [pattern] satisfies PR-001
#   Service Mesh Reference Architecture [reference_architecture] satisfies PR-001
```

---

## US4: Citation Completeness Verification

```python
# Every retrieval result — regardless of mode — carries a citation
vector_result = await retrieval.vector_search(
    RetrievalQuery(query_text="event-driven integration")
)
keyword_result = await retrieval.keyword_search(
    RetrievalQuery(query_text="saga pattern")
)

for result in [vector_result, keyword_result]:
    for entry in result.items:
        assert entry.citation is not None
        assert entry.citation.item_id != ""
        assert entry.citation.item_version != ""
        # Verify the citation resolves
        item = await retrieval.resolve_citation(entry.citation)
        assert item is not None
```

---

## Knowledge Item File Format (Git Connector)

```markdown
---
id: PAT-012
version: "1.3.0"
kind: pattern
title: "API Gateway Pattern"
tags: [api, gateway, routing]
domain: integration
---

## Overview

The API Gateway pattern provides a single entry point for client requests...

## When to Use

Use this pattern when you need to decouple clients from backend services...
```

---

## What Gets Rejected During Indexing

| Scenario | Behavior |
|---|---|
| Item missing `id` or `version` in frontmatter | Rejected with `SchemaValidationError`; item not indexed |
| Item with unknown `kind` value | Rejected; item not indexed |
| Embedding model unavailable at index time | `IndexingError` raised; full re-index fails |
| Canonical Git repo unreachable | that connector's items are not updated for this run; other connectors continue; previously indexed items from the failed connector remain active; `IndexerResult` reports the connector failure |
| Citation with unknown `item_id` | `resolve_citation` returns `None` |
