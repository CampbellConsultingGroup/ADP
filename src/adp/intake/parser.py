"""Parse LLM JSON response into ExtractedProposal records (ADP-SPEC-006)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from adp.intake.models import ExtractedProposal, ProposalStatus, RequirementKind, VerificationStatus

_logger = logging.getLogger("adp.intake")


class LLMResponseParser:
    """Convert raw LLM response JSON into typed ExtractedProposal records."""

    def parse(
        self,
        raw_response: dict[str, Any],
        submission_id: str,
        operation_id: str,
    ) -> list[ExtractedProposal]:
        """Parse LLM response; skip malformed items with a warning."""
        try:
            content = raw_response["choices"][0]["message"]["content"]
            data = json.loads(content) if isinstance(content, str) else content
            items = data.get("requirements", [])
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            _logger.warning("Failed to parse LLM response: %s", exc)
            return []

        proposals: list[ExtractedProposal] = []
        for item in items:
            try:
                kind_raw = str(item.get("kind", "functional"))
                try:
                    kind = RequirementKind(kind_raw)
                except ValueError:
                    kind = RequirementKind.FUNCTIONAL

                confidence = float(item.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))

                proposals.append(
                    ExtractedProposal(
                        proposal_id=str(uuid.uuid4()),
                        operation_id=operation_id,
                        submission_id=submission_id,
                        draft_statement=str(item["statement"]),
                        kind=kind,
                        source_excerpt=str(item.get("source_excerpt", "")),
                        verification_status=VerificationStatus.UNVERIFIED,
                        confidence=confidence,
                        proposed_links=list(item.get("referenced_principles", [])),
                        status=ProposalStatus.PENDING,
                    )
                )
            except (KeyError, TypeError) as exc:
                _logger.warning("Skipping malformed proposal item: %s", exc)

        return proposals
