// Key Vault + user-assigned managed identity (ADP-fnv.3).
//
// RBAC-authorized (not legacy access policies) -- the identity gets the
// built-in "Key Vault Secrets User" role (read-only), and the deploying
// principal gets "Key Vault Secrets Officer" so this same deployment/script
// can write the actual secret values afterward. Purge protection is
// deliberately left off so ADP-fnv.8 (teardown) can fully delete the vault
// immediately rather than leaving it in a soft-deleted, billable-adjacent
// state for the retention period -- acceptable for a non-prod/single
// environment where "easy to tear down" matters more than purge resistance.
//
// The identity's AcrPull grant also lives here (moved from keycloak.bicep,
// ADP-vav) so it exists -- and has time to propagate -- in stage 1, before
// stage 2's container apps first pull from ACR.
//
// This module creates the vault + identity + role assignments only; the
// actual secret VALUES (ADP_LLM_API_KEY, the Postgres connection string)
// are set imperatively by deploy.sh via `az keyvault secret set` after this
// deploys, so no secret value ever appears in a Bicep template or ARM
// deployment parameter.

@description('Azure region.')
param location string

@description('Key Vault name. Must be globally unique, 3-24 chars, alphanumeric + hyphens.')
param keyVaultName string = 'adp-kv-${uniqueString(resourceGroup().id)}'

@description('User-assigned managed identity name -- attached to the API container app (ADP-fnv.6) for Key Vault secret references and ACR pull.')
param identityName string = 'adp-identity'

@description('Object ID of the principal running this deployment, granted Key Vault Secrets Officer so it can write secret values immediately after this deploys.')
param deployerPrincipalId string

@description('ACR resource ID -- the identity is granted AcrPull for image pulls by every container app and job.')
param acrId string

var keyVaultSecretsUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var keyVaultSecretsOfficerRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: identityName
  location: location
}

resource keyVault 'Microsoft.KeyVault/vaults@2025-05-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    // enablePurgeProtection intentionally omitted (not set to false): Azure
    // rejects an explicit `false` since enabling it is a one-way switch --
    // omitting it leaves purge protection off, letting ADP-fnv.8 (teardown)
    // fully delete the vault immediately.
    enableSoftDelete: true
  }
}

resource identitySecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identity.id, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource deployerSecretsOfficer 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, deployerPrincipalId, 'KeyVaultSecretsOfficer')
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsOfficerRoleId
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// Name and scope deliberately unchanged from when this lived in
// keycloak.bicep (guid(acrId, identity id, 'AcrPull') at resource-group
// scope), so the existing assignment is an in-place no-op, not a duplicate.
resource identityAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrId, identity.id, 'AcrPull')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output identityId string = identity.id
output identityPrincipalId string = identity.properties.principalId
output identityClientId string = identity.properties.clientId
