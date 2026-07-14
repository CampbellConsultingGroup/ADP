"""DesignImporter — re-imports an exported canonical model.json (ADP-SPEC-011 US5).

FR-007: exported artifacts must be re-importable with element-for-element equivalence.
v1 scope: only the current schema version is supported; no migration framework.
"""

from __future__ import annotations

import json

from adp.models import SCHEMA_VERSION, ArchitectureDescription
from adp.validate import build_id_index, validate_references


class DesignImporter:
    """Re-imports and validates an exported canonical model.json."""

    def import_from_json(self, json_str: str) -> ArchitectureDescription:
        """Parse and validate a canonical model JSON string.

        Raises ValueError on JSON parse error or schema version mismatch.
        Raises pydantic.ValidationError on schema-invalid content.
        Re-runs referential integrity validation (build_id_index + validate_references).
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

        found_version = data.get("schema_version", "<missing>")
        # Same-major versions are import-compatible: minor bumps are additive
        # (new Optional fields), so a 1.0.0 bundle loads cleanly into 1.1.0.
        # A different major implies a breaking change and is rejected.
        found_major = str(found_version).split(".", 1)[0]
        current_major = SCHEMA_VERSION.split(".", 1)[0]
        if found_major != current_major:
            raise ValueError(
                f"Schema version {found_version!r} is not supported; "
                f"current: {SCHEMA_VERSION!r}. "
                "Re-export from an ADP instance running a compatible major version, "
                "or wait for a migration."
            )

        # Pydantic raises ValidationError on schema violations
        design = ArchitectureDescription.model_validate(data)

        # Re-run referential integrity (redundant but explicit — FR-007)
        index = build_id_index(design)
        validate_references(design, index)

        return design
