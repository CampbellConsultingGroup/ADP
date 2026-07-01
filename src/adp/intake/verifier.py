"""Source excerpt verification — ensures proposals are grounded in submitted text (FR-007)."""

from adp.intake.models import VerificationStatus


class SourceExcerptVerifier:
    """Verify that a proposal's source excerpt is a verbatim substring of the source text."""

    def verify(self, excerpt: str, source_text: str) -> VerificationStatus:
        """Return VERIFIED if excerpt (case-insensitive) is found in source_text."""
        if not excerpt:
            return VerificationStatus.UNVERIFIED
        if excerpt.lower() in source_text.lower():
            return VerificationStatus.VERIFIED
        return VerificationStatus.UNVERIFIED
