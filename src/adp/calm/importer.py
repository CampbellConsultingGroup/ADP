"""CALM Pattern Importer — ingests FINOS CALM JSON files into the ADP knowledge base (ADP-SPEC-022).

Parsing is intentionally lenient: extracts what it can from any JSON dict that resembles
a CALM document. Only raises on non-dict input.

CLI usage:
    adp-import-calm pattern.json
    adp-import-calm --dir ./calm-patterns/
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import click

from adp.calm.models import CALMImportResult
from adp.knowledge.schema import KnowledgeItem, KnowledgeType

logger = logging.getLogger(__name__)

_MAX_FULL_TEXT = 10_000


# ── String helpers ────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Lowercase, replace non-alphanumeric runs with '-', strip and truncate to 60 chars."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:60]


def _extract_pattern_name(data: dict, fallback: str) -> str:
    """Best-effort name extraction from a CALM document dict."""
    # 1. top-level title field (most authoritative — present in CALM pattern schema docs)
    if data.get("title"):
        return str(data["title"])

    # 2. top-level name field
    if data.get("name"):
        return str(data["name"])

    # 3. $id URL — strip extension, title-case the path segment
    schema_id = data.get("$id", "")
    if schema_id:
        segment = schema_id.rstrip("/").split("/")[-1]
        segment = re.sub(r"\.[^.]+$", "", segment)  # strip .json etc.
        if segment:
            return segment.replace("-", " ").replace("_", " ").title()

    # 4. first node's name (instance format)
    nodes = data.get("nodes", [])
    if nodes and isinstance(nodes, list) and nodes[0].get("name"):
        return str(nodes[0]["name"])

    return fallback


def _schema_nodes(data: dict) -> list[dict]:
    """Extract nodes from CALM pattern schema format (properties.nodes.prefixItems)."""
    prefix_items = (
        data.get("properties", {})
        .get("nodes", {})
        .get("prefixItems", [])
    )
    nodes = []
    for item in prefix_items:
        props = item.get("properties", {})
        nodes.append({
            "unique-id": props.get("unique-id", {}).get("const", "?"),
            "node-type": props.get("node-type", {}).get("const", "unknown"),
            "name": props.get("name", {}).get("const", "?"),
        })
    return nodes


def _schema_relationships(data: dict) -> list[dict]:
    """Extract relationships from CALM pattern schema format (properties.relationships.prefixItems)."""
    prefix_items = (
        data.get("properties", {})
        .get("relationships", {})
        .get("prefixItems", [])
    )
    rels = []
    for item in prefix_items:
        props = item.get("properties", {})
        uid = props.get("unique-id", {}).get("const", "?")
        protocol = props.get("protocol", {}).get("const", "")
        connects_const = props.get("relationship-type", {}).get("const", {})
        connects = connects_const.get("connects", {}) if isinstance(connects_const, dict) else {}
        src = connects.get("source", {}).get("node", "?")
        dst = connects.get("destination", {}).get("node", "?")
        rels.append({"unique-id": uid, "protocol": protocol, "src": src, "dst": dst})
    return rels


def _generate_full_text(name: str, data: dict) -> str:
    """Generate a human-readable summary of a CALM document for embedding.

    Handles both instance format (nodes/relationships as top-level arrays) and
    pattern schema format (nodes/relationships under properties.*.prefixItems).
    """
    # Instance format: nodes directly in top-level array
    nodes_instance = data.get("nodes", []) or []
    rels_instance = data.get("relationships", []) or []
    controls = data.get("controls", []) or []

    # Pattern schema format: nodes/relationships in properties.*.prefixItems
    nodes_schema = _schema_nodes(data) if not nodes_instance else []
    rels_schema = _schema_relationships(data) if not rels_instance else []

    description = data.get("description", "")

    lines: list[str] = [f"Pattern: {name}"]
    if description:
        lines.append(description)
    lines.append("")

    if nodes_instance:
        lines.append(f"Nodes ({len(nodes_instance)}):")
        for n in nodes_instance:
            node_type = n.get("node-type", "unknown")
            node_name = n.get("name", n.get("unique-id", "?"))
            desc = n.get("description", "")
            line = f"- [{node_type}] {node_name}"
            if desc:
                line += f": {desc}"
            lines.append(line)
        lines.append("")
    elif nodes_schema:
        lines.append(f"Nodes ({len(nodes_schema)}):")
        for n in nodes_schema:
            lines.append(f"- [{n['node-type']}] {n['name']} (id: {n['unique-id']})")
        lines.append("")

    if rels_instance:
        lines.append(f"Relationships ({len(rels_instance)}):")
        for r in rels_instance:
            uid = r.get("unique-id", "?")
            rel_type = r.get("relationship-type", "connects")
            connects = r.get("connects", {}) or {}
            src = connects.get("source-node", "?")
            dst = connects.get("destination-node", "?")
            protocol = connects.get("protocol", "")
            proto_str = f" [{protocol}]" if protocol else ""
            lines.append(f"- {uid} ({rel_type}): {src} → {dst}{proto_str}")
        lines.append("")
    elif rels_schema:
        lines.append(f"Relationships ({len(rels_schema)}):")
        for r in rels_schema:
            proto_str = f" [{r['protocol']}]" if r["protocol"] else ""
            lines.append(f"- {r['unique-id']}: {r['src']} → {r['dst']}{proto_str}")
        lines.append("")

    if controls:
        lines.append(f"Controls: {len(controls)} control requirement(s)")
        for c in controls:
            desc = c.get("description", "")
            if desc:
                lines.append(f"- {desc}")
        lines.append("")

    full_text = "\n".join(lines).strip()
    return full_text[:_MAX_FULL_TEXT]


# ── Core parsing ──────────────────────────────────────────────────────────────

def parse_calm_document(
    data: Any,
    source_ref: str = "",
) -> tuple[KnowledgeItem, str]:
    """Parse a CALM JSON dict into a KnowledgeItem + full_text string.

    Raises ValueError if data is not a dict.
    Never fails on missing CALM fields — uses best-effort extraction.
    """
    if not isinstance(data, dict):
        raise ValueError(f"CALM document must be a dict, got {type(data).__name__}")

    name = _extract_pattern_name(data, "Imported CALM Pattern")
    full_text = _generate_full_text(name, data)

    if name != "Imported CALM Pattern":
        item_id = f"calm-{_slugify(name)}"
    else:
        item_id = f"calm-{uuid.uuid4().hex[:8]}"

    nodes = data.get("nodes", []) or []
    relationships = data.get("relationships", []) or []
    # Also count from schema format if top-level arrays are absent
    if not nodes:
        nodes = _schema_nodes(data)
    if not relationships:
        relationships = _schema_relationships(data)
    schema_id = data.get("$id", "")

    metadata: dict[str, Any] = {
        "calm_node_count": len(nodes),
        "calm_relationship_count": len(relationships),
        "calm_source": "import",
    }
    if schema_id:
        metadata["calm_schema_id"] = schema_id

    effective_source = source_ref or schema_id or "adp:calm-import"

    item = KnowledgeItem(
        id=item_id,
        version="1.0.0",
        kind=KnowledgeType.REFERENCE_ARCHITECTURE,
        title=name,
        full_text=full_text,
        source_ref=effective_source,
        metadata=metadata,
    )
    return item, full_text


# ── Async DB import ───────────────────────────────────────────────────────────

async def import_calm_data(
    data: dict,
    source_ref: str,
    db_url: str,
) -> CALMImportResult:
    """Parse a CALM dict and upsert into the knowledge base. Returns a result summary."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adp.knowledge.embedder import EmbeddingProvider
    from adp.knowledge.index import KnowledgeIndex

    try:
        item, full_text = parse_calm_document(data, source_ref)
    except ValueError as exc:
        return CALMImportResult(items_failed=1, errors=[str(exc)])

    # Generate embedding
    embedding: list[float]
    try:
        embedder = EmbeddingProvider("all-MiniLM-L6-v2")
        embedding = embedder.embed(f"{item.title}\n{full_text}")
    except Exception as exc:
        logger.warning("Embedding generation failed, using zero vector: %s", exc)
        embedding = [0.0] * 384

    # Upsert into DB
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    idx = KnowledgeIndex(session_factory=session_factory)

    try:
        async with session_factory() as session:
            # Check if item already exists (to report created vs updated)
            existing = await idx.get_item(item.id, None, session)
            await idx.upsert_item(item, embedding, session)
            await session.commit()
            was_update = existing is not None
    except Exception as exc:
        await engine.dispose()
        return CALMImportResult(items_failed=1, errors=[str(exc)])
    finally:
        await engine.dispose()

    item_dict = {
        "id": item.id,
        "version": item.version,
        "kind": item.kind.value,
        "title": item.title,
        "source_ref": item.source_ref,
        "metadata": item.metadata,
    }
    if was_update:
        return CALMImportResult(items_updated=1, items=[item_dict])
    return CALMImportResult(items_created=1, items=[item_dict])


async def import_calm_file(path: Path, db_url: str) -> CALMImportResult:
    """Read a CALM JSON file and import it into the knowledge base."""
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return CALMImportResult(items_failed=1, errors=[f"{path.name}: invalid JSON — {exc}"])
    except OSError as exc:
        return CALMImportResult(items_failed=1, errors=[f"{path.name}: {exc}"])

    result = await import_calm_data(data, str(path), db_url)
    # Attach filename context to errors
    if result.errors:
        result.errors = [f"{path.name}: {e}" for e in result.errors]
    return result


async def import_calm_dir(directory: Path, db_url: str) -> CALMImportResult:
    """Import all *.json files in a directory."""
    aggregate = CALMImportResult()
    for json_file in sorted(directory.glob("*.json")):
        result = await import_calm_file(json_file, db_url)
        aggregate.items_created += result.items_created
        aggregate.items_updated += result.items_updated
        aggregate.items_failed += result.items_failed
        aggregate.errors.extend(result.errors)
        aggregate.items.extend(result.items)
    return aggregate


# ── CLI ───────────────────────────────────────────────────────────────────────

_DEFAULT_DB_URL = "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"


@click.command()
@click.argument("path")
@click.option("--dir", "is_dir", is_flag=True, help="Import all *.json files in PATH directory")
@click.option(
    "--db-url",
    envvar="ADP_DATABASE_URL",
    default=_DEFAULT_DB_URL,
    show_default=True,
    help="PostgreSQL async URL",
)
def cli(path: str, is_dir: bool, db_url: str) -> None:
    """Import a FINOS CALM pattern JSON file (or directory) into the ADP knowledge base."""
    target = Path(path)

    if is_dir:
        if not target.is_dir():
            click.echo(f"Error: {path} is not a directory", err=True)
            raise SystemExit(1)
        result = asyncio.run(import_calm_dir(target, db_url))
    else:
        if not target.is_file():
            click.echo(f"Error: {path} is not a file", err=True)
            raise SystemExit(1)
        result = asyncio.run(import_calm_file(target, db_url))

    for item in result.items:
        click.echo(f"  ✓ {item.get('id')}  {item.get('title')}")
    for err in result.errors:
        click.echo(f"  ✗ {err}", err=True)

    click.echo(
        f"\nDone — created: {result.items_created}"
        f"  updated: {result.items_updated}"
        f"  failed: {result.items_failed}"
    )

    if result.items_failed > 0:
        raise SystemExit(1)
