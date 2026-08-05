"""Create/refresh Keycloak users via the admin REST API (ADP-cm9 follow-up).

Idempotent bootstrap of test/seed users on an already-provisioned realm --
`--import-realm` (IGNORE_EXISTING) won't add users to a live realm, and the
realm defines groups but no users, with self-registration disabled. Runs from a
Container Apps Job (`adp-keycloak-admin`, overriding --command) inside the VNet,
since Keycloak has internal-only ingress. Same env-driven shape as
keycloak_admin_patch.py.

MFA (ADP-odp) gotcha: a realm's `requiredActions[].defaultAction` only gets
assigned to users created through Keycloak's own self-registration/first-login
flows -- users created via this admin-API POST do NOT inherit it automatically
(registration is disabled here anyway, so every user goes through this script).
New users are therefore given CONFIGURE_TOTP explicitly below so MFA enrollment
is actually enforced on first login, not just nominally configured at the realm
level. Existing users are left alone on re-run (no forced re-enrollment).

Required env vars:
  KEYCLOAK_URL              Base URL incl. /auth, e.g. https://adp-keycloak.internal.../auth
  KEYCLOAK_REALM            Realm name, e.g. ADPRealm
  KEYCLOAK_ADMIN_USERNAME   Master-realm admin username
  KEYCLOAK_ADMIN_PASSWORD   Master-realm admin password
  KC_USERS                  JSON array of objects, each:
                              {"username": "...", "password": "...",
                               "email": "...", "groups": ["EnterpriseArchitect"]}
                            Re-running resets the password and re-asserts group
                            membership (idempotent).
"""

from __future__ import annotations

import json
import os
import sys

import httpx


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: required env var {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def _admin_token(client: httpx.Client, base_url: str, username: str, password: str) -> str:
    resp = client.post(
        f"{base_url}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": username,
            "password": password,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _find_user_id(
    client: httpx.Client, base: str, realm: str, hdr: dict, username: str
) -> str | None:
    resp = client.get(
        f"{base}/admin/realms/{realm}/users",
        params={"username": username, "exact": "true"},
        headers=hdr,
    )
    resp.raise_for_status()
    hits = resp.json()
    return hits[0]["id"] if hits else None


def _find_group_id(client: httpx.Client, base: str, realm: str, hdr: dict, name: str) -> str:
    resp = client.get(
        f"{base}/admin/realms/{realm}/groups",
        params={"search": name},
        headers=hdr,
    )
    resp.raise_for_status()
    for g in resp.json():
        if g["name"] == name:
            return g["id"]
    print(f"ERROR: group {name!r} not found in realm {realm!r}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    base = _env("KEYCLOAK_URL").rstrip("/")
    realm = _env("KEYCLOAK_REALM")
    admin_user = _env("KEYCLOAK_ADMIN_USERNAME")
    admin_pass = _env("KEYCLOAK_ADMIN_PASSWORD")
    users = json.loads(_env("KC_USERS"))

    with httpx.Client(timeout=30.0) as client:
        token = _admin_token(client, base, admin_user, admin_pass)
        hdr = {"Authorization": f"Bearer {token}"}

        for u in users:
            username = u["username"]
            uid = _find_user_id(client, base, realm, hdr, username)
            if uid is None:
                resp = client.post(
                    f"{base}/admin/realms/{realm}/users",
                    json={
                        "username": username,
                        "email": u.get("email", ""),
                        "emailVerified": True,
                        "enabled": True,
                        "requiredActions": ["CONFIGURE_TOTP"],
                    },
                    headers=hdr,
                )
                resp.raise_for_status()
                uid = _find_user_id(client, base, realm, hdr, username)
                action = "created"
            else:
                action = "updated"

            # (Re)set a permanent password -- idempotent on re-run.
            pw_resp = client.put(
                f"{base}/admin/realms/{realm}/users/{uid}/reset-password",
                json={"type": "password", "value": u["password"], "temporary": False},
                headers=hdr,
            )
            pw_resp.raise_for_status()

            # Assert group membership (PUT is idempotent).
            for group_name in u.get("groups", []):
                gid = _find_group_id(client, base, realm, hdr, group_name)
                join = client.put(
                    f"{base}/admin/realms/{realm}/users/{uid}/groups/{gid}",
                    headers=hdr,
                )
                join.raise_for_status()

            print(f"OK: {action} user {username!r} (id={uid}) groups={u.get('groups', [])}")


if __name__ == "__main__":
    main()
