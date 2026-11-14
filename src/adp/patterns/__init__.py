"""EA Patterns-as-Code — pattern metamodel and YAML format (934, PATTERN-01).

Public API (``specs/934-pattern-metamodel/contracts/python-api.md``). Specs 935–937
build on exactly these names; everything else in the package is private.

935-pattern-registry adds the pure registry names below (lifecycle table, knowledge projection,
flowchart views). The DB-backed ``adp.patterns.store`` and ``adp.patterns.router`` are imported
directly by their callers and deliberately not re-exported here.
"""

from adp.patterns.cel import (
    PATTERN_CEL_FUNCTIONS,
    PATTERN_CEL_VARIABLES,
    CelEngine,
    CelError,
    CelResult,
    default_engine,
)
from adp.patterns.lifecycle import allowed_transitions, allowed_transitions_ordered, is_allowed
from adp.patterns.models import (
    Cardinality,
    Constraint,
    ElementType,
    Motivation,
    OwnerRole,
    ParseResult,
    PatternDefinition,
    PatternIssue,
    PatternKind,
    PatternRelation,
    PatternRelationType,
    Plateau,
    Polarity,
    RelationshipType,
    RenderHint,
    Role,
    RoleRelationship,
    Severity,
    Transition,
    TransitionStrategy,
    ViewKind,
)
from adp.patterns.parse import (
    compute_digest,
    parse_pattern_yaml,
    to_canonical_json,
    to_canonical_yaml,
    validate_pattern,
)
from adp.patterns.projection import ProjectedItem, build_projection, knowledge_kind_for
from adp.patterns.registry_models import (
    ImportStatus,
    LifecycleTransitionRequest,
    PatternLifecycle,
    PatternViewKind,
)
from adp.patterns.render import (
    CatalogEdge,
    CatalogNode,
    RenderedView,
    RenderOptions,
    TraceRef,
    render_catalog,
    render_structure,
    render_traceability,
    sanitize_label,
)

__all__ = [
    "PATTERN_CEL_FUNCTIONS",
    "PATTERN_CEL_VARIABLES",
    "Cardinality",
    "CelEngine",
    "CelError",
    "CelResult",
    "Constraint",
    "ElementType",
    "Motivation",
    "OwnerRole",
    "ParseResult",
    "PatternDefinition",
    "PatternIssue",
    "PatternKind",
    "PatternRelation",
    "PatternRelationType",
    "Plateau",
    "Polarity",
    "RelationshipType",
    "RenderHint",
    "Role",
    "RoleRelationship",
    "Severity",
    "Transition",
    "TransitionStrategy",
    "ViewKind",
    "compute_digest",
    "default_engine",
    "parse_pattern_yaml",
    "to_canonical_json",
    "to_canonical_yaml",
    "validate_pattern",
    # 935-pattern-registry
    "CatalogEdge",
    "CatalogNode",
    "ImportStatus",
    "LifecycleTransitionRequest",
    "PatternLifecycle",
    "PatternViewKind",
    "ProjectedItem",
    "RenderOptions",
    "RenderedView",
    "TraceRef",
    "allowed_transitions",
    "allowed_transitions_ordered",
    "build_projection",
    "is_allowed",
    "knowledge_kind_for",
    "render_catalog",
    "render_structure",
    "render_traceability",
    "sanitize_label",
]
