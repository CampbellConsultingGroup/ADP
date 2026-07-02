"""Document generator — converts ArchitectureDescription → Markdown with typed frontmatter.

ART-II: all content is derived from the canonical model; nothing is hand-authored.
ART-XIV: output is byte-identical for the same model version (no timestamps in body;
generated_at in frontmatter uses seconds precision only for stability).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import yaml

from adp.docs.models import DocumentMetadata, GeneratedDocument
from adp.models import ArchitectureDescription

logger = logging.getLogger(__name__)

_GENERATOR = "ADP-SPEC-011"


class DocumentGenerator:
    """Generates a Markdown stakeholder document from the canonical model."""

    def generate(self, design: ArchitectureDescription) -> GeneratedDocument:
        """Produce a Markdown document with YAML frontmatter from the design.

        Raises ValueError if design.title is empty.
        Output is byte-identical for the same design object (ART-XIV).
        """
        if not (design.title or "").strip():
            raise ValueError(f"Cannot generate document: design {design.id!r} has no title")

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        metadata = DocumentMetadata(
            design_id=design.id,
            schema_version=design.schema_version,
            generated_at=generated_at,
            generator=_GENERATOR,
            level=None,
        )

        frontmatter = yaml.dump(
            {
                "design_id": metadata.design_id,
                "schema_version": metadata.schema_version,
                "generated_at": metadata.generated_at,
                "generator": metadata.generator,
                "level": metadata.level,
            },
            default_flow_style=False,
            sort_keys=True,
            allow_unicode=True,
        ).rstrip()

        body_lines: list[str] = [
            f"---\n{frontmatter}\n---",
            "",
            f"# {design.title}",
            "",
            f"**Design ID**: {design.id}  ",
            f"**Schema Version**: {design.schema_version}  ",
            f"**Generated**: {generated_at}",
        ]

        if design.description:
            body_lines += ["", design.description]

        # Elements section
        if design.elements:
            body_lines += ["", "## Elements", ""]
            for el in sorted(design.elements, key=lambda e: e.id):
                body_lines.append(f"### {el.id} — {el.name} ({el.kind})")
                if el.description:
                    body_lines.append("")
                    body_lines.append(el.description)
                if el.satisfies:
                    body_lines.append("")
                    body_lines.append(f"**Satisfies**: {', '.join(el.satisfies)}")
                if el.provenance:
                    body_lines.append(f"**Provenance**: {el.provenance}")
                body_lines.append("")

        # Requirements section
        if design.requirements:
            body_lines += ["## Requirements", ""]
            body_lines.append("| ID | Title | Description |")
            body_lines.append("|---|---|---|")
            for req in sorted(design.requirements, key=lambda r: r.id):
                desc = (req.description or "").replace("|", "\\|")
                body_lines.append(f"| {req.id} | {req.title} | {desc} |")
            body_lines.append("")

        # Traceability summary
        satisfied_ids = set()
        for el in design.elements:
            satisfied_ids.update(el.satisfies or [])
        orphans = [e for e in design.elements if not (e.satisfies)]
        if orphans:
            body_lines += [
                "## Traceability Summary",
                "",
                f"**Orphan elements** (no satisfied requirements): {len(orphans)}",
                "",
            ]
            for el in sorted(orphans, key=lambda e: e.id):
                body_lines.append(f"- {el.id} ({el.name})")
            body_lines.append("")

        markdown = "\n".join(body_lines)

        logger.debug("document.generated", extra={"design_id": design.id})
        return GeneratedDocument(design_id=design.id, markdown=markdown, metadata=metadata)
