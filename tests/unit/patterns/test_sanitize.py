"""Label sanitisation for the diagram-core flowchart dialect (935 FR-017, research D10)."""

from __future__ import annotations

import pytest

from adp.patterns.render import sanitize_label


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Domain App", "Domain App"),
        ('Say "hi"', "Say 'hi'"),
        ("a [b] {c} (d) <e> |f|", "a b c d e f"),
        ("x --> y", "x y"),
        ("a == b -. c .- d ~~ e", "a b c d e"),
        ("<script>alert(1)</script>", "script alert 1 /script"),
        ("/edge/", "edge"),
        ("R&D", "R and D"),
        ("hash # and ; semi", "hash and semi"),
        ("tabs\tand\nnewlines", "tabs and newlines"),
        ("   ", "?"),
        ("«platform» Backbone · 1", "«platform» Backbone · 1"),
        ("emoji 🚀 ok", "emoji 🚀 ok"),
    ],
)
def test_sanitize(raw: str, expected: str) -> None:
    assert sanitize_label(raw) == expected


def test_truncates_at_60_with_ellipsis() -> None:
    out = sanitize_label("x" * 200)
    assert len(out) == 60
    assert out.endswith("…")


def test_never_emits_dialect_metacharacters() -> None:
    nasty = '"]}) --> ==> -.-> ~~~ |x| [/a/] {{b}} ([c]) %% comment; #x'
    out = sanitize_label(nasty)
    for bad in ('"', "[", "]", "{", "}", "(", ")", "|", "-->", "==", "-.", ".-", "~~", ";", "#"):
        assert bad not in out, bad
