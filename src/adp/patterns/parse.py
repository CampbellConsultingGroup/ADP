"""Parse, validate and canonicalise EA pattern documents (934 FR-008..FR-014).

``parse_pattern_yaml`` never raises: every problem — oversized input, YAML aliases,
syntax errors, schema errors, rule violations, CEL compile errors — comes back as a
:class:`~adp.patterns.models.PatternIssue` with a stable code and a path.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml
from pydantic import ValidationError

from adp.patterns.cardinality import format_cardinality
from adp.patterns.cel import CelEngine, default_engine
from adp.patterns.models import ParseResult, PatternDefinition, PatternIssue

MAX_DOCUMENT_BYTES = 256 * 1024


# ── YAML loading ──────────────────────────────────────────────────────────────────
class _YamlRejected(Exception):
    def __init__(self, code: str, message: str, mark: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.mark = mark


class _SafeNoAliasLoader(yaml.SafeLoader):
    """SafeLoader refusing anchors and aliases before anything is expanded (alias bombs)."""

    def compose_node(self, parent: Any, index: Any) -> Any:  # type: ignore[override]
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent):
            raise _YamlRejected("P2.alias", "YAML aliases are not allowed", event.start_mark)
        if getattr(event, "anchor", None):
            raise _YamlRejected("P2.alias", "YAML anchors are not allowed", event.start_mark)
        return super().compose_node(parent, index)


def _position(mark: Any) -> tuple[int | None, int | None]:
    if mark is None:
        return None, None
    return mark.line + 1, mark.column + 1


def _issue(code: str, message: str, path: str = "", mark: Any = None) -> PatternIssue:
    line, column = _position(mark)
    return PatternIssue(path=path, code=code, message=message, line=line, column=column)


def _load_single_mapping(text: str) -> dict[str, Any]:
    loader = _SafeNoAliasLoader(text)
    try:
        node = loader.get_node() if loader.check_node() else None
        if node is not None and loader.check_node():
            raise _YamlRejected("P3.multi_document", "only one YAML document per file is allowed")
        data = loader.construct_document(node) if node is not None else None
    finally:
        loader.dispose()
    if not isinstance(data, dict):
        raise _YamlRejected("P4.not_mapping", "the document root must be a mapping")
    return data


# ── Pydantic errors → issues ──────────────────────────────────────────────────────
def _loc_to_path(loc: tuple[Any, ...]) -> str:
    path = ""
    for part in loc:
        if part == "[key]":
            continue
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path


def _validation_issues(exc: ValidationError) -> list[PatternIssue]:
    issues: list[PatternIssue] = []
    for err in exc.errors():
        if err["type"] == "pattern_rules":
            for code, path, message in (err.get("ctx") or {}).get("issues", []):
                issues.append(PatternIssue(path=path, code=code, message=message))
            continue
        issues.append(
            PatternIssue(
                path=_loc_to_path(tuple(err["loc"])),
                code=f"schema.{err['type']}",
                message=err["msg"],
            )
        )
    return issues


# ── Public API ────────────────────────────────────────────────────────────────────
def validate_pattern(defn: PatternDefinition, engine: CelEngine) -> list[PatternIssue]:
    """V7: compile-check every role selector and constraint expression."""
    targets: list[tuple[str, str]] = [
        (f"roles.{key}.selector", role.selector)
        for key, role in defn.roles.items()
        if role.selector is not None
    ]
    targets += [(f"constraints[{i}].expr", con.expr) for i, con in enumerate(defn.constraints)]
    issues: list[PatternIssue] = []
    for path, expr in targets:
        for err in engine.compile_check(expr):
            issues.append(
                PatternIssue(
                    path=path,
                    code=f"V7.{err.code}",
                    message=err.message,
                    line=err.line,
                    column=err.column,
                )
            )
    return issues


def parse_pattern_yaml(text: str | bytes, engine: CelEngine | None = None) -> ParseResult:
    """Parse and fully validate one pattern document. Never raises (FR-012)."""
    try:
        raw = text.encode("utf-8") if isinstance(text, str) else bytes(text)
        if len(raw) > MAX_DOCUMENT_BYTES:
            return ParseResult(
                definition=None,
                issues=[_issue("P1.too_large", f"document exceeds {MAX_DOCUMENT_BYTES} bytes")],
            )
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            return ParseResult(
                definition=None,
                issues=[_issue("P5.yaml_syntax", f"document is not valid UTF-8: {exc.reason}")],
            )
        try:
            data = _load_single_mapping(source)
        except _YamlRejected as exc:
            return ParseResult(
                definition=None, issues=[_issue(exc.code, exc.message, mark=exc.mark)]
            )
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            problem = getattr(exc, "problem", None) or str(exc)
            return ParseResult(
                definition=None,
                issues=[_issue("P5.yaml_syntax", f"invalid YAML: {problem}", mark=mark)],
            )

        try:
            defn = PatternDefinition.model_validate(data)
        except ValidationError as exc:
            return ParseResult(definition=None, issues=_validation_issues(exc))

        issues = validate_pattern(defn, engine or default_engine())
        return ParseResult(definition=defn, issues=issues)
    except Exception as exc:  # noqa: BLE001 - last line of defence for FR-012
        return ParseResult(
            definition=None,
            issues=[_issue("P0.internal", f"unexpected error: {type(exc).__name__}")],
        )


# ── Canonical forms ───────────────────────────────────────────────────────────────
def _canonical_data(defn: PatternDefinition) -> dict[str, Any]:
    data = defn.model_dump(mode="json")
    # Role order is semantic; encode as ordered pairs so sort_keys cannot erase it (research D5).
    data["roles"] = [[key, role] for key, role in data["roles"].items()]
    return data


def to_canonical_json(defn: PatternDefinition) -> str:
    return json.dumps(
        _canonical_data(defn), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def compute_digest(defn: PatternDefinition) -> str:
    return hashlib.sha256(to_canonical_json(defn).encode("utf-8")).hexdigest()


class _CanonicalDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def to_canonical_yaml(defn: PatternDefinition) -> str:
    """Fixed key order (field declaration), shorthand cardinality, defaults omitted, no aliases."""
    data = defn.model_dump(mode="json", exclude_defaults=True)
    data["roles"] = {}
    for key, role in defn.roles.items():
        dumped = role.model_dump(mode="json", exclude_defaults=True)
        card = role.cardinality
        dumped["cardinality"] = format_cardinality(card.min, card.max, card.per)
        data["roles"][key] = dumped
    return yaml.dump(
        data,
        Dumper=_CanonicalDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=4096,
    )
