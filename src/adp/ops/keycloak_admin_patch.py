"""Patch a live Keycloak realm or client via the admin REST API (ADP-cm9).

Keycloak's `--import-realm` uses the IGNORE_EXISTING strategy: once a realm has
been provisioned, redeploying the realm-JSON image is a no-op for that realm --
config changes only take effect through the admin REST API against the running
instance. This script is that mechanism, driven entirely by env vars so it can
run unmodified from a Container Apps Job (`adp-keycloak-admin`, Manual trigger)
with different env-var overrides per invocation. Reused by ADP-odp for the MFA
realm-level otpPolicy/requiredActions change.

Required env vars:
  KEYCLOAK_URL              Base URL, e.g. https://adp-keycloak.internal...
  KEYCLOAK_REALM            Realm name, e.g. ADPRealm
  KEYCLOAK_ADMIN_USERNAME   Admin username (master realm)
  KEYCLOAK_ADMIN_PASSWORD   Admin password (master realm)
  KC_PATCH_TARGET           "client" or "realm"
  KC_PATCH_BODY             JSON object; fields are shallow-merged into the
                             existing representation before PUT

  KC_PATCH_CLIENT_ID        Required when KC_PATCH_TARGET=client (the
                             client's clientId, e.g. adp-frontend)
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


def _get_admin_token(client: httpx.Client, base_url: str, username: str, password: str) -> str:
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


def _patch_client(
    client: httpx.Client, base_url: str, realm: str, token: str, client_id: str, patch: dict
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get(
        f"{base_url}/admin/realms/{realm}/clients",
        params={"clientId": client_id},
        headers=headers,
    )
    resp.raise_for_status()
    matches = resp.json()
    if not matches:
        print(f"ERROR: no client with clientId={client_id!r} in realm {realm!r}", file=sys.stderr)
        sys.exit(1)
    current = matches[0]
    internal_id = current["id"]
    current.update(patch)
    put_resp = client.put(
        f"{base_url}/admin/realms/{realm}/clients/{internal_id}",
        json=current,
        headers=headers,
    )
    put_resp.raise_for_status()
    print(
        f"OK: patched client {client_id!r} (id={internal_id}) "
        f"in realm {realm!r}: {list(patch.keys())}"
    )


def _patch_realm(client: httpx.Client, base_url: str, realm: str, token: str, patch: dict) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get(f"{base_url}/admin/realms/{realm}", headers=headers)
    resp.raise_for_status()
    current = resp.json()
    current.update(patch)
    put_resp = client.put(f"{base_url}/admin/realms/{realm}", json=current, headers=headers)
    put_resp.raise_for_status()
    print(f"OK: patched realm {realm!r}: {list(patch.keys())}")


def main() -> None:
    base_url = _env("KEYCLOAK_URL").rstrip("/")
    realm = _env("KEYCLOAK_REALM")
    username = _env("KEYCLOAK_ADMIN_USERNAME")
    password = _env("KEYCLOAK_ADMIN_PASSWORD")
    target = _env("KC_PATCH_TARGET")
    patch = json.loads(_env("KC_PATCH_BODY"))

    if target not in ("client", "realm"):
        print(
            f"ERROR: KC_PATCH_TARGET must be 'client' or 'realm', got {target!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    with httpx.Client(timeout=30.0) as client:
        token = _get_admin_token(client, base_url, username, password)
        if target == "client":
            client_id = _env("KC_PATCH_CLIENT_ID")
            _patch_client(client, base_url, realm, token, client_id, patch)
        else:
            _patch_realm(client, base_url, realm, token, patch)


if __name__ == "__main__":
    main()
