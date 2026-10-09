#!/usr/bin/env bash
# Deploy or update the whole ADP Azure environment in ONE invocation, from an
# empty subscription or against an existing environment (ADP-fnv, ADP-vav).
#
# Usage: ./deploy.sh [location]          (default: centralus)
#   ADP_DEPLOY_ASSUME_YES=1  skip the two "Proceed?" prompts (what-if still prints)
#   ADP_ALLOW_PUBLIC=1       allow deploying adp-api with NO IP restriction
#
# Two stages, because the apps need things that can only be created once the
# infrastructure exists. Running both in one template guaranteed a failing
# first pass and a second (and third) re-run (ADP-vav):
#
#   1. infra.bicep (subscription scope) -- RG, ACR, VNet/DNS, Postgres, Key
#      Vault + identity (+ its AcrPull grant), Container Apps environment.
#      Retried up to 3x on known-transient ARM errors (e.g. Postgres briefly
#      not seeing a just-created subnet); fails fast on SkuNotAvailable.
#   -- between stages, from stage 1's outputs --
#      * seed Key Vault secrets (admin passwords, Postgres connection string
#        from the real FQDN, ADP_LLM_API_KEY from the repo-root .env)
#      * grant the CD service principal its 3 roles if missing (they're
#        deleted along with adp-rg; see .github/workflows/deploy-azure.yml)
#      * build the Keycloak + API images, the API one with the real
#        VITE_KEYCLOAK_URL baked in
#   2. apps.bicep (resource-group scope) -- Keycloak, API (with the IP
#      allow-list), migration + Keycloak-admin jobs.
#   -- then --
#      * run DB migrations (alembic upgrade head; idempotent)
#      * point the Keycloak adp-frontend client's redirect URIs at the API's
#        actual domain (idempotent; needed on every new environment domain)
#
# Password-type secrets are cached locally in infra/azure/.secrets/
# (gitignored, chmod 600) so re-running this script doesn't change them out
# from under an already-running server. The API ingress allow-list lives in
# infra/azure/.secrets/allowed-ips: one "CIDR description..." per line, '#'
# comments allowed. If that file is missing but adp-api already exists, it is
# created from the live rules; with neither, the script refuses to deploy a
# public API unless ADP_ALLOW_PUBLIC=1.
#
# The API image is tagged with the git short SHA (plus -dirty-<ts> for
# uncommitted changes): reusing a tag string is a no-op in Container Apps'
# revision diffing (ADP-fnv.5). Keycloak uses :latest -- if you edit
# infra/keycloak/, force a new revision with
# `az containerapp update --revision-suffix <name>`.
#
# Not handled here: purging a soft-deleted Key Vault left by a manual RG
# delete (the script detects it and tells you the command), loading data
# (seed-data.sh, deliberately manual), and creating Keycloak users
# (RUNBOOK.md).

set -euo pipefail

LOCATION="${1:-centralus}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SECRETS_DIR="$SCRIPT_DIR/.secrets"
PG_PASSWORD_FILE="$SECRETS_DIR/postgres-admin-password"
KC_PASSWORD_FILE="$SECRETS_DIR/keycloak-admin-password"
ALLOWED_IPS_FILE="$SECRETS_DIR/allowed-ips"
RESOURCE_GROUP="adp-rg"
# Sub-scope deployment records are location-bound: reusing one name across
# regions fails with InvalidDeploymentLocation, so the region is in the name.
INFRA_DEPLOYMENT="adp-infra-${LOCATION}"
APPS_DEPLOYMENT="adp-apps"
CD_APP_NAME="adp-github-actions-deploy"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

confirm() {
  if [[ "${ADP_DEPLOY_ASSUME_YES:-}" == "1" ]]; then
    echo "$1 [y/N] y (ADP_DEPLOY_ASSUME_YES=1)"
    return 0
  fi
  local answer
  read -r -p "$1 [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]]
}

# Run a command until it succeeds -- for steps that race Azure RBAC
# propagation right after stage 1 grants a role (minutes, worst case).
retry() {
  local attempts="$1" delay="$2"; shift 2
  local i
  for ((i = 1; i <= attempts; i++)); do
    if "$@"; then return 0; fi
    if ((i < attempts)); then
      echo "  ...not ready yet (attempt $i/$attempts), retrying in ${delay}s"
      sleep "$delay"
    fi
  done
  return 1
}

# Start a Container Apps job execution and wait for it to finish.
# Usage: run_job <job-name> [extra az containerapp job start args...]
run_job() {
  local job="$1"; shift
  local execution status=""
  execution="$(az containerapp job start -g "$RESOURCE_GROUP" -n "$job" "$@" --query name -o tsv)"
  echo "  started $execution"
  for _ in $(seq 1 60); do
    status="$(az containerapp job execution show -g "$RESOURCE_GROUP" -n "$job" \
      --job-execution-name "$execution" --query properties.status -o tsv)"
    [[ "$status" == "Succeeded" || "$status" == "Failed" ]] && break
    sleep 10
  done
  echo "  $execution: $status"
  [[ "$status" == "Succeeded" ]]
}

# ---------------------------------------------------------------- preflight
echo "== Preflight =="
az account show --query "{subscription:name, user:user.name}" -o tsv >/dev/null \
  || { echo "Not logged in -- run 'az login' first."; exit 1; }

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"
for f in "$PG_PASSWORD_FILE" "$KC_PASSWORD_FILE"; do
  if [[ ! -f "$f" ]]; then
    echo "  Generating $(basename "$f") (first run) -> $f"
    openssl rand -base64 24 > "$f"
    chmod 600 "$f"
  fi
done
PG_ADMIN_PASSWORD="$(cat "$PG_PASSWORD_FILE")"
KC_ADMIN_PASSWORD="$(cat "$KC_PASSWORD_FILE")"

DEPLOYER_PRINCIPAL_ID="$(az ad signed-in-user show --query id -o tsv)"

RG_EXISTS="$(az group exists --name "$RESOURCE_GROUP")"
if [[ "$RG_EXISTS" == "true" ]]; then
  RG_LOCATION="$(az group show --name "$RESOURCE_GROUP" --query location -o tsv)"
  if [[ "$RG_LOCATION" != "$LOCATION" ]]; then
    echo "  $RESOURCE_GROUP already exists in $RG_LOCATION, not $LOCATION."
    echo "  Re-run as './deploy.sh $RG_LOCATION', or destroy it first (destroy.sh)."
    exit 1
  fi
  PG_STATE="$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n adp-postgres \
    --query state -o tsv 2>/dev/null || true)"
  if [[ "$PG_STATE" == "Stopped" ]]; then
    echo "  adp-postgres is stopped (environment paused). Run ./resume.sh first."
    exit 1
  fi
else
  # A manual `az group delete` soft-deletes the Key Vault without purging it,
  # and the vault name (derived from the RG id) stays reserved until purged.
  DELETED_VAULTS="$(az keyvault list-deleted --query "[?starts_with(name,'adp-kv-')].name" -o tsv)"
  if [[ -n "$DELETED_VAULTS" ]]; then
    echo "  Soft-deleted Key Vault(s) from a previous environment block this deploy:"
    for v in $DELETED_VAULTS; do echo "    az keyvault purge --name $v"; done
    echo "  Purge them (or run destroy.sh), then re-run."
    exit 1
  fi
fi

# API ingress allow-list.
if [[ ! -f "$ALLOWED_IPS_FILE" ]] && [[ "$RG_EXISTS" == "true" ]] \
   && az containerapp show -g "$RESOURCE_GROUP" -n adp-api --query name -o tsv >/dev/null 2>&1; then
  echo "  No $ALLOWED_IPS_FILE -- creating it from adp-api's live allow-list."
  az containerapp ingress access-restriction list -g "$RESOURCE_GROUP" -n adp-api \
    --query "[?action=='Allow'].[ipAddressRange, description]" -o tsv \
    | sed 's/\t/  /' > "$ALLOWED_IPS_FILE"
  chmod 600 "$ALLOWED_IPS_FILE"
fi
ALLOWED_IPS_JSON='[]'
if [[ -f "$ALLOWED_IPS_FILE" ]]; then
  ALLOWED_IPS_JSON="$(python3 - "$ALLOWED_IPS_FILE" <<'PY'
import ipaddress, json, sys
ranges = []
for raw in open(sys.argv[1]):
    line = raw.split("#", 1)[0].strip()
    if not line:
        continue
    cidr, _, desc = line.partition(" ")
    ipaddress.ip_network(cidr, strict=False)  # fail loudly on a typo
    ranges.append({"cidr": cidr, "description": desc.strip() or "allowed"})
print(json.dumps(ranges))
PY
)"
fi
if [[ "$ALLOWED_IPS_JSON" == "[]" && "${ADP_ALLOW_PUBLIC:-}" != "1" ]]; then
  echo "  No IP allow-list: adp-api would be reachable from anywhere."
  echo "  Add one 'CIDR description' per line to $ALLOWED_IPS_FILE,"
  echo "  or re-run with ADP_ALLOW_PUBLIC=1 to deploy it public on purpose."
  exit 1
fi
echo "  API allow-list: $(python3 -c "import json,sys; print(', '.join(r['cidr'] for r in json.loads(sys.argv[1])) or 'NONE (public)')" "$ALLOWED_IPS_JSON")"

API_IMAGE_TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
  API_IMAGE_TAG="${API_IMAGE_TAG}-dirty-$(date +%s)"
fi
echo "  Location $LOCATION, API image tag $API_IMAGE_TAG"

# ---------------------------------------------------------- stage 1: infra
INFRA_PARAMS=(
  location="$LOCATION"
  postgresAdminPassword="$PG_ADMIN_PASSWORD"
  deployerPrincipalId="$DEPLOYER_PRINCIPAL_ID"
)

echo
echo "== Stage 1/2: infrastructure -- what-if =="
az deployment sub what-if --name "$INFRA_DEPLOYMENT" --location "$LOCATION" \
  --template-file "$SCRIPT_DIR/infra.bicep" --parameters "${INFRA_PARAMS[@]}"
confirm "Deploy stage 1 (infrastructure)?" || { echo "Aborted."; exit 1; }

# Known-transient failures seen on first-time creates (cross-resource-provider
# eventual consistency): re-applying the same template is idempotent.
TRANSIENT='doesn.t exist in virtual network|SubnetNotFound|InvalidResourceReference|AnotherOperationInProgress|RetryableError|ParentResourceNotFound'
for attempt in 1 2 3; do
  echo "== Stage 1/2: deploying (attempt $attempt/3) =="
  if az deployment sub create --name "$INFRA_DEPLOYMENT" --location "$LOCATION" \
       --template-file "$SCRIPT_DIR/infra.bicep" --parameters "${INFRA_PARAMS[@]}" \
       --output none 2> "$WORK_DIR/stage1.err"; then
    break
  fi
  if grep -q "SkuNotAvailable" "$WORK_DIR/stage1.err"; then
    echo "  Azure has no capacity for the Postgres SKU in $LOCATION (SkuNotAvailable)."
    echo "  This is regional capacity, not a template problem: try another region,"
    echo "  e.g. './deploy.sh westus2' (destroy the partial RG first with destroy.sh)."
    exit 1
  fi
  if (( attempt < 3 )) && grep -Eq "$TRANSIENT" "$WORK_DIR/stage1.err"; then
    echo "  Transient ARM error (resource not visible yet); retrying in 60s:"
    grep -Eo "$TRANSIENT[^\"]{0,120}" "$WORK_DIR/stage1.err" | head -3 | sed 's/^/    /'
    # A failed Postgres create leaves the server 'Dropping'; wait it out.
    while [[ "$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n adp-postgres \
                 --query state -o tsv 2>/dev/null || true)" == "Dropping" ]]; do
      sleep 20
    done
    sleep 60
    continue
  fi
  echo "  Stage 1 failed with a non-transient error:"
  cat "$WORK_DIR/stage1.err"
  exit 1
done

infra_output() {
  az deployment sub show --name "$INFRA_DEPLOYMENT" --query "properties.outputs.$1.value" -o tsv
}
KEY_VAULT_NAME="$(infra_output keyVaultName)"
KEY_VAULT_URI="$(infra_output keyVaultUri)"
ACR_NAME="$(infra_output acrName)"
ACR_ID="$(infra_output acrId)"
ACR_LOGIN_SERVER="$(infra_output acrLoginServer)"
POSTGRES_FQDN="$(infra_output postgresServerFqdn)"
POSTGRES_DB="$(infra_output postgresDatabaseName)"
KEYCLOAK_DB="$(infra_output postgresKeycloakDatabaseName)"
IDENTITY_ID="$(infra_output identityId)"
ENV_ID="$(infra_output containerAppsEnvironmentId)"
ENV_DOMAIN="$(infra_output containerAppsEnvironmentDefaultDomain)"
echo "  Key Vault $KEY_VAULT_NAME | ACR $ACR_NAME | env domain $ENV_DOMAIN"

# ------------------------------------------------------- between the stages
echo
echo "== Seeding Key Vault secrets =="
set_secret() {
  az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "$1" --value "$2" \
    --output none 2>/dev/null
}
# The deployer's Secrets Officer grant is made in stage 1; on a brand-new
# vault it can take a few minutes to propagate, hence the retries.
retry 20 15 set_secret postgres-admin-password "$PG_ADMIN_PASSWORD"
set_secret keycloak-admin-password "$KC_ADMIN_PASSWORD"
set_secret postgres-connection-string \
  "postgresql+asyncpg://adp_admin:${PG_ADMIN_PASSWORD}@${POSTGRES_FQDN}:5432/${POSTGRES_DB}"
echo "  postgres-admin-password, keycloak-admin-password, postgres-connection-string set."

LLM_API_KEY=""
if [[ -f "$REPO_ROOT/.env" ]]; then
  LLM_API_KEY="$(grep -E '^ADP_LLM_API_KEY=' "$REPO_ROOT/.env" | head -1 | cut -d= -f2- || true)"
fi
if [[ -n "$LLM_API_KEY" ]]; then
  set_secret adp-llm-api-key "$LLM_API_KEY"
  echo "  adp-llm-api-key set (from repo-root .env)."
elif ! az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name adp-llm-api-key \
       --query id -o tsv >/dev/null 2>&1; then
  # adp-api references this secret, so it must exist for stage 2 to succeed.
  set_secret adp-llm-api-key "not-set"
  echo "  WARNING: no ADP_LLM_API_KEY in .env -- placeholder stored; AI features will use stubs."
fi

echo "== Ensuring the CD service principal's roles ($CD_APP_NAME) =="
CD_SP_ID="$(az ad sp list --display-name "$CD_APP_NAME" --query "[0].id" -o tsv 2>/dev/null || true)"
if [[ -z "$CD_SP_ID" ]]; then
  echo "  No '$CD_APP_NAME' service principal found -- skipping (CD won't be able to deploy)."
else
  RG_ID="$(az group show --name "$RESOURCE_GROUP" --query id -o tsv)"
  ensure_role() {
    local role="$1" scope="$2"
    if [[ -n "$(az role assignment list --assignee "$CD_SP_ID" --role "$role" --scope "$scope" \
                 --query "[0].id" -o tsv)" ]]; then
      echo "  ok:      $role"
    else
      az role assignment create --assignee-object-id "$CD_SP_ID" \
        --assignee-principal-type ServicePrincipal --role "$role" --scope "$scope" --output none
      echo "  granted: $role"
    fi
  }
  ensure_role "AcrPush" "$ACR_ID"
  ensure_role "Container Registry Tasks Contributor" "$ACR_ID"
  ensure_role "Container Apps Contributor" "$RG_ID"
fi

echo "== Building images in $ACR_NAME =="
echo "  adp-keycloak:latest (infra/keycloak/)"
az acr build --registry "$ACR_NAME" --image adp-keycloak:latest \
  "$SCRIPT_DIR/../keycloak" --output none
VITE_KEYCLOAK_URL="https://adp-api.${ENV_DOMAIN}/auth"
echo "  adp-api:$API_IMAGE_TAG (repo root), VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL"
az acr build --registry "$ACR_NAME" --image "adp-api:${API_IMAGE_TAG}" \
  --build-arg VITE_KEYCLOAK_URL="$VITE_KEYCLOAK_URL" "$REPO_ROOT" --output none

# ----------------------------------------------------------- stage 2: apps
APPS_PARAMS_FILE="$WORK_DIR/apps.parameters.json"
python3 - "$APPS_PARAMS_FILE" <<PY
import json, sys
values = {
    "location": "$LOCATION",
    "environmentId": "$ENV_ID",
    "environmentDefaultDomain": "$ENV_DOMAIN",
    "identityId": "$IDENTITY_ID",
    "acrLoginServer": "$ACR_LOGIN_SERVER",
    "keyVaultUri": "$KEY_VAULT_URI",
    "postgresFqdn": "$POSTGRES_FQDN",
    "keycloakDatabaseName": "$KEYCLOAK_DB",
    "apiImageTag": "$API_IMAGE_TAG",
    "allowedIpRanges": json.loads('''$ALLOWED_IPS_JSON'''),
}
json.dump({
    "\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {k: {"value": v} for k, v in values.items()},
}, open(sys.argv[1], "w"), indent=2)
PY

echo
echo "== Stage 2/2: apps -- what-if =="
az deployment group what-if --resource-group "$RESOURCE_GROUP" --name "$APPS_DEPLOYMENT" \
  --template-file "$SCRIPT_DIR/apps.bicep" --parameters "@$APPS_PARAMS_FILE"
confirm "Deploy stage 2 (apps)?" || { echo "Aborted after stage 1 (infrastructure is in place)."; exit 1; }

echo "== Stage 2/2: deploying =="
# AcrPull for the apps' identity is also granted in stage 1; on a brand-new
# environment its propagation can lag the first image pull, so allow a retry.
retry 3 60 az deployment group create --resource-group "$RESOURCE_GROUP" --name "$APPS_DEPLOYMENT" \
  --template-file "$SCRIPT_DIR/apps.bicep" --parameters "@$APPS_PARAMS_FILE" --output none

apps_output() {
  az deployment group show --resource-group "$RESOURCE_GROUP" --name "$APPS_DEPLOYMENT" \
    --query "properties.outputs.$1.value" -o tsv
}
API_FQDN="$(apps_output apiFqdn)"
KEYCLOAK_FQDN="$(apps_output keycloakFqdn)"

# ------------------------------------------------------------ post-deploy
echo
echo "== Running DB migrations (adp-migrate) =="
run_job adp-migrate || { echo "Migration failed -- see RUNBOOK.md for reading job logs."; exit 1; }

echo "== Pointing Keycloak's adp-frontend client at https://$API_FQDN =="
# Keycloak's --import-realm uses IGNORE_EXISTING, so the realm JSON's pinned
# redirect URIs never update on a live realm; patch them through the admin
# API (ADP-cm9). Retried because a fresh Keycloak takes a while to boot.
PATCH_BODY="{\"redirectUris\":[\"https://${API_FQDN}/*\"],\"webOrigins\":[\"https://${API_FQDN}\"]}"
retry 5 30 run_job adp-keycloak-admin \
  --image "${ACR_LOGIN_SERVER}/adp-api:${API_IMAGE_TAG}" \
  --container-name keycloak-admin \
  --command "python3" "/app/src/adp/ops/keycloak_admin_patch.py" \
  --env-vars \
    KEYCLOAK_URL="https://${KEYCLOAK_FQDN}/auth" \
    KEYCLOAK_REALM=ADPRealm \
    KEYCLOAK_ADMIN_USERNAME=admin \
    "KEYCLOAK_ADMIN_PASSWORD=secretref:keycloak-admin-password" \
    KC_PATCH_TARGET=client KC_PATCH_CLIENT_ID=adp-frontend \
    "KC_PATCH_BODY=${PATCH_BODY}" \
  || { echo "Keycloak client patch failed -- logins will be rejected until it succeeds."; exit 1; }

echo
echo "== Done: https://$API_FQDN =="
echo "Not automated (by design): load data with seed-data.sh on a NEW environment,"
echo "and create Keycloak users (RUNBOOK.md) -- neither is safe to repeat blindly."
