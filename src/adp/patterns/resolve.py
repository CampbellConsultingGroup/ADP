"""Reference resolution for stored patterns (935 FR-003, research D3). Pure, no I/O.

The store gathers lookup sets in a few batched queries and hands them to
:func:`resolve_references`. Unresolved references are warnings on import/update and errors
(blocking) on promotion to ``current``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from adp.patterns.models import PatternDefinition, PatternIssue, Severity


@dataclass(frozen=True)
class ReferencedIds:
    """Every external id a definition cites, in declared order."""

    principles: list[str] = field(default_factory=list)
    controls: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReferenceLookups:
    """The subset of referenced ids that exist (principles: active knowledge items of kind
    ``principle``; controls: compliance controls; patterns: registry families; applications)."""

    principles: frozenset[str] = frozenset()
    controls: frozenset[str] = frozenset()
    patterns: frozenset[str] = frozenset()
    applications: frozenset[str] = frozenset()


def referenced_ids(defn: PatternDefinition) -> ReferencedIds:
    return ReferencedIds(
        principles=list(defn.motivation.principles),
        controls=list(defn.motivation.controls),
        patterns=[r.target for r in defn.relations],
        applications=list(defn.known_implementations),
    )


_CHECKS: tuple[tuple[str, str, str, str], ...] = (
    # (code, lookup attr, path template, noun)
    ("R1.unresolved_principle", "principles", "motivation.principles[{i}]", "principle"),
    ("R2.unresolved_control", "controls", "motivation.controls[{i}]", "control"),
    ("R3.unresolved_relation", "patterns", "relations[{i}].target", "pattern family"),
    ("R4.unresolved_implementation", "applications", "known_implementations[{i}]", "application"),
)


def resolve_references(
    defn: PatternDefinition, lookups: ReferenceLookups, *, blocking: bool
) -> list[PatternIssue]:
    """One issue per reference that does not resolve, in a stable order (R1..R4, then index)."""
    refs = referenced_ids(defn)
    severity = Severity.ERROR if blocking else Severity.WARNING
    suffix = "" if blocking else "; it must resolve before the version can become current"
    issues: list[PatternIssue] = []
    for code, attr, path, noun in _CHECKS:
        known: frozenset[str] = getattr(lookups, attr)
        for i, ref in enumerate(getattr(refs, attr)):
            if ref not in known:
                issues.append(
                    PatternIssue(
                        path=path.format(i=i),
                        code=code,
                        message=f"{noun} '{ref}' does not exist{suffix}",
                        severity=severity,
                    )
                )
    return issues
