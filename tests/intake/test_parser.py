"""Tests for LLMResponseParser — JSON parsing into ExtractedProposal records (US1)."""

from __future__ import annotations

from adp.intake.models import RequirementKind
from adp.intake.parser import LLMResponseParser

_parser = LLMResponseParser()

_VALID_RESPONSE = {
    "choices": [{
        "message": {
            "content": '{"requirements": ['
                '{"statement": "The system must authenticate all API requests.", '
                '"kind": "functional", '
                '"source_excerpt": "authenticate all API requests", '
                '"confidence": 0.95, '
                '"referenced_principles": ["Zero Trust"]},'
                '{"statement": "Response time under 200ms.", '
                '"kind": "non_functional", '
                '"source_excerpt": "response time under 200ms", '
                '"confidence": 0.88, '
                '"referenced_principles": []},'
                '{"statement": "Support 10k concurrent users.", '
                '"kind": "constraint", '
                '"source_excerpt": "10k concurrent users", '
                '"confidence": 0.90, '
                '"referenced_principles": []}'
                ']}'
        }
    }],
}


def test_parser_extracts_three_proposals() -> None:
    """Parser returns 3 proposals from a valid response."""
    proposals = _parser.parse(_VALID_RESPONSE, "sub-001", "op-001")
    assert len(proposals) == 3


def test_parser_extracts_correct_statement() -> None:
    proposals = _parser.parse(_VALID_RESPONSE, "sub-001", "op-001")
    assert proposals[0].draft_statement == "The system must authenticate all API requests."


def test_parser_assigns_kind() -> None:
    proposals = _parser.parse(_VALID_RESPONSE, "sub-001", "op-001")
    assert proposals[0].kind == RequirementKind.FUNCTIONAL
    assert proposals[1].kind == RequirementKind.NON_FUNCTIONAL
    assert proposals[2].kind == RequirementKind.CONSTRAINT


def test_parser_extracts_source_excerpt() -> None:
    proposals = _parser.parse(_VALID_RESPONSE, "sub-001", "op-001")
    assert proposals[0].source_excerpt == "authenticate all API requests"


def test_parser_extracts_confidence() -> None:
    proposals = _parser.parse(_VALID_RESPONSE, "sub-001", "op-001")
    assert abs(proposals[0].confidence - 0.95) < 0.001


def test_parser_extracts_referenced_principles() -> None:
    proposals = _parser.parse(_VALID_RESPONSE, "sub-001", "op-001")
    assert proposals[0].proposed_links == ["Zero Trust"]
    assert proposals[1].proposed_links == []


def test_parser_assigns_proposal_id() -> None:
    proposals = _parser.parse(_VALID_RESPONSE, "sub-001", "op-001")
    assert all(len(p.proposal_id) > 0 for p in proposals)
    assert len({p.proposal_id for p in proposals}) == 3  # unique ids


def test_parser_returns_empty_on_invalid_json() -> None:
    bad_response = {"choices": [{"message": {"content": "not json"}}]}
    assert _parser.parse(bad_response, "sub-001", "op-001") == []


def test_parser_skips_malformed_items() -> None:
    valid_item = (
        '{"statement": "Valid req.", "kind": "functional", '
        '"source_excerpt": "Valid req.", "confidence": 0.9, "referenced_principles": []}'
    )
    response = {
        "choices": [{"message": {"content":
            f'{{"requirements": [{{"bad": "item"}}, {valid_item}]}}'}}]
    }
    proposals = _parser.parse(response, "sub-001", "op-001")
    assert len(proposals) == 1
    assert proposals[0].draft_statement == "Valid req."
