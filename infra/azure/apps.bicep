// ADP Azure deployment -- stage 2 of 2: apps (ADP-fnv, ADP-vav).
//
// Resource-group scope. Deploys Keycloak, the API, and the migration +
// Keycloak-admin jobs into the environment infra.bicep (stage 1) created.
// deploy.sh runs this only after it has seeded every Key Vault secret these
// apps reference and built both images, so every reference resolves on the
// first attempt. All inputs come from stage 1's outputs.

@description('Azure region -- must match stage 1.')
param location string

@description('Container Apps environment resource ID (stage 1 output).')
param environmentId string

@description('Container Apps environment default domain (stage 1 output) -- the public Keycloak URL is built from it.')
param environmentDefaultDomain string

@description('User-assigned managed identity resource ID (stage 1 output).')
param identityId string

@description('ACR login server (stage 1 output).')
param acrLoginServer string

@description('Key Vault URI (stage 1 output).')
param keyVaultUri string

@description('Postgres Flexible Server FQDN (stage 1 output).')
param postgresFqdn string

@description('Name of the Keycloak database on the Flexible Server (stage 1 output).')
param keycloakDatabaseName string

@description('Tag of the custom Keycloak image (infra/keycloak/Dockerfile), built and pushed by deploy.sh before this runs.')
param keycloakImageTag string = 'latest'

@description('Tag of the API image (repo-root Dockerfile), built and pushed by deploy.sh before this runs. No default -- a unique tag (git short SHA) reliably produces a new revision, unlike a floating :latest (ADP-fnv.5 lesson).')
param apiImageTag string

@description('Client IP ranges allowed to reach the API, as objects { cidr, description }. Empty = fully public (deploy.sh refuses this unless explicitly overridden).')
param allowedIpRanges array

// Public URL the browser reaches Keycloak through (ADP-cm9) -- adp-api's own
// external FQDN, plus /auth. Constructed from the environment's default
// domain (known before apiApp itself deploys) rather than apiApp's fqdn
// output, to avoid a keycloak <-> apiApp circular dependency.
var keycloakPublicBaseUrl = 'https://adp-api.${environmentDefaultDomain}/auth'

module keycloak 'modules/keycloak.bicep' = {
  name: 'keycloakDeploy'
  params: {
    location: location
    environmentId: environmentId
    identityId: identityId
    acrLoginServer: acrLoginServer
    keycloakImageTag: keycloakImageTag
    keyVaultUri: keyVaultUri
    postgresFqdn: postgresFqdn
    keycloakDatabaseName: keycloakDatabaseName
    keycloakPublicBaseUrl: keycloakPublicBaseUrl
  }
}

module apiApp 'modules/apiapp.bicep' = {
  name: 'apiAppDeploy'
  params: {
    location: location
    environmentId: environmentId
    identityId: identityId
    acrLoginServer: acrLoginServer
    apiImageTag: apiImageTag
    keyVaultUri: keyVaultUri
    keycloakFqdn: keycloak.outputs.fqdn
    keycloakPublicBaseUrl: keycloakPublicBaseUrl
    allowedIpRanges: allowedIpRanges
  }
}

module migrationJob 'modules/migrationjob.bicep' = {
  name: 'migrationJobDeploy'
  params: {
    location: location
    environmentId: environmentId
    identityId: identityId
    acrLoginServer: acrLoginServer
    apiImageTag: apiImageTag
    keyVaultUri: keyVaultUri
  }
}

module keycloakAdminJob 'modules/keycloakadminjob.bicep' = {
  name: 'keycloakAdminJobDeploy'
  params: {
    location: location
    environmentId: environmentId
    identityId: identityId
    acrLoginServer: acrLoginServer
    apiImageTag: apiImageTag
    keyVaultUri: keyVaultUri
    keycloakFqdn: keycloak.outputs.fqdn
    keycloakRealm: 'ADPRealm'
  }
}

output keycloakFqdn string = keycloak.outputs.fqdn
output apiFqdn string = apiApp.outputs.fqdn
output migrationJobName string = migrationJob.outputs.jobName
output keycloakAdminJobName string = keycloakAdminJob.outputs.jobName
