// VNet-integrated Container Apps environment (ADP-fnv.4).
//
// Hosts both the API (external ingress, ADP-fnv.6) and Keycloak (internal
// ingress, ADP-fnv.5) container apps -- one environment, not separate
// platforms, keeping this the simplest viable compute layer versus AKS.
// `internal: false` at the environment level only controls whether the
// environment's default domain gets a public endpoint at all; each
// container app still independently chooses external vs internal-only
// ingress, so this doesn't force Keycloak to be public.

@description('Azure region.')
param location string

@description('Container Apps environment name.')
param environmentName string = 'adp-env'

@description('Log Analytics workspace name (required for Container Apps logging).')
param logAnalyticsName string = 'adp-logs'

@description('Delegated subnet resource ID from modules/network.bicep.')
param infrastructureSubnetId string

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: infrastructureSubnetId
      internal: false
    }
  }
}

output environmentId string = environment.id
output environmentName string = environment.name
output environmentDefaultDomain string = environment.properties.defaultDomain
