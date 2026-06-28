"""Schema generator for ADP architecture descriptions.

This is the SOLE authorized writer of generated/architecture-description.schema.json.
Never edit that file by hand (ART-II / QG-02).

Usage:
    adp-generate               # regenerate the schema
    adp-generate --check       # exit non-zero if committed schema would change
    adp-generate --validate PATH  # validate a JSON file against the model
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from adp.models import SCHEMA_VERSION, ArchitectureDescription

_SCHEMA_PATH = Path("generated/architecture-description.schema.json")

_SCHEMA_ID = "https://adp.example.org/schemas/architecture-description.schema.json"


def generate() -> str:
    """Return the canonical JSON Schema as a sorted, deterministic string."""
    schema = ArchitectureDescription.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = _SCHEMA_ID
    schema["title"] = "Architecture Description"
    schema["schema_version"] = SCHEMA_VERSION
    return json.dumps(schema, sort_keys=True, indent=2) + "\n"


def check(committed_path: Path = _SCHEMA_PATH) -> None:
    """Fail with a diff if the committed schema diverges from generated output.

    Raises FileNotFoundError with a clear message if the committed file is absent.
    Calls sys.exit(1) on drift.
    """
    if not committed_path.exists():
        raise FileNotFoundError(
            f"Schema file not found: {committed_path}\n"
            "Run 'adp-generate' to produce it before running --check."
        )

    fresh = generate()
    committed = committed_path.read_text(encoding="utf-8")

    if fresh == committed:
        return

    diff = list(
        difflib.unified_diff(
            committed.splitlines(keepends=True),
            fresh.splitlines(keepends=True),
            fromfile=str(committed_path),
            tofile="<regenerated>",
        )
    )
    print(
        "Schema drift detected — run 'adp-generate' to regenerate.\n"
        f"Diff ({committed_path}):\n" + "".join(diff),
        file=sys.stderr,
    )
    sys.exit(1)


def validate(path: Path) -> None:
    """Validate a JSON file against the ArchitectureDescription model.

    Calls sys.exit(1) and prints errors if validation fails.
    """
    import pydantic

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        ArchitectureDescription.model_validate(data)
        print(f"✓ {path} is schema-valid and referentially intact.")
    except pydantic.ValidationError as exc:
        print(f"✗ Validation failed for {path}:\n{exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="adp-generate",
        description="Generate or verify the ADP JSON Schema.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed schema would change (CI drift gate).",
    )
    parser.add_argument(
        "--validate",
        metavar="PATH",
        type=Path,
        help="Validate a JSON file against the ArchitectureDescription model.",
    )
    args = parser.parse_args()

    if args.check:
        check()
    elif args.validate:
        validate(args.validate)
    else:
        schema_str = generate()
        try:
            _SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SCHEMA_PATH.write_text(schema_str, encoding="utf-8")
            print(f"✓ Schema written to {_SCHEMA_PATH}")
        except OSError as exc:
            print(f"Error writing schema to {_SCHEMA_PATH}: {exc}", file=sys.stderr)
            sys.exit(1)
