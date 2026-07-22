#!/usr/bin/env bash
# Pause the ADP Azure environment (ADP-fnv.9) -- a cheaper middle ground
# between fully torn down (destroy.sh) and running 24/7: stops the
# compute you pay for while KEEPING all data/config, so a later resume.sh
# brings everything back exactly as it was (no rebuild, no re-migration).
#
# What this pauses (stops costing money):
#   - adp-postgres compute (`az postgres flexible-server stop`) -- Azure
#     auto-restarts a stopped Flexible Server after 7 days if not resumed
#     manually, so this is meant for short gaps (overnight, a few days),
#     not indefinite storage.
#   - adp-api / adp-keycloak container app compute (both set to
#     min=0/max=1 -- Container Apps rejects max-replicas=0 outright, so
#     "paused" means "eligible to scale to zero", not a hard-forced zero).
#     adp-api is already min=0/max=1 normally (ADP-fnv.6) and scales down
#     on its own when idle; the only real change here is Keycloak, which
#     normally stays warm at min=1/max=1 (ADP-fnv.5) -- dropping it to
#     min=0 lets the platform scale it to zero after its cooldown period
#     (~300s of no traffic) instead of paying to keep it always-on.
#
# What STILL costs money while paused (small, but non-zero):
#   - Postgres storage (the 32GB volume itself, ~$4/month) and backups.
#   - ACR image storage (Basic SKU, ~$5/month regardless of activity).
#   - Key Vault (~$0.03/10k operations -- negligible at rest).
#   - Log Analytics workspace (pay-per-GB ingested; near-zero once apps
#     are quiet, since nothing is generating new logs while paused).
#   - The Container Apps environment resource itself has no idle charge.
#
# Usage: ./pause.sh [resource-group]

set -euo pipefail

RESOURCE_GROUP="${1:-adp-rg}"

echo "== Making adp-api and adp-keycloak eligible to scale to zero =="
az containerapp update --name adp-api --resource-group "$RESOURCE_GROUP" \
  --min-replicas 0 --max-replicas 1 --output none
az containerapp update --name adp-keycloak --resource-group "$RESOURCE_GROUP" \
  --min-replicas 0 --max-replicas 1 --output none
echo "  Both set to min=0/max=1. Actual replica count drops to 0 after the"
echo "  environment's cooldown period (~5 min) once traffic stops -- not"
echo "  instant. Confirm with:"
echo "    az containerapp replica list --name adp-keycloak --resource-group $RESOURCE_GROUP"

echo "== Stopping adp-postgres (compute only -- storage/data retained) =="
az postgres flexible-server stop --resource-group "$RESOURCE_GROUP" --name adp-postgres --output none
echo "  Postgres stop requested."

echo
echo "== Paused. Run resume.sh to bring the environment back. =="
echo "Reminder: Azure auto-restarts a stopped Postgres Flexible Server after"
echo "7 days -- if you're pausing longer than that, re-run pause.sh to stop it again."
