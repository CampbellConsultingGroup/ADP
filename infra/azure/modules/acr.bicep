// Azure Container Registry (ADP-fnv.1).
//
// Admin user is disabled by design (adminUserEnabled: false) — the API
// container app (ADP-fnv.6) pulls images via its managed identity's
// AcrPull role assignment, not a shared admin username/password.

@description('Azure region.')
param location string

@description('Registry name. Must be globally unique, alphanumeric only, 5-50 chars.')
param acrName string

@allowed(['Basic', 'Standard', 'Premium'])
param acrSku string = 'Basic'

resource acr 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: acrName
  location: location
  sku: {
    name: acrSku
  }
  properties: {
    adminUserEnabled: false
  }
}

output acrName string = acr.name
output loginServer string = acr.properties.loginServer
output acrId string = acr.id
