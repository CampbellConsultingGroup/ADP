"""Pattern views as diagram-core flowchart text (935 FR-017/FR-018; research.md D10). Pure.

Targets the vendored flowchart dialect the web app actually parses
(``web/src/diagrams/core/dsl/flowchart-parser.ts``), not real Mermaid:

- labels are unquoted (the parser keeps quote characters), sanitised, and truncated at 60;
- no ``x``/``o`` arrowheads, so a prohibited edge is a dotted arrow with a "✕" label;
- subgraph titles only as ``subgraph id [Title]``; ``direction`` only inside a subgraph;
- ``classDef`` supports fill/stroke/stroke-width/stroke-dasharray only, so the palette uses light
  fills (default dark text stays legible) drawn from ``c4-theme.json`` colours;
- node ids are always generated, never user text.

Every view starts with a provenance comment ``%% adp-pattern <key>@<version> view=<v>
digest=<12>`` and is deterministic for the same input (input list order never matters where it
is not semantic).
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from adp.patterns.cardinality import format_cardinality
from adp.patterns.conformance_models import ConformanceReport, FindingKind, PlateauState
from adp.patterns.models import PatternDefinition, PatternKind, RenderHintKind, Severity
from adp.patterns.snapshot import PortfolioSnapshot

MAX_LABEL = 60
CATALOG_NODE_CAP = 40

# Light fills from src/adp/theme/c4-theme.json (component fill/stroke, system/container/person
# strokes, relationship grey); the shape, not the colour, carries "anti-pattern".
_PALETTE: dict[str, str] = {
    "role": "fill:#85BBE0,stroke:#78A8CC",
    "mediator": "fill:#FFFFFF,stroke:#1168BD,stroke-width:2px",
    "focus": "fill:#85BBE0,stroke:#08427B,stroke-width:3px",
    "pattern": "fill:#FFFFFF,stroke:#2874A6",
    "antipattern": "fill:#FFFFFF,stroke:#707070,stroke-dasharray:4 2",
    "motivation": "fill:#FFFFFF,stroke:#08427B",
    "unknown": "fill:#FFFFFF,stroke:#707070,stroke-dasharray:2 2",
    # 936: element outcomes (meaning is also in the label suffix, never colour alone) and plateaus
    "pass": "fill:#FFFFFF,stroke:#1168BD",
    "warn": "fill:#FFFFFF,stroke:#707070,stroke-dasharray:4 2",
    "fail": "fill:#FFFFFF,stroke:#08427B,stroke-width:3px",
    "reached": "fill:#85BBE0,stroke:#08427B",
    "pending": "fill:#FFFFFF,stroke:#707070,stroke-dasharray:4 2",
}
_LEGEND_LABELS: dict[str, str] = {
    "role": "Role",
    "mediator": "Platform / mediating role",
    "focus": "This pattern",
    "pattern": "Related pattern",
    "antipattern": "Anti-pattern",
    "motivation": "Principle / control",
    "unknown": "Not in registry",
    "pass": "Passes",
    "warn": "Warning",
    "fail": "Fails",
    "reached": "Plateau reached",
    "pending": "Plateau pending",
}

_SYMMETRIC = {"conflicts_with", "alternative_to"}

_CONNECTOR_RUNS = re.compile(r"-{2,}|={2,}|~{2,}|-\.|\.-")
_FORBIDDEN = re.compile(r'[\[\]{}()<>|#;"\\]')


@dataclass(frozen=True)
class RenderOptions:
    direction: Literal["LR", "TB"] = "LR"
    include_legend: bool = False


@dataclass(frozen=True)
class RenderedView:
    text: str
    truncated: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogNode:
    """A pattern family as shown in the catalog: its representative version (current, else latest
    proposed, else latest draft). ``lifecycle``/``kind`` are None for an unresolved target."""

    key: str
    name: str
    version: str | None
    lifecycle: str | None
    kind: str | None


@dataclass(frozen=True)
class CatalogEdge:
    source: str
    target: str
    relation_type: str


@dataclass(frozen=True)
class TraceRef:
    id: str
    label: str
    resolved: bool


# ── Labels and ids ──────────────────────────────────────────────────────────────────────
def sanitize_label(text: str, max_len: int = MAX_LABEL) -> str:
    """Make arbitrary text safe as an unquoted label in the flowchart dialect."""
    s = text.replace('"', "'").replace("&", " and ")
    s = _CONNECTOR_RUNS.sub(" ", s)
    s = _FORBIDDEN.sub(" ", s)
    s = " ".join(s.split())
    s = s.strip("/ ")  # a label wrapped in slashes would parse as a parallelogram
    if not s:
        return "?"
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s


def _pattern_id(key: str) -> str:
    return "pt_" + hashlib.sha1(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]


def _role_id(key: str) -> str:
    return f"r_{key}"


def _header(key: str, version: str, view: str, digest: str, opts: RenderOptions) -> list[str]:
    return [
        f"%% adp-pattern {key}@{version} view={view} digest={digest[:12]}",
        f"flowchart {opts.direction}",
    ]


def _edge(src: str, dst: str, label: str | None, style: str = "solid") -> str:
    if not label:
        return {
            "solid": f"    {src} --> {dst}",
            "dotted": f"    {src} -.-> {dst}",
            "thick": f"    {src} ==> {dst}",
        }[style]
    text = sanitize_label(label)
    return {
        "solid": f"    {src} -- {text} --> {dst}",
        "dotted": f"    {src} -. {text} .-> {dst}",
        "thick": f"    {src} == {text} ==> {dst}",
    }[style]


def _styles(classes: dict[str, list[str]], opts: RenderOptions) -> list[str]:
    """classDef + class lines (and an optional legend) for the classes actually used."""
    used = [c for c in _PALETTE if classes.get(c)]
    out: list[str] = []
    if opts.include_legend and used:
        out.append("    subgraph legend [Legend]")
        out.append("        direction TB")
        for c in used:
            out.append(f"        lg_{c}[{_LEGEND_LABELS[c]}]")
        out.append("    end")
        for c in used:
            classes[c].append(f"lg_{c}")
    for c in used:
        out.append(f"    classDef {c} {_PALETTE[c]}")
    for c in used:
        out.append(f"    class {','.join(classes[c])} {c}")
    return out


# ── Structure ───────────────────────────────────────────────────────────────────────────
def render_structure(defn: PatternDefinition, opts: RenderOptions | None = None) -> RenderedView:
    """Roles as nodes (``«stereotype» Label · cardinality``), relationships and render hints as
    edges. Needs no registry data."""
    from adp.patterns.parse import compute_digest

    opts = opts or RenderOptions()
    lines = _header(defn.pattern, defn.version, "structure", compute_digest(defn), opts)
    mediating = {r.via for r in defn.relationships if r.via}
    classes: dict[str, list[str]] = {c: [] for c in _PALETTE}

    for key, role in defn.roles.items():
        name = role.label or key.replace("_", " ").title()
        head = f"«{role.stereotype}» {name}" if role.stereotype else name
        card = role.cardinality
        label = sanitize_label(f"{head} · {format_cardinality(card.min, card.max, card.per)}")
        rid = _role_id(key)
        if role.stereotype == "platform" or key in mediating:
            lines.append(f"    {rid}([{label}])")
            classes["mediator"].append(rid)
        else:
            lines.append(f"    {rid}[{label}]")
            classes["role"].append(rid)

    for rel in defn.relationships:
        label = f"{rel.type.value}: {rel.label}" if rel.label else rel.type.value
        style = "solid" if rel.required else "dotted"
        if rel.via:
            lines.append(_edge(_role_id(rel.source), _role_id(rel.via), label, style))
            lines.append(_edge(_role_id(rel.via), _role_id(rel.target), None, style))
        else:
            lines.append(_edge(_role_id(rel.source), _role_id(rel.target), label, style))

    for constraint in defn.constraints:
        hint = constraint.render_hint
        if hint is None or hint.source is None or hint.target is None:
            continue  # notes and partial hints have no edge form in this dialect
        src, dst = _role_id(hint.source), _role_id(hint.target)
        if hint.kind == RenderHintKind.PROHIBITED_EDGE:
            lines.append(_edge(src, dst, f"✕ {hint.label}", "dotted"))
        elif hint.kind == RenderHintKind.REQUIRED_EDGE:
            lines.append(_edge(src, dst, hint.label, "thick"))

    lines += _styles(classes, opts)
    return RenderedView("\n".join(lines) + "\n")


# ── Catalog ─────────────────────────────────────────────────────────────────────────────
def _neighbourhood(focus: str, edges: list[CatalogEdge], depth: int) -> dict[str, int]:
    adjacency: dict[str, set[str]] = {}
    for e in edges:
        adjacency.setdefault(e.source, set()).add(e.target)
        adjacency.setdefault(e.target, set()).add(e.source)
    seen = {focus: 0}
    queue = deque([focus])
    while queue:
        key = queue.popleft()
        if seen[key] >= depth:
            continue
        for nxt in sorted(adjacency.get(key, ())):
            if nxt not in seen:
                seen[nxt] = seen[key] + 1
                queue.append(nxt)
    return seen


def render_catalog(
    focus: CatalogNode,
    focus_digest: str,
    nodes: list[CatalogNode],
    edges: list[CatalogEdge],
    depth: int = 1,
    opts: RenderOptions | None = None,
) -> RenderedView:
    """The focus pattern plus every pattern within ``depth`` (1–3) relation hops, either
    direction. Unknown targets render with the ``unknown`` class rather than being dropped."""
    opts = opts or RenderOptions()
    depth = max(1, min(3, depth))
    by_key = {n.key: n for n in nodes}
    by_key[focus.key] = focus
    reach = _neighbourhood(focus.key, edges, depth)
    ordered = sorted(reach, key=lambda k: (reach[k], k))
    truncated: list[str] = []
    if len(ordered) > CATALOG_NODE_CAP:
        truncated.append(
            f"catalog limited to {CATALOG_NODE_CAP} patterns ({len(ordered)} within depth {depth})"
        )
        ordered = ordered[:CATALOG_NODE_CAP]
    shown = set(ordered)

    lines = _header(focus.key, focus.version or "?", "catalog", focus_digest, opts)
    classes: dict[str, list[str]] = {c: [] for c in _PALETTE}
    for key in ordered:
        node = by_key.get(key) or CatalogNode(key, key, None, None, None)
        pid = _pattern_id(key)
        if node.kind is None:
            lines.append(f"    {pid}[{sanitize_label(f'{key} · not in registry')}]")
            classes["unknown"].append(pid)
            continue
        text = f"{node.name} · {node.version}"
        if node.lifecycle == "deprecated":
            text += " · deprecated"
        label = sanitize_label(text)
        if node.kind == PatternKind.ANTI_PATTERN.value:
            lines.append(f"    {pid}{{{{{label}}}}}")
            classes["focus" if key == focus.key else "antipattern"].append(pid)
        else:
            lines.append(f"    {pid}[{label}]")
            classes["focus" if key == focus.key else "pattern"].append(pid)

    unique = sorted(
        {
            (e.source, e.relation_type, e.target)
            for e in edges
            if e.source in shown and e.target in shown
        }
    )
    for src, rel, dst in unique:
        label = rel.replace("_", " ")
        style = "dotted" if rel in _SYMMETRIC else "solid"
        lines.append(_edge(_pattern_id(src), _pattern_id(dst), label, style))

    lines += _styles(classes, opts)
    return RenderedView("\n".join(lines) + "\n", truncated)


# ── Traceability ────────────────────────────────────────────────────────────────────────
def render_traceability(
    defn: PatternDefinition,
    digest: str,
    principles: list[TraceRef],
    controls: list[TraceRef],
    implementations: list[TraceRef],
    opts: RenderOptions | None = None,
) -> RenderedView:
    """Principles and controls → the pattern → its known implementations, one subgraph column
    each (empty columns omitted). Unresolved references are shown as unknown, not dropped."""
    opts = opts or RenderOptions()
    lines = _header(defn.pattern, defn.version, "traceability", digest, opts)
    classes: dict[str, list[str]] = {c: [] for c in _PALETTE}
    focus = _pattern_id(defn.pattern)

    def ref_node(prefix: str, i: int, ref: TraceRef, resolved_class: str) -> str:
        nid = f"{prefix}_{i}"
        text = ref.label if ref.resolved else f"{ref.id} · not found"
        classes[resolved_class if ref.resolved else "unknown"].append(nid)
        return f"        {nid}[{sanitize_label(text)}]"

    if principles or controls:
        lines.append("    subgraph col_motivation [Motivation]")
        lines.append("        direction TB")
        lines += [ref_node("pr", i, r, "motivation") for i, r in enumerate(principles)]
        lines += [ref_node("ct", i, r, "motivation") for i, r in enumerate(controls)]
        lines.append("    end")
    lines.append(f"    {focus}[{sanitize_label(f'{defn.name} · {defn.version}')}]")
    classes["focus"].append(focus)
    if implementations:
        lines.append("    subgraph col_impl [Known implementations]")
        lines.append("        direction TB")
        lines += [ref_node("ap", i, r, "role") for i, r in enumerate(implementations)]
        lines.append("    end")

    lines += [f"    pr_{i} --> {focus}" for i in range(len(principles))]
    lines += [f"    ct_{i} --> {focus}" for i in range(len(controls))]
    lines += [f"    {focus} --> ap_{i}" for i in range(len(implementations))]
    lines += _styles(classes, opts)
    return RenderedView("\n".join(lines) + "\n")


# ── Conformance (936 FR-020) ────────────────────────────────────────────────────────────
_OUTCOME_RANK = {"fail": 0, "unknown": 1, "warn": 2, "pass": 3}
_OUTCOME_SUFFIX = {"fail": " · FAIL", "unknown": " · unknown", "warn": " · warn", "pass": ""}


def _outcomes(report: ConformanceReport) -> dict[tuple[str, str], str]:
    """Worst outcome per (element type, id) across all findings."""
    worst: dict[tuple[str, str], str] = {}
    for f in report.findings:
        if f.kind in (FindingKind.UNVERIFIABLE,) or f.severity == Severity.INFO:
            continue
        if f.kind in (
            FindingKind.EVALUATION_ERROR,
            FindingKind.FIELD_UNAVAILABLE,
            FindingKind.LIMIT,
        ):
            outcome = "unknown"
        elif f.severity == Severity.ERROR:
            outcome = "fail"
        else:
            outcome = "warn"
        for ref in f.element_refs:
            key = (ref.type.value, ref.id)
            if key not in worst or _OUTCOME_RANK[outcome] < _OUTCOME_RANK[worst[key]]:
                worst[key] = outcome
    return worst


def render_conformance(
    defn: PatternDefinition,
    digest: str,
    report: ConformanceReport,
    snapshot: PortfolioSnapshot,
    opts: RenderOptions | None = None,
    max_per_role: int = 8,
) -> RenderedView:
    """The pattern bound to real elements: one group per role, elements worst-first (capped,
    then '+k more'), evidence edges for declared relationships between shown elements."""
    opts = opts or RenderOptions()
    lines = _header(defn.pattern, defn.version, "conformance", digest, opts)
    classes: dict[str, list[str]] = {c: [] for c in _PALETTE}
    worst = _outcomes(report)
    failed_roles = {
        f.code[2:]
        for f in report.findings
        if f.code.startswith("K:") and "/" not in f.code and f.kind == FindingKind.VIOLATION
    }
    shown: dict[str, dict[str, str]] = {}  # role -> element id -> node id
    truncated: list[str] = []
    for binding in report.bindings:
        role_key = binding.role_key
        role = defn.roles.get(role_key)
        etype = binding.element_type.value
        ranked = sorted(
            binding.elements,
            key=lambda e: (_OUTCOME_RANK[worst.get((etype, e.id), "pass")], e.name, e.id),
        )
        title = f"{binding.label} · {binding.count}" + (" ⚠" if role_key in failed_roles else "")
        lines.append(f"    subgraph r_{role_key} [{sanitize_label(title)}]")
        if not ranked:
            lines.append(f"        e_{role_key}_none[{sanitize_label('none bound')}]")
            classes["unknown"].append(f"e_{role_key}_none")
        mediator = role is not None and role.stereotype == "platform"
        shown[role_key] = {}
        for i, el in enumerate(ranked[:max_per_role]):
            nid = f"e_{role_key}_{i}"
            outcome = worst.get((etype, el.id), "pass")
            label = sanitize_label(el.name, MAX_LABEL - len(_OUTCOME_SUFFIX[outcome]))
            label += _OUTCOME_SUFFIX[outcome]
            lines.append(f"        {nid}([{label}])" if mediator else f"        {nid}[{label}]")
            classes[outcome].append(nid)
            shown[role_key][el.id] = nid
        hidden = len(ranked) - max_per_role
        if hidden > 0:
            lines.append(f"        e_{role_key}_more[+{hidden} more]")
            classes["unknown"].append(f"e_{role_key}_more")
            truncated.append(f"role {role_key}: {hidden} more element(s) not drawn")
        lines.append("    end")

    seen: set[tuple[str, str, str]] = set()
    for rel in defn.relationships:
        target_role = rel.via or rel.target
        for s_id, s_node in sorted(shown.get(rel.source, {}).items()):
            for t_id, t_node in sorted(shown.get(target_role, {}).items()):
                if s_id == t_id or not _has_evidence(snapshot, rel.type.value, s_id, t_id):
                    continue
                key = (s_node, t_node, rel.type.value)
                if key not in seen:
                    seen.add(key)
                    lines.append(_edge(s_node, t_node, rel.type.value))
    lines += _styles(classes, opts)
    return RenderedView("\n".join(lines) + "\n", truncated)


def _has_evidence(snapshot: PortfolioSnapshot, rel: str, s: str, t: str) -> bool:
    if rel in ("publishes", "delivers"):
        return bool(snapshot.integrations_between(s, t))
    if rel == "consumes":
        return bool(snapshot.integrations_between(t, s))
    if rel in ("integrates_with", "depends_on"):
        return bool(snapshot.integrations_between(s, t) or snapshot.integrations_between(t, s))
    if rel == "serves":
        return snapshot.serves(s, t)
    if rel == "realizes":
        return snapshot.realizes(s, t)
    return False


# ── Transition (936 FR-020) ─────────────────────────────────────────────────────────────
def render_transition(
    defn: PatternDefinition,
    digest: str,
    state: PlateauState | None,
    opts: RenderOptions | None = None,
) -> RenderedView:
    """from_pattern (anti-pattern) → plateaus in order → target pattern; reached plateaus
    highlighted, the edge into the next plateau labelled with its blocking constraints."""
    opts = opts or RenderOptions()
    lines = _header(defn.pattern, defn.version, "transition", digest, opts)
    classes: dict[str, list[str]] = {c: [] for c in _PALETTE}
    transition = defn.transition
    if transition is None:
        return RenderedView("\n".join(lines) + "\n")
    source = _pattern_id(transition.from_pattern)
    lines.append(f"    {source}{{{{{sanitize_label(transition.from_pattern)}}}}}")
    classes["antipattern"].append(source)
    reached_ids: set[str] = set()
    if state is not None and state.reached:
        for p in transition.plateaus:
            reached_ids.add(p.id)
            if p.id == state.reached:
                break
    nodes = []
    for p in transition.plateaus:
        nid = f"p_{p.id}"
        nodes.append((p.id, nid))
        label = sanitize_label(f"{p.id} {p.name} · {', '.join(p.exit_criteria)}")
        lines.append(f"    {nid}[/{label}/]")
        classes["reached" if p.id in reached_ids else "pending"].append(nid)
    realized = next((r.target for r in defn.relations if r.type.value == "realizes"), None)
    target_key = realized or defn.pattern
    target = _pattern_id(target_key)
    if target == source:
        target = f"{target}_t"
    lines.append(f"    {target}[{sanitize_label(realized or defn.name)}]")
    classes["pattern"].append(target)

    blocked = state.next if state else None
    blocking = ", ".join(state.blocking) if state and state.blocking else ""
    chain: list[tuple[str | None, str]] = [(None, source), *nodes, (None, target)]
    for (_, a), (pid, b) in zip(chain, chain[1:], strict=False):
        edge_label = (
            f"blocked: {blocking}" if pid is not None and pid == blocked and blocking else None
        )
        lines.append(_edge(a, b, edge_label))
    lines += _styles(classes, opts)
    return RenderedView("\n".join(lines) + "\n")
