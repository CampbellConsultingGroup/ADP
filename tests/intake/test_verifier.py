"""Tests for SourceExcerptVerifier (US1 / FR-007)."""

from adp.intake.models import VerificationStatus
from adp.intake.verifier import SourceExcerptVerifier

_v = SourceExcerptVerifier()


def test_exact_match_is_verified() -> None:
    assert _v.verify("the text", "contains the text here") == VerificationStatus.VERIFIED


def test_case_insensitive_match_is_verified() -> None:
    result = _v.verify("The System Must", "The system must handle requests")
    assert result == VerificationStatus.VERIFIED


def test_missing_excerpt_is_unverified() -> None:
    assert _v.verify("not present", "other content here") == VerificationStatus.UNVERIFIED


def test_empty_excerpt_is_unverified() -> None:
    assert _v.verify("", "some source text") == VerificationStatus.UNVERIFIED


def test_partial_substring_is_verified() -> None:
    source = "All API requests must be authenticated before reaching any service."
    result = _v.verify("authenticated before reaching any service", source)
    assert result == VerificationStatus.VERIFIED
