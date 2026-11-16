"""940-org-units-geography (research R4): the committed ISO 3166 / UN M49 geography data file."""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "adp"
    / "organization"
    / "data"
    / "geographies.json"
)


def _load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_has_provenance() -> None:
    d = _load()
    assert "unstats.un.org" in d["source"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["retrieved"])


def test_five_m49_regions() -> None:
    regions = {r["name"]: r["m49"] for r in _load()["regions"]}
    assert regions == {
        "Africa": "002",
        "Americas": "019",
        "Asia": "142",
        "Europe": "150",
        "Oceania": "009",
    }


def test_country_codes_valid_unique_and_complete() -> None:
    d = _load()
    codes = [c["iso2"] for r in d["regions"] for c in r["countries"]] + [
        u["iso2"] for u in d["unassigned"]
    ]
    assert all(re.fullmatch(r"[A-Z]{2}", c) for c in codes)
    assert len(codes) == len(set(codes))
    assert 240 <= len(codes) <= 260


def test_unassigned_holds_codes_m49_lacks() -> None:
    assert {"TW", "AQ"} <= {u["iso2"] for u in _load()["unassigned"]}


def test_known_placements() -> None:
    region_of = {c["iso2"]: r["name"] for r in _load()["regions"] for c in r["countries"]}
    assert region_of["DE"] == "Europe"
    assert region_of["BR"] == "Americas"
    assert region_of["JP"] == "Asia"
    assert region_of["NG"] == "Africa"
    assert region_of["AU"] == "Oceania"
    assert region_of["NA"] == "Africa"  # Namibia's code must survive parsing
