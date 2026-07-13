"""Traceability query functions operating on deserialized content dicts (FR-005).

All functions accept the deserialized ArchitectureDescription content dict and
return typed model instances. No database I/O — pure Python logic, independently
testable without a running database.
"""

from __future__ import annotations

from adp.models import (
    ArchitectureDescription,
    Element,
    Requirement,
    SolutionOption,
    Verdict,
)
from adp.store.records import VerdictChain


def _description_from(content: dict) -> ArchitectureDescription:  # type: ignore[type-arg]
    return ArchitectureDescription.model_validate(content)


def query_satisfies(content: dict, requirement_id: str) -> list[Element]:  # type: ignore[type-arg]
    """Return elements whose satisfies list contains requirement_id."""
    desc = _description_from(content)
    return [e for e in desc.elements if requirement_id in e.satisfies]


def query_orphan_requirements(content: dict) -> list[Requirement]:  # type: ignore[type-arg]
    """Return requirements satisfied by no element and no option."""
    desc = _description_from(content)
    satisfied: set[str] = set()
    for element in desc.elements:
        satisfied.update(element.satisfies)
    for option in desc.options:
        satisfied.update(option.satisfies)
    return [r for r in desc.requirements if r.id not in satisfied]


def query_verdict_chain(content: dict, option_id: str) -> VerdictChain:  # type: ignore[type-arg]
    """Return full traceability chain for one SolutionOption.

    Raises EntityNotFoundError if option_id is not found.
    """
    from adp.store.store import EntityNotFoundError

    desc = _description_from(content)

    option: SolutionOption | None = next(
        (o for o in desc.options if o.id == option_id), None
    )
    if option is None:
        raise EntityNotFoundError(option_id, f"SolutionOption {option_id!r} not found in design")

    req_ids = set(option.satisfies)
    satisfies_requirements = [r for r in desc.requirements if r.id in req_ids]
    satisfying_elements = [
        e for e in desc.elements if any(rid in e.satisfies for rid in req_ids)
    ]
    verdict: Verdict | None = next(
        (v for v in desc.verdicts if v.option_id == option_id), None
    )

    return VerdictChain(
        option=option,
        satisfies_requirements=satisfies_requirements,
        satisfying_elements=satisfying_elements,
        verdict=verdict,
    )


def query_by_provenance(content: dict, provenance_value: str) -> list[Element | SolutionOption]:  # type: ignore[type-arg]
    """Return elements and options whose provenance field equals provenance_value."""
    desc = _description_from(content)
    results: list[Element | SolutionOption] = []
    results.extend(e for e in desc.elements if e.provenance == provenance_value)
    results.extend(o for o in desc.options if o.provenance == provenance_value)
    return results


def query_relationships(content: dict, element_id: str) -> list:  # type: ignore[type-arg]
    """Return all relationships where source or target equals element_id."""

    desc = _description_from(content)
    return [
        r for r in desc.relationships if r.source == element_id or r.target == element_id
    ]
