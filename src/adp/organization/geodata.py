"""Geography seed rows from the committed ISO 3166 / UN M49 data file (940, research R4).

Pure and dependency-free on purpose: migration 048 and the tests both call ``geography_seed_rows``,
so the seeded tree can't drift between them, and the migration doesn't import the store.

Stable ids let later specs refer to known places:
    geo-001       Global (the M49 "World" code)
    geo-m49-NNN   a region, by its M49 code (e.g. geo-m49-150 Europe)
    geo-XX        a country, by its ISO 3166-1 alpha-2 code (e.g. geo-DE)
Countries the source places in no region (e.g. AQ, TW) sit directly under Global.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).resolve().parent / "data" / "geographies.json"

GLOBAL_ID = "geo-001"


def region_id(m49: str) -> str:
    return f"geo-m49-{m49}"


def country_id(iso2: str) -> str:
    return f"geo-{iso2}"


def geography_seed_rows(now: datetime) -> list[dict[str, Any]]:
    """Every seeded geography row, parents before children."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    def row(id_: str, name: str, level: int, parent: str | None, code: str | None, m49: str | None):
        return {
            "id": id_,
            "name": name,
            "code": code,
            "m49": m49,
            "parent_id": parent,
            "level": level,
            "created_at": now,
            "updated_at": now,
        }

    rows = [row(GLOBAL_ID, "Global", 1, None, None, "001")]
    for region in data["regions"]:
        rid = region_id(region["m49"])
        rows.append(row(rid, region["name"], 2, GLOBAL_ID, None, region["m49"]))
    for region in data["regions"]:
        rid = region_id(region["m49"])
        for c in region["countries"]:
            rows.append(
                row(country_id(c["iso2"]), c["name"], 3, rid, c["iso2"], c.get("m49") or None)
            )
    for c in data["unassigned"]:
        # No region in the source: directly under Global, still a country (level 3 by kind).
        rows.append(
            row(country_id(c["iso2"]), c["name"], 3, GLOBAL_ID, c["iso2"], c.get("m49") or None)
        )
    return rows
