"""Unit tests for adp.compliance.models — Pydantic validation rules (COMPLY-01).

Tests MUST fail before models are implemented (TDD — ART-IV).
"""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from adp.compliance.models import (
    Control,
    ControlCreate,
    ControlNode,
    ControlUpdate,
    RegulatoryFrameworkCreate,
    RegulatoryFrameworkDetail,
    RegulatoryFrameworkUpdate,
)

_NOW = datetime.datetime(2026, 8, 17, 12, 0, 0)


# ── RegulatoryFrameworkCreate ────────────────────────────────────────────────

class TestRegulatoryFrameworkCreate:
    def test_valid_full_create(self):
        fw = RegulatoryFrameworkCreate(
            name="GDPR", jurisdiction="EU", authority="European Commission",
            version="2016/679", effective_date=datetime.date(2018, 5, 25),
            source_url="https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        )
        assert fw.name == "GDPR"
        assert fw.effective_date == datetime.date(2018, 5, 25)

    def test_valid_without_optional_fields(self):
        fw = RegulatoryFrameworkCreate(
            name="SOC 2 Type II", jurisdiction="US", authority="AICPA", version="2017 TSC",
        )
        assert fw.effective_date is None
        assert fw.source_url is None

    @pytest.mark.parametrize("field", ["name", "jurisdiction", "authority", "version"])
    def test_blank_required_field_rejected(self, field):
        kwargs = {"name": "X", "jurisdiction": "Y", "authority": "Z", "version": "1"}
        kwargs[field] = "   "
        with pytest.raises(ValidationError, match="must not be blank"):
            RegulatoryFrameworkCreate(**kwargs)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            RegulatoryFrameworkCreate(
                name="X", jurisdiction="Y", authority="Z", version="1", bogus="nope"
            )

    # ── source_url scheme validation (security review finding, 923-derived-compliance-status:
    #    source_url is rendered as an <a href> with no frontend sanitization, so a dangerous
    #    scheme like javascript: must be rejected server-side before it can ever be stored) ────

    @pytest.mark.parametrize(
        "bad_url", ["javascript:alert(document.cookie)", "data:text/html,<script>1</script>",
                    "ftp://example.com/x", "not-a-url"],
    )
    def test_source_url_rejects_non_http_scheme(self, bad_url):
        with pytest.raises(ValidationError, match="http"):
            RegulatoryFrameworkCreate(
                name="X", jurisdiction="Y", authority="Z", version="1", source_url=bad_url,
            )

    @pytest.mark.parametrize(
        "good_url", ["https://example.com/reg", "http://example.com/reg"],
    )
    def test_source_url_accepts_http_and_https(self, good_url):
        fw = RegulatoryFrameworkCreate(
            name="X", jurisdiction="Y", authority="Z", version="1", source_url=good_url,
        )
        assert fw.source_url == good_url

    def test_source_url_none_is_valid(self):
        fw = RegulatoryFrameworkCreate(
            name="X", jurisdiction="Y", authority="Z", version="1", source_url=None,
        )
        assert fw.source_url is None

    # ── name/jurisdiction/authority/version length caps, matching the DB columns exactly
    #    (bug found live: a paragraph-length jurisdiction/version reached the INSERT and
    #    crashed create_framework() with a raw 500 -- asyncpg.StringDataRightTruncationError --
    #    instead of a clean 422) ────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("field", ["name", "jurisdiction", "authority"])
    def test_255_char_field_over_limit_rejected(self, field):
        kwargs = {"name": "X", "jurisdiction": "Y", "authority": "Z", "version": "1"}
        kwargs[field] = "x" * 256
        with pytest.raises(ValidationError, match="at most 255 characters"):
            RegulatoryFrameworkCreate(**kwargs)

    def test_version_over_100_chars_rejected(self):
        with pytest.raises(ValidationError, match="at most 100 characters"):
            RegulatoryFrameworkCreate(
                name="X", jurisdiction="Y", authority="Z", version="x" * 101,
            )


class TestRegulatoryFrameworkUpdate:
    def test_empty_update_valid(self):
        upd = RegulatoryFrameworkUpdate()
        assert upd.name is None

    def test_blank_field_rejected_if_set(self):
        with pytest.raises(ValidationError, match="must not be blank"):
            RegulatoryFrameworkUpdate(authority="   ")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            RegulatoryFrameworkUpdate(bogus="nope")

    def test_source_url_rejects_non_http_scheme_if_set(self):
        with pytest.raises(ValidationError, match="http"):
            RegulatoryFrameworkUpdate(source_url="javascript:alert(1)")

    def test_source_url_accepts_https_if_set(self):
        upd = RegulatoryFrameworkUpdate(source_url="https://example.com/reg")
        assert upd.source_url == "https://example.com/reg"


class TestRegulatoryFrameworkDetail:
    def test_empty_controls_default(self):
        detail = RegulatoryFrameworkDetail(
            id="f1", name="GDPR", jurisdiction="EU", authority="EC", version="2016/679",
            effective_date=None, source_url=None, created_at=_NOW, updated_at=_NOW,
        )
        assert detail.controls == []

    def test_nested_controls_round_trip(self):
        child = ControlNode(
            id="c2", framework_id="f1", parent_id="c1", code="Art. 5(1)(a)",
            title="Lawfulness", description="...", position=0,
            created_at=_NOW, updated_at=_NOW, children=[],
        )
        parent = ControlNode(
            id="c1", framework_id="f1", parent_id=None, code="Art. 5",
            title="Principles", description="...", position=0,
            created_at=_NOW, updated_at=_NOW, children=[child],
        )
        detail = RegulatoryFrameworkDetail(
            id="f1", name="GDPR", jurisdiction="EU", authority="EC", version="2016/679",
            effective_date=None, source_url=None, created_at=_NOW, updated_at=_NOW,
            controls=[parent],
        )
        assert len(detail.controls) == 1
        assert len(detail.controls[0].children) == 1
        assert detail.controls[0].children[0].code == "Art. 5(1)(a)"


# ── ControlCreate ─────────────────────────────────────────────────────────────

class TestControlCreate:
    def test_valid_top_level(self):
        c = ControlCreate(code="AC-2", title="Account Management", description="...")
        assert c.parent_id is None
        assert c.position == 0

    def test_valid_nested(self):
        c = ControlCreate(
            parent_id="parent-id", code="AC-2(1)", title="Automated", description="..."
        )
        assert c.parent_id == "parent-id"

    @pytest.mark.parametrize("field", ["code", "title", "description"])
    def test_blank_required_field_rejected(self, field):
        kwargs = {"code": "AC-2", "title": "Account Management", "description": "..."}
        kwargs[field] = ""
        with pytest.raises(ValidationError, match="must not be blank"):
            ControlCreate(**kwargs)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ControlCreate(code="AC-2", title="X", description="...", bogus="nope")

    # ── code/title length caps, matching the DB columns exactly (bug found live:
    #    an over-length value used to reach the INSERT and crash with a raw 500
    #    (asyncpg.StringDataRightTruncationError) instead of a clean 422) ────────

    def test_code_over_100_chars_rejected(self):
        with pytest.raises(ValidationError, match="at most 100 characters"):
            ControlCreate(code="x" * 101, title="X", description="...")

    def test_title_over_255_chars_rejected(self):
        with pytest.raises(ValidationError, match="at most 255 characters"):
            ControlCreate(code="AC-2", title="x" * 256, description="...")

    def test_code_and_title_at_exact_limit_accepted(self):
        c = ControlCreate(code="x" * 100, title="y" * 255, description="...")
        assert len(c.code) == 100
        assert len(c.title) == 255


class TestControlUpdate:
    def test_empty_update_valid(self):
        upd = ControlUpdate()
        assert upd.title is None

    @pytest.mark.parametrize("field", ["code", "title", "description"])
    def test_blank_field_rejected_if_set(self, field):
        with pytest.raises(ValidationError, match="must not be blank"):
            ControlUpdate(**{field: "  "})

    def test_code_over_100_chars_rejected_if_set(self):
        with pytest.raises(ValidationError, match="at most 100 characters"):
            ControlUpdate(code="x" * 101)

    def test_title_over_255_chars_rejected_if_set(self):
        with pytest.raises(ValidationError, match="at most 255 characters"):
            ControlUpdate(title="x" * 256)

    def test_reparent_and_recode_both_settable(self):
        upd = ControlUpdate(parent_id="new-parent", code="AC-3")
        assert upd.parent_id == "new-parent"
        assert upd.code == "AC-3"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ControlUpdate(bogus="nope")


class TestControlReadModels:
    def test_control_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Control(
                id="c1", framework_id="f1", parent_id=None, code="AC-2", title="X",
                description=None, position=0, created_at=_NOW, updated_at=_NOW, bogus="nope",
            )

    def test_control_node_default_children_empty(self):
        node = ControlNode(
            id="c1", framework_id="f1", parent_id=None, code="AC-2", title="X",
            description=None, position=0, created_at=_NOW, updated_at=_NOW,
        )
        assert node.children == []
