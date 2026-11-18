"""ADP-blp.12: every request that takes a confirmation_id says what it is.

The field reads like a control and is only an audit annotation (see adp.authz.confirmation).
A new governed action that adds the field without the shared description would bring the
misleading reading back.
"""

from __future__ import annotations

import json
from pathlib import Path

from adp.authz.confirmation import CONFIRMATION_ID_DESCRIPTION

_OPENAPI = Path(__file__).resolve().parents[2] / "generated" / "openapi.json"


def test_every_request_confirmation_id_carries_the_shared_description():
    schemas = json.loads(_OPENAPI.read_text())["components"]["schemas"]
    # Request bodies only: a response that echoes a stored confirmation id (pattern lifecycle
    # history) is a record of what was sent, not an input.
    request_bodies = {
        name: schema["properties"]["confirmation_id"]
        for name, schema in schemas.items()
        if "confirmation_id" in schema.get("properties", {})
        and "confirmation_id" in schema.get("required", [])
        and "actor" not in schema["properties"]
    }
    assert len(request_bodies) >= 8, sorted(request_bodies)
    undocumented = sorted(
        name
        for name, field in request_bodies.items()
        if field.get("description") != CONFIRMATION_ID_DESCRIPTION
    )
    assert undocumented == []


def test_the_description_does_not_claim_verification():
    text = CONFIRMATION_ID_DESCRIPTION.lower()
    assert "not issued or verified by the server" in text
    assert "does not authorise" in text
