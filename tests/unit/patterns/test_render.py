"""Pattern views as diagram-core flowchart text (935 US4, FR-017; research D10).

Goldens live in tests/unit/patterns/goldens/ and are also parsed by the in-app flowchart parser
in web/src/patterns/goldens.test.ts (the zero-errors guarantee). Regenerate with
``pytest tests/unit/patterns/test_render.py --update-goldens`` and review the diff by hand.
"""

from __future__ import annotations

import random
import re

import pytest
import yaml

from adp.patterns import compute_digest, parse_pattern_yaml
from adp.patterns.models import PatternDefinition
from adp.patterns.render import (
    CatalogEdge,
    CatalogNode,
    RenderOptions,
    TraceRef,
    render_catalog,
    render_structure,
    render_traceability,
)

from .conftest import load_fixture, valid_fixture_paths

BACKBONE = "ea.integration.domain-event-backbone@1.0.0.yaml"
MESH = "ea.integration.point-to-point-mesh@1.0.0.yaml"
TRANSITION = "ea.integration.mesh-to-backbone@1.0.0.yaml"
ONE_SOR = "ea.data.one-sor-per-capability@1.0.0.yaml"
REGISTRY = [BACKBONE, MESH, TRANSITION, ONE_SOR]


def _defn(name: str) -> PatternDefinition:
    result = parse_pattern_yaml(load_fixture(name))
    assert result.definition is not None, result.issues
    return result.definition


def _node(defn: PatternDefinition, lifecycle: str = "current") -> CatalogNode:
    return CatalogNode(
        key=defn.pattern,
        name=defn.name,
        version=defn.version,
        lifecycle=lifecycle,
        kind=defn.kind.value,
    )


def _registry() -> tuple[list[CatalogNode], list[CatalogEdge]]:
    defns = [_defn(n) for n in REGISTRY]
    nodes = [_node(d) for d in defns]
    edges = [CatalogEdge(d.pattern, r.target, r.type.value) for d in defns for r in d.relations]
    return nodes, edges


def _stem(name: str) -> str:
    return name.removesuffix(".yaml").replace("@", "_")


# ── Goldens ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", valid_fixture_paths(), ids=lambda p: p.name)
def test_golden_structure(path, golden) -> None:  # type: ignore[no-untyped-def]
    view = render_structure(_defn(path.name))
    golden(f"structure__{_stem(path.name)}.mmd", view.text)


@pytest.mark.parametrize(("focus", "depth"), [(BACKBONE, 1), (MESH, 1), (MESH, 2), (TRANSITION, 1)])
def test_golden_catalog(focus: str, depth: int, golden) -> None:  # type: ignore[no-untyped-def]
    defn = _defn(focus)
    nodes, edges = _registry()
    view = render_catalog(_node(defn), compute_digest(defn), nodes, edges, depth=depth)
    golden(f"catalog__{_stem(focus)}__depth{depth}.mmd", view.text)


def test_golden_traceability(golden) -> None:  # type: ignore[no-untyped-def]
    defn = _defn(BACKBONE)
    view = render_traceability(
        defn,
        compute_digest(defn),
        principles=[
            TraceRef("P-API-FIRST", "API First Design", True),
            TraceRef("P-NO-P2P", "P-NO-P2P", False),
        ],
        controls=[TraceRef("ctl-1", "GDPR Art. 32 Security of processing", True)],
        implementations=[TraceRef("app-1", "Enterprise Event Hub", True)],
    )
    golden(f"traceability__{_stem(BACKBONE)}.mmd", view.text)


# ── Rules ─────────────────────────────────────────────────────────────────────────
def test_header_provenance() -> None:
    defn = _defn(BACKBONE)
    lines = render_structure(defn).text.splitlines()
    assert lines[0] == (
        f"%% adp-pattern {defn.pattern}@{defn.version} view=structure "
        f"digest={compute_digest(defn)[:12]}"
    )
    assert lines[1] == "flowchart LR"
    assert render_structure(defn, RenderOptions(direction="TB")).text.splitlines()[1] == (
        "flowchart TB"
    )


def test_structure_edges_hints_and_shapes() -> None:
    text = render_structure(_defn(BACKBONE)).text
    assert "    r_backbone([«platform» Backbone · 1])" in text
    assert "    r_domain_app[Domain App · 2..*]" in text
    assert "    r_domain_app -- publishes --> r_backbone" in text
    assert "    r_domain_app -. ✕ no direct cross-domain .-> r_domain_app" in text
    assert "    class r_backbone mediator" in text


def test_optional_relationship_is_dotted() -> None:
    text = render_structure(_defn(MESH)).text
    assert "    r_app -. integrates_with .-> r_app" in text


def test_via_renders_two_edges() -> None:
    data = yaml.safe_load(load_fixture(BACKBONE))
    data["relationships"] = [
        {
            "id": "R1",
            "source": "domain_app",
            "target": "domain_app",
            "type": "publishes",
            "via": "backbone",
            "label": "domain events",
        },
    ]
    text = render_structure(PatternDefinition.model_validate(data)).text
    assert "    r_domain_app -- publishes: domain events --> r_backbone" in text
    assert "    r_backbone --> r_domain_app" in text


def test_required_edge_hint_is_thick() -> None:
    data = yaml.safe_load(load_fixture(BACKBONE))
    data["constraints"][1]["render_hint"] = {
        "kind": "required_edge",
        "source": "domain_app",
        "target": "backbone",
        "label": "must publish",
    }
    text = render_structure(PatternDefinition.model_validate(data)).text
    assert "    r_domain_app == must publish ==> r_backbone" in text


def test_hostile_names_are_sanitised_and_ids_generated() -> None:
    data = yaml.safe_load(load_fixture(BACKBONE))
    data["roles"]["backbone"]["label"] = 'Bad"] --> x{{<script>'
    text = render_structure(PatternDefinition.model_validate(data)).text
    node = next(line for line in text.splitlines() if line.strip().startswith("r_backbone("))
    assert "<script>" not in node and "-->" not in node and '"' not in node
    for line in text.splitlines()[2:]:
        ids = re.findall(r"^\s*([A-Za-z0-9_]+)[\[\(\{]", line)
        assert all(re.fullmatch(r"(r|pt|pr|ct|ap|lg)_[A-Za-z0-9_]+", i) for i in ids), line


def test_catalog_depth_limits_neighbourhood() -> None:
    nodes, edges = _registry()
    focus = _defn(TRANSITION)
    one = render_catalog(_node(focus), compute_digest(focus), nodes, edges, depth=1).text
    two = render_catalog(_node(focus), compute_digest(focus), nodes, edges, depth=2).text
    assert "Domain Event Backbone" in one
    assert "Point-to-Point Mesh" not in one  # transition -> backbone -> mesh is 2 hops
    assert "Point-to-Point Mesh" in two


def test_catalog_marks_deprecated_antipattern_and_unresolved() -> None:
    nodes, edges = _registry()
    nodes = [
        CatalogNode(n.key, n.name, n.version, "deprecated", n.kind)
        if n.key == "ea.integration.point-to-point-mesh"
        else n
        for n in nodes
    ]
    edges = [
        *edges,
        CatalogEdge("ea.integration.domain-event-backbone", "ea.not.written", "requires"),
    ]
    focus = _defn(BACKBONE)
    text = render_catalog(_node(focus), compute_digest(focus), nodes, edges, depth=1).text
    assert "{{Point-to-Point Mesh · 1.0.0 · deprecated}}" in text
    assert "[ea.not.written · not in registry]" in text
    assert " antipattern" in text and " unknown" in text


def test_symmetric_relations_are_dotted() -> None:
    nodes, _ = _registry()
    edges = [
        CatalogEdge(
            "ea.integration.domain-event-backbone",
            "ea.integration.point-to-point-mesh",
            "conflicts_with",
        )
    ]
    focus = _defn(BACKBONE)
    text = render_catalog(_node(focus), compute_digest(focus), nodes, edges, depth=1).text
    assert re.search(r"pt_\w+ -\. conflicts with \.-> pt_\w+", text)


def test_catalog_node_cap_reports_truncation() -> None:
    focus = CatalogNode("ea.x.focus", "Focus", "1.0.0", "current", "portfolio-rule")
    nodes = [focus] + [
        CatalogNode(f"ea.x.n{i:03d}", f"N{i}", "1.0.0", "current", "portfolio-rule")
        for i in range(60)
    ]
    edges = [CatalogEdge("ea.x.focus", n.key, "requires") for n in nodes[1:]]
    view = render_catalog(focus, "0" * 64, nodes, edges, depth=1)
    assert view.truncated and "40" in view.truncated[0]
    assert view.text.count("[N") == 39  # cap 40 nodes including the focus


def test_catalog_is_deterministic_under_shuffling() -> None:
    nodes, edges = _registry()
    focus = _defn(BACKBONE)
    first = render_catalog(_node(focus), compute_digest(focus), nodes, edges, depth=3).text
    rng = random.Random(7)
    for _ in range(50):
        n, e = nodes[:], edges[:]
        rng.shuffle(n)
        rng.shuffle(e)
        assert render_catalog(_node(focus), compute_digest(focus), n, e, depth=3).text == first


def test_traceability_skips_empty_columns_and_marks_unknown() -> None:
    defn = _defn(MESH)
    text = render_traceability(defn, compute_digest(defn), [], [], []).text
    assert "subgraph" not in text
    defn = _defn(BACKBONE)
    text = render_traceability(
        defn, compute_digest(defn), [TraceRef("P-X", "P-X", False)], [], []
    ).text
    assert "subgraph col_motivation [Motivation]" in text
    assert "pr_0[P-X · not found]" in text
    assert "class pr_0 unknown" in text


def test_legend_lists_only_used_classes() -> None:
    text = render_structure(_defn(MESH), RenderOptions(include_legend=True)).text
    assert "subgraph legend [Legend]" in text
    assert "lg_role[Role]" in text
    assert "lg_mediator" not in text


# ── 936: conformance and transition views ──────────────────────────────────────────
def _conformance_inputs(direct: bool):  # type: ignore[no-untyped-def]
    from adp.patterns.conformance_models import PinIn, ScopeType
    from adp.patterns.engine import evaluate_pattern
    from adp.patterns.models import ElementType
    from adp.patterns.snapshot import Scope

    from .test_engine_fixtures import _estate

    snap = _estate(direct=direct)
    defn = _defn(BACKBONE)
    pins = [PinIn(role_key="backbone", element_type=ElementType.APPLICATION, element_id="hub")]
    report = evaluate_pattern(
        defn,
        snap,
        Scope(ScopeType.BUSINESS_DOMAIN, scope_ref="claims"),
        pins,
        digest=compute_digest(defn),
    )
    return defn, snap, report


@pytest.mark.parametrize("direct", [True, False], ids=["non_conformant", "conformant"])
def test_golden_conformance(direct: bool, golden) -> None:  # type: ignore[no-untyped-def]
    from adp.patterns.render import render_conformance

    defn, snap, report = _conformance_inputs(direct)
    view = render_conformance(defn, compute_digest(defn), report, snap)
    name = "non_conformant" if direct else "conformant"
    golden(f"conformance__{_stem(BACKBONE)}__{name}.mmd", view.text)


def test_conformance_marks_offenders_and_collapses_worst_first() -> None:
    from adp.patterns.render import render_conformance

    defn, snap, report = _conformance_inputs(direct=True)
    text = render_conformance(defn, compute_digest(defn), report, snap, max_per_role=2).text
    assert "Claims Core → Billing · FAIL" in text  # the C1 offender is shown first
    assert re.search(r"e_cross_domain_integration_more\[\+3 more\]", text)
    assert "subgraph r_backbone [Backbone · 1]" in text
    assert "class " in text and " fail" in text


def test_conformance_view_is_deterministic() -> None:
    from adp.patterns.render import render_conformance

    defn, snap, report = _conformance_inputs(direct=True)
    first = render_conformance(defn, compute_digest(defn), report, snap).text
    shuffled = report.model_copy(update={"findings": list(reversed(report.findings))})
    assert render_conformance(defn, compute_digest(defn), shuffled, snap).text == first


def test_golden_transition(golden) -> None:  # type: ignore[no-untyped-def]
    from adp.patterns.conformance_models import PlateauState
    from adp.patterns.render import render_transition

    defn = _defn(TRANSITION)
    state = PlateauState(reached="PL1", next="PL2", blocking=["C2"])
    view = render_transition(defn, compute_digest(defn), state)
    assert "-- blocked: C2 -->" in view.text
    assert re.search(r"class p_PL1 reached", view.text)
    assert re.search(r"class p_PL2 pending", view.text)
    golden(f"transition__{_stem(TRANSITION)}__PL1.mmd", view.text)


def test_transition_without_state_is_all_pending() -> None:
    from adp.patterns.render import render_transition

    defn = _defn(TRANSITION)
    text = render_transition(defn, compute_digest(defn), None).text
    assert "reached" not in text.split("classDef")[0]
    assert "class p_PL1,p_PL2 pending" in text
