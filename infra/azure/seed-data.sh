#!/usr/bin/env bash
# One-time (or occasional) bootstrap: copy data from a local Postgres
# database into the already-provisioned Azure Postgres instance.
#
# This is deliberately NOT part of deploy.sh or the CD pipeline
# (.github/workflows/deploy-azure.yml). Unlike infrastructure provisioning
# or an app-image rollout, this is NOT idempotent -- re-running it against
# already-seeded data will duplicate rows or hit unique-constraint errors.
# It is a human-triggered operational action, run from your own
# authenticated `az` session -- the CI service principal is deliberately
# scoped to zero Postgres access (ADP-cm9 security review), and this script
# does not change that.
#
# What it does:
#   1. pg_dump the local database (data-only, excluding bookkeeping tables
#      that shouldn't migrate between environments: alembic_version --
#      already correct on the target from its own migration run;
#      audit_entries/operations -- environment-specific audit/operational
#      records, not content).
#   2. Reorder rows for the two self-referencing hierarchy tables
#      (business_capabilities, technical_capabilities -- both have a
#      parent_id FK to their own table) by `level` ascending, so parents
#      always insert before children. This avoids needing
#      `pg_dump --disable-triggers`, which requires superuser privileges
#      Azure's admin login doesn't have (`ALTER TABLE ... DISABLE TRIGGER`
#      needs the ability to disable system-generated FK-enforcement
#      triggers, not just table ownership).
#   3. Strip psql-only meta-commands (`\restrict`/`\unrestrict`, a newer
#      pg_dump security marker) -- not valid SQL, and there's no psql
#      client in the API image (only libpq-dev, for asyncpg's build), so
#      restore runs via a small psycopg2-based script instead.
#   4. Stage the cleaned dump in a throwaway Azure Storage Account (Azure
#      Postgres has no public network access by design -- VNet-injected --
#      so nothing outside the VNet can reach it directly; the storage
#      account is the bridge, reachable from your machine over the
#      internet with no change to Postgres's network posture).
#   5. Build a small image containing src/adp/ops/restore_sql_dump.py,
#      push to the existing ACR, and run it via a Container Apps Job
#      (already inside the VNet) that downloads the staged dump and
#      executes it.
#   6. Clean up the storage account.
#
# Usage: ./seed-data.sh [local-database-url]
#   local-database-url defaults to the standard local dev connection.

set -euo pipefail

LOCAL_DB_URL="${1:-postgresql://adp_user:adp_pass@127.0.0.1:5432/adp}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESOURCE_GROUP="adp-rg"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "== Dumping local database (data-only, excluding bookkeeping tables) =="
pg_dump "$LOCAL_DB_URL" \
  --no-owner --no-privileges --data-only --inserts --column-inserts \
  --exclude-table=alembic_version --exclude-table=audit_entries --exclude-table=operations \
  -f "$WORK_DIR/dump.sql"

echo "== Reordering self-referencing hierarchy tables (business_capabilities, technical_capabilities) =="
python3 - "$LOCAL_DB_URL" "$WORK_DIR" << 'PYEOF'
import sys
import psycopg2

local_db_url, work_dir = sys.argv[1], sys.argv[2]
conn = psycopg2.connect(local_db_url)
cur = conn.cursor()

def generate_inserts(table, order_col):
    cur.execute(f"SELECT * FROM {table} ORDER BY {order_col} ASC")
    cols = [d[0] for d in cur.description]
    col_list = ", ".join(cols)
    lines = []
    for row in cur.fetchall():
        values_sql = cur.mogrify("(" + ", ".join(["%s"] * len(row)) + ")", row).decode("utf-8")
        lines.append(f"INSERT INTO public.{table} ({col_list}) VALUES {values_sql};")
    return lines

reordered = {
    "business_capabilities": generate_inserts("business_capabilities", "level"),
    "technical_capabilities": generate_inserts("technical_capabilities", "level"),
}
conn.close()

dump_path = f"{work_dir}/dump.sql"
with open(dump_path) as f:
    lines = f.readlines()

out_lines = []
replaced = {k: False for k in reordered}
for line in lines:
    matched = False
    for table, insert_lines in reordered.items():
        if line.startswith(f"INSERT INTO public.{table}"):
            if not replaced[table]:
                out_lines.append("\n".join(insert_lines) + "\n")
                replaced[table] = True
            matched = True
            break
    if not matched:
        out_lines.append(line)

with open(dump_path, "w") as f:
    f.writelines(out_lines)

print(f"Reordered: {replaced}")
PYEOF

echo "== Stripping psql-only meta-commands (\\restrict/\\unrestrict) =="
sed -i '/^\\\\/d' "$WORK_DIR/dump.sql"

ROW_COUNT=$(grep -c "^INSERT INTO" "$WORK_DIR/dump.sql")
echo "  $ROW_COUNT rows ready to restore."

EXISTING_ACR="$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv)"
if [[ -z "$EXISTING_ACR" ]]; then
  echo "ERROR: no ACR found in $RESOURCE_GROUP -- run deploy.sh first." >&2
  exit 1
fi

echo "== Building the migration-capable image (includes src/adp/ops/restore_sql_dump.py) =="
IMAGE_TAG="seed-$(date +%s)"
az acr build --registry "$EXISTING_ACR" --image "adp-api:${IMAGE_TAG}" "$REPO_ROOT" --output none

echo "== Staging the dump in a throwaway Storage Account (VNet bridge) =="
STORAGE_NAME="adpseed$(openssl rand -hex 3)"
az storage account create -g "$RESOURCE_GROUP" -n "$STORAGE_NAME" -l eastus2 \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 \
  --allow-blob-public-access false --output none
az storage container create --account-name "$STORAGE_NAME" --name migration --auth-mode login --output none

ACCOUNT_KEY="$(az storage account keys list --account-name "$STORAGE_NAME" -g "$RESOURCE_GROUP" --query "[0].value" -o tsv)"
az storage blob upload --account-name "$STORAGE_NAME" --container-name migration \
  --name dump.sql --file "$WORK_DIR/dump.sql" --account-key "$ACCOUNT_KEY" --overwrite --output none

EXPIRY="$(date -u -d "+2 hours" '+%Y-%m-%dT%H:%MZ')"
SAS="$(az storage blob generate-sas --account-name "$STORAGE_NAME" --account-key "$ACCOUNT_KEY" \
  --container-name migration --name dump.sql --permissions r --expiry "$EXPIRY" -o tsv)"
DUMP_URL="https://${STORAGE_NAME}.blob.core.windows.net/migration/dump.sql?${SAS}"

echo "== Ensuring the Postgres admin password is available to the migration job =="
KEY_VAULT_NAME="$(az keyvault list -g "$RESOURCE_GROUP" --query "[0].name" -o tsv)"
IDENTITY_ID="$(az identity show -g "$RESOURCE_GROUP" -n adp-identity --query id -o tsv)"
az containerapp job secret set -g "$RESOURCE_GROUP" -n adp-keycloak-admin \
  --secrets "postgres-admin-password=keyvaultref:https://${KEY_VAULT_NAME}.vault.azure.net/secrets/postgres-admin-password,identityref:${IDENTITY_ID}" \
  --output none

POSTGRES_FQDN="$(az postgres flexible-server show -g "$RESOURCE_GROUP" -n adp-postgres --query "fullyQualifiedDomainName" -o tsv)"

echo "== Running the restore (Container Apps Job, inside the VNet) =="
EXECUTION_ID="$(az containerapp job start -g "$RESOURCE_GROUP" -n adp-keycloak-admin \
  --image "${EXISTING_ACR}.azurecr.io/adp-api:${IMAGE_TAG}" \
  --container-name keycloak-admin \
  --command "python3" "/app/src/adp/ops/restore_sql_dump.py" \
  --env-vars \
    PGHOST="$POSTGRES_FQDN" PGPORT=5432 PGDATABASE=adp PGUSER=adp_admin \
    "PGPASSWORD=secretref:postgres-admin-password" \
    "DUMP_URL=${DUMP_URL}" \
  --query "name" -o tsv)"

echo "  Job started: $EXECUTION_ID -- polling for completion..."
for _ in $(seq 1 30); do
  STATUS="$(az containerapp job execution show -g "$RESOURCE_GROUP" -n adp-keycloak-admin \
    --job-execution-name "$EXECUTION_ID" --query "properties.status" -o tsv)"
  if [[ "$STATUS" == "Succeeded" || "$STATUS" == "Failed" ]]; then
    break
  fi
  sleep 6
done
echo "  Job status: $STATUS"
if [[ "$STATUS" != "Succeeded" ]]; then
  echo "Check logs with:"
  echo "  az containerapp job logs show -g $RESOURCE_GROUP -n adp-keycloak-admin --execution $EXECUTION_ID --container keycloak-admin"
fi

echo "== Cleaning up the staging Storage Account =="
az storage account delete -g "$RESOURCE_GROUP" -n "$STORAGE_NAME" --yes --output none

if [[ "$STATUS" == "Succeeded" ]]; then
  echo "== Done. Data restored to Azure Postgres. =="
else
  echo "== FAILED -- see log command above. =="
  exit 1
fi
