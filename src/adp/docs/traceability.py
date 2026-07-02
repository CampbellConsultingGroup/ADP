"""Traceability matrix generator — ADP-SPEC-011 US3.

ART-XI: every element traces to its requirements, provenance, and verdicts.
ART-XIV: output is deterministic (elements sorted by ID).
"""

from __future__ import annotations

from datetime import datetime, timezone

from adp.docs.models import TraceabilityEntry, TraceabilityMatrix
from adp.models import ArchitectureDescription


class TraceabilityGenerator:
    """Generates a machine-readable traceability matrix from the canonical model."""

    def generate(self, design: ArchitectureDescription) -> TraceabilityMatrix:
        """Build TraceabilityMatrix with one entry per element, sorted by element ID.

        v2 note: verdict_ids is always [] in v1. Populate from audit_log entries
        with action="validate" that reference this design version in a future spec.
        """
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        entries: list[TraceabilityEntry] = []
        for el in sorted(design.elements, key=lambda e: e.id):
            satisfied = list(el.satisfies or [])
            entries.append(TraceabilityEntry(
                element_id=el.id,
                element_name=el.name,
                element_kind=el.kind,
                satisfied_requirements=satisfied,
                provenance=el.provenance,
                verdict_ids=[],  # v2: populate verdict_ids from audit_log verdict entries
                is_orphan=len(satisfied) == 0,
            ))

        orphan_count = sum(1 for e in entries if e.is_orphan)

        return TraceabilityMatrix(
            design_id=design.id,
            schema_version=design.schema_version,
            generated_at=generated_at,
            total_elements=len(entries),
            orphan_count=orphan_count,
            entries=entries,
        )
