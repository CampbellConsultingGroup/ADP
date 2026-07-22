#!/usr/bin/env bash
# Resume the ADP Azure environment after pause.sh (ADP-fnv.9). Reverses
# exactly what pause.sh did: starts Postgres, then restores each container
# app's normal scale settings (NOT the same 0/0 pair for both -- Keycloak
# and the API scale differently by design, see modules/keycloak.bicep and
# modules/apiapp.bicep).
#
# Usage: ./resume.sh [resource-group]

set -euo pipefail

RESOURCE_GROUP="${1:-adp-rg}"

echo "== Starting adp-postgres =="
az postgres flexible-server start --resource-group "$RESOURCE_GROUP" --name adp-postgres --output none
echo "  Postgres start requested (takes a minute or two to become Ready)."

echo "== Restoring container app scale settings =="
# adp-keycloak: minReplicas=maxReplicas=1 (always warm -- JVM cold start is
# tens of seconds, and auth needs to be available on demand, not lazily
# spun up per ADP-fnv.5's design).
az containerapp update --name adp-keycloak --resource-group "$RESOURCE_GROUP" \
  --min-replicas 1 --max-replicas 1 --output none
echo "  adp-keycloak restored to 1/1 (always-on)."

# adp-api: minReplicas=0/maxReplicas=1 -- its normal scale-to-zero-eligible
# config (ADP-fnv.6); this is NOT "always on", it just allows the platform
# to scale it up again on the next request instead of being hard-capped at
# zero the way pause.sh left it.
az containerapp update --name adp-api --resource-group "$RESOURCE_GROUP" \
  --min-replicas 0 --max-replicas 1 --output none
echo "  adp-api restored to 0/1 (scales up on next request)."

echo
echo "== Waiting for Postgres to be Ready =="
until [[ "$(az postgres flexible-server show --resource-group "$RESOURCE_GROUP" --name adp-postgres --query state -o tsv 2>/dev/null)" == "Ready" ]]; do
  sleep 10
  echo "  ... still starting"
done
echo "  Postgres is Ready."

echo
echo "== Resumed. Keycloak will take ~15-20s to finish warming up (JVM boot). =="
