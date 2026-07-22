#!/usr/bin/env bash
# Deploy/update the ADP Azure environment foundation (resource group, ACR,
# VNet, Postgres Flexible Server, Key Vault + managed identity, Container
# Apps environment, Keycloak, API app). Subsequent epic tasks extend
# main.bicep with more modules; this script doesn't change as the
# environment grows.
#
# Usage: ./deploy.sh [location]
#
# All secret VALUES (Postgres admin password, Keycloak admin password, the
# assembled Postgres connection string, ADP_LLM_API_KEY) are written into
# Key Vault BEFORE the main deployment runs, not after -- both the Keycloak
# and API container apps deployed in the same template read them via Key
# Vault secret references at provisioning time, so if they don't exist yet
# that deployment fails. This only works because Key Vault already exists
# from a prior run of this script (ADP-fnv.3); a genuine from-scratch
# rebuild needs two passes -- run once to create Key Vault (the container
# app modules will fail that first time), then again once these secrets
# exist -- the same transient-failure-then-retry pattern already seen with
# the Postgres server in ADP-fnv.2.
#
# Password-type secrets are cached locally in infra/azure/.secrets/
# (gitignored, chmod 600) so re-running this script doesn't change them out
# from under an already-running server.
#
# Both custom images (Keycloak, API) are built fresh on every run. The API
# image is tagged with the current git short SHA rather than a floating
# `:latest` -- reusing the same tag string is a no-op in Container Apps'
# revision diffing (it won't re-pull even though the digest changed),
# discovered the hard way in ADP-fnv.5. Keycloak still uses `:latest`
# because its Dockerfile only changes when the realm export changes, not on
# every app commit; if you edit infra/keycloak/, force a new revision with
# `az containerapp update --revision-suffix <name>` same as ADP-fnv.5 did.

set -euo pipefail

LOCATION="${1:-eastus2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SECRETS_DIR="$SCRIPT_DIR/.secrets"
PG_PASSWORD_FILE="$SECRETS_DIR/postgres-admin-password"
KC_PASSWORD_FILE="$SECRETS_DIR/keycloak-admin-password"
RESOURCE_GROUP="adp-rg"

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

if [[ ! -f "$PG_PASSWORD_FILE" ]]; then
  echo "Generating Postgres admin password (first run) -> $PG_PASSWORD_FILE"
  openssl rand -base64 24 > "$PG_PASSWORD_FILE"
  chmod 600 "$PG_PASSWORD_FILE"
fi
PG_ADMIN_PASSWORD="$(cat "$PG_PASSWORD_FILE")"

if [[ ! -f "$KC_PASSWORD_FILE" ]]; then
  echo "Generating Keycloak admin password (first run) -> $KC_PASSWORD_FILE"
  openssl rand -base64 24 > "$KC_PASSWORD_FILE"
  chmod 600 "$KC_PASSWORD_FILE"
fi
KC_ADMIN_PASSWORD="$(cat "$KC_PASSWORD_FILE")"

DEPLOYER_PRINCIPAL_ID="$(az ad signed-in-user show --query id -o tsv)"

API_IMAGE_TAG="$(cd "$REPO_ROOT" && git rev-parse --short HEAD)"
if ! git -C "$REPO_ROOT" diff --quiet 2>/dev/null || ! git -C "$REPO_ROOT" diff --cached --quiet 2>/dev/null; then
  API_IMAGE_TAG="${API_IMAGE_TAG}-dirty-$(date +%s)"
fi

EXISTING_KEY_VAULT="$(az keyvault list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || true)"
EXISTING_ACR="$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || true)"

if [[ -n "$EXISTING_KEY_VAULT" ]]; then
  echo "== Pre-seeding secrets into existing Key Vault ($EXISTING_KEY_VAULT) =="
  az keyvault secret set --vault-name "$EXISTING_KEY_VAULT" --name "postgres-admin-password" \
    --value "$PG_ADMIN_PASSWORD" --output none
  az keyvault secret set --vault-name "$EXISTING_KEY_VAULT" --name "keycloak-admin-password" \
    --value "$KC_ADMIN_PASSWORD" --output none
  echo "  postgres-admin-password, keycloak-admin-password set."

  # The connection string needs the server's real FQDN/DB name; both are
  # fixed/known after ADP-fnv.2 first deployed, so a live lookup is safe
  # even before this run's own deployment happens.
  POSTGRES_FQDN="$(az postgres flexible-server show --resource-group "$RESOURCE_GROUP" \
    --name adp-postgres --query "fullyQualifiedDomainName" -o tsv 2>/dev/null || true)"
  if [[ -n "$POSTGRES_FQDN" ]]; then
    PG_CONNECTION_STRING="postgresql+asyncpg://adp_admin:${PG_ADMIN_PASSWORD}@${POSTGRES_FQDN}:5432/adp"
    az keyvault secret set --vault-name "$EXISTING_KEY_VAULT" --name "postgres-connection-string" \
      --value "$PG_CONNECTION_STRING" --output none
    echo "  postgres-connection-string set."
  fi

  if [[ -f "$REPO_ROOT/.env" ]]; then
    LLM_API_KEY="$(grep -E '^ADP_LLM_API_KEY=' "$REPO_ROOT/.env" | head -1 | cut -d= -f2-)"
    if [[ -n "$LLM_API_KEY" ]]; then
      az keyvault secret set --vault-name "$EXISTING_KEY_VAULT" --name "adp-llm-api-key" \
        --value "$LLM_API_KEY" --output none
      echo "  adp-llm-api-key set (from local .env)."
    fi
  fi
else
  echo "== No existing Key Vault found -- skipping secret pre-seed (first-ever run) =="
fi

if [[ -n "$EXISTING_ACR" ]]; then
  echo "== Building Keycloak image (infra/keycloak/) to $EXISTING_ACR =="
  az acr build --registry "$EXISTING_ACR" --image adp-keycloak:latest "$SCRIPT_DIR/../keycloak" --output none

  echo "== Building API image (repo root Dockerfile) to $EXISTING_ACR, tag $API_IMAGE_TAG =="
  az acr build --registry "$EXISTING_ACR" --image "adp-api:${API_IMAGE_TAG}" "$REPO_ROOT" --output none
else
  echo "== No existing ACR found -- skipping image builds (first-ever run) =="
fi

echo "== What-if (dry run) =="
az deployment sub what-if \
  --name "adp-foundation" \
  --location "$LOCATION" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters location="$LOCATION" postgresAdminPassword="$PG_ADMIN_PASSWORD" \
    deployerPrincipalId="$DEPLOYER_PRINCIPAL_ID" apiImageTag="$API_IMAGE_TAG"

echo
read -r -p "Proceed with deployment? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted."
  exit 1
fi

echo "== Deploying =="
az deployment sub create \
  --name "adp-foundation" \
  --location "$LOCATION" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters location="$LOCATION" postgresAdminPassword="$PG_ADMIN_PASSWORD" \
    deployerPrincipalId="$DEPLOYER_PRINCIPAL_ID" apiImageTag="$API_IMAGE_TAG" \
  --output table

KEY_VAULT_NAME="$(az deployment sub show --name "adp-foundation" --query "properties.outputs.keyVaultName.value" -o tsv)"
API_FQDN="$(az deployment sub show --name "adp-foundation" --query "properties.outputs.apiFqdn.value" -o tsv)"
echo "== Done. Key Vault: $KEY_VAULT_NAME | API: https://$API_FQDN =="
