"""Pattern binding and conformance engine (936 FR-008–FR-017, research.md D4/D5). Pure.

Inputs: a :class:`PatternDefinition`, a :class:`PortfolioSnapshot`, a :class:`Scope`, pins and a
:class:`CelEngine`. Output: findings, bindings, a derived status and (for transition patterns) a
plateau state. Nothing is stored; the same inputs always give the same report.

Order of findings: binding (B*, S:*), implicit cardinality (K:*), relationship evidence (E:*),
declared constraints in declared order, limits (L1).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from adp.patterns.cel import CelEngine, default_engine
from adp.patterns.conformance_models import (
    AdoptionScope,
    BindingResult,
    ConformanceReport,
    ConformanceStatus,
    DiscoveryReport,
    ElementRef,
    EvalLimits,
    Finding,
    FindingKind,
    PinIn,
    PlateauState,
    RoleBinding,
    ScopeType,
)
from adp.patterns.models import (
    ElementType,
    PatternDefinition,
    PatternKind,
    Polarity,
    RelationshipType,
    RoleRelationship,
    Severity,
)
from adp.patterns.snapshot import SCOPE_KEYS, Element, PortfolioSnapshot, Scope, in_scope

_INTEGRATION_RELS = {
    RelationshipType.PUBLISHES,
    RelationshipType.DELIVERS,
    RelationshipType.CONSUMES,
    RelationshipType.INTEGRATES_WITH,
    RelationshipType.DEPENDS_ON,
}


class Budget:
    """Element-evaluation budget for one report (FR-015)."""

    def __init__(self, limit: int) -> None:
        self.remaining = limit

    def spend(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


# ── Helpers ─────────────────────────────────────────────────────────────────────────────
def _ref(snap: PortfolioSnapshot, etype: ElementType, eid: str) -> ElementRef:
    return ElementRef(type=etype, id=eid, name=snap.name(etype, eid))


def _finding(
    code: str,
    kind: FindingKind,
    severity: Severity,
    rule: str,
    refs: Iterable[ElementRef] = (),
    limits: EvalLimits | None = None,
) -> Finding:
    cap = (limits or EvalLimits()).max_element_refs
    refs = list(refs)
    return Finding(
        code=code,
        kind=kind,
        severity=severity,
        rule=rule,
        element_refs=refs[:cap],
        element_count=len(refs),
        truncated=len(refs) > cap,
    )


def _label(defn: PatternDefinition, role_key: str) -> str:
    role = defn.roles[role_key]
    return role.label or role_key.replace("_", " ").title()


class _Context:
    """Per-report evaluation state shared by bindings and constraints."""

    def __init__(
        self,
        defn: PatternDefinition,
        snap: PortfolioSnapshot,
        scope: Scope,
        cel: CelEngine,
        budget: Budget,
    ) -> None:
        self.defn = defn
        self.snap = snap
        self.scope = scope
        self.cel = cel
        self.budget = budget
        self.bound: dict[str, list[str]] = {}
        self._compiled: dict[str, Any] = {}
        self._scope_lists: dict[str, list[Element]] | None = None

    # CEL plumbing -------------------------------------------------------------------------
    def _role_elements(self, role_key: str) -> list[Element]:
        role = self.defn.roles.get(role_key)
        if role is None:
            return []
        return [
            el
            for eid in self.bound.get(role_key, [])
            if (el := self.snap.element(role.element_type, eid)) is not None
        ]

    def _activation(self, it: Element) -> dict[str, Any]:
        if self._scope_lists is None:
            self._scope_lists = {
                key: [
                    self.snap.of_type(etype)[eid] for eid in in_scope(self.snap, self.scope, etype)
                ]
                for etype, key in SCOPE_KEYS.items()
            }
        return {
            "it": it,
            "bindings": {k: self._role_elements(k) for k in self.defn.roles},
            "scope": self._scope_lists,
        }

    def _functions(self) -> dict[str, Any]:
        def role(key: str) -> list[str]:
            return list(self.bound.get(key, []))

        def bound(element: dict[str, Any], key: str) -> bool:
            return element.get("id") in self.bound.get(key, [])

        return {"role": role, "bound": bound}

    def run(self, expr: str, it: Element) -> tuple[str, Any]:
        """Evaluate one expression. Returns (outcome, value) where outcome is one of
        ``bool``, ``non_bool``, ``missing``, ``unavailable``, ``budget``, ``error``."""
        if not self.budget.spend():
            return "budget", None
        program = self._compiled.get(expr)
        if program is None:
            if self.cel.compile_check(expr):
                return "error", None
            program = self._compiled[expr] = self.cel.compile(expr)
        result = self.cel.evaluate(program, self._activation(it), self._functions())
        if result.error == "budget_exceeded":
            return "budget", None
        if result.error == "missing_key":
            if _mentions(expr, self.snap.unavailable_fields):
                return "unavailable", None
            return "error", None
        if result.error is not None:
            return "error", None
        if not isinstance(result.value, bool):
            return "non_bool", result.value
        return "bool", result.value


def _mentions(expr: str, fields: frozenset[str]) -> bool:
    return any(re.search(rf"\b{re.escape(f)}\b", expr) for f in fields)


# ── Bindings (FR-008) ───────────────────────────────────────────────────────────────────
def _resolve(ctx: _Context, pins: list[PinIn]) -> BindingResult:
    snap, defn = ctx.snap, ctx.defn
    findings: list[Finding] = []
    roles: list[RoleBinding] = []
    pins_by_role: dict[str, list[PinIn]] = {}
    for pin in pins:
        pins_by_role.setdefault(pin.role_key, []).append(pin)

    for key, role in defn.roles.items():
        etype = role.element_type
        chosen: list[str] = []
        role_pins = pins_by_role.get(key, [])
        if role_pins:
            for pin in role_pins:
                if snap.element(etype, pin.element_id) is None:
                    findings.append(
                        _finding(
                            "B3.dangling_pin",
                            FindingKind.BINDING,
                            Severity.ERROR,
                            f"Pinned {etype.value} '{pin.element_id}' for role '{key}' "
                            "no longer exists",
                            [ElementRef(type=etype, id=pin.element_id, name=pin.element_id)],
                        )
                    )
                    continue
                chosen.append(pin.element_id)
                if role.selector:
                    outcome, value = ctx.run(role.selector, snap.of_type(etype)[pin.element_id])
                    if not (outcome == "bool" and value):
                        findings.append(
                            _finding(
                                "B2.pin_fails_selector",
                                FindingKind.BINDING,
                                Severity.WARNING,
                                f"Pinned element does not match the selector of role '{key}'",
                                [_ref(snap, etype, pin.element_id)],
                            )
                        )
        else:
            errored: list[str] = []
            for eid in in_scope(snap, ctx.scope, etype):
                if not role.selector:
                    chosen.append(eid)
                    continue
                outcome, value = ctx.run(role.selector, snap.of_type(etype)[eid])
                if outcome == "bool":
                    if value:
                        chosen.append(eid)
                else:
                    errored.append(eid)
            if errored:
                findings.append(
                    _finding(
                        f"S:{key}",
                        FindingKind.EVALUATION_ERROR,
                        Severity.ERROR,
                        f"The selector of role '{key}' could not be evaluated for some elements",
                        [_ref(snap, etype, e) for e in errored],
                    )
                )
        unique = sorted(set(chosen), key=lambda e: (snap.name(etype, e), e))
        ctx.bound[key] = unique
        roles.append(
            RoleBinding(
                role_key=key,
                element_type=etype,
                label=_label(defn, key),
                elements=[_ref(snap, etype, e) for e in unique],
                count=len(unique),
            )
        )
    return BindingResult(roles=roles, findings=findings)


def resolve_bindings(
    defn: PatternDefinition,
    snapshot: PortfolioSnapshot,
    scope: Scope,
    pins: list[PinIn],
    cel: CelEngine,
    budget: Budget,
) -> BindingResult:
    """Bind registry elements to every role (pins authoritative; spec GT-8)."""
    return _resolve(_Context(defn, snapshot, scope, cel, budget), pins)


# ── Evidence (FR-012) ───────────────────────────────────────────────────────────────────
def _supported(rel: RelationshipType, src: ElementType, dst: ElementType) -> bool:
    if rel in _INTEGRATION_RELS:
        return src == dst == ElementType.APPLICATION
    if rel == RelationshipType.SERVES:
        return src == ElementType.APPLICATION and dst == ElementType.BUSINESS_CAPABILITY
    if rel == RelationshipType.REALIZES:
        return src == ElementType.APPLICATION and dst == ElementType.TECHNICAL_CAPABILITY
    return False


def _evidence(snap: PortfolioSnapshot, rel: RelationshipType, s: str, t: str) -> bool:
    if rel in (RelationshipType.PUBLISHES, RelationshipType.DELIVERS):
        return bool(snap.integrations_between(s, t))
    if rel == RelationshipType.CONSUMES:
        return bool(snap.integrations_between(t, s))
    if rel in (RelationshipType.INTEGRATES_WITH, RelationshipType.DEPENDS_ON):
        return bool(snap.integrations_between(s, t) or snap.integrations_between(t, s))
    if rel == RelationshipType.SERVES:
        return snap.serves(s, t)
    if rel == RelationshipType.REALIZES:
        return snap.realizes(s, t)
    return False


def _implicit(ctx: _Context, limits: EvalLimits) -> list[Finding]:
    defn, snap = ctx.defn, ctx.snap
    out: list[Finding] = []

    # K:<role> — bound count within cardinality.
    for key, role in defn.roles.items():
        card = role.cardinality
        n = len(ctx.bound.get(key, []))
        if n < card.min or (card.max is not None and n > card.max):
            span = f"{card.min}..{'*' if card.max is None else card.max}"
            refs = [_ref(snap, role.element_type, e) for e in ctx.bound.get(key, [])]
            out.append(
                _finding(
                    f"K:{key}",
                    FindingKind.VIOLATION,
                    Severity.ERROR,
                    f"Role '{_label(defn, key)}' needs {span} bound elements; found {n}",
                    refs if card.max is not None and n > card.max else [],
                    limits,
                )
            )

    # K:<role>/<per> — per-element cardinality through the linking relationship's evidence.
    for key, role in defn.roles.items():
        per = role.cardinality.per
        if per is None:
            continue
        link = _link(defn, key, per)
        if link is None:
            continue
        card = role.cardinality
        per_type = defn.roles[per].element_type
        offenders = []
        for p in ctx.bound.get(per, []):
            count = 0
            for e in ctx.bound.get(key, []):
                s, t = (e, p) if link.source == key else (p, e)
                if _evidence(snap, link.type, s, t):
                    count += 1
            if count < card.min or (card.max is not None and count > card.max):
                offenders.append(_ref(snap, per_type, p))
        if offenders:
            span = f"{card.min}..{'*' if card.max is None else card.max}"
            out.append(
                _finding(
                    f"K:{key}/{per}",
                    FindingKind.VIOLATION,
                    Severity.ERROR,
                    f"Each '{_label(defn, per)}' needs {span} '{_label(defn, key)}'",
                    offenders,
                    limits,
                )
            )

    # E:<rel> — evidence for required relationships (via: first hop to the mediator).
    for rel in defn.relationships:
        if not rel.required:
            continue
        target_role = rel.via or rel.target
        src_type = defn.roles[rel.source].element_type
        dst_type = defn.roles[target_role].element_type
        if not _supported(rel.type, src_type, dst_type):
            out.append(
                _finding(
                    f"E:{rel.id}",
                    FindingKind.UNVERIFIABLE,
                    Severity.INFO,
                    f"No registry evidence exists for '{rel.type.value}' between "
                    f"{src_type.value} and {dst_type.value}",
                )
            )
            continue
        targets = ctx.bound.get(target_role, [])
        offenders = [
            _ref(snap, src_type, s)
            for s in ctx.bound.get(rel.source, [])
            if not any(_evidence(snap, rel.type, s, t) for t in targets if t != s)
        ]
        if offenders:
            via = f" via '{_label(defn, rel.via)}'" if rel.via else ""
            out.append(
                _finding(
                    f"E:{rel.id}",
                    FindingKind.VIOLATION,
                    Severity.ERROR,
                    f"Each '{_label(defn, rel.source)}' must {rel.type.value} to "
                    f"'{_label(defn, rel.target)}'{via}",
                    offenders,
                    limits,
                )
            )
    return out


def _link(defn: PatternDefinition, a: str, b: str) -> RoleRelationship | None:
    for rel in defn.relationships:
        if {rel.source, rel.target} == {a, b}:
            return rel
    return None


# ── Declared constraints (FR-010) ───────────────────────────────────────────────────────
def _declared(ctx: _Context, limits: EvalLimits) -> tuple[list[Finding], list[Finding]]:
    defn, snap = ctx.defn, ctx.snap
    findings: list[Finding] = []
    limit_findings: list[Finding] = []
    for c in defn.constraints:
        if c.for_each:
            etype = defn.roles[c.for_each].element_type
            subjects = [(eid, snap.of_type(etype)[eid]) for eid in ctx.bound.get(c.for_each, [])]
        else:
            etype = None
            subjects = [("", {})]
        hits: list[str] = []
        errors: list[str] = []
        unavailable: list[str] = []
        exhausted = False
        for eid, element in subjects:
            outcome, value = ctx.run(c.expr, element)
            if outcome == "budget":
                exhausted = True
                break
            if outcome == "bool":
                if (c.polarity == Polarity.REQUIRE and value is False) or (
                    c.polarity == Polarity.DETECT and value is True
                ):
                    hits.append(eid)
            elif outcome == "unavailable":
                unavailable.append(eid)
            else:
                errors.append(eid)

        def refs(ids: list[str]) -> list[ElementRef]:
            return [_ref(snap, etype, i) for i in ids if i] if etype else []

        if hits:
            kind = FindingKind.VIOLATION if c.polarity == Polarity.REQUIRE else FindingKind.MATCH
            findings.append(_finding(c.id, kind, c.severity, c.rule, refs(hits), limits))
        if errors:
            findings.append(
                _finding(
                    c.id,
                    FindingKind.EVALUATION_ERROR,
                    Severity.ERROR,
                    f"{c.rule} (expression could not be evaluated)",
                    refs(errors),
                    limits,
                )
            )
        if unavailable:
            findings.append(
                _finding(
                    c.id,
                    FindingKind.FIELD_UNAVAILABLE,
                    c.severity,
                    f"{c.rule} (needs data you are not permitted to read)",
                    refs(unavailable),
                    limits,
                )
            )
        if exhausted:
            limit_findings.append(
                _finding(
                    "L1.limit_exceeded",
                    FindingKind.LIMIT,
                    Severity.ERROR,
                    f"Evaluation limit reached while evaluating {c.id}; {c.id} is incomplete",
                )
            )
    return findings, limit_findings


# ── Status and plateau (FR-013/FR-014) ─────────────────────────────────────────────────
_FAILING = {FindingKind.VIOLATION, FindingKind.MATCH, FindingKind.BINDING, FindingKind.LIMIT}


def compute_conformance_status(
    findings: list[Finding], bindings: BindingResult
) -> ConformanceStatus:
    """Minimum aggregation, first match wins. ``match`` findings (an adopted anti-pattern's
    detections) count like violations."""
    if not any(r.count for r in bindings.roles):
        return ConformanceStatus.NOT_APPLICABLE
    if any(f.severity == Severity.ERROR and f.kind in _FAILING for f in findings):
        return ConformanceStatus.NON_CONFORMANT
    if any(
        f.kind == FindingKind.EVALUATION_ERROR
        or (f.kind == FindingKind.FIELD_UNAVAILABLE and f.severity == Severity.ERROR)
        for f in findings
    ):
        return ConformanceStatus.INDETERMINATE
    if any(
        f.severity == Severity.WARNING and f.kind in (FindingKind.VIOLATION, FindingKind.MATCH)
        for f in findings
    ):
        return ConformanceStatus.CONFORMANT_WITH_WARNINGS
    return ConformanceStatus.CONFORMANT


_BLOCKING = {
    FindingKind.VIOLATION,
    FindingKind.MATCH,
    FindingKind.EVALUATION_ERROR,
    FindingKind.FIELD_UNAVAILABLE,
    FindingKind.LIMIT,
}


def compute_transition_plateau(
    defn: PatternDefinition, findings: list[Finding]
) -> PlateauState | None:
    """Highest consecutively reached plateau of a transition pattern; None for other kinds."""
    if defn.kind != PatternKind.TRANSITION or defn.transition is None:
        return None
    failing = {f.code for f in findings if f.kind in _BLOCKING}
    reached: str | None = None
    for plateau in defn.transition.plateaus:
        blocking = [c for c in plateau.exit_criteria if c in failing]
        if blocking:
            return PlateauState(reached=reached, next=plateau.id, blocking=blocking)
        reached = plateau.id
    return PlateauState(reached=reached, next=None, blocking=[])


# ── Entry points ────────────────────────────────────────────────────────────────────────
def _run(
    defn: PatternDefinition,
    snap: PortfolioSnapshot,
    scope: Scope,
    pins: list[PinIn],
    cel: CelEngine,
    limits: EvalLimits,
) -> tuple[BindingResult, list[Finding]]:
    ctx = _Context(defn, snap, scope, cel, Budget(limits.max_element_evaluations))
    bindings = _resolve(ctx, pins)
    declared, limit_findings = _declared(ctx, limits)
    findings = [*bindings.findings, *_implicit(ctx, limits), *declared, *limit_findings]
    return bindings, findings


def _adoption_scope(scope: Scope) -> AdoptionScope:
    return AdoptionScope(
        scope_type=scope.scope_type,
        scope_ref=scope.scope_ref,
        member_ids=sorted(scope.member_ids)
        if scope.scope_type == ScopeType.APPLICATION_SET
        else [],
    )


def evaluate_pattern(
    defn: PatternDefinition,
    snapshot: PortfolioSnapshot,
    scope: Scope,
    pins: list[PinIn],
    *,
    engine: CelEngine | None = None,
    limits: EvalLimits | None = None,
    digest: str | None = None,
    adoption_id: str | None = None,
    now: datetime | None = None,
) -> ConformanceReport:
    """Full conformance report for one pattern version against one scope."""
    limits = limits or EvalLimits()
    bindings, findings = _run(defn, snapshot, scope, pins, engine or default_engine(), limits)
    return ConformanceReport(
        adoption_id=adoption_id,
        pattern_key=defn.pattern,
        version=defn.version,
        digest=digest,
        evaluated_at=now or datetime.now(timezone.utc),
        scope=_adoption_scope(scope),
        bindings=bindings.roles,
        findings=findings,
        status=compute_conformance_status(findings, bindings),
        plateau=compute_transition_plateau(defn, findings),
    )


def not_applicable_report(
    pattern_key: str, scope: Scope, finding: Finding, adoption_id: str | None = None
) -> ConformanceReport:
    """A report for an adoption with nothing to evaluate (B1: no current version)."""
    return ConformanceReport(
        adoption_id=adoption_id,
        pattern_key=pattern_key,
        evaluated_at=datetime.now(timezone.utc),
        scope=_adoption_scope(scope),
        findings=[finding],
        status=ConformanceStatus.NOT_APPLICABLE,
    )


def discover(
    defn: PatternDefinition,
    snapshot: PortfolioSnapshot,
    *,
    engine: CelEngine | None = None,
    limits: EvalLimits | None = None,
    digest: str,
    now: datetime | None = None,
) -> DiscoveryReport:
    """Anti-pattern matches across the whole portfolio, by selectors only (FR-017)."""
    limits = limits or EvalLimits()
    _, findings = _run(
        defn, snapshot, Scope(ScopeType.PORTFOLIO), [], engine or default_engine(), limits
    )
    matches = [f for f in findings if f.kind == FindingKind.MATCH]
    return DiscoveryReport(
        pattern_key=defn.pattern,
        version=defn.version,
        digest=digest,
        evaluated_at=now or datetime.now(timezone.utc),
        matches=matches,
        match_count=sum(m.element_count or 1 for m in matches),
    )
