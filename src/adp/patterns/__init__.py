"""EA Patterns-as-Code — pattern metamodel and YAML format (934, PATTERN-01).

Public API (``specs/934-pattern-metamodel/contracts/python-api.md``). Specs 935–937
build on exactly these names; everything else in the package is private.
"""

from adp.patterns.cel import (
    PATTERN_CEL_FUNCTIONS,
    PATTERN_CEL_VARIABLES,
    CelEngine,
    CelError,
    CelResult,
    default_engine,
)
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
]
