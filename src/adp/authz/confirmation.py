"""What a ``confirmation_id`` is, and is not (ADP-blp.12).

Some actions are consequential enough that the constitution (ART-VIII, human in the loop) asks
for a recorded confirmation: accepting a recommended option or an agent suggestion, exporting a
design, changing a pattern's lifecycle state, and editing or restoring an agent prompt or a
scoring rubric (``adp.authz.permissions.REQUIRES_CONFIRMATION``). Their requests carry a
``confirmation_id``.

**It is an audit annotation, not a control.** The client makes the value up after the user
confirms in the UI; the server checks only that it is present and stores it with the action. It
does not prove that a person saw a prompt, it is not issued or verified by the server, and it can
be any non-empty string. A caller with the permission can send one without any dialog.

What protects these actions is authentication and the role check on the route, plus, where a
stale or repeated request would do harm, an ``expected_version`` (prompt and rubric edits) or the
legal-transition rule (pattern lifecycle).

Decision (2026-11-18): keep it this way. A server-issued, single-use challenge would add a
request, stored state and an expiry failure to every governed action while still not proving a
human confirmed, and a second approver ("four eyes") would be a separate feature. If either is
wanted later, this is the place to start.
"""

from __future__ import annotations

#: The description every request model gives its ``confirmation_id`` field, so the API
#: documentation says the same thing wherever the field appears.
CONFIRMATION_ID_DESCRIPTION = (
    "Recorded with the action for audit: the client's own reference for the user having "
    "confirmed. Must be non-empty. It is not issued or verified by the server and does not "
    "authorise anything; the caller's role does."
)
