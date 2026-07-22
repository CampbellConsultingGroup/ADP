# Keycloak with the ADP realm baked in (ADP-fnv.5).
#
# Bakes adp-realm.json into the image rather than mounting it via an Azure
# Files volume -- avoids provisioning a storage account + file share just
# for one static config file, given ACR + `az acr build` already work
# (ADP-fnv.1). `start --import-realm` skips the import if the realm
# already exists, so re-deploying this image is safe against an existing
# server.
FROM quay.io/keycloak/keycloak:26.2

# Keycloak's dir importer requires the filename to match `<realm-name>-realm.json`
# exactly -- the realm inside is named "ADPRealm", so the file must be named
# ADPRealm-realm.json (not adp-realm.json), or the server refuses to start
# with "File name / realm name mismatch".
COPY adp-realm.json /opt/keycloak/data/import/ADPRealm-realm.json
