"""Git repository connector — reads knowledge items from Markdown/YAML frontmatter."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Iterator

import frontmatter

from adp.knowledge.schema import (
    KnowledgeItem,
    KnowledgeRelationship,
    KnowledgeType,
    SchemaValidationError,
)

_REQUIRED_FIELDS = {"id", "version", "kind", "title"}
_RELATIONSHIP_FIELDS = {"satisfies", "extends", "supersedes", "implements"}


class GitConnector:
    """Read knowledge items and relationships from a Git-managed document repository."""

    def __init__(self, repo_url: str = "", local_path: str = "") -> None:
        self._repo_url = repo_url
        self._local_path = Path(local_path) if local_path else None

    def pull_or_clone(self) -> None:
        """Clone the repo if absent; pull if already cloned."""
        if not self._repo_url or not self._local_path:
            return

        import git

        if (self._local_path / ".git").exists():
            repo = git.Repo(self._local_path)
            repo.remotes.origin.pull()
        else:
            self._local_path.mkdir(parents=True, exist_ok=True)
            git.Repo.clone_from(self._repo_url, self._local_path)

    def _walk_files(self) -> Iterator[Path]:
        if self._local_path is None:
            return
        for ext in ("*.md", "*.yaml", "*.yml"):
            yield from self._local_path.rglob(ext)

    def read_items(self) -> Iterator[KnowledgeItem]:
        """Parse frontmatter from all Markdown/YAML files and yield KnowledgeItem records."""
        for path in self._walk_files():
            try:
                post = frontmatter.load(str(path))
                meta = dict(post.metadata)
                missing = _REQUIRED_FIELDS - meta.keys()
                if missing:
                    raise SchemaValidationError(
                        f"{path}: missing required frontmatter fields: {missing}"
                    )
                # Validate kind
                try:
                    kind = KnowledgeType(str(meta["kind"]))
                except ValueError as exc:
                    raise SchemaValidationError(
                        f"{path}: unknown kind {meta['kind']!r}"
                    ) from exc

                extra_meta = {k: v for k, v in meta.items()
                              if k not in _REQUIRED_FIELDS | _RELATIONSHIP_FIELDS}

                yield KnowledgeItem(
                    id=str(meta["id"]),
                    version=str(meta["version"]),
                    kind=kind,
                    title=str(meta["title"]),
                    full_text=post.content.strip() or str(meta.get("title", "")),
                    metadata=extra_meta,
                    source_ref=f"git:{self._repo_url}:{path.name}",
                )
            except SchemaValidationError:
                raise
            except Exception as exc:
                raise SchemaValidationError(f"{path}: {exc}") from exc

    def read_relationships(self) -> Iterator[KnowledgeRelationship]:
        """Parse relationship frontmatter fields and yield KnowledgeRelationship records."""
        for path in self._walk_files():
            try:
                post = frontmatter.load(str(path))
                meta = post.metadata
                item_id = str(meta.get("id", ""))
                if not item_id:
                    continue

                for rel_type in _RELATIONSHIP_FIELDS:
                    targets = meta.get(rel_type)
                    if not targets:
                        continue
                    if isinstance(targets, str):
                        targets = [targets]
                    if not isinstance(targets, list):
                        targets = [str(targets)]
                    target_list: list[str] = targets
                    for target_id in target_list:
                        yield KnowledgeRelationship(
                            id=f"REL-{uuid.uuid4().hex[:8]}",
                            source_id=item_id,
                            target_id=str(target_id),
                            relationship_type=rel_type,
                        )
            except Exception:
                continue
