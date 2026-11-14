"""EA pattern metamodel (934, data-model.md).

``PatternDefinition`` is the canonical, immutable in-memory form of one version of an
Enterprise Architecture pattern. It is pure: no persistence, no evaluation and — by
design — no import of the CEL engine, so ``model_json_schema()`` stays engine-free.

Cross-field rules V1–V6, V8 and V9 are *collected* by a single after-validator and
reported together (one ``PydanticCustomError`` carrying every issue); ``adp.patterns.parse``
expands them into individual :class:`PatternIssue` values. V7 (CEL compile) lives in
``adp.patterns.parse.validate_pattern``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic_core import PydanticCustomError

from adp.patterns.cardinality import CardinalityError, parse_cardinality

_FROZEN = ConfigDict(extra="forbid", frozen=True)

# ── Constrained strings ──────────────────────────────────────────────────────────
PatternKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){1,4}$")]
RoleKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
RelationshipId = Annotated[str, StringConstraints(pattern=r"^R[0-9]{1,3}$")]
ConstraintId = Annotated[str, StringConstraints(pattern=r"^C[0-9]{1,3}$")]
PlateauId = Annotated[str, StringConstraints(pattern=r"^PL[0-9]{1,2}$")]
SemVer = Annotated[str, StringConstraints(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")]
CelExpr = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
Label = Annotated[str, StringConstraints(min_length=1, max_length=60)]
Tag = Annotated[str, StringConstraints(min_length=1, max_length=40)]

# Shorthand accepted for cardinality in authored YAML (exact grammar in adp.patterns.cardinality).
CardinalityShorthand = Annotated[
    str,
    StringConstraints(pattern=r"^\s*\d+(\.\.(\d+|\*))?(\s+per\s+[a-z][a-z0-9_]{0,39})?\s*$"),
]

RESERVED_ROLE_KEYS = frozenset({"it", "scope", "bindings"})


# ── Enums ─────────────────────────────────────────────────────────────────────────
class PatternKind(StrEnum):
    REFERENCE_ARCHITECTURE = "reference-architecture"
    PORTFOLIO_RULE = "portfolio-rule"
    TRANSITION = "transition"
    ANTI_PATTERN = "anti-pattern"


class OwnerRole(StrEnum):
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    SOLUTION = "solution"
    TECHNICAL = "technical"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    IDENTITY = "identity"


class ElementType(StrEnum):
    """Each maps to an existing ADP registry entity (spec GT-1/GT-2)."""

    BUSINESS_CAPABILITY = "business_capability"
    VALUE_STREAM = "value_stream"
    BUSINESS_DOMAIN = "business_domain"
    APPLICATION = "application"
    INTEGRATION = "integration"
    TECHNICAL_CAPABILITY = "technical_capability"
    AGENT = "agent"


class RelationshipType(StrEnum):
    """``owns`` is deliberately absent: no registry evidence exists for it (spec GT-3)."""

    PUBLISHES = "publishes"
    CONSUMES = "consumes"
    DELIVERS = "delivers"
    SERVES = "serves"
    REALIZES = "realizes"
    DEPENDS_ON = "depends_on"
    INTEGRATES_WITH = "integrates_with"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Polarity(StrEnum):
    REQUIRE = "require"
    DETECT = "detect"


class PatternRelationType(StrEnum):
    REALIZES = "realizes"
    SPECIALIZES = "specializes"
    REPLACES = "replaces"
    CONFLICTS_WITH = "conflicts_with"
    REQUIRES = "requires"
    ALTERNATIVE_TO = "alternative_to"


class TransitionStrategy(StrEnum):
    STRANGLER = "strangler"
    PHASED_COEXISTENCE = "phased-coexistence"
    PARALLEL_RUN = "parallel-run"
    BIG_BANG = "big-bang"


class ViewKind(StrEnum):
    STRUCTURE = "structure"
    CONFORMANCE = "conformance"
    TRANSITION = "transition"
    CATALOG = "catalog"
    TRACEABILITY = "traceability"


class RenderHintKind(StrEnum):
    PROHIBITED_EDGE = "prohibited_edge"
    REQUIRED_EDGE = "required_edge"
    NOTE = "note"


# ── Sub-models ────────────────────────────────────────────────────────────────────
def _coerce_cardinality(value: Any) -> Any:
    """Accept the shorthand string (or a bare int) as well as the longhand mapping."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        value = str(value)
    if isinstance(value, str):
        try:
            lo, hi, per = parse_cardinality(value)
        except CardinalityError as exc:
            raise ValueError(str(exc)) from exc
        return {"min": lo, "max": hi, "per": per}
    return value


class Cardinality(BaseModel):
    model_config = _FROZEN

    min: int = Field(ge=0)
    max: int | None = Field(default=None, ge=1, description="None means unbounded")
    per: RoleKey | None = None

    @model_validator(mode="after")
    def _max_not_below_min(self) -> Cardinality:
        if self.max is not None and self.max < self.min:
            raise ValueError("cardinality max must be >= min")
        return self


class Role(BaseModel):
    model_config = _FROZEN

    element_type: ElementType
    cardinality: Annotated[
        Cardinality,
        BeforeValidator(
            _coerce_cardinality, json_schema_input_type=CardinalityShorthand | int | Cardinality
        ),
    ]
    selector: CelExpr | None = None
    label: Label | None = None
    stereotype: Annotated[str, StringConstraints(min_length=1, max_length=30)] | None = None
    description: str | None = None


class RoleRelationship(BaseModel):
    model_config = _FROZEN

    id: RelationshipId
    source: RoleKey
    target: RoleKey
    type: RelationshipType
    via: RoleKey | None = None
    label: Label | None = None
    required: bool = True


class RenderHint(BaseModel):
    model_config = _FROZEN

    kind: RenderHintKind
    source: RoleKey | None = None
    target: RoleKey | None = None
    label: Label


class Constraint(BaseModel):
    model_config = _FROZEN

    id: ConstraintId
    rule: Annotated[str, StringConstraints(min_length=1, max_length=280)]
    for_each: RoleKey | None = None
    expr: CelExpr
    polarity: Polarity = Polarity.REQUIRE
    severity: Severity = Severity.ERROR
    render_hint: RenderHint | None = None


class Motivation(BaseModel):
    model_config = _FROZEN

    context: str
    problem: str
    forces: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    liabilities: list[str] = Field(default_factory=list)
    principles: list[str] = Field(
        default_factory=list, description="Knowledge-base principle ids (resolved in 935)"
    )
    controls: list[str] = Field(
        default_factory=list, description="Compliance control ids (resolved in 935)"
    )


class Plateau(BaseModel):
    model_config = _FROZEN

    id: PlateauId
    name: Label
    description: str | None = None
    exit_criteria: list[ConstraintId] = Field(min_length=1)


class Transition(BaseModel):
    model_config = _FROZEN

    from_pattern: PatternKey
    strategy: TransitionStrategy
    plateaus: list[Plateau] = Field(min_length=1, max_length=10)


class PatternRelation(BaseModel):
    model_config = _FROZEN

    type: PatternRelationType
    target: PatternKey
    note: str | None = None


# ── Issues ────────────────────────────────────────────────────────────────────────
class PatternIssue(BaseModel):
    """One validation finding. ``path`` uses ``a.b[1].c`` notation; ``""`` is the whole document."""

    model_config = _FROZEN

    path: str
    code: str
    message: str
    severity: Severity = Severity.ERROR
    line: int | None = None
    column: int | None = None


# ── Root ──────────────────────────────────────────────────────────────────────────
class PatternDefinition(BaseModel):
    """One version of an EA pattern.

    There is no ``lifecycle`` field: that is registry state (GT-4).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="ADP EA Pattern",
    )

    pattern: PatternKey
    version: SemVer
    kind: PatternKind
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    summary: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    owner_role: OwnerRole
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    motivation: Motivation
    roles: dict[RoleKey, Role] = Field(
        min_length=1, max_length=25, description="Declared order is semantic"
    )
    relationships: list[RoleRelationship] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    transition: Transition | None = None
    relations: list[PatternRelation] = Field(default_factory=list)
    known_implementations: list[str] = Field(default_factory=list)
    views: list[ViewKind] = Field(default_factory=lambda: [ViewKind.STRUCTURE])

    @model_validator(mode="after")
    def _cross_field_rules(self) -> PatternDefinition:
        issues = collect_rule_issues(self)
        if issues:
            raise PydanticCustomError(
                "pattern_rules",
                "{count} pattern rule violation(s)",
                {"count": len(issues), "issues": issues},
            )
        return self


def collect_rule_issues(d: PatternDefinition) -> list[tuple[str, str, str]]:
    """Return ``(code, path, message)`` for every V1–V6/V8/V9 violation (V7 is in parse.py)."""
    out: list[tuple[str, str, str]] = []
    roles = d.roles

    def need_role(key: str | None, path: str) -> None:
        if key is not None and key not in roles:
            out.append(("V2.unknown_role", path, f"role '{key}' is not declared in roles"))

    # V1 reserved names
    for key in roles:
        if key in RESERVED_ROLE_KEYS:
            out.append(
                (
                    "V1.reserved_role",
                    f"roles.{key}",
                    f"'{key}' is a reserved name and cannot be a role key",
                )
            )

    # V2 references + V5 per-linkage
    linked: set[frozenset[str]] = set()
    for i, rel in enumerate(d.relationships):
        need_role(rel.source, f"relationships[{i}].source")
        need_role(rel.target, f"relationships[{i}].target")
        need_role(rel.via, f"relationships[{i}].via")
        linked.add(frozenset((rel.source, rel.target)))
    for key, role in roles.items():
        per = role.cardinality.per
        path = f"roles.{key}.cardinality.per"
        if per is None:
            continue
        if per not in roles:
            need_role(per, path)
        elif frozenset((key, per)) not in linked:
            out.append(
                (
                    "V5.per_unlinked",
                    path,
                    f"'per {per}' needs a relationship between '{key}' and '{per}'",
                )
            )
    for i, con in enumerate(d.constraints):
        need_role(con.for_each, f"constraints[{i}].for_each")
        if con.render_hint is not None:
            need_role(con.render_hint.source, f"constraints[{i}].render_hint.source")
            need_role(con.render_hint.target, f"constraints[{i}].render_hint.target")

    # V3 unique ids
    id_lists: list[tuple[str, list[str]]] = [
        ("relationships", [r.id for r in d.relationships]),
        ("constraints", [c.id for c in d.constraints]),
    ]
    for label, ids in id_lists:
        seen: set[str] = set()
        for i, item_id in enumerate(ids):
            if item_id in seen:
                out.append(("V3.duplicate_id", f"{label}[{i}].id", f"duplicate id '{item_id}'"))
            seen.add(item_id)

    # V4 transition presence + plateaus
    if d.kind == PatternKind.TRANSITION and d.transition is None:
        out.append(
            (
                "V4.transition_required",
                "transition",
                "a transition pattern must declare a transition",
            )
        )
    if d.kind != PatternKind.TRANSITION and d.transition is not None:
        out.append(
            (
                "V4.transition_forbidden",
                "transition",
                f"a {d.kind.value} pattern cannot declare a transition",
            )
        )
    if d.transition is not None:
        constraint_ids = {c.id for c in d.constraints}
        previous: set[str] = set()
        seen_plateaus: set[str] = set()
        for i, plateau in enumerate(d.transition.plateaus):
            path = f"transition.plateaus[{i}]"
            if plateau.id in seen_plateaus:
                out.append(
                    ("V3.duplicate_id", f"{path}.id", f"duplicate plateau id '{plateau.id}'")
                )
            seen_plateaus.add(plateau.id)
            criteria = set(plateau.exit_criteria)
            unknown = sorted(criteria - constraint_ids)
            if unknown:
                out.append(
                    (
                        "V4.unknown_criterion",
                        f"{path}.exit_criteria",
                        f"unknown constraint id(s): {', '.join(unknown)}",
                    )
                )
            elif not previous <= criteria:
                missing = ", ".join(sorted(previous - criteria))
                out.append(
                    (
                        "V4.not_cumulative",
                        f"{path}.exit_criteria",
                        f"must include the previous plateau's criteria ({missing})",
                    )
                )
            previous = criteria

    # V6 polarity by kind
    is_anti = d.kind == PatternKind.ANTI_PATTERN
    expected = Polarity.DETECT if is_anti else Polarity.REQUIRE
    for i, con in enumerate(d.constraints):
        if con.polarity != expected:
            out.append(
                (
                    "V6.polarity",
                    f"constraints[{i}].polarity",
                    f"{d.kind.value} constraints must use polarity '{expected.value}'",
                )
            )
    for i, relation in enumerate(d.relations):
        if is_anti and relation.type == PatternRelationType.REPLACES:
            out.append(
                (
                    "V6.antipattern_replaces",
                    f"relations[{i}]",
                    "an anti-pattern cannot replace another pattern",
                )
            )

    # V8 relations
    seen_rel: set[tuple[str, str]] = set()
    for i, relation in enumerate(d.relations):
        if relation.target == d.pattern:
            out.append(("V8.self_relation", f"relations[{i}]", "a pattern cannot relate to itself"))
        pair = (relation.type.value, relation.target)
        if pair in seen_rel:
            out.append(
                (
                    "V8.duplicate_relation",
                    f"relations[{i}]",
                    f"duplicate relation {pair[0]} → {pair[1]}",
                )
            )
        seen_rel.add(pair)

    # V9 owner role (relaxed by a future spec)
    if d.owner_role != OwnerRole.ENTERPRISE:
        out.append(
            (
                "V9.owner_role",
                "owner_role",
                "only owner_role 'enterprise' is accepted in this release",
            )
        )

    return out


class ParseResult(BaseModel):
    """Outcome of :func:`adp.patterns.parse.parse_pattern_yaml`."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    definition: PatternDefinition | None
    issues: list[PatternIssue]

    @property
    def ok(self) -> bool:
        return self.definition is not None and not any(
            i.severity == Severity.ERROR for i in self.issues
        )
