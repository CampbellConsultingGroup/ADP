"""Backward-compatible re-export of LLMClient (ADP-SPEC-023 Move C).

The canonical location is now adp.llm.client.
This module is kept so existing callers within adp.intake continue to work.
New code should import directly from adp.llm.client.
"""

from adp.llm.client import (  # noqa: F401
    _EXTRACTION_SYSTEM_PROMPT,
    LLMClient,
    _is_anthropic,
    _strip_code_fence,
)
