// ADP Azure deployment -- stage 1 of 2: infrastructure (ADP-fnv, ADP-vav).
//
// Subscription-scope: creates the resource group plus everything the apps
// depend on but that holds no app-specific config -- ACR, VNet + private DNS,
// Postgres, Key Vault + managed identity (incl. its AcrPull grant), and the
// Container Apps environment.
//
// The apps (Keycloak, API, migration + Keycloak-admin jobs) live in
// apps.bicep, stage 2. They need Key Vault secret values and ACR images that
// deploy.sh can only create once this stage's resources exist, so running
// both in one template guaranteed a failing first pass (ADP-vav). deploy.sh
// runs this stage, seeds secrets + builds images from its outputs, then runs
// apps.bicep -- one invocation, no expected failures.

targetScope = 'subscription'

@description('Azure region for all resources. centralus since 2026-10-08: eastus2 had no Postgres Standard_B1ms capacity in any zone.')
param location string = 'centralus'

@description('Name of the resource group ADP is deployed into.')
param resourceGroupName string = 'adp-rg'

@description('Name of the Azure Container Registry. Must be globally unique, alphanumeric only, 5-50 chars.')
param acrName string = 'adpacr${uniqueString(subscription().id)}'

@description('ACR SKU -- Basic is cheapest and sufficient for a single-environment deployment.')
@allowed(['Basic', 'Standard', 'Premium'])
param acrSku string = 'Basic'

@description('Postgres Flexible Server admin password. Supplied at deploy time via deploy.sh -- never hardcoded/committed.')
@secure()
param postgresAdminPassword string

@description('Availability zone for the Postgres server, or empty to let Azure pick (see modules/postgres.bicep).')
param postgresAvailabilityZone string = ''

@description('Object ID of the principal running this deployment (az ad signed-in-user show), granted Key Vault Secrets Officer.')
param deployerPrincipalId string

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
    availabilityZone: postgresAvailabilityZone
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
    acrId: acr.outputs.acrId
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

output resourceGroupName string = rg.name
output acrName string = acr.outputs.acrName
output acrId string = acr.outputs.acrId
output acrLoginServer string = acr.outputs.loginServer
output postgresServerName string = postgres.outputs.serverName
output postgresServerFqdn string = postgres.outputs.serverFqdn
output postgresDatabaseName string = postgres.outputs.databaseName
output postgresKeycloakDatabaseName string = postgres.outputs.keycloakDatabaseName
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output identityId string = keyVault.outputs.identityId
output identityClientId string = keyVault.outputs.identityClientId
output containerAppsEnvironmentId string = containerAppsEnv.outputs.environmentId
output containerAppsEnvironmentName string = containerAppsEnv.outputs.environmentName
output containerAppsEnvironmentDefaultDomain string = containerAppsEnv.outputs.environmentDefaultDomain
