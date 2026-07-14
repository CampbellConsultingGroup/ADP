"""Unit tests for hybrid-search fusion + helpers (ADP-b6o)."""

from __future__ import annotations

from adp.search import build_text, rrf_fuse


def test_build_text_joins_non_empty_parts():
    assert build_text("Payments", "Handles checkout") == "Payments Handles checkout"
    assert build_text("Payments", None, "  ", "Gateway") == "Payments Gateway"
    assert build_text(None, "") == ""


def test_rrf_fuse_ranks_items_in_both_legs_highest():
    # A appears in both legs; B only vector; C only keyword.
    vector = [("cap", "A", "a"), ("cap", "B", "b")]
    keyword = [("cap", "A", "a"), ("cap", "C", "c")]
    hits = rrf_fuse(vector, keyword)
    assert hits[0].entity_id == "A"  # dual-leg item wins
    ids = {h.entity_id for h in hits}
    assert ids == {"A", "B", "C"}


def test_rrf_fuse_respects_weights():
    # Same single-leg rank in each leg; the heavier-weighted leg's item wins.
    vector = [("cap", "V", "v")]
    keyword = [("cap", "K", "k")]
    hits = rrf_fuse(vector, keyword, vector_weight=0.9, keyword_weight=0.1)
    assert hits[0].entity_id == "V"
    hits2 = rrf_fuse(vector, keyword, vector_weight=0.1, keyword_weight=0.9)
    assert hits2[0].entity_id == "K"


def test_rrf_fuse_empty_and_limit():
    assert rrf_fuse([], []) == []
    many = [("cap", str(i), str(i)) for i in range(20)]
    assert len(rrf_fuse(many, [], limit=5)) == 5


def test_rrf_fuse_keyword_only_and_vector_only_both_contribute():
    # keyword-only leg still returns results (and vice versa).
    assert [h.entity_id for h in rrf_fuse([], [("cap", "K", "k")])] == ["K"]
    assert [h.entity_id for h in rrf_fuse([("cap", "V", "v")], [])] == ["V"]
