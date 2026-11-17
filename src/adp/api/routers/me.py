"""What the signed-in user may do (ADP-blp.62).

The frontend needs to know, before a click, whether an action is allowed, so it can disable a
control and say why instead of letting the user fill in a form and then refusing it. It used to
guess from a hand-copied list of role names, for a few screens only. This returns the caller's
role and the actions the server's own permission table grants it, so the two cannot drift.
It grants nothing: every route is still checked by adp.authz.enforcement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import PERMISSION_GRANTS, PERMISSIONS_VERSION

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class MyPermissions(BaseModel):
    role: str
    actions: list[str]
    permissions_version: str


@router.get("/permissions", response_model=MyPermissions)
async def my_permissions(user: AuthenticatedUser = Depends(get_current_user)) -> MyPermissions:
    granted = PERMISSION_GRANTS.get(user.role, frozenset())
    return MyPermissions(
        role=user.role.value,
        actions=sorted(action.value for action in granted),
        permissions_version=PERMISSIONS_VERSION,
    )
