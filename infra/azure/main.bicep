// ADP Azure deployment — entry point (ADP-fnv).
//
// Subscription-scope: creates the resource group everything else in the
// epic deploys into, then hands off to per-resource modules scoped to it.
// Each epic task (ADP-fnv.N) adds its module here rather than a separate
// deployment, so the whole environment builds from one `main.bicep` and
// tears down as one resource group (ADP-fnv.8).

targetScope = 'subscription'

@description('Azure region for all resources.')
param location string = 'eastus2'

@description('Name of the resource group ADP is deployed into.')
param resourceGroupName string = 'adp-rg'

@description('Name of the Azure Container Registry. Must be globally unique, alphanumeric only, 5-50 chars.')
param acrName string = 'adpacr${uniqueString(subscription().id)}'

@description('ACR SKU — Basic is cheapest and sufficient for a single-environment deployment.')
@allowed(['Basic', 'Standard', 'Premium'])
param acrSku string = 'Basic'

@description('Postgres Flexible Server admin password. Supplied at deploy time via deploy.sh -- never hardcoded/committed.')
@secure()
param postgresAdminPassword string

@description('Object ID of the principal running this deployment (az ad signed-in-user show), granted Key Vault Secrets Officer.')
param deployerPrincipalId string

@description('Tag of the custom Keycloak image (infra/keycloak/Dockerfile), already built+pushed to ACR by deploy.sh before this runs.')
param keycloakImageTag string = 'latest'

@description('Tag of the API image (Dockerfile at repo root), already built+pushed to ACR by deploy.sh before this runs. No default -- deploy.sh always supplies a unique tag (git short SHA) so a rebuild reliably produces a new revision, unlike a floating :latest tag (ADP-fnv.5 lesson).')
param apiImageTag string

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
}

module acr 'modules/acr.bicep' = {
  name: 'acrDeploy'
  scope: rg
  params: {
    location: location
    acrName: acrName
    acrSku: acrSku
  }
}

module network 'modules/network.bicep' = {
  name: 'networkDeploy'
  scope: rg
  params: {
    location: location
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgresDeploy'
  scope: rg
  params: {
    location: location
    adminPassword: postgresAdminPassword
    delegatedSubnetId: network.outputs.postgresSubnetId
    privateDnsZoneId: network.outputs.privateDnsZoneId
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVaultDeploy'
  scope: rg
  params: {
    location: location
    deployerPrincipalId: deployerPrincipalId
  }
}

module containerAppsEnv 'modules/containerappsenv.bicep' = {
  name: 'containerAppsEnvDeploy'
  scope: rg
  params: {
    location: location
    infrastructureSubnetId: network.outputs.containerAppsSubnetId
  }
}

module keycloak 'modules/keycloak.bicep' = {
  name: 'keycloakDeploy'
  scope: rg
  params: {
    location: location
    environmentId: containerAppsEnv.outputs.environmentId
    identityId: keyVault.outputs.identityId
    acrId: acr.outputs.acrId
    acrLoginServer: acr.outputs.loginServer
    keycloakImageTag: keycloakImageTag
    keyVaultUri: keyVault.outputs.keyVaultUri
    postgresFqdn: postgres.outputs.serverFqdn
    keycloakDatabaseName: postgres.outputs.keycloakDatabaseName
  }
}

module apiApp 'modules/apiapp.bicep' = {
  name: 'apiAppDeploy'
  scope: rg
  params: {
    location: location
    environmentId: containerAppsEnv.outputs.environmentId
    identityId: keyVault.outputs.identityId
    acrLoginServer: acr.outputs.loginServer
    apiImageTag: apiImageTag
    keyVaultUri: keyVault.outputs.keyVaultUri
    keycloakFqdn: keycloak.outputs.fqdn
  }
}

module migrationJob 'modules/migrationjob.bicep' = {
  name: 'migrationJobDeploy'
  scope: rg
  params: {
    location: location
    environmentId: containerAppsEnv.outputs.environmentId
    identityId: keyVault.outputs.identityId
    acrLoginServer: acr.outputs.loginServer
    apiImageTag: apiImageTag
    keyVaultUri: keyVault.outputs.keyVaultUri
  }
}

output resourceGroupName string = rg.name
output acrName string = acr.outputs.acrName
output acrLoginServer string = acr.outputs.loginServer
output postgresServerName string = postgres.outputs.serverName
output postgresServerFqdn string = postgres.outputs.serverFqdn
output postgresDatabaseName string = postgres.outputs.databaseName
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output identityId string = keyVault.outputs.identityId
output identityClientId string = keyVault.outputs.identityClientId
output containerAppsEnvironmentId string = containerAppsEnv.outputs.environmentId
output containerAppsEnvironmentName string = containerAppsEnv.outputs.environmentName
output keycloakFqdn string = keycloak.outputs.fqdn
output apiFqdn string = apiApp.outputs.fqdn
output migrationJobName string = migrationJob.outputs.jobName
