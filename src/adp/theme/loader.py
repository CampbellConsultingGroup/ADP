"""ThemeLoader: load and validate the locked C4 theme artifact."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from adp.theme.models import LockedTheme, ThemeValidationError

_HERE = Path(__file__).parent
THEME_PATH = _HERE / "c4-theme.json"
SCHEMA_PATH = _HERE / "c4-theme.schema.json"


class ThemeLoader:
    """Loads c4-theme.json, validates it against c4-theme.schema.json, and returns LockedTheme."""

    def __init__(
        self,
        theme_path: Path = THEME_PATH,
        schema_path: Path = SCHEMA_PATH,
    ) -> None:
        self._theme_path = theme_path
        self._schema_path = schema_path

    def _load_schema(self) -> dict:  # type: ignore[type-arg]
        return json.loads(self._schema_path.read_text(encoding="utf-8"))

    def validate_raw(self, data: dict) -> None:  # type: ignore[type-arg]
        """Validate a raw theme dict against the JSON Schema.

        Raises ThemeValidationError (NOT jsonschema.ValidationError) on failure
        so callers have a stable exception type to catch.
        """
        schema = self._load_schema()
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            raise ThemeValidationError(
                f"Theme validation failed: {exc.message}",
                failing_constraint=exc.validator or "unknown",
            ) from exc

    def load(self) -> LockedTheme:
        """Read c4-theme.json, validate against schema, and return LockedTheme.

        Raises ThemeValidationError if the theme file is missing, not valid JSON,
        or fails JSON Schema validation. Never returns a non-locked theme.
        """
        try:
            raw = self._theme_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ThemeValidationError(
                f"Cannot read theme file {self._theme_path}: {exc}",
                failing_constraint="file_not_found",
            ) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ThemeValidationError(
                f"Theme file is not valid JSON: {exc}",
                failing_constraint="json_decode",
            ) from exc

        self.validate_raw(data)
        return LockedTheme.model_validate(data)

    def load_and_validate(self) -> LockedTheme:
        """Convenience wrapper — identical to load()."""
        return self.load()
