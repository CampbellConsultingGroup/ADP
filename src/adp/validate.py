"""Reference integrity validation for ArchitectureDescription.

Called by the ArchitectureDescription model_validator. Kept separate so the
logic is independently testable without constructing a full model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from adp.models import ArchitectureDescription


@runtime_checkable
class _HasId(Protocol):
    id: str


def build_id_index(description: "ArchitectureDescription") -> dict[str, _HasId]:
    """Return a mapping of every entity ID to its entity across all collections.

    Raises ValueError listing all duplicate IDs found (collect-all strategy).
    """
    index: dict[str, _HasId] = {}
    duplicates: list[str] = []

    collections: list[list[_HasId]] = [
        description.requirements,  # type: ignore[list-item]
        description.elements,  # type: ignore[list-item]
        description.relationships,  # type: ignore[list-item]
        description.options,  # type: ignore[list-item]
        description.findings,  # type: ignore[list-item]
        description.verdicts,  # type: ignore[list-item]
        description.audit_log,  # type: ignore[list-item]
    ]

    for collection in collections:
        for entity in collection:
            eid = entity.id
            if eid in index:
                duplicates.append(eid)
            else:
                index[eid] = entity

    if duplicates:
        raise ValueError(f"Duplicate entity IDs detected: {', '.join(sorted(set(duplicates)))}")

    return index


def validate_references(
    description: "ArchitectureDescription",
    index: dict[str, _HasId],
) -> None:
    """Check every cross-entity reference resolves to an existing entity ID.

    Collects all missing references before raising a single ValueError so the
    caller receives the full list of problems at once.
    """
    errors: list[str] = []

    req_ids = {r.id for r in description.requirements}
    elm_ids = {e.id for e in description.elements}
    opt_ids = {o.id for o in description.options}
    subject_ids = elm_ids | opt_ids

    for element in description.elements:
        for ref in element.satisfies:
            if ref not in req_ids:
                errors.append(
                    f"Element {element.id!r}: satisfies references"
                    f" unknown Requirement {ref!r}"
                )

    for rel in description.relationships:
        if rel.source not in elm_ids:
            errors.append(
                f"Relationship {rel.id!r}: source references unknown Element {rel.source!r}"
            )
        if rel.target not in elm_ids:
            errors.append(
                f"Relationship {rel.id!r}: target references unknown Element {rel.target!r}"
            )

    for option in description.options:
        for ref in option.satisfies:
            if ref not in req_ids:
                errors.append(
                    f"SolutionOption {option.id!r}: satisfies references"
                    f" unknown Requirement {ref!r}"
                )

    for finding in description.findings:
        if finding.subject not in subject_ids:
            errors.append(
                f"Finding {finding.id!r}: subject references unknown"
                f" Element or SolutionOption {finding.subject!r}"
            )

    for verdict in description.verdicts:
        if verdict.option_id not in opt_ids:
            errors.append(
                f"Verdict {verdict.id!r}: option_id references unknown"
                f" SolutionOption {verdict.option_id!r}"
            )

    if errors:
        msg = "Referential integrity violations:\n" + "\n".join(f"  • {e}" for e in errors)
        raise ValueError(msg)
